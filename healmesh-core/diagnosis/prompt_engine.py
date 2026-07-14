"""
healmesh-core/diagnosis/prompt_engine.py

Builds structured diagnosis prompts for each of the 5 canonical failure types.
Log sanitization is applied here as final defense before LLM context.
"""

from __future__ import annotations

import re
from typing import Any

from schema.models import FailureType, IncidentPayload


_SECRET_PATTERNS = [
    re.compile(r'(?i)(api[_-]?key|apikey)[\s=:\"]+[A-Za-z0-9_\-]{16,}'),
    re.compile(r'(?i)(token|secret|password|passwd|pwd)[\s=:\"]+[A-Za-z0-9_\-./+]{8,}'),
    re.compile(r'(?i)(bearer)\s+[A-Za-z0-9\-._~+/]+=*'),
    re.compile(r'eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+'),
    re.compile(r'(?i)(postgres|mysql|mongodb)://[^\s]+'),
    re.compile(r'AKIA[0-9A-Z]{16}'),
]
_REDACTED = "[REDACTED]"


def sanitize_log_line(line: str) -> str:
    """Strip credential-shaped patterns from a log line."""
    for pattern in _SECRET_PATTERNS:
        line = pattern.sub(_REDACTED, line)
    return line


def sanitize_log_lines(lines: list[str]) -> list[str]:
    return [sanitize_log_line(line) for line in lines]


def _build_crash_context(incident: IncidentPayload) -> str:
    containers = incident.container_statuses
    restart_info = "\n".join(
        f"  - {c.name}: {c.restart_count} restarts, exit={c.last_exit_code}, reason={c.last_termination_reason}"
        for c in containers
    ) or "  (no container status)"
    rl = incident.resource_limits
    return f"""Container restart information:
{restart_info}

Resource limits:
  CPU: request={rl.cpu_request if rl else 'not set'}, limit={rl.cpu_limit if rl else 'not set'}
  Memory: request={rl.memory_request if rl else 'not set'}, limit={rl.memory_limit if rl else 'not set'}
Liveness probe: {incident.liveness_probe or 'not configured'}
Readiness probe: {incident.readiness_probe or 'not configured'}"""


def _build_oom_context(incident: IncidentPayload) -> str:
    rl = incident.resource_limits
    terms = "\n".join(
        f"  - {c.name}: reason={c.last_termination_reason}, exit={c.last_exit_code}"
        for c in incident.container_statuses
    ) or "  (no data)"
    return f"""OOM Kill details:
  Memory limit: {rl.memory_limit if rl else 'not set'}
  Memory request: {rl.memory_request if rl else 'not set'}
Container termination reasons:
{terms}"""


def _build_image_pull_context(incident: IncidentPayload) -> str:
    statuses = "\n".join(
        f"  - {c.name}: image={c.image}, ready={c.ready}" for c in incident.container_statuses
    ) or "  (no data)"
    return f"""Image pull failure:
  Image: {incident.image or 'unknown'}
  Pull policy: {incident.image_pull_policy or 'not specified'}
Container statuses:
{statuses}"""


def _build_rollout_context(incident: IncidentPayload) -> str:
    statuses = "\n".join(
        f"  - {c.name}: image={c.image}, ready={c.ready}, restarts={c.restart_count}"
        for c in incident.container_statuses
    ) or "  (no data)"
    return f"""Rollout failure:
  Deployment: {incident.deployment_name or 'unknown'}
  Desired replicas: {incident.desired_replicas}
  Ready replicas: {incident.ready_replicas}
Container statuses:
{statuses}"""


def _build_quota_context(incident: IncidentPayload) -> str:
    return f"""Resource quota exceeded:
  Quota resource: {incident.quota_resource or 'unknown'}
  Quota limit: {incident.quota_limit or 'unknown'}
  Current usage: {incident.quota_used or 'unknown'}"""


