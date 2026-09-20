import hashlib
import hmac

from aicentralv2.services.cadu_slack_connector import authorization_url, normalize_event, verify_signature


def test_slack_authorization_url_is_state_bound():
    value = authorization_url(
        client_id="slack-client", redirect_uri="https://auth.centralcomm.media/slack/callback", state="opaque",
    )
    assert "state=opaque" in value
    assert "channels%3Ahistory" in value


def test_slack_signature_rejects_replay_and_accepts_valid_body():
    secret, timestamp, body = "secret", "1700000000", b'{"type":"event_callback"}'
    base = f"v0:{timestamp}:".encode() + body
    signature = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    assert verify_signature(signing_secret=secret, timestamp=timestamp, body=body, signature=signature, now=1700000001)
    assert not verify_signature(signing_secret=secret, timestamp=timestamp, body=body, signature=signature, now=1700001000)


def test_slack_event_is_provider_neutral():
    result = normalize_event({
        "event_id": "Ev1", "team_id": "T1",
        "event": {"type": "message", "channel": "C1", "user": "U1", "ts": "2", "text": "briefing"},
    })
    assert result["event_id"] == "Ev1"
    assert result["channel_id"] == "C1"
    assert result["thread_id"] == "2"
