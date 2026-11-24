import os
from typing import Any, Dict, Optional
import httpx


class WhatsAppCallingClient:
    """
    Client for Meta WhatsApp Business Calling API (Graph API).
    Supports both:
      1. WebRTC Cloud API signaling (pre_accept / accept / terminate with SDP Answer)
      2. Native SIP over TLS integration (wa.meta.vc) via call_settings
    """

    def __init__(self) -> None:
        self.access_token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
        self.phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        self.graph_version = os.getenv("META_GRAPH_VERSION", "v22.0")

    @property
    def base_url(self) -> str:
        return f"https://graph.facebook.com/{self.graph_version}/{self.phone_number_id}"

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def send_call_action(
        self,
        call_id: str,
        action: str,
        sdp_answer: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "call_id": call_id,
            "action": action,
        }
        if sdp_answer:
            payload["session"] = {"sdp_type": "answer", "sdp": sdp_answer}

        if not self.access_token or not self.phone_number_id:
            return {"status": "mocked", "payload": payload}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{self.base_url}/calls", headers=self.headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    async def initiate_outbound_call(self, to_number: str, sdp_offer: str) -> Dict[str, Any]:
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "action": "connect",
            "session": {"sdp_type": "offer", "sdp": sdp_offer},
        }
        if not self.access_token or not self.phone_number_id:
            return {"status": "mocked", "payload": payload}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{self.base_url}/calls", headers=self.headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    async def get_sip_call_settings(self) -> Dict[str, Any]:
        """Retrieves Meta-generated SIP credentials for wa.meta.vc TLS trunking."""
        if not self.access_token or not self.phone_number_id:
            return {
                "status": "mocked",
                "sip_domain": "wa.meta.vc",
                "transport": "TLS",
                "note": "Set WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID to fetch live SIP credentials.",
            }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self.base_url}/settings", headers=self.headers)
            resp.raise_for_status()
            return resp.json()
