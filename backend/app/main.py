import json
import os
import time
import uuid
from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.models import AgentConfig, OutboundCallRequest, SipTrunkConfig
from app.whatsapp_calling import WhatsAppCallingClient
from app.livekit_sip import LiveKitSipManager

app = FastAPI(title="Aureum Voice AI — Control & Signaling API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

current_config = AgentConfig()
active_calls: Dict[str, Dict[str, Any]] = {}
telemetry_clients: List[WebSocket] = []

wa_client = WhatsAppCallingClient()
sip_manager = LiveKitSipManager()


async def broadcast_telemetry(event_type: str, payload: Dict[str, Any]) -> None:
    message = json.dumps({"type": event_type, "timestamp": time.time(), "data": payload})
    stale: List[WebSocket] = []
    for ws in telemetry_clients:
        try:
            await ws.send_text(message)
        except Exception:
            stale.append(ws)
    for ws in stale:
        if ws in telemetry_clients:
            telemetry_clients.remove(ws)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "service": "aureum-voice-ai"}


@app.get("/api/config", response_model=AgentConfig)
async def get_config() -> AgentConfig:
    return current_config


@app.put("/api/config", response_model=AgentConfig)
async def update_config(new_config: AgentConfig) -> AgentConfig:
    global current_config
    current_config = new_config
    await broadcast_telemetry("config_updated", current_config.model_dump())
    return current_config


@app.get("/api/calls")
async def list_calls() -> Dict[str, Any]:
    return {"active_calls": list(active_calls.values())}


@app.post("/api/livekit/token")
async def create_web_session_token(participant: str = "web-operator") -> Dict[str, str]:
    room_name = f"aureum-web-{uuid.uuid4().hex[:8]}"
    token = sip_manager.create_browser_token(room_name, participant)
    active_calls[room_name] = {
        "call_id": room_name,
        "channel": "webrtc_web",
        "peer": participant,
        "status": "ready",
        "started_at": time.time(),
    }
    await broadcast_telemetry("call_started", active_calls[room_name])
    return {
        "room_name": room_name,
        "token": token,
        "livekit_url": os.getenv("LIVEKIT_PUBLIC_URL", "ws://localhost:7880"),
    }


@app.post("/api/sip/trunks")
async def register_sip_trunk(trunk: SipTrunkConfig) -> Dict[str, Any]:
    try:
        res = await sip_manager.create_inbound_trunk_and_dispatch(
            name=trunk.name, numbers=trunk.numbers
        )
        await broadcast_telemetry("sip_trunk_registered", {"name": trunk.name, **res})
        return res
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LiveKit SIP error: {exc}") from exc


@app.post("/api/calls/outbound")
async def launch_outbound_call(req: OutboundCallRequest) -> Dict[str, Any]:
    call_id = f"call-{uuid.uuid4().hex[:8]}"
    call_record = {
        "call_id": call_id,
        "channel": req.channel,
        "peer": req.target_number,
        "status": "dialing",
        "started_at": time.time(),
    }
    active_calls[call_id] = call_record
    await broadcast_telemetry("call_started", call_record)

    if req.channel == "whatsapp_cloud":
        # In SIP mode, outbound calls dial sip:+<number>@wa.meta.vc;transport=tls
        # In WebRTC webhook mode, initiate_outbound_call sends the SDP offer via Graph API
        wa_res = await wa_client.get_sip_call_settings()
        return {"call": call_record, "whatsapp": wa_res}

    return {
        "call": call_record,
        "note": "Configure SIP_TRUNK_ID to dispatch live PSTN INVITE via LiveKit SIP.",
    }


@app.get("/webhooks/whatsapp/calls")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
):
    expected = os.getenv("WHATSAPP_VERIFY_TOKEN", "aureum_voice_verify_2026")
    if hub_mode == "subscribe" and hub_verify_token == expected:
        return int(hub_challenge) if hub_challenge.isdigit() else hub_challenge
    raise HTTPException(status_code=403, detail="Invalid WhatsApp verify token")


@app.post("/webhooks/whatsapp/calls")
async def handle_whatsapp_call_webhook(request: Request) -> Dict[str, str]:
    body = await request.json()
    entries = body.get("entry", [])
    for entry in entries:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for call in value.get("calls", []):
                call_id = call.get("id", f"wacid-{uuid.uuid4().hex[:6]}")
                event = call.get("event")
                caller = call.get("from", "unknown")

                if event == "connect":
                    active_calls[call_id] = {
                        "call_id": call_id,
                        "channel": "whatsapp_cloud",
                        "peer": caller,
                        "status": "connected",
                        "started_at": time.time(),
                    }
                    await broadcast_telemetry("call_started", active_calls[call_id])
                    # Pre-accept while WebRTC/LiveKit room media negotiates
                    await wa_client.send_call_action(call_id=call_id, action="pre_accept")
                elif event == "terminate":
                    if call_id in active_calls:
                        active_calls[call_id]["status"] = "terminated"
                    await broadcast_telemetry("call_ended", {"call_id": call_id, "peer": caller})

    return {"status": "processed"}


@app.post("/api/telemetry/transcript")
async def ingest_worker_transcript(payload: Dict[str, Any]) -> Dict[str, str]:
    await broadcast_telemetry("transcript", payload)
    return {"status": "ok"}


@app.websocket("/ws/telemetry")
async def telemetry_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    telemetry_clients.append(websocket)
    await websocket.send_text(
        json.dumps(
            {
                "type": "snapshot",
                "timestamp": time.time(),
                "data": {
                    "config": current_config.model_dump(),
                    "active_calls": list(active_calls.values()),
                },
            }
        )
    )
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in telemetry_clients:
            telemetry_clients.remove(websocket)
