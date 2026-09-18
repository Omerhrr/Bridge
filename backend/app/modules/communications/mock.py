"""Mock telecom provider — records actions locally, no external calls.

Used for development, testing and demos without real credentials. Every
outbound action is returned as a structured result so conversations and runs
remain fully observable.
"""

import uuid


class MockVoiceProvider:
    name = "mock"

    def make_call(self, to: str, from_number: str | None = None) -> dict:
        return {"provider": self.name, "call_id": f"call_{uuid.uuid4().hex[:10]}", "to": to, "status": "queued"}

    def collect_speech(self, prompt: str, timeout: int = 10) -> dict:
        return {"provider": self.name, "action": "GetSpeech", "prompt": prompt, "timeout": timeout}


class MockSMSProvider:
    name = "mock"

    def send_sms(self, to: str, message: str, from_number: str | None = None) -> dict:
        return {
            "provider": self.name,
            "message_id": f"msg_{uuid.uuid4().hex[:10]}",
            "to": to,
            "message": message,
            "status": "sent",
        }
