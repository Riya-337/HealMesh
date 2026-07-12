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