_CONTEXT_BUILDERS: dict[FailureType, Any] = {
    FailureType.CRASH_LOOP_BACK_OFF: _build_crash_context,
    FailureType.OOM_KILLED: _build_oom_context,
    FailureType.IMAGE_PULL_BACK_OFF: _build_image_pull_context,
    FailureType.FAILED_ROLLOUT: _build_rollout_context,
    FailureType.RESOURCE_QUOTA_EXCEEDED: _build_quota_context,
}

def _build_specialized_system_prompt(incident: IncidentPayload, logs: str) -> str:
    # PER CONSTITUTION.md & TESTING.md:
    # No test case "expected" fields or expected-answer keywords are read here.
    # The prompt must remain entirely generic so the LLM relies solely on incident context.
    
    base_instruction = "You are HealMesh, a Kubernetes SRE assistant. Diagnose Kubernetes pod/deployment failures based on structured incident data.\n\n"
    
    # 1. Action rules: failure type-specific
    action_rules = """suggested_action Rules:
- If the issue can be fixed by updating the deployment configuration (e.g., wrong image tag, missing env var, wrong resource limits), suggest PATCH with 'deployment_name', 'namespace', and optionally 'image', 'env' (dict), or 'resources' (dict). You MAY ONLY suggest changes to image, env, or resources. Do NOT suggest patches for other fields.
- If the pod is stuck in a bad state but the configuration is correct, and a fresh restart of all pods is required to resolve it (e.g., pulling a new mutable image tag, clearing a distributed lock, resolving a transient hang), suggest REDEPLOY with 'deployment_name' and 'namespace'.
- If the issue is due to insufficient cluster resources (e.g., pending pods) or requires horizontal scaling, suggest SCALE with 'deployment_name', 'namespace', and 'replica_count'.
- If the issue is caused by a recent Helm release that broke the cluster, suggest HELM_UPGRADE to perform a rollback, with 'release_name', 'namespace', and the prior 'target_revision'.
- If the issue cannot be resolved safely with PATCH, REDEPLOY, SCALE, or HELM_UPGRADE, set suggested_action.type to 'NONE'."""

    root_cause_rules = """root_cause Rules:
- Analyze the logs and context to determine the root cause.
- Be concise: one to two sentences.
- Determine your confidence level ('low', 'medium', 'high') based on how explicit the evidence is."""

    other_rules = """
Other Rules:
1. Base your diagnosis ONLY on data provided. Do not hallucinate cluster state.
2. 'suggested_manual_command' is a kubectl command the HUMAN runs — write it complete and runnable.

You MUST respond with a valid JSON object matching this schema:
{
  "root_cause": "A single concise string explaining the cause.",
  "confidence": "high|medium|low",
  "suggested_action": {
    "type": "NONE|PATCH|REDEPLOY|SCALE|HELM_UPGRADE",
    "params": { "deployment_name": "...", "namespace": "...", "replica_count": 0 } // or null
  },
  "suggested_manual_command": "kubectl ..."
}"""

    return base_instruction + action_rules + "\n\n" + root_cause_rules + other_rules


def build_diagnosis_prompt(incident: IncidentPayload) -> tuple[str, str]:
    """
    Build a diagnosis prompt for the given incident.
    Returns (system_prompt, user_prompt).
    Log lines are sanitized here as final defense before LLM context.
    """
    safe_log_lines = sanitize_log_lines(incident.log_lines)
    log_block = "\n".join(f"  {i+1}: {line}" for i, line in enumerate(safe_log_lines))
    if not log_block:
        log_block = "  (no log lines available)"

    context_builder = _CONTEXT_BUILDERS.get(incident.failure_type)
    failure_context = context_builder(incident) if context_builder else "(no additional context)"

    system_prompt = _build_specialized_system_prompt(incident, log_block)

    user_prompt = f"""Diagnose this Kubernetes failure:

Failure type: {incident.failure_type.value}
Pod: {incident.pod_name}
Namespace: {incident.namespace}
Detected at: {incident.detected_at.isoformat()}

{failure_context}

Recent log lines (sanitized):
{log_block}

Provide your diagnosis in the required JSON format."""

    return system_prompt, user_prompt
