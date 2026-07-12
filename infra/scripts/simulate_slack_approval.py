import os
import json
import time
import hmac
import hashlib
import requests
import sys

def create_signature(secret: str, timestamp: str, body: str) -> str:
    sig_basestring = f"v0:{timestamp}:{body}"
    my_signature = "v0=" + hmac.new(
        secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()
    return my_signature

def main():
    if len(sys.argv) != 2:
        print("Usage: python simulate_slack_approval.py <action_id>")
        sys.exit(1)
        
    action_id = sys.argv[1]
    secret = os.environ.get("SLACK_SIGNING_SECRET", "dummy_secret")
    
    payload_dict = {
        "type": "block_actions",
        "user": {
            "id": "U123",
            "username": "local_admin"
        },
        "actions": [
            {
                "value": json.dumps({"action_id": action_id, "decision": "approved"})
            }
        ]
    }
    
    # URL encoded form data
    body = "payload=" + requests.utils.quote(json.dumps(payload_dict))
    
    timestamp = str(int(time.time()))
    signature = create_signature(secret, timestamp, body)
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Slack-Request-Timestamp": timestamp,
        "X-Slack-Signature": signature
    }
    
    url = os.environ.get("HEALMESH_URL", "http://127.0.0.1:8000/interactions")
    print(f"Sending approval for action {action_id} to {url}")
    resp = requests.post(url, data=body, headers=headers)
    print(f"Response: {resp.status_code}")
    print(resp.text)

if __name__ == "__main__":
    main()
