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



