"""
healmesh-core/tests/test_schema.py

Pydantic schema validation tests for IncidentPayload and related models.

Tests verify:
- Valid payloads pass for all 5 failure types
- Required fields are enforced
- Invalid enums are rejected
- Extra fields are rejected (extra="forbid")
- Log line count is capped at 50
- Denylist namespaces are rejected
- ScaleParams bounds are enforced
"""
import os
import sys
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schema.models import (
    FailureType,
    IncidentPayload,
    ScaleParams,
)


def _base_payload(**overrides) -> dict:
    """Return a minimal valid incident payload dict."""
    base = {
        "pod_name": "test-pod-abc123",
        "namespace": "default",
        "failure_type": "CrashLoopBackOff",
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }
    base.update(overrides)
    return base


# ── Valid payloads for all 5 failure types ─────────────────────────────────

class TestValidPayloads:
    def test_crash_loop_back_off(self):
        payload = IncidentPayload(**_base_payload(failure_type="CrashLoopBackOff"))
        assert payload.failure_type == FailureType.CRASH_LOOP_BACK_OFF

    def test_oom_killed(self):
        payload = IncidentPayload(**_base_payload(failure_type="OOMKilled"))
        assert payload.failure_type == FailureType.OOM_KILLED

    def test_image_pull_back_off(self):
        payload = IncidentPayload(**_base_payload(failure_type="ImagePullBackOff"))
        assert payload.failure_type == FailureType.IMAGE_PULL_BACK_OFF

    def test_failed_rollout(self):
        payload = IncidentPayload(**_base_payload(failure_type="FailedRollout"))
        assert payload.failure_type == FailureType.FAILED_ROLLOUT

    def test_resource_quota_exceeded(self):
        payload = IncidentPayload(**_base_payload(failure_type="ResourceQuotaExceeded"))
        assert payload.failure_type == FailureType.RESOURCE_QUOTA_EXCEEDED


# ── Required field enforcement ──────────────────────────────────────────────

class TestRequiredFields:
    def test_missing_pod_name_rejected(self):
        data = _base_payload()
        del data["pod_name"]
        with pytest.raises(ValidationError) as exc_info:
            IncidentPayload(**data)
        assert "pod_name" in str(exc_info.value)

    def test_missing_failure_type_rejected(self):
        data = _base_payload()
        del data["failure_type"]
        with pytest.raises(ValidationError) as exc_info:
            IncidentPayload(**data)
        assert "failure_type" in str(exc_info.value)

    def test_missing_namespace_rejected(self):
        data = _base_payload()
        del data["namespace"]
        with pytest.raises(ValidationError) as exc_info:
            IncidentPayload(**data)
        assert "namespace" in str(exc_info.value)

    def test_missing_detected_at_rejected(self):
        data = _base_payload()
        del data["detected_at"]
        with pytest.raises(ValidationError) as exc_info:
            IncidentPayload(**data)
        assert "detected_at" in str(exc_info.value)


# ── Enum validation ─────────────────────────────────────────────────────────

class TestEnumValidation:
    def test_invalid_failure_type_rejected(self):
        with pytest.raises(ValidationError):
            IncidentPayload(**_base_payload(failure_type="PodEvicted"))

    def test_hallucinated_failure_type_rejected(self):
        with pytest.raises(ValidationError):
            IncidentPayload(**_base_payload(failure_type="NetworkPartition"))

    def test_empty_failure_type_rejected(self):
        with pytest.raises(ValidationError):
            IncidentPayload(**_base_payload(failure_type=""))


# ── Extra field rejection ───────────────────────────────────────────────────

class TestExtraFields:
    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            IncidentPayload(**_base_payload(unknown_field="surprise"))
        assert "extra" in str(exc_info.value).lower() or "unknown_field" in str(exc_info.value)


# ── Field length / bounds ───────────────────────────────────────────────────

