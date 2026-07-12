"""
healmesh-core/main.py

HealMesh Core Service — FastAPI application.

Endpoints:
  POST /incident  — receives incident from healmesh-k8s watcher
  GET  /health    — liveness/readiness probe
  GET  /diagnoses — recent diagnoses (for debugging)

Pipeline: schema validation → audit → rate limit → LLM → parse → audit → Slack
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from pydantic import ValidationError

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

from audit.logger import AuditLogger
from diagnosis.llm_client import GeminiClient
from diagnosis.prompt_engine import build_diagnosis_prompt
from parser.action_parser import parse_confidence, parse_llm_response
from schema.models import Diagnosis, IncidentPayload, IncidentSubmitResponse
from surface.slack.notifier import SlackNotifier
from surface.slack.webhook import router as slack_router
from surface.slack.interaction import router as interaction_router

_MAX_LLM_CALLS_PER_MINUTE = int(os.environ.get("LLM_MAX_CALLS_PER_MINUTE", "30"))
_call_times: list[float] = []


def _check_rate_limit() -> bool:
    now = time.time()
    global _call_times
    _call_times = [t for t in _call_times if now - t < 60.0]
    if len(_call_times) >= _MAX_LLM_CALLS_PER_MINUTE:
        return False
    _call_times.append(now)
    return True


_gemini: GeminiClient | None = None
_audit: AuditLogger | None = None
_slack: SlackNotifier | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _gemini, _audit, _slack
    logger.info("healmesh-core starting up...")
    _gemini = GeminiClient()
    _audit = AuditLogger()
    _slack = SlackNotifier()
    logger.info("healmesh-core ready")
    yield
    logger.info("healmesh-core shutting down")


app = FastAPI(
    title="healmesh-core",
    description="HealMesh diagnosis engine",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(slack_router)
app.include_router(interaction_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "healmesh-core", "timestamp": datetime.utcnow().isoformat()}


@app.post("/incident", response_model=IncidentSubmitResponse)
async def submit_incident(request: Request) -> IncidentSubmitResponse:
    """
    Receive an incident from healmesh-k8s and produce a diagnosis.
    Pipeline: validate → audit → rate limit → LLM → parse → audit → Slack → respond
    """
    try:
        body = await request.json()
        incident = IncidentPayload(**body)
    except ValidationError as e:
        logger.warning("Incident schema validation failed: %s", e)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Schema validation failed: {e.error_count()} error(s)")
    except Exception as e:
        logger.warning("Failed to parse incident request: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request body")

    try:
        _audit.log_incident(incident)
    except Exception as e:
        logger.error("Failed to log incident: %s", e, exc_info=True)

    if not _check_rate_limit():
        logger.warning("Rate limit exceeded for incident %s", incident.incident_id)
        return IncidentSubmitResponse(
            incident_id=incident.incident_id, diagnosis_id=uuid4(),
            status="rate_limited", message="LLM rate limit exceeded. Incident logged."
        )

    system_prompt, user_prompt = build_diagnosis_prompt(incident)
    llm_response = _gemini.diagnose(system_prompt, user_prompt)
    prompt_snapshot = f"{system_prompt}\n\n---USER---\n{user_prompt}"

    parsed_action = parse_llm_response(llm_response.parsed_json)
    confidence = parse_confidence(llm_response.parsed_json)

    root_cause = "Diagnosis unavailable (LLM call failed)"
    suggested_command = None
    if llm_response.success and llm_response.parsed_json:
        root_cause = llm_response.parsed_json.get("root_cause", root_cause)
        suggested_command = llm_response.parsed_json.get("suggested_manual_command")
    elif not llm_response.success:
        err = (llm_response.error or "").lower()
        if "resourceexhausted" in err or "quota" in err or "429" in err:
            root_cause = "Diagnosis unavailable (LLM quota exhausted)"
        # else: keep generic "LLM call failed" for parse errors, timeouts, etc.

    diagnosis = Diagnosis(
        incident_id=incident.incident_id,
        root_cause=root_cause,
        confidence=confidence,
        suggested_manual_command=suggested_command,
        parsed_action=parsed_action,
        llm_model=llm_response.model_used,
        latency_ms=llm_response.latency_ms,
    )

    try:
        _audit.log_diagnosis(diagnosis, prompt_snapshot)
    except Exception as e:
        logger.error("Failed to log diagnosis: %s", e, exc_info=True)

    try:
        _slack.send_diagnosis(incident, diagnosis)
    except Exception as e:
        logger.error("Failed to send to Slack: %s", e, exc_info=True)

    return IncidentSubmitResponse(
        incident_id=incident.incident_id,
        diagnosis_id=diagnosis.diagnosis_id,
        status="diagnosed",
        message=f"Diagnosis complete: {confidence.value} confidence",
        diagnosis=diagnosis,
    )


@app.get("/diagnoses")
async def get_recent_diagnoses(limit: int = 10):
    if limit > 50:
        limit = 50
    try:
        return {"diagnoses": _audit.get_recent_diagnoses(limit)}
    except Exception as e:
        logger.error("Failed to retrieve diagnoses: %s", e)
        raise HTTPException(status_code=500, detail="Database error")
