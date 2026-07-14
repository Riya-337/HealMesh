"""
healmesh-core/tests/test_parser.py

Comprehensive test suite for the Remediation Action Parser.

INVARIANT under test: Every LLM output that cannot be cleanly mapped to a valid
RemediationActionType + valid params MUST produce action_type=NONE.
There is NO code path where garbage LLM output results in an action.

This module must achieve 100% branch coverage of parser/action_parser.py.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from parser.action_parser import NAMESPACE_DENYLIST, parse_confidence, parse_llm_response
from schema.models import DiagnosisConfidence, RemediationActionType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scale_payload(
    deployment_name: str = "my-deploy",
    namespace: str = "production",
    replica_count: int = 3,
) -> dict:
    return {
        "suggested_action": {
            "type": "SCALE",
            "params": {
                "deployment_name": deployment_name,
                "namespace": namespace,
                "replica_count": replica_count,
            },
        },
        "root_cause": "Pod restarting due to OOM",
        "confidence": "high",
    }


def _make_patch_payload(
    deployment_name: str = "my-deploy",
    namespace: str = "production",
    image: str | None = "nginx:latest",
    env: dict | None = None,
    resources: dict | None = None,
) -> dict:
    params = {
        "deployment_name": deployment_name,
        "namespace": namespace,
    }
    if image is not None:
        params["image"] = image
    if env is not None:
        params["env"] = env
    if resources is not None:
        params["resources"] = resources

    return {
        "suggested_action": {
            "type": "PATCH",
            "params": params,
        },
        "root_cause": "Container image misconfigured",
        "confidence": "medium",
    }


def _make_redeploy_payload(
    deployment_name: str = "my-deploy",
    namespace: str = "production",
) -> dict:
    return {
        "suggested_action": {
            "type": "REDEPLOY",
            "params": {
                "deployment_name": deployment_name,
                "namespace": namespace,
            },
        },
        "root_cause": "Rollout stuck",
        "confidence": "medium",
    }


def _make_helm_payload(
    release_name: str = "my-release",
    namespace: str = "production",
    target_revision: int = 1,
) -> dict:
    return {
        "suggested_action": {
            "type": "HELM_UPGRADE",
            "params": {
                "release_name": release_name,
                "namespace": namespace,
                "target_revision": target_revision,
            },
        },
        "root_cause": "Helm chart misconfiguration",
        "confidence": "low",
    }


# ---------------------------------------------------------------------------
# Valid inputs — one test per enum value
# ---------------------------------------------------------------------------

class TestValidInputs:
    def test_scale_action_valid(self):
        result = parse_llm_response(_make_scale_payload())
        assert result.action_type == RemediationActionType.SCALE
        assert result.parse_failed is False
        assert result.params is not None
        assert result.params.replica_count == 3
        assert result.params.namespace == "production"
        assert result.params.deployment_name == "my-deploy"

    def test_patch_action_valid(self):
        result = parse_llm_response(_make_patch_payload())
        assert result.action_type == RemediationActionType.PATCH
        assert result.parse_failed is False
        assert result.params is not None
        assert result.params.deployment_name == "my-deploy"
        assert result.params.image == "nginx:latest"

    def test_redeploy_action_valid(self):
        result = parse_llm_response(_make_redeploy_payload())
        assert result.action_type == RemediationActionType.REDEPLOY
        assert result.parse_failed is False
        assert result.params is not None
        assert result.params.deployment_name == "my-deploy"

    def test_helm_upgrade_action_valid(self):
        result = parse_llm_response(_make_helm_payload())
        assert result.action_type == RemediationActionType.HELM_UPGRADE
        assert result.parse_failed is False
        assert result.params is not None
        assert result.params.release_name == "my-release"

    def test_none_action_explicit(self):
        payload = {
            "suggested_action": {"type": "NONE"},
            "root_cause": "Could not determine root cause",
            "confidence": "low",
        }
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is False
        assert result.params is None

    def test_no_suggested_action_key(self):
        """When suggested_action is absent, result is NONE without parse_failed."""
        payload = {"root_cause": "something", "confidence": "high"}
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is False

    def test_helm_upgrade_with_extra_fields_like_target_version_rejected(self):
        payload = _make_helm_payload()
        payload["suggested_action"]["params"]["target_version"] = "v2.0.0"
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True


# ---------------------------------------------------------------------------
# Gate 1: None / non-dict LLM response
# ---------------------------------------------------------------------------

class TestNullAndNonDictInput:
    def test_none_input_returns_none_action(self):
        result = parse_llm_response(None)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True
        assert result.parse_error is not None

    def test_non_dict_string_returns_none(self):
        result = parse_llm_response("SCALE")  # type: ignore[arg-type]
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_non_dict_list_returns_none(self):
        result = parse_llm_response([{"type": "SCALE"}])  # type: ignore[arg-type]
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_non_dict_integer_returns_none(self):
        result = parse_llm_response(42)  # type: ignore[arg-type]
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_non_dict_bool_returns_none(self):
        result = parse_llm_response(True)  # type: ignore[arg-type]
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_empty_dict_no_action_key_returns_none(self):
        result = parse_llm_response({})
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is False  # No suggested_action = intentional NONE


# ---------------------------------------------------------------------------
# Gate 2: suggested_action not a dict
# ---------------------------------------------------------------------------

class TestSuggestedActionNotDict:
    def test_suggested_action_is_string(self):
        result = parse_llm_response({"suggested_action": "SCALE"})
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_suggested_action_is_list(self):
        result = parse_llm_response({"suggested_action": ["SCALE"]})
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_suggested_action_is_int(self):
        result = parse_llm_response({"suggested_action": 99})
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_suggested_action_is_none_value(self):
        """Explicit None value for suggested_action key treated as absent."""
        result = parse_llm_response({"suggested_action": None})
        assert result.action_type == RemediationActionType.NONE
        # None value → treated as missing → parse_failed=False
        assert result.parse_failed is False


# ---------------------------------------------------------------------------
# Gate 3: Unknown / hallucinated action types
# ---------------------------------------------------------------------------

class TestHallucinatedActionTypes:
    @pytest.mark.parametrize("bad_type", [
        "EXEC",
        "DELETE",
        "DESTROY",
        "RUN",
        "RESTART",
        "APPLY",
        "ROLLBACK",
        "KUBECTL",
        "BASH",
        "RM -RF /",
        "$(rm -rf /)",
        "'; DROP TABLE incidents; --",
        "scale",          # wrong case
        "Scale",          # mixed case
        "scale_deployment",
        "patch_resource",
        "helm upgrade",   # with space
        "HELM-UPGRADE",   # with hyphen
        "NONE123",
        "NONE; EXEC shell",
        "",
        "   ",
        "null",
        "true",
        "1",
        "UNKNOWN_ACTION",
        "REDEPLOY_ALL",
        "PATCH_AND_RESTART",
    ])
    def test_unknown_action_type_returns_none(self, bad_type: str):
        payload = {
            "suggested_action": {
                "type": bad_type,
                "params": {"deployment_name": "d", "namespace": "n", "replica_count": 1},
            }
        }
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True
        assert "Unknown action type" in (result.parse_error or "")

    def test_prompt_injection_shell_command_as_type(self):
        """Classic prompt injection: shell command as the action type field."""
        payload = {
            "suggested_action": {
                "type": "SCALE; rm -rf / --no-preserve-root",
                "params": {},
            }
        }
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_free_text_action_type(self):
        """LLM responds with a sentence instead of an enum value."""
        payload = {
            "suggested_action": {
                "type": "You should scale the deployment up to 5 replicas",
                "params": {},
            }
        }
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True


# ---------------------------------------------------------------------------
# Gate 3: Missing 'type' field
# ---------------------------------------------------------------------------

class TestMissingTypeField:
    def test_missing_type_field_returns_none(self):
        payload = {
            "suggested_action": {
                "params": {"deployment_name": "d", "namespace": "n", "replica_count": 2}
            }
        }
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True
        assert "type" in (result.parse_error or "").lower()

    def test_type_field_is_none_value(self):
        payload = {"suggested_action": {"type": None, "params": {}}}
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True


# ---------------------------------------------------------------------------
# Gate 5: SCALE parameter validation
# ---------------------------------------------------------------------------

class TestScaleParamValidation:
    def test_scale_extra_fields_rejected(self):
        """Pydantic extra=forbid: extra fields on ScaleParams → NONE."""
        payload = {
            "suggested_action": {
                "type": "SCALE",
                "params": {
                    "deployment_name": "d",
                    "namespace": "production",
                    "replica_count": 3,
                    "evil_extra_field": "do_something_bad",
                },
            }
        }
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_scale_replica_count_string_rejected(self):
        """replica_count as string (LLM hallucination) → NONE."""
        payload = _make_scale_payload(replica_count="three")  # type: ignore[arg-type]
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_scale_negative_replica_count_rejected(self):
        """Negative replica count violates ge=0 → NONE."""
        payload = _make_scale_payload(replica_count=-1)
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_scale_absurd_replica_count_rejected(self):
        """>100 replicas violates le=100 → NONE."""
        payload = _make_scale_payload(replica_count=999)
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_scale_zero_replicas_allowed(self):
        """Zero replicas (scale down to 0) is explicitly valid."""
        payload = _make_scale_payload(replica_count=0)
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.SCALE
        assert result.parse_failed is False
        assert result.params.replica_count == 0

    def test_scale_exactly_100_replicas_allowed(self):
        """Boundary: exactly 100 replicas is valid."""
        payload = _make_scale_payload(replica_count=100)
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.SCALE
        assert result.params.replica_count == 100

    def test_scale_missing_deployment_name(self):
        payload = {
            "suggested_action": {
                "type": "SCALE",
                "params": {"namespace": "production", "replica_count": 3},
            }
        }
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_scale_missing_namespace(self):
        payload = {
            "suggested_action": {
                "type": "SCALE",
                "params": {"deployment_name": "d", "replica_count": 3},
            }
        }
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_scale_missing_replica_count(self):
        payload = {
            "suggested_action": {
                "type": "SCALE",
                "params": {"deployment_name": "d", "namespace": "production"},
            }
        }
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_scale_null_params(self):
        """Null params for SCALE → NONE."""
        payload = {"suggested_action": {"type": "SCALE", "params": None}}
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_scale_params_as_list(self):
        """Params as list instead of dict → NONE."""
        payload = {
            "suggested_action": {
                "type": "SCALE",
                "params": [{"deployment_name": "d", "namespace": "n", "replica_count": 3}],
            }
        }
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_scale_missing_params_key_entirely(self):
        """No params key at all for SCALE → NONE."""
        payload = {"suggested_action": {"type": "SCALE"}}
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True


# ---------------------------------------------------------------------------
# Namespace denylist enforcement
# ---------------------------------------------------------------------------

class TestNamespaceDenylist:
    @pytest.mark.parametrize("denied_ns", ["kube-system", "kube-public", "healmesh"])
    def test_scale_denied_namespace(self, denied_ns: str):
        payload = _make_scale_payload(namespace=denied_ns)
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    @pytest.mark.parametrize("denied_ns", ["kube-system", "kube-public", "healmesh"])
    def test_patch_denied_namespace(self, denied_ns: str):
        payload = _make_patch_payload(namespace=denied_ns)
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    @pytest.mark.parametrize("denied_ns", ["kube-system", "kube-public", "healmesh"])
    def test_redeploy_denied_namespace(self, denied_ns: str):
        payload = _make_redeploy_payload(namespace=denied_ns)
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    @pytest.mark.parametrize("denied_ns", ["kube-system", "kube-public", "healmesh"])
    def test_helm_upgrade_denied_namespace(self, denied_ns: str):
        payload = _make_helm_payload(namespace=denied_ns)
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_namespace_denylist_is_frozenset(self):
        """NAMESPACE_DENYLIST must be a frozenset (immutable, not configurable)."""
        assert isinstance(NAMESPACE_DENYLIST, frozenset)

    def test_namespace_denylist_contains_required_entries(self):
        assert "kube-system" in NAMESPACE_DENYLIST
        assert "kube-public" in NAMESPACE_DENYLIST
        assert "healmesh" in NAMESPACE_DENYLIST

    def test_allowed_namespace_passes_denylist(self):
        """A legitimate namespace should not be blocked."""
        payload = _make_scale_payload(namespace="my-app-production")
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.SCALE
        assert result.parse_failed is False


# ---------------------------------------------------------------------------
# PATCH, REDEPLOY, HELM_UPGRADE param validation
# ---------------------------------------------------------------------------

class TestPatchParamValidation:
    def test_patch_valid(self):
        result = parse_llm_response(_make_patch_payload())
        assert result.action_type == RemediationActionType.PATCH
        assert result.parse_failed is False

    def test_patch_missing_deployment_name(self):
        payload = {
            "suggested_action": {
                "type": "PATCH",
                "params": {
                    "namespace": "production",
                    "image": "nginx:latest",
                },
            }
        }
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_patch_no_optional_fields_rejected(self):
        payload = {
            "suggested_action": {
                "type": "PATCH",
                "params": {
                    "deployment_name": "my-deploy",
                    "namespace": "production",
                },
            }
        }
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_patch_extra_fields_rejected(self):
        payload = {
            "suggested_action": {
                "type": "PATCH",
                "params": {
                    "deployment_name": "d",
                    "namespace": "production",
                    "image": "nginx:latest",
                    "extra_evil": "bad",
                    "securityContext": {"privileged": True}
                },
            }
        }
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True


class TestRedeployParamValidation:
    def test_redeploy_valid(self):
        result = parse_llm_response(_make_redeploy_payload())
        assert result.action_type == RemediationActionType.REDEPLOY
        assert result.parse_failed is False

    def test_redeploy_missing_namespace(self):
        payload = {
            "suggested_action": {
                "type": "REDEPLOY",
                "params": {"deployment_name": "my-deploy"},
            }
        }
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_redeploy_extra_fields_rejected(self):
        payload = {
            "suggested_action": {
                "type": "REDEPLOY",
                "params": {
                    "deployment_name": "d",
                    "namespace": "production",
                    "force": True,
                },
            }
        }
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True


class TestHelmUpgradeParamValidation:
    def test_helm_upgrade_valid(self):
        result = parse_llm_response(_make_helm_payload())
        assert result.action_type == RemediationActionType.HELM_UPGRADE
        assert result.parse_failed is False

    def test_helm_upgrade_missing_target_revision(self):
        payload = {
            "suggested_action": {
                "type": "HELM_UPGRADE",
                "params": {
                    "release_name": "my-release",
                    "namespace": "production",
                },
            }
        }
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True

    def test_helm_upgrade_extra_fields_rejected(self):
        payload = {
            "suggested_action": {
                "type": "HELM_UPGRADE",
                "params": {
                    "release_name": "r",
                    "target_revision": 1,
                    "namespace": "production",
                    "chart": "c",  # extra field not allowed anymore
                },
            }
        }
        result = parse_llm_response(payload)
        assert result.action_type == RemediationActionType.NONE
        assert result.parse_failed is True


# ---------------------------------------------------------------------------
# Confidence parsing
# ---------------------------------------------------------------------------

class TestConfidenceParsing:
    def test_high_confidence(self):
        assert parse_confidence({"confidence": "high"}) == DiagnosisConfidence.HIGH

    def test_medium_confidence(self):
        assert parse_confidence({"confidence": "medium"}) == DiagnosisConfidence.MEDIUM

    def test_low_confidence(self):
        assert parse_confidence({"confidence": "low"}) == DiagnosisConfidence.LOW

    def test_unknown_confidence_defaults_to_low(self):
        assert parse_confidence({"confidence": "very_high"}) == DiagnosisConfidence.LOW

    def test_missing_confidence_key_defaults_to_low(self):
        assert parse_confidence({"root_cause": "something"}) == DiagnosisConfidence.LOW

    def test_none_input_defaults_to_low(self):
        assert parse_confidence(None) == DiagnosisConfidence.LOW

    def test_non_dict_defaults_to_low(self):
        assert parse_confidence("high") == DiagnosisConfidence.LOW  # type: ignore[arg-type]

    def test_empty_dict_defaults_to_low(self):
        assert parse_confidence({}) == DiagnosisConfidence.LOW

    def test_confidence_none_value_defaults_to_low(self):
        """Explicit None value for confidence key."""
        assert parse_confidence({"confidence": None}) == DiagnosisConfidence.LOW

    def test_confidence_integer_value_defaults_to_low(self):
        assert parse_confidence({"confidence": 1}) == DiagnosisConfidence.LOW

    def test_confidence_uppercase_defaults_to_low(self):
        """Enum is case-sensitive; 'HIGH' != 'high' → low."""
        assert parse_confidence({"confidence": "HIGH"}) == DiagnosisConfidence.LOW


# ---------------------------------------------------------------------------
# Return-type invariant
# ---------------------------------------------------------------------------

class TestReturnTypeInvariant:
    """Parser must ALWAYS return a ParsedRemediationAction — never raise."""

    @pytest.mark.parametrize("bad_input", [
        None,
        {},
        [],
        "string",
        42,
        True,
        {"suggested_action": "EXEC rm -rf /"},
        {"suggested_action": {"type": "DROP TABLE users"}},
        {"suggested_action": {"type": "SCALE", "params": None}},
        {"suggested_action": {"type": "SCALE", "params": "not a dict"}},
        {"suggested_action": {"type": "SCALE", "params": [1, 2, 3]}},
    ])
    def test_never_raises(self, bad_input):
        """parse_llm_response must not raise under any circumstance."""
        from schema.models import ParsedRemediationAction
        try:
            result = parse_llm_response(bad_input)
            assert isinstance(result, ParsedRemediationAction)
        except Exception as exc:
            pytest.fail(f"parse_llm_response raised unexpectedly: {exc}")

    def test_result_action_type_always_valid_enum(self):
        """Regardless of input, action_type is always a RemediationActionType."""
        for bad in [None, {}, "garbage", {"suggested_action": {"type": "EVIL"}}]:
            result = parse_llm_response(bad)
            assert isinstance(result.action_type, RemediationActionType)


# ---------------------------------------------------------------------------
# Gate 5: No registered param parser (lines 161-162 coverage)
# This guard fires when a new enum value is added to RemediationActionType
# but its corresponding parser is not added to _PARAM_PARSERS.
# The parser must still fail closed to NONE rather than raising KeyError.
# ---------------------------------------------------------------------------

class TestUnregisteredParamParser:
    """
    TESTING.md §1 requires 100% branch coverage on action_parser.py.
    Lines 161-162 are the internal programmer-error guard at Gate 5:
    if a valid enum value has no registered param parser, the parser
    returns NONE rather than crashing.

    We trigger this branch by temporarily removing SCALE from _PARAM_PARSERS.
    """

    def test_missing_param_parser_routes_to_none(self):
        """Gate 5: valid action_type with no registered parser → NONE, parse_failed=True."""
        import parser.action_parser as ap

        original_parsers = dict(ap._PARAM_PARSERS)
        del ap._PARAM_PARSERS[RemediationActionType.SCALE]
        try:
            result = parse_llm_response({
                "suggested_action": {
                    "type": "SCALE",
                    "params": {
                        "namespace": "production",
                        "deployment_name": "my-deploy",
                        "replica_count": 2,
                    },
                },
                "root_cause": "high load",
                "confidence": "high",
            })
            assert result.action_type == RemediationActionType.NONE
            assert result.parse_failed is True
            assert result.parse_error is not None
        finally:
            ap._PARAM_PARSERS.update(original_parsers)

    def test_param_parser_registry_complete_for_all_non_none_actions(self):
        """
        Regression guard: every non-NONE RemediationActionType must have
        a param parser registered. If a new action type is added to the enum
        without registering a parser, this test fails immediately, ensuring
        the programmer-error guard above is never silently triggered in production.
        """
        import parser.action_parser as ap

        non_none_actions = [
            a for a in RemediationActionType if a != RemediationActionType.NONE
        ]
        for action in non_none_actions:
            assert action in ap._PARAM_PARSERS, (
                f"RemediationActionType.{action.value} has no entry in _PARAM_PARSERS. "
                f"Add a param parser before enabling this action type."
            )
