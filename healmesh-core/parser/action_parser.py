"""
healmesh-core/parser/action_parser.py

THE MOST SECURITY-CRITICAL MODULE IN HEALMESH.

INVARIANT (Constitution Article 2, Invariant 1):
  - Every LLM response passes through this parser.
  - Only RemediationActionType enum values are accepted.
  - Anything outside the enum → NONE.
  - Malformed JSON → NONE.
  - Missing required parameters → NONE.
  - Parameters out of bounds → NONE.
  - There is NO code path where unparseable LLM output results in an action.

This module must have 100% branch coverage in tests.
Any change requires a new test case in test_parser.py.
See docs/TESTING.md §2.1 for the complete test matrix.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from schema.models import (
    DiagnosisConfidence,
    HelmUpgradeParams,
    ParsedRemediationAction,
    PatchParams,
    RedeployParams,
    RemediationActionType,
    ScaleParams,
)

logger = logging.getLogger(__name__)

# Hardcoded namespace denylist — enforced here as defense-in-depth.
# The EXECUTOR also enforces this. This list MUST NOT be read from config.
NAMESPACE_DENYLIST: frozenset[str] = frozenset({"kube-system", "kube-public", "healmesh"})


def _parse_scale_params(params: dict[str, Any]) -> ScaleParams | None:
    try:
        parsed = ScaleParams(**params)
        if parsed.namespace in NAMESPACE_DENYLIST:
            logger.warning("SCALE targeting denylisted namespace '%s'", parsed.namespace)
            return None
        return parsed
    except (ValidationError, TypeError, KeyError) as e:
        logger.warning("SCALE params validation failed: %s", e)
        return None


def _parse_patch_params(params: dict[str, Any]) -> PatchParams | None:
    try:
        parsed = PatchParams(**params)
        if parsed.namespace in NAMESPACE_DENYLIST:
            logger.warning("PATCH targeting denylisted namespace '%s'", parsed.namespace)
            return None
        return parsed
    except (ValidationError, TypeError, KeyError) as e:
        logger.warning("PATCH params validation failed: %s", e)
        return None


def _parse_redeploy_params(params: dict[str, Any]) -> RedeployParams | None:
    try:
        parsed = RedeployParams(**params)
        if parsed.namespace in NAMESPACE_DENYLIST:
            logger.warning("REDEPLOY targeting denylisted namespace '%s'", parsed.namespace)
            return None
        return parsed
    except (ValidationError, TypeError, KeyError) as e:
        logger.warning("REDEPLOY params validation failed: %s", e)
        return None


def _parse_helm_upgrade_params(params: dict[str, Any]) -> HelmUpgradeParams | None:
    try:
        parsed = HelmUpgradeParams(**params)
        if parsed.namespace in NAMESPACE_DENYLIST:
            logger.warning("HELM_UPGRADE targeting denylisted namespace '%s'", parsed.namespace)
            return None
        return parsed
    except (ValidationError, TypeError, KeyError) as e:
        logger.warning("HELM_UPGRADE params validation failed: %s", e)
        return None


_PARAM_PARSERS = {
    RemediationActionType.SCALE: _parse_scale_params,
    RemediationActionType.PATCH: _parse_patch_params,
    RemediationActionType.REDEPLOY: _parse_redeploy_params,
    RemediationActionType.HELM_UPGRADE: _parse_helm_upgrade_params,
}


def parse_llm_response(llm_json: dict[str, Any] | None) -> ParsedRemediationAction:
    """
    Parse the LLM's JSON response into a closed-enum ParsedRemediationAction.

    INVARIANT: This function ALWAYS returns a valid ParsedRemediationAction.
    On any parse failure, it returns NONE with parse_failed=True.
    It NEVER raises an exception to the caller.
    """
    # Gate 1: Null/empty response
    if llm_json is None:
        logger.warning("Parser: LLM response was None — routing to NONE")
        return ParsedRemediationAction(
            action_type=RemediationActionType.NONE, parse_failed=True,
            parse_error="LLM response was None"
        )

    if not isinstance(llm_json, dict):
        logger.warning("Parser: LLM response was not a dict (type=%s)", type(llm_json).__name__)
        return ParsedRemediationAction(
            action_type=RemediationActionType.NONE, parse_failed=True,
            parse_error=f"LLM response was not a dict: {type(llm_json).__name__}"
        )

    # Gate 2: Extract suggested_action
    suggested_action = llm_json.get("suggested_action")
    if suggested_action is None:
        return ParsedRemediationAction(action_type=RemediationActionType.NONE, parse_failed=False)

    if not isinstance(suggested_action, dict):
        logger.warning("Parser: suggested_action was not a dict")
        return ParsedRemediationAction(
            action_type=RemediationActionType.NONE, parse_failed=True,
            parse_error="suggested_action field was not a dict"
        )

    # Gate 3: Validate action type is in the closed enum
    raw_action_type = suggested_action.get("type")
    if raw_action_type is None:
        logger.warning("Parser: suggested_action missing 'type' field")
        return ParsedRemediationAction(
            action_type=RemediationActionType.NONE, parse_failed=True,
            parse_error="suggested_action missing required 'type' field"
        )

    try:
        action_type = RemediationActionType(raw_action_type)
    except ValueError:
        logger.warning("Parser: LLM returned unknown action type '%s' — routing to NONE", raw_action_type)
        return ParsedRemediationAction(
            action_type=RemediationActionType.NONE, parse_failed=True,
            parse_error=f"Unknown action type: '{raw_action_type}' is not in the allowed enum"
        )

    # Gate 4: Handle NONE explicitly
    if action_type == RemediationActionType.NONE:
        return ParsedRemediationAction(action_type=RemediationActionType.NONE, parse_failed=False)

    # Gate 5: Parse action-specific parameters
    raw_params = suggested_action.get("params")
    param_parser = _PARAM_PARSERS.get(action_type)
    if param_parser is None:
        logger.error("Parser: no param parser for action type '%s'", action_type)
        return ParsedRemediationAction(
            action_type=RemediationActionType.NONE, parse_failed=True,
            parse_error=f"No parameter parser registered for '{action_type}'"
        )

    if raw_params is None or not isinstance(raw_params, dict):
        logger.warning("Parser: action type '%s' missing or non-dict params", action_type)
        return ParsedRemediationAction(
            action_type=RemediationActionType.NONE, parse_failed=True,
            parse_error=f"Action type '{action_type}' requires params dict"
        )

    parsed_params = param_parser(raw_params)
    if parsed_params is None:
        return ParsedRemediationAction(
            action_type=RemediationActionType.NONE, parse_failed=True,
            parse_error=f"Parameter validation failed for action type '{action_type}'"
        )

    logger.info("Parser: successfully parsed action type '%s'", action_type)
    return ParsedRemediationAction(action_type=action_type, params=parsed_params, parse_failed=False)


def parse_confidence(llm_json: dict[str, Any] | None) -> DiagnosisConfidence:
    """Extract confidence level from LLM response. Defaults to 'low' on any failure."""
    if not llm_json or not isinstance(llm_json, dict):
        return DiagnosisConfidence.LOW
    raw = llm_json.get("confidence", "low")
    try:
        return DiagnosisConfidence(raw)
    except ValueError:
        logger.warning("Parser: unknown confidence value '%s' — defaulting to low", raw)
        return DiagnosisConfidence.LOW
