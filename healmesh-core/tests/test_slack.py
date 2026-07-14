import pytest
from fastapi.testclient import TestClient
from main import app
import hmac
import hashlib
import time

client = TestClient(app)

def test_slack_webhook_missing_secret(monkeypatch):
    monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)
    response = client.post("/slack/actions", data={"payload": "test"})
    assert response.status_code == 500

def test_slack_webhook_missing_headers(monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test_secret")
    response = client.post("/slack/actions", data={"payload": "test"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing Slack headers"

def test_slack_webhook_invalid_timestamp(monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test_secret")
    headers = {
        "X-Slack-Signature": "v0=invalid",
        "X-Slack-Request-Timestamp": "not_an_int"
    }
    response = client.post("/slack/actions", headers=headers, data={"payload": "test"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid timestamp"

def test_slack_webhook_expired_timestamp(monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test_secret")
    expired_ts = str(int(time.time()) - 600)
    headers = {
        "X-Slack-Signature": "v0=invalid",
        "X-Slack-Request-Timestamp": expired_ts
    }
    response = client.post("/slack/actions", headers=headers, data={"payload": "test"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Timestamp expired"

def test_slack_webhook_invalid_signature(monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test_secret")
    valid_ts = str(int(time.time()))
    headers = {
        "X-Slack-Signature": "v0=invalid_sig",
        "X-Slack-Request-Timestamp": valid_ts
    }
    response = client.post("/slack/actions", headers=headers, data={"payload": "test"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid signature"

def test_slack_webhook_valid_signature(monkeypatch):
    secret = "test_secret"
    monkeypatch.setenv("SLACK_SIGNING_SECRET", secret)
    
    timestamp = str(int(time.time()))
    body = "payload=test"
    sig_basestring = f"v0:{timestamp}:{body}"
    my_signature = "v0=" + hmac.new(
        key=secret.encode("utf-8"),
        msg=sig_basestring.encode("utf-8"),
        digestmod=hashlib.sha256
    ).hexdigest()
    
    headers = {
        "X-Slack-Signature": my_signature,
        "X-Slack-Request-Timestamp": timestamp,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    response = client.post("/slack/actions", headers=headers, data=body)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_slack_interaction_unauthorized(monkeypatch):
    import json
    from unittest.mock import patch, MagicMock
    secret = "test_secret"
    monkeypatch.setenv("SLACK_SIGNING_SECRET", secret)
    monkeypatch.setenv("APPROVER_ALLOWLIST", "U12345,U67890")
    
    timestamp = str(int(time.time()))
    payload = {
        "type": "block_actions",
        "user": {"id": "U_HACKER", "username": "Hacker"},
        "actions": [{"value": '{"action_id": "test-uuid", "decision": "approved"}'}]
    }
    import urllib.parse
    body = "payload=" + urllib.parse.quote(json.dumps(payload))
    
    sig_basestring = f"v0:{timestamp}:{body}"
    my_signature = "v0=" + hmac.new(
        key=secret.encode("utf-8"),
        msg=sig_basestring.encode("utf-8"),
        digestmod=hashlib.sha256
    ).hexdigest()
    
    headers = {
        "X-Slack-Signature": my_signature,
        "X-Slack-Request-Timestamp": timestamp,
        "Content-Type": "application/x-www-form-urlencoded"
    }

    # Mock DB calls
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    # Return fake action_params
    mock_cursor.fetchone.side_effect = [[{"fake": "params"}], ["mocked_approval_id"]]
    
    with patch("surface.slack.interaction.get_db_connection", return_value=mock_conn), \
         patch("surface.slack.interaction.process_approval", return_value=("mocked_approval_id",)) as mock_process, \
         patch("surface.slack.interaction.trigger_executor") as mock_executor:
        
        response = client.post("/interactions", headers=headers, data=body)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        
        # Assert executor was NOT called
        mock_executor.assert_not_called()
        
        # Assert process_approval was called with "rejected" and "(UNAUTHORIZED)"
        mock_process.assert_called_once_with(mock_conn, "test-uuid", "rejected", "U_HACKER", "Hacker (UNAUTHORIZED)")

@pytest.mark.asyncio
async def test_slack_interaction_rate_limit(monkeypatch):
    import httpx
    import json
    from unittest.mock import patch, MagicMock, AsyncMock
    
    secret = "test_secret"
    monkeypatch.setenv("SLACK_SIGNING_SECRET", secret)
    monkeypatch.setenv("APPROVER_ALLOWLIST", "U12345")
    
    timestamp = str(int(time.time()))
    payload = {
        "type": "block_actions",
        "user": {"id": "U12345", "username": "ValidUser"},
        "channel": {"id": "C12345"},
        "message": {"ts": "12345.6789"},
        "actions": [{"value": '{"action_id": "test-rl-uuid", "decision": "approved"}'}]
    }
    import urllib.parse
    body = "payload=" + urllib.parse.quote(json.dumps(payload))
    
    sig_basestring = f"v0:{timestamp}:{body}"
    my_signature = "v0=" + hmac.new(
        key=secret.encode("utf-8"),
        msg=sig_basestring.encode("utf-8"),
        digestmod=hashlib.sha256
    ).hexdigest()
    
    headers = {
        "X-Slack-Signature": my_signature,
        "X-Slack-Request-Timestamp": timestamp,
        "Content-Type": "application/x-www-form-urlencoded"
    }

    # Mock DB calls
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.side_effect = [[{"fake": "params"}], ["mocked_approval_id"]]
    
    # Mock httpx client to return 429
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_post = AsyncMock(return_value=mock_response)
    
    mock_client_instance = MagicMock()
    mock_client_instance.post = mock_post
    mock_client_instance.__aenter__.return_value = mock_client_instance
    
    mock_notifier_instance = MagicMock()
    
    with patch("surface.slack.interaction.get_db_connection", return_value=mock_conn), \
         patch("surface.slack.interaction.process_approval", return_value=("mocked_approval_id",)), \
         patch("httpx.AsyncClient", return_value=mock_client_instance), \
         patch("surface.slack.notifier.SlackNotifier", return_value=mock_notifier_instance):
        
        # Send request directly to interaction endpoint
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        response = client.post("/interactions", headers=headers, data=body)
        assert response.status_code == 200
        
        # Allow background tasks (trigger_executor) to execute
        import asyncio
        await asyncio.sleep(0.1)
        
        mock_notifier_instance.send_rate_limit_alert.assert_called_once_with("C12345", "12345.6789", "test-rl-uuid")
