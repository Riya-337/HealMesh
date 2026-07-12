import json
import logging
import httpx
from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel

from .webhook import verify_slack_signature
from approval.workflow import process_approval
from schema.config import get_secret

logger = logging.getLogger(__name__)
router = APIRouter()

def get_db_connection():
    import psycopg2
    import os
    dsn = get_secret("POSTGRES_DSN", os.environ.get("POSTGRES_DSN", "postgresql://healmesh:healmesh@localhost:5432/healmesh"))
    return psycopg2.connect(dsn)

async def trigger_executor(action_id: str, approval_id: str, action_params: dict):
    """
    Calls the Go executor service over HTTPS.
    Uses approval_id as the idempotency key.
    """
    executor_url = os.environ.get("EXECUTOR_URL", "https://localhost:8443")
    
    payload = {
        "action_type": "SCALE",
        "params": action_params,
        "approval_id": approval_id, # Idempotency key
    }
    
    # Needs explicit TLS configuration for internal certs, using verify=False for local dev if needed, 
    # but ideally we mount the CA.
    ca_cert = os.environ.get("INTERNAL_CA_CERT")
    
    try:
        async with httpx.AsyncClient(verify=ca_cert if ca_cert else False) as client:
            response = await client.post(f"{executor_url}/api/v1/execute", json=payload, timeout=10.0)
            response.raise_for_status()
            logger.info(f"Triggered executor for approval {approval_id}, status {response.status_code}")
    except Exception as e:
        logger.error(f"Failed to trigger executor: {e}")

@router.post("/interactions")
async def slack_interaction(request: Request):
    """
    Handles interactive component payloads from Slack.
    Must verify signature BEFORE parsing.
    """
    await verify_slack_signature(request)
    
    form = await request.form()
    payload_str = form.get("payload")
    if not payload_str:
        raise HTTPException(status_code=400, detail="Missing payload")
        
    payload = json.loads(payload_str)
    
    # Process button click
    if payload.get("type") == "block_actions":
        action = payload["actions"][0]
        value = action.get("value")
        if not value:
            return {"status": "ok"}
            
        try:
            data = json.loads(value)
            action_id = data.get("action_id")
            decision = data.get("decision")
        except json.JSONDecodeError:
            return {"status": "error"}
            
        user_id = payload["user"]["id"]
        user_name = payload["user"].get("username", "Unknown")
        
        # 1. Single atomic DB transaction for identity write and approval state
        try:
            conn = get_db_connection()
            with conn:
                # Retrieve action_params inside the same transaction
                with conn.cursor() as cursor:
                    cursor.execute("SELECT action_params FROM healmesh.actions WHERE id = %s", (action_id,))
                    row = cursor.fetchone()
                    if not row:
                        logger.error(f"Action {action_id} not found")
                        return {"status": "error"}
                    action_params = row[0]
                    
                # Process approval (insert is the state transition)
                approval = process_approval(conn, action_id, decision, user_id, user_name)
                approval_id = approval[0]
        except Exception as e:
            logger.error(f"DB Error processing approval: {e}")
            return {"status": "error"}
        finally:
            if 'conn' in locals():
                conn.close()
                
        # 2. Trigger the executor if approved
        if decision == "approved":
            import asyncio
            # Fire and forget executor call so Slack gets a quick 200 OK
            asyncio.create_task(trigger_executor(action_id, approval_id, action_params))
            
    return {"status": "ok"}
