"""
healmesh-core/audit/logger.py

Append-only audit logger.

INVARIANT (Constitution Article 2, Invariant 5):
This class has NO update() or delete() methods.
Corrections are made by inserting a new compensating record.

Enforced at two levels:
1. This Python class (no mutation methods exist)
2. Postgres trigger (UPDATE/DELETE raise an error — see infra/postgres/001_init.sql)

Test: tests/test_audit.py verifies via reflection that no update/delete methods exist.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg2
import psycopg2.extras

from schema.models import Diagnosis, IncidentPayload

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Append-only audit logger backed by Postgres.

    INVARIANT: This class does not and must not have update() or delete() methods.
    If you are adding one, you are violating Constitution Article 2, Invariant 5.
    """

    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or self._dsn_from_env()

    @staticmethod
    def _dsn_from_env() -> str:
        host = os.environ.get("POSTGRES_HOST", "localhost")
        port = os.environ.get("POSTGRES_PORT", "5432")
        db = os.environ.get("POSTGRES_DB", "healmesh")
        user = os.environ.get("POSTGRES_USER", "healmesh")
        password = os.environ.get("POSTGRES_PASSWORD", "")
        return f"postgresql://{user}:{password}@{host}:{port}/{db}"

    def _connect(self) -> psycopg2.extensions.connection:
        conn = psycopg2.connect(self._dsn)
        psycopg2.extras.register_uuid()
        return conn

    def log_incident(self, incident: IncidentPayload) -> None:
        """Insert an incident record (append only)."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO healmesh.incidents
                        (id, pod_name, namespace, failure_type, raw_payload, detected_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(incident.incident_id),
                        incident.pod_name,
                        incident.namespace,
                        incident.failure_type.value,
                        psycopg2.extras.Json(incident.model_dump(mode="json")),
                        incident.detected_at,
                    )
                )
            conn.commit()
        logger.info("Audit: logged incident %s", incident.incident_id)

    def log_diagnosis(self, diagnosis: Diagnosis, prompt_snapshot: str) -> None:
        """Insert a diagnosis record and its parsed action (append only)."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO healmesh.diagnoses
                        (id, incident_id, root_cause, confidence,
                         suggested_manual_command, raw_llm_response,
                         prompt_snapshot, llm_model, latency_ms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(diagnosis.diagnosis_id),
                        str(diagnosis.incident_id),
                        diagnosis.root_cause,
                        diagnosis.confidence.value,
                        diagnosis.suggested_manual_command,
                        psycopg2.extras.Json({}),
                        prompt_snapshot,
                        diagnosis.llm_model,
                        diagnosis.latency_ms,
                    )
                )
                action = diagnosis.parsed_action
                params_json = action.params.model_dump(mode="json") if action.params else None
                parse_status = (
                    "not_suggested" if action.action_type.value == "NONE" and not action.parse_failed
                    else "parse_failed" if action.parse_failed
                    else "parsed_ok"
                )
                cur.execute(
                    """
                    INSERT INTO healmesh.actions
                        (diagnosis_id, action_type, action_params, parse_status)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        str(diagnosis.diagnosis_id),
                        action.action_type.value,
                        psycopg2.extras.Json(params_json) if params_json else None,
                        parse_status,
                    )
                )
            conn.commit()
        logger.info("Audit: logged diagnosis %s", diagnosis.diagnosis_id)

    def get_incident(self, incident_id: UUID) -> dict[str, Any] | None:
        """Retrieve an incident record by ID."""
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM healmesh.incidents WHERE id = %s", (str(incident_id),))
                row = cur.fetchone()
                return dict(row) if row else None

    def get_recent_diagnoses(self, limit: int = 20) -> list[dict[str, Any]]:
        """Retrieve the N most recent diagnoses."""
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT d.*, i.failure_type, i.pod_name, i.namespace
                    FROM healmesh.diagnoses d
                    JOIN healmesh.incidents i ON d.incident_id = i.id
                    ORDER BY d.created_at DESC LIMIT %s
                    """,
                    (limit,)
                )
                return [dict(row) for row in cur.fetchall()]

    # INTENTIONAL ABSENCE: No update() or delete() methods exist.
    # Corrections to audit records are made via new compensating records.
    # See docs/TESTING.md §2.3 for the reflection test that verifies this absence.
