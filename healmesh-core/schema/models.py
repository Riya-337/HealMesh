"""
healmesh-core/schema/models.py

Pydantic v2 data models for HealMesh incident, diagnosis, and remediation action contracts.

INVARIANT: RemediationActionType is the CLOSED set of actions the executor may take.
Extending it requires a DECISION_LOG.md entry AND full test coverage.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class FailureType(str, enum.Enum):
    """The five canonical Kubernetes failure types HealMesh detects in Phase 1."""
    CRASH_LOOP_BACK_OFF = "CrashLoopBackOff"
    OOM_KILLED = "OOMKilled"
    IMAGE_PULL_BACK_OFF = "ImagePullBackOff"
    FAILED_ROLLOUT = "FailedRollout"
    RESOURCE_QUOTA_EXCEEDED = "ResourceQuotaExceeded"


class DiagnosisConfidence(str, enum.Enum):
    """Confidence level of the LLM diagnosis."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RemediationActionType(str, enum.Enum):
    """
    CLOSED enum of allowed remediation actions.

    INVARIANT (Constitution Article 2, Invariant 1):
    This is the complete set of actions the executor may ever take.
    Any LLM output that does not map to one of these values is treated as NONE.
    Adding a new value requires a DECISION_LOG.md entry AND full test coverage.
    """
    PATCH = "PATCH"
    REDEPLOY = "REDEPLOY"
    SCALE = "SCALE"
    HELM_UPGRADE = "HELM_UPGRADE"
    NONE = "NONE"


class ContainerStatus(BaseModel):
    """Status of a single container within a pod."""
    name: str
    image: str
    restart_count: int = Field(ge=0, default=0)
    ready: bool = False
    last_exit_code: int | None = None
    last_termination_reason: str | None = None


class ResourceLimits(BaseModel):
    """Resource requests/limits relevant to the failure type."""
    cpu_request: str | None = None
    cpu_limit: str | None = None
    memory_request: str | None = None
    memory_limit: str | None = None


class IncidentPayload(BaseModel):
    """
    Incident payload sent from healmesh-k8s to healmesh-core.
    Malformed payloads are rejected and logged — never passed to the LLM.
    """
    model_config = {"extra": "forbid"}

    incident_id: UUID = Field(default_factory=uuid4)
    pod_name: str = Field(min_length=1, max_length=253)
    namespace: str = Field(min_length=1, max_length=63)
    failure_type: FailureType
    detected_at: datetime
    container_statuses: list[ContainerStatus] = Field(default_factory=list)
    log_lines: list[str] = Field(default_factory=list, description="Last N log lines, sanitized")
    resource_limits: ResourceLimits | None = None
    image: str | None = None
    image_pull_policy: str | None = None
    liveness_probe: dict[str, Any] | None = None
    readiness_probe: dict[str, Any] | None = None
    deployment_name: str | None = None
    desired_replicas: int | None = None
    ready_replicas: int | None = None
    quota_resource: str | None = None
    quota_limit: str | None = None
    quota_used: str | None = None

    @field_validator("namespace")
    @classmethod
    def namespace_not_in_denylist(cls, v: str) -> str:
        """Deny system namespaces at schema level."""
        denylist = {"kube-system", "kube-public", "healmesh"}
        if v in denylist:
            raise ValueError(
                f"Namespace '{v}' is in the protected denylist and cannot be targeted"
            )
        return v

    @field_validator("log_lines", mode="before")
    @classmethod
    def truncate_log_lines(cls, v: list[Any]) -> list[Any]:
        """Enforce max 50 line count (belt-and-suspenders; watcher also caps this)."""
        if isinstance(v, list) and len(v) > 50:
            return v[:50]
        return v


class ScaleParams(BaseModel):
    """Parameters for a SCALE action."""
    model_config = {"extra": "forbid"}
    deployment_name: str = Field(min_length=1, max_length=253)
    namespace: str = Field(min_length=1, max_length=63)
    replica_count: int = Field(ge=0, le=100)


class PatchParams(BaseModel):
    """Parameters for a PATCH action (Phase 3+)."""
    model_config = {"extra": "forbid"}
    deployment_name: str = Field(min_length=1, max_length=253)
    namespace: str = Field(min_length=1, max_length=63)
    image: str | None = None
    env: dict[str, str] | None = None
    resources: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_at_least_one_patch_field(self) -> "PatchParams":
        if self.image is None and self.env is None and self.resources is None:
            raise ValueError("PATCH action requires at least one of 'image', 'env', or 'resources' to be set")
        return self


class RedeployParams(BaseModel):
    """Parameters for a REDEPLOY action (Phase 3+)."""
    model_config = {"extra": "forbid"}
    deployment_name: str
    namespace: str


class HelmUpgradeParams(BaseModel):
    """Parameters for a HELM_UPGRADE action (Phase 3+)."""
    model_config = {"extra": "forbid"}
    release_name: str
    chart: str
    namespace: str
    values: dict[str, Any] = Field(default_factory=dict)


class ParsedRemediationAction(BaseModel):
    """
    Output of the Remediation Action Parser.
    INVARIANT: action_type is ALWAYS a valid RemediationActionType.
    If the LLM output could not be parsed, action_type is NONE.
    """
    model_config = {"extra": "forbid"}
    action_type: RemediationActionType
    params: ScaleParams | PatchParams | RedeployParams | HelmUpgradeParams | None = None
    parse_failed: bool = False
    parse_error: str | None = None

    @model_validator(mode="after")
    def validate_params_match_action(self) -> "ParsedRemediationAction":
        if self.action_type == RemediationActionType.NONE:
            if self.params is not None:
                raise ValueError("NONE action must have no params")
        elif self.action_type == RemediationActionType.SCALE:
            if self.params is not None and not isinstance(self.params, ScaleParams):
                raise ValueError("SCALE action requires ScaleParams")
        return self


class Diagnosis(BaseModel):
    """Full diagnosis produced by healmesh-core for one incident."""
    diagnosis_id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)
    root_cause: str = Field(min_length=1)
    confidence: DiagnosisConfidence
    suggested_manual_command: str | None = Field(
        default=None,
        description="Suggested kubectl command as plain text. NEVER fed to executor."
    )
    parsed_action: ParsedRemediationAction
    llm_model: str
    latency_ms: int | None = None


class IncidentSubmitResponse(BaseModel):
    """Response to healmesh-k8s when an incident is submitted."""
    incident_id: UUID
    diagnosis_id: UUID
    status: str
    message: str
    # Inline diagnosis — populated on success so callers don't need a
    # follow-up GET /diagnoses/{id} call (avoids PostgreSQL dependency
    # in environments where the audit DB is not running).
    diagnosis: Diagnosis | None = None
