from typing import Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import psycopg2
import json

class ApprovalRecord(BaseModel):
    action_id: str
    decision: str
    approver_id: str
    approver_name: Optional[str]

def process_approval(db_conn, action_id: str, decision: str, approver_id: str, approver_name: Optional[str] = None):
    """
    Records an approval decision atomically in the database.
    Since the database is append-only, the state transition (action becoming 'approved' or 'rejected')
    is inherently represented by the insertion of the approval record itself.
    """
    with db_conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO healmesh.approvals (action_id, decision, approver_id, approver_name, decided_at)
            VALUES (%s, %s, %s, %s, NOW())
            RETURNING id, decision;
            """,
            (action_id, decision, approver_id, approver_name)
        )
        result = cursor.fetchone()
        
    return result

def start_execution(db_conn, approval_id: str):
    """
    Creates the initial execution record (pending state).
    """
    with db_conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO healmesh.executions (approval_id, status)
            VALUES (%s, 'pending')
            RETURNING id;
            """,
            (approval_id,)
        )
        return cursor.fetchone()[0]

def log_execution_event(db_conn, approval_id: str, status: str, pre_snapshot: Optional[Dict[str, Any]] = None, post_snapshot: Optional[Dict[str, Any]] = None, error_msg: Optional[str] = None):
    """
    Due to the append-only invariant, state changes in execution must be new row inserts.
    Instead of updating a single row, we insert a new execution state row.
    """
    pre_json = json.dumps(pre_snapshot) if pre_snapshot else None
    post_json = json.dumps(post_snapshot) if post_snapshot else None
    
    with db_conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO healmesh.executions (approval_id, status, pre_action_snapshot, post_action_snapshot, error_message, completed_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            RETURNING id;
            """,
            (approval_id, status, pre_json, post_json, error_msg)
        )
        return cursor.fetchone()[0]
