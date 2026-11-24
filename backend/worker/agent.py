import asyncio
import logging
import os
import httpx
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, llm
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import google

logger = logging.getLogger("aureum-voice-worker")
API_BASE_URL = os.getenv("AUREUM_API_URL", "http://api:8000")


async def push_transcript_event(room_name: str, role: str, text: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(
                f"{API_BASE_URL}/api/telemetry/transcript",
                json={"call_id": room_name, "role": role, "text": text},
            )
    except Exception:
        pass


class AureumVoiceAgent(Agent):
    def __init__(self, instructions: str) -> None:
        super().__init__(instructions=instructions)

    @llm.function_tool(description="Look up a customer lead or order status in the CRM by phone or email.")
    async def lookup_crm_lead(self, identifier: str) -> str:
        logger.info("Executing CRM lookup for %s", identifier)
        return (
            f"Lead {identifier}: VIP Ecommerce Founder, interested in AI Voice Automation, "
            "last contacted 2 days ago. Qualified for technical demo."
        )

    @llm.function_tool(description="Schedule a follow-up callback or calendar slot for the caller.")
    async def schedule_callback(self, preferred_time: str, topic: str) -> str:
        logger.info("Scheduling callback at %s for %s", preferred_time, topic)
        return f"Confirmed callback slot at {preferred_time} regarding '{topic}'."


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Fetch live agent configuration from the Control Panel API
    model_id = os.getenv("GEMINI_LIVE_MODEL", "gemini-3.8-live")
    voice_name = os.getenv("GEMINI_LIVE_VOICE", "Aoede")
    instructions = (
        "You are Aureum Voice AI, a sharp, natural real-time voice agent. "
        "Keep answers concise and conversational."
    )

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{API_BASE_URL}/api/config")
            if resp.status_code == 200:
                cfg = resp.json()
                model_id = cfg.get("model", model_id)
                voice_name = cfg.get("voice", voice_name)
                instructions = cfg.get("system_prompt", instructions)
    except Exception:
        logger.warning("Using fallback env config for Gemini Live worker.")

    # Native Speech-to-Speech via Gemini Live API (no separate STT or TTS hops)
    realtime_model = google.realtime.RealtimeModel(
        model=model_id,
        voice=voice_name,
        instructions=instructions,
    )

    session = AgentSession(llm=realtime_model)

    @session.on("user_input_transcribed")
    def on_user_transcript(ev) -> None:
        if getattr(ev, "is_final", True) and getattr(ev, "transcript", ""):
            asyncio.create_task(push_transcript_event(ctx.room.name, "user", ev.transcript))

    @session.on("conversation_item_added")
    def on_agent_item(ev) -> None:
        item = getattr(ev, "item", None)
        if item and getattr(item, "role", "") == "assistant":
            text = getattr(item, "text_content", "") or ""
            if text:
                asyncio.create_task(push_transcript_event(ctx.room.name, "assistant", text))

    await session.start(room=ctx.room, agent=AureumVoiceAgent(instructions=instructions))
    await session.generate_reply(
        instructions="Greet the caller briefly and ask how you can help them today."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
