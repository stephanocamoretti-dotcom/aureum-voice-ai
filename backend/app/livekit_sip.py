import os
from typing import Any, Dict, List
from livekit import api


class LiveKitSipManager:
    """
    Manages LiveKit rooms, browser WebRTC tokens, and native SIP Trunks + Dispatch Rules
    for both PSTN SIP providers (Twilio/Telnyx/Asterisk) and WhatsApp SIP (wa.meta.vc).
    """

    def __init__(self) -> None:
        self.url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
        self.api_key = os.getenv("LIVEKIT_API_KEY", "devkey")
        self.api_secret = os.getenv("LIVEKIT_API_SECRET", "secret")

    def create_browser_token(self, room_name: str, participant_identity: str) -> str:
        token = (
            api.AccessToken(self.api_key, self.api_secret)
            .with_identity(participant_identity)
            .with_name(participant_identity)
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                )
            )
        )
        return token.to_jwt()

    async def create_inbound_trunk_and_dispatch(
        self,
        name: str,
        numbers: List[str],
        room_prefix: str = "aureum-call-",
    ) -> Dict[str, Any]:
        lk = api.LiveKitAPI(self.url, self.api_key, self.api_secret)
        try:
            trunk = await lk.sip.create_sip_inbound_trunk(
                api.CreateSIPInboundTrunkRequest(
                    trunk=api.SIPInboundTrunkInfo(name=name, numbers=numbers)
                )
            )
            rule = await lk.sip.create_sip_dispatch_rule(
                api.CreateSIPDispatchRuleRequest(
                    rule=api.SIPDispatchRule(
                        dispatch_rule_individual=api.SIPDispatchRuleIndividual(
                            room_prefix=room_prefix
                        )
                    ),
                    trunk_ids=[trunk.sip_trunk_id],
                    name=f"{name}-dispatch",
                )
            )
            return {
                "sip_trunk_id": trunk.sip_trunk_id,
                "sip_dispatch_rule_id": rule.sip_dispatch_rule_id,
            }
        finally:
            await lk.aclose()

    async def dial_outbound_sip(
        self,
        sip_trunk_id: str,
        target_number: str,
        room_name: str,
    ) -> Dict[str, Any]:
        lk = api.LiveKitAPI(self.url, self.api_key, self.api_secret)
        try:
            participant = await lk.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    sip_trunk_id=sip_trunk_id,
                    sip_call_to=target_number,
                    room_name=room_name,
                    participant_identity=f"sip-{target_number}",
                    participant_name=target_number,
                    play_dialtone=True,
                )
            )
            return {
                "participant_id": participant.participant_id,
                "sip_call_id": participant.sip_call_id,
                "room_name": room_name,
            }
        finally:
            await lk.aclose()
