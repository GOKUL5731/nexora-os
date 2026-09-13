import base64
import json

from nexora_os.backend.realtime.livekit_provider import LiveKitProvider


def test_unconfigured_status_never_exposes_secret():
    provider = LiveKitProvider(url="", api_key="", api_secret="secret-value")
    status = provider.status()
    assert status["configured"] is False
    assert status["secret_configured"] is True
    assert "secret-value" not in json.dumps(status)


def test_issue_token_contains_room_permissions_without_secret():
    provider = LiveKitProvider("wss://example.livekit.cloud", "APIKEY123", "secret-value")
    result = provider.issue_token("jarvis-room", "user-1", "Gokul", 120)
    assert result["ok"] is True
    assert "secret-value" not in json.dumps(result)
    token = result["token"]
    payload = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
    assert payload["iss"] == "APIKEY123"
    assert payload["video"]["room"] == "jarvis-room"
    assert payload["video"]["roomJoin"] is True
