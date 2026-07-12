"""
healmesh-core/surface/slack/notifier.py
Slack notification sender for HealMesh diagnoses.
"""

from __future__ import annotations

import logging
import os

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from schema.models import Diagnosis, DiagnosisConfidence, IncidentPayload

logger = logging.getLogger(__name__)

_CONFIDENCE_EMOJI = {
    DiagnosisConfidence.HIGH: "🟢",
    DiagnosisConfidence.MEDIUM: "🟡",
    DiagnosisConfidence.LOW: "🔴",
}
_FAILURE_EMOJI = {
    "CrashLoopBackOff": "🔄",
    "OOMKilled": "💾",
    "ImagePullBackOff": "📦",
    "FailedRollout": "🚀",
    "ResourceQuotaExceeded": "⚖️",
}


class SlackNotifier:
    def __init__(self) -> None:
        from schema.config import get_secret
        self._token = get_secret("SLACK_BOT_TOKEN")
        self._channel = os.environ.get("SLACK_CHANNEL_ID", "")
        self._client = WebClient(token=self._token) if self._token else None
        if not self._token or not self._channel:
            logger.warning("SLACK_BOT_TOKEN or SLACK_CHANNEL_ID not set — Slack delivery disabled")

    def send_diagnosis(self, incident: IncidentPayload, diagnosis: Diagnosis) -> None:
        if not self._client:
            logger.info("Slack disabled — skipping delivery for incident %s", incident.incident_id)
            return

        failure_emoji = _FAILURE_EMOJI.get(incident.failure_type.value, "⚠️")
        confidence_emoji = _CONFIDENCE_EMOJI.get(diagnosis.confidence, "❓")

        blocks = [
            {"type": "header", "text": {"type": "plain_text",
             "text": f"{failure_emoji} HealMesh: {incident.failure_type.value}"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Pod:*\n`{incident.pod_name}`"},
                {"type": "mrkdwn", "text": f"*Namespace:*\n`{incident.namespace}`"},
            ]},
            {"type": "section", "text": {"type": "mrkdwn",
             "text": f"*Root Cause:*\n{diagnosis.root_cause}"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn",
                 "text": f"*Confidence:*\n{confidence_emoji} {diagnosis.confidence.value.capitalize()}"},
                {"type": "mrkdwn", "text": f"*Incident ID:*\n`{incident.incident_id}`"},
            ]},
        ]
        if diagnosis.suggested_manual_command:
            blocks.append({"type": "section", "text": {"type": "mrkdwn",
                "text": f"*Suggested Command (human to run):*\n```{diagnosis.suggested_manual_command}```"}})
        blocks.append({"type": "divider"})
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn",
            "text": f"🤖 HealMesh | Phase 1 (Read-Only) | Model: {diagnosis.llm_model} | Latency: {diagnosis.latency_ms}ms"}]})

        try:
            self._client.chat_postMessage(
                channel=self._channel, blocks=blocks,
                text=f"HealMesh: {incident.failure_type.value} in {incident.namespace}/{incident.pod_name}",
            )
            logger.info("Slack diagnosis delivered for incident %s", incident.incident_id)
        except SlackApiError as e:
            logger.error("Slack API error: %s", e.response["error"])
