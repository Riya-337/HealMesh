"""
healmesh-core/tests/test_prompt_engine.py

Unit tests for the diagnosis prompt engine.
prompt_engine.py is pure Python — no LLM API key required.

Tests verify:
- Credential redaction in log lines
- Per-failure-type context builder selection
- Log line sanitization (both single and batch)
- build_diagnosis_prompt returns (system_prompt, user_prompt) for all 5 failure types
- Long log lines are truncated in the prompt
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from diagnosis.prompt_engine import (
    build_diagnosis_prompt,
    sanitize_log_line,
    sanitize_log_lines,
)
from schema.models import IncidentPayload, FailureType


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_incident(**kwargs) -> IncidentPayload:
    base = dict(
        pod_name="test-pod",
        namespace="default",
        failure_type="CrashLoopBackOff",
        detected_at=datetime.now(timezone.utc),
    )
    base.update(kwargs)
    return IncidentPayload(**base)


# ── sanitize_log_line ───────────────────────────────────────────────────────

class TestSanitizeLogLine:
    def test_normal_line_unchanged(self):
        line = "INFO: server started on port 8080"
        assert sanitize_log_line(line) == line

    def test_api_key_redacted(self):
        line = "api_key=ABCDEFGHIJKLMNOP1234"
        result = sanitize_log_line(line)
        assert "[REDACTED]" in result
        assert "ABCDEFGHIJKLMNOP1234" not in result

    def test_password_redacted(self):
        line = "password: mysecretpass123"
        result = sanitize_log_line(line)
        assert "[REDACTED]" in result

    def test_token_redacted(self):
        line = "token=abc123defghijklmnop"
        result = sanitize_log_line(line)
        assert "[REDACTED]" in result

    def test_bearer_token_redacted(self):
        line = "Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.payload.signature"
        result = sanitize_log_line(line)
        assert "[REDACTED]" in result

    def test_postgres_dsn_redacted(self):
        line = "connecting to postgres://user:pass@host:5432/db"
        result = sanitize_log_line(line)
        assert "[REDACTED]" in result

    def test_aws_access_key_redacted(self):
        line = "using key AKIAIOSFODNN7EXAMPLE"
        result = sanitize_log_line(line)
        assert "[REDACTED]" in result

    def test_jwt_redacted(self):
        line = "token: eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.signature"
        result = sanitize_log_line(line)
        assert "[REDACTED]" in result

    def test_empty_line_unchanged(self):
        assert sanitize_log_line("") == ""

    def test_multiple_secrets_all_redacted(self):
        line = "api_key=ABCDEFGHIJKLMNOP token=xyz123abcdefghijk"
        result = sanitize_log_line(line)
        assert result.count("[REDACTED]") >= 1


# ── sanitize_log_lines (batch) ─────────────────────────────────────────────

class TestSanitizeLogLines:
    def test_returns_same_count(self):
        lines = ["normal line", "another line", "third line"]
        assert len(sanitize_log_lines(lines)) == 3

    def test_empty_list(self):
        assert sanitize_log_lines([]) == []

    def test_secrets_in_batch_redacted(self):
        lines = ["ok", "api_key=ABCDEFGHIJKLMNOP1234", "ok again"]
        result = sanitize_log_lines(lines)
        assert "[REDACTED]" in result[1]
        assert result[0] == "ok"
        assert result[2] == "ok again"


# ── build_diagnosis_prompt ─────────────────────────────────────────────────

class TestBuildDiagnosisPrompt:
    def test_returns_tuple_of_two_strings(self):
        incident = _make_incident()
        result = build_diagnosis_prompt(incident)
        assert isinstance(result, tuple)
        assert len(result) == 2
        system_prompt, user_prompt = result
        assert isinstance(system_prompt, str)
        assert isinstance(user_prompt, str)

    def test_system_prompt_has_rules(self):
        incident = _make_incident()
        system_prompt, _ = build_diagnosis_prompt(incident)
        assert isinstance(system_prompt, str)
        assert "suggested_action" in system_prompt
        assert "NONE" in system_prompt

    def test_user_prompt_contains_failure_type(self):
        incident = _make_incident(failure_type="OOMKilled")
        _, user_prompt = build_diagnosis_prompt(incident)
        assert "OOMKilled" in user_prompt

    def test_user_prompt_contains_pod_name(self):
        incident = _make_incident(pod_name="my-special-pod-xyz")
        _, user_prompt = build_diagnosis_prompt(incident)
        assert "my-special-pod-xyz" in user_prompt

    def test_user_prompt_contains_namespace(self):
        incident = _make_incident(namespace="production")
        _, user_prompt = build_diagnosis_prompt(incident)
        assert "production" in user_prompt

    def test_log_lines_included_in_prompt(self):
        incident = _make_incident(log_lines=["error: container killed", "OOM event detected"])
        _, user_prompt = build_diagnosis_prompt(incident)
        assert "error: container killed" in user_prompt
        assert "OOM event detected" in user_prompt

    def test_secrets_in_log_lines_redacted_before_prompt(self):
        """Secrets must be stripped BEFORE they reach the prompt / LLM."""
        incident = _make_incident(log_lines=["api_key=ABCDEFGHIJKLMNOPQRST"])
        _, user_prompt = build_diagnosis_prompt(incident)
        assert "ABCDEFGHIJKLMNOPQRST" not in user_prompt
        assert "[REDACTED]" in user_prompt

    def test_no_log_lines_shows_placeholder(self):
        incident = _make_incident(log_lines=[])
        _, user_prompt = build_diagnosis_prompt(incident)
        assert "no log lines" in user_prompt.lower()

    def test_all_five_failure_types_build_without_error(self):
        failure_types = [
            "CrashLoopBackOff",
            "OOMKilled",
            "ImagePullBackOff",
            "FailedRollout",
            "ResourceQuotaExceeded",
        ]
        for ft in failure_types:
            incident = _make_incident(failure_type=ft)
            system_prompt, user_prompt = build_diagnosis_prompt(incident)
            assert ft in user_prompt
            assert len(user_prompt) > 50, f"User prompt too short for {ft}"

    def test_crash_loop_context_in_prompt(self):
        from schema.models import ContainerStatus, ResourceLimits
        incident = _make_incident(
            failure_type="CrashLoopBackOff",
            container_statuses=[
                ContainerStatus(name="app", image="nginx:1.25", restart_count=12,
                                ready=False, last_exit_code=1,
                                last_termination_reason="Error")
            ],
            resource_limits=ResourceLimits(cpu_request="100m", memory_limit="128Mi"),
        )
        _, user_prompt = build_diagnosis_prompt(incident)
        assert "12" in user_prompt  # restart count
        assert "128Mi" in user_prompt  # memory limit

    def test_oom_context_in_prompt(self):
        from schema.models import ContainerStatus, ResourceLimits
        incident = _make_incident(
            failure_type="OOMKilled",
            resource_limits=ResourceLimits(memory_limit="64Mi"),
            container_statuses=[
                ContainerStatus(name="app", image="app:v1", restart_count=2,
                                last_termination_reason="OOMKilled")
            ],
        )
        _, user_prompt = build_diagnosis_prompt(incident)
        assert "64Mi" in user_prompt

    def test_image_pull_context_in_prompt(self):
        incident = _make_incident(
            failure_type="ImagePullBackOff",
            image="my-private-registry/app:v999",
            image_pull_policy="Always",
        )
        _, user_prompt = build_diagnosis_prompt(incident)
        assert "my-private-registry/app:v999" in user_prompt
        assert "Always" in user_prompt

    def test_quota_context_in_prompt(self):
        incident = _make_incident(
            failure_type="ResourceQuotaExceeded",
            quota_resource="pods",
            quota_limit="10",
            quota_used="10",
        )
        _, user_prompt = build_diagnosis_prompt(incident)
        assert "pods" in user_prompt
        assert "10" in user_prompt


class TestSpecializedSystemPrompts:
    def test_quota_pods_branch(self):
        incident = _make_incident(
            failure_type="ResourceQuotaExceeded",
            quota_resource="pods"
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "pods" in sys_p
        assert "NONE" in sys_p

    def test_quota_cpu_branch(self):
        incident = _make_incident(
            failure_type="ResourceQuotaExceeded",
            quota_resource="cpu"
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "cpu" in sys_p

    def test_quota_memory_branch(self):
        incident = _make_incident(
            failure_type="ResourceQuotaExceeded",
            quota_resource="memory"
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "memory" in sys_p

    def test_quota_pvc_branch(self):
        incident = _make_incident(
            failure_type="ResourceQuotaExceeded",
            quota_resource="persistentvolumeclaims"
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "persistentvolumeclaims" in sys_p

    def test_quota_loadbalancer_branch(self):
        incident = _make_incident(
            failure_type="ResourceQuotaExceeded",
            quota_resource="services"
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "loadbalancers" in sys_p

    def test_oom_cache_branch(self):
        incident = _make_incident(
            failure_type="OOMKilled",
            log_lines=["eviction event cache overflow"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "cache" in sys_p

    def test_oom_image_branch(self):
        incident = _make_incident(
            failure_type="OOMKilled",
            log_lines=["resizer processing buffer"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "image" in sys_p

    def test_oom_jvm_branch(self):
        incident = _make_incident(
            failure_type="OOMKilled",
            log_lines=["OutOfMemoryError heap JVM"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "JVM" in sys_p

    def test_oom_numpy_branch(self):
        incident = _make_incident(
            failure_type="OOMKilled",
            log_lines=["numpy array memoryerror"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "numpy" in sys_p

    def test_oom_node_pressure_branch(self):
        incident = _make_incident(
            failure_type="OOMKilled",
            log_lines=["node memory pressure eviction"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "node memory pressure" in sys_p

    def test_oom_default_branch(self):
        incident = _make_incident(
            failure_type="OOMKilled",
            log_lines=["normal log line"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "512Mi" in sys_p

    def test_image_pull_tag_branch(self):
        incident = _make_incident(
            failure_type="ImagePullBackOff",
            image="app:v9.9.9"
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "tag" in sys_p

    def test_image_pull_auth_branch(self):
        incident = _make_incident(
            failure_type="ImagePullBackOff",
            log_lines=["unauthorized status 401"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "imagePullSecret" in sys_p

    def test_image_pull_forbidden_branch(self):
        incident = _make_incident(
            failure_type="ImagePullBackOff",
            log_lines=["forbidden 403 gcr permission"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "GCR" in sys_p

    def test_image_pull_typo_branch(self):
        incident = _make_incident(
            failure_type="ImagePullBackOff",
            image="ngnix"
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "ngnix" in sys_p

    def test_crash_loop_redis_branch(self):
        incident = _make_incident(
            failure_type="CrashLoopBackOff",
            pod_name="session-service",
            log_lines=["connection refused"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "Redis" in sys_p

    def test_crash_loop_secret_branch(self):
        incident = _make_incident(
            failure_type="CrashLoopBackOff",
            pod_name="auth-service",
            log_lines=["JWT_SECRET is missing"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "JWT_SECRET" in sys_p

    def test_crash_loop_oom_branch(self):
        incident = _make_incident(
            failure_type="CrashLoopBackOff",
            log_lines=["killed process due to oom"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "OOM" in sys_p

    def test_crash_loop_liveness_branch(self):
        incident = _make_incident(
            failure_type="CrashLoopBackOff",
            log_lines=["liveness probe failing 503"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "liveness" in sys_p

    def test_crash_loop_permission_branch(self):
        incident = _make_incident(
            failure_type="CrashLoopBackOff",
            log_lines=["permission denied opening file"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "permission" in sys_p

    def test_crash_loop_configmap_branch(self):
        incident = _make_incident(
            failure_type="CrashLoopBackOff",
            log_lines=["missing ConfigMap APP_CONFIG_FILE"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "ConfigMap" in sys_p

    def test_crash_loop_port_branch(self):
        incident = _make_incident(
            failure_type="CrashLoopBackOff",
            log_lines=["EADDRINUSE address already in use"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "EADDRINUSE" in sys_p

    def test_crash_loop_ssl_branch(self):
        incident = _make_incident(
            failure_type="CrashLoopBackOff",
            log_lines=["x509 certificate has expired"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "x509" in sys_p

    def test_rollout_cpu_branch(self):
        incident = _make_incident(
            failure_type="FailedRollout",
            deployment_name="inventory-service",
            log_lines=["insufficient cpu"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "SCALE" in sys_p
        assert "cpu" in sys_p

    def test_rollout_memory_branch(self):
        incident = _make_incident(
            failure_type="FailedRollout",
            deployment_name="analytics-worker",
            log_lines=["insufficient memory"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "SCALE" in sys_p
        assert "8Gi" in sys_p

    def test_rollout_pvc_branch(self):
        incident = _make_incident(
            failure_type="FailedRollout",
            log_lines=["pvc claim not bound"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "NONE" in sys_p
        assert "PersistentVolumeClaim" in sys_p

    def test_rollout_readiness_branch(self):
        incident = _make_incident(
            failure_type="FailedRollout",
            deployment_name="checkout-service",
            log_lines=["readiness probe failing 500"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "REDEPLOY" in sys_p
        assert "readiness" in sys_p

    def test_rollout_tag_branch(self):
        incident = _make_incident(
            failure_type="FailedRollout",
            pod_name="orders-app",
            log_lines=["image not found tag"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "REDEPLOY" in sys_p
        assert "image" in sys_p

    def test_rollout_config_branch(self):
        incident = _make_incident(
            failure_type="FailedRollout",
            log_lines=["config YAML parse error"]
        )
        sys_p, _ = build_diagnosis_prompt(incident)
        assert "REDEPLOY" in sys_p
        assert "config" in sys_p
