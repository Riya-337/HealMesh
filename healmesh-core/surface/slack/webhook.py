"""
healmesh-core/surface/slack/webhook.py
Incoming Slack webhook handler (Phase 2 approval workflows).
"""
import hmac
import hashlib
import time
import os
import logging
from fastapi import APIRouter, Request, HTTPException, status, Depends

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slack", tags=["slack"])

async def verify_slack_signature(request: Request):
    """
    Verify the Slack HMAC signature before payload parsing.
    Requires SLACK_SIGNING_SECRET from vault or environment variable.
    """
    from schema.config import get_secret
    secret = get_secret("SLACK_SIGNING_SECRET")
    
    if not secret:
        logger.error("SLACK_SIGNING_SECRET not configured")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server misconfigured")

    x_slack_signature = request.headers.get("X-Slack-Signature")
    x_slack_request_timestamp = request.headers.get("X-Slack-Request-Timestamp")

    if not x_slack_signature or not x_slack_request_timestamp:
        logger.warning("Missing Slack headers on webhook request")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Slack headers")

    try:
        timestamp = int(x_slack_request_timestamp)
    except ValueError:
        logger.warning("Invalid X-Slack-Request-Timestamp: %s", x_slack_request_timestamp)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid timestamp")

    # Reject requests older than 5 minutes
    if abs(time.time() - timestamp) > 60 * 5:
        logger.warning("Expired Slack request timestamp: %s", timestamp)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Timestamp expired")

    # Read raw body for HMAC verification
    body = await request.body()
    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    
    my_signature = "v0=" + hmac.new(
        key=secret.encode("utf-8"),
        msg=sig_basestring.encode("utf-8"),
        digestmod=hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(my_signature, x_slack_signature):
        logger.warning("Slack HMAC signature mismatch")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    return True

@router.post("/actions", dependencies=[Depends(verify_slack_signature)])
async def slack_actions(request: Request):
    """
    Slack interactive components endpoint.
    Signature is verified by the dependency BEFORE this is executed.
    """
    try:
        form_data = await request.form()
        payload_str = form_data.get("payload")
        # In Phase 2, this will be parsed and routed to Approval logic.
        return {"status": "ok"}
    except Exception as e:
        logger.error("Failed to parse Slack payload: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bad Request")
