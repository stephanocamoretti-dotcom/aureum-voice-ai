import os
from typing import Literal, Optional
from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    model: str = Field(default=os.getenv("GEMINI_LIVE_MODEL", "gemini-3.8-live"))
    voice: str = Field(default=os.getenv("GEMINI_LIVE_VOICE", "Aoede"))
    active_channel: Literal["whatsapp_cloud", "sip_trunk", "webrtc_web"] = "whatsapp_cloud"
    system_prompt: str = (
        "You are Aureum Voice AI, a sharp, natural, low-latency AI voice agent. "
        "Speak concisely, adapt to interruptions immediately, and use your CRM/booking tools when needed."
    )
    enable_crm_tool: bool = True
    enable_booking_tool: bool = True
    enable_human_handoff: bool = True


class OutboundCallRequest(BaseModel):
    target_number: str = Field(..., description="E.164 phone number, e.g. +15551234567")
    channel: Literal["whatsapp_cloud", "sip_trunk"] = "sip_trunk"
    custom_context: Optional[str] = None


class SipTrunkConfig(BaseModel):
    name: str = "Primary SIP Trunk"
    sip_host: str = Field(default=os.getenv("SIP_TRUNK_HOST", "sip.yourprovider.com"))
    username: str = Field(default=os.getenv("SIP_TRUNK_USERNAME", ""))
    password: str = Field(default=os.getenv("SIP_TRUNK_PASSWORD", ""))
    caller_id: str = Field(default=os.getenv("SIP_CALLER_ID", "+15550001234"))
    numbers: list[str] = Field(default_factory=lambda: ["+15550001234"])