class TestFieldBounds:
    def test_empty_pod_name_rejected(self):
        with pytest.raises(ValidationError):
            IncidentPayload(**_base_payload(pod_name=""))

    def test_log_lines_over_50_truncated_to_50(self):
        lines = [f"log line {i}" for i in range(75)]
        payload = IncidentPayload(**_base_payload(log_lines=lines))
        assert len(payload.log_lines) == 50

    def test_log_lines_under_50_kept_intact(self):
        lines = [f"log line {i}" for i in range(20)]
        payload = IncidentPayload(**_base_payload(log_lines=lines))
        assert len(payload.log_lines) == 20

    def test_empty_log_lines_ok(self):
        payload = IncidentPayload(**_base_payload(log_lines=[]))
        assert payload.log_lines == []


# ── Namespace denylist ──────────────────────────────────────────────────────

class TestNamespaceDenylist:
    def test_kube_system_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            IncidentPayload(**_base_payload(namespace="kube-system"))
        assert "denylist" in str(exc_info.value).lower()

    def test_kube_public_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            IncidentPayload(**_base_payload(namespace="kube-public"))
        assert "denylist" in str(exc_info.value).lower()

    def test_healmesh_namespace_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            IncidentPayload(**_base_payload(namespace="healmesh"))
        assert "denylist" in str(exc_info.value).lower()

    def test_default_namespace_allowed(self):
        payload = IncidentPayload(**_base_payload(namespace="default"))
        assert payload.namespace == "default"

    def test_custom_namespace_allowed(self):
        payload = IncidentPayload(**_base_payload(namespace="my-app"))
        assert payload.namespace == "my-app"


# ── ScaleParams ─────────────────────────────────────────────────────────────

class TestScaleParams:
    def test_valid_scale_params(self):
        params = ScaleParams(
            deployment_name="my-deployment",
            namespace="default",
            replica_count=3,
        )
        assert params.replica_count == 3

    def test_zero_replicas_allowed(self):
        """Scale down to zero is a valid operation."""
        params = ScaleParams(
            deployment_name="my-deployment",
            namespace="default",
            replica_count=0,
        )
        assert params.replica_count == 0

    def test_negative_replicas_rejected(self):
        with pytest.raises(ValidationError):
            ScaleParams(
                deployment_name="my-deployment",
                namespace="default",
                replica_count=-1,
            )

    def test_over_100_replicas_rejected(self):
        with pytest.raises(ValidationError):
            ScaleParams(
                deployment_name="my-deployment",
                namespace="default",
                replica_count=101,
            )

    def test_100_replicas_allowed(self):
        params = ScaleParams(
            deployment_name="my-deployment",
            namespace="default",
            replica_count=100,
        )
        assert params.replica_count == 100

    def test_scale_params_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            ScaleParams(
                deployment_name="my-deployment",
                namespace="default",
                replica_count=3,
                unexpected_field="oops",
            )


# ── ParsedRemediationAction ─────────────────────────────────────────────────

class TestParsedRemediationAction:
    def test_none_action_with_params_rejected(self):
        from schema.models import ParsedRemediationAction, RemediationActionType
        with pytest.raises(ValidationError):
            ParsedRemediationAction(
                action_type=RemediationActionType.NONE,
                params=ScaleParams(deployment_name="d", namespace="n", replica_count=1)
            )

    def test_scale_action_with_wrong_params_rejected(self):
        from schema.models import ParsedRemediationAction, RemediationActionType, PatchParams
        with pytest.raises(ValidationError):
            ParsedRemediationAction(
                action_type=RemediationActionType.SCALE,
                params=PatchParams(deployment_name="d", namespace="n", image="img")
            )

    def test_patch_action_with_wrong_params_rejected(self):
        from schema.models import ParsedRemediationAction, RemediationActionType, RedeployParams
        with pytest.raises(ValidationError):
            ParsedRemediationAction(
                action_type=RemediationActionType.PATCH,
                params=RedeployParams(deployment_name="d", namespace="n")
            )

    def test_redeploy_action_with_wrong_params_rejected(self):
        from schema.models import ParsedRemediationAction, RemediationActionType
        with pytest.raises(ValidationError):
            ParsedRemediationAction(
                action_type=RemediationActionType.REDEPLOY,
                params=ScaleParams(deployment_name="d", namespace="n", replica_count=1)
            )
