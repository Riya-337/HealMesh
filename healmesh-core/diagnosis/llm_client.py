"""
healmesh-core/diagnosis/llm_client.py

Configurable LLM provider client (Google Gemini / Groq) for HealMesh diagnosis.

INVARIANT (Constitution Article 2, Invariant 2):
This is the ONLY place the LLM API is called. No orchestration middleware.
No LangChain, no LlamaIndex, no third-party gateway.
The call path: incident → prompt → this function → raw LLM response.
The Remediation Action Parser then enforces the closed enum.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass

import google.generativeai as genai
from google.api_core import exceptions as api_exceptions
from google.api_core import retry as api_retry
from groq import Groq

logger = logging.getLogger(__name__)

# Retry on transient errors ONLY — never on ResourceExhausted (quota/rate-limit).
_RETRY_POLICY = api_retry.Retry(
    predicate=api_retry.if_exception_type(
        api_exceptions.ServiceUnavailable,
        api_exceptions.InternalServerError,
        api_exceptions.DeadlineExceeded,
    )
)

_DIAGNOSIS_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "root_cause": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "suggested_action": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["PATCH", "REDEPLOY", "SCALE", "HELM_UPGRADE", "NONE"]},
                "params": {
                    "type": "object",
                    "properties": {
                        "deployment_name": {"type": "string"},
                        "namespace": {"type": "string"},
                        "replica_count": {"type": "integer"}
                    }
                }
            },
            "required": ["type"]
        },
        "suggested_manual_command": {"type": "string"}
    },
    "required": ["root_cause", "confidence", "suggested_action"]
}


@dataclass
class LLMResponse:
    """Raw LLM response before parsing."""
    raw_text: str
    parsed_json: dict | None
    model_used: str
    latency_ms: int
    success: bool
    error: str | None = None


class GeminiClient:
    """
    Direct LLM client supporting Google Gemini and Groq backends.
    We keep the class name GeminiClient for main.py compatibility.
    """

    def __init__(self) -> None:
        self.provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
        if self.provider == "groq":
            from schema.config import get_secret
            api_key = get_secret("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY environment variable is not set.")
            self.model_name = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
            self.groq_client = Groq(api_key=api_key)
            logger.info("Initialized Groq client with model: %s", self.model_name)
        else:
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise ValueError(
                    "GEMINI_API_KEY environment variable is not set. "
                    "Get a free key at: https://aistudio.google.com/app/apikey"
                )
            genai.configure(api_key=api_key, transport="rest")
            self.model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
            logger.info("Initialized Gemini client with model: %s", self.model_name)

    def diagnose(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Call LLM provider to produce a structured diagnosis. Returns raw response."""
        start_ms = int(time.time() * 1000)
        try:
            if self.provider == "groq":
                # Direct Groq API call
                chat_completion = self.groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    model=self.model_name,
                    temperature=0.1,
                    max_tokens=2048,
                    response_format={"type": "json_object"},
                )
                latency_ms = int(time.time() * 1000) - start_ms
                raw_text = chat_completion.choices[0].message.content or ""
            else:
                # Direct Google Gemini API call
                model = genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=system_prompt,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json",
                        response_schema=_DIAGNOSIS_RESPONSE_SCHEMA,
                        temperature=0.1,
                        max_output_tokens=2048,
                    ),
                )
                response = model.generate_content(user_prompt)
                latency_ms = int(time.time() * 1000) - start_ms
                raw_text = response.text

            try:
                parsed = json.loads(raw_text)
                if isinstance(parsed, dict):
                    # Auto-unwrap nested single-key dictionaries or "diagnosis" wrapped objects
                    if len(parsed) == 1:
                        key = list(parsed.keys())[0]
                        if isinstance(parsed[key], dict) and any(k in parsed[key] for k in ["root_cause", "suggested_action", "confidence"]):
                            parsed = parsed[key]
                    elif "diagnosis" in parsed and isinstance(parsed["diagnosis"], dict):
                        parsed = parsed["diagnosis"]
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("LLM response was not valid JSON: %s. Raw text: %r", e, raw_text)
                return LLMResponse(
                    raw_text=raw_text, parsed_json=None, model_used=self.model_name,
                    latency_ms=latency_ms, success=False, error=f"JSON parse error: {e}"
                )
            return LLMResponse(
                raw_text=raw_text, parsed_json=parsed, model_used=self.model_name,
                latency_ms=latency_ms, success=True
            )
        except Exception as e:
            latency_ms = int(time.time() * 1000) - start_ms
            logger.error("LLM API call failed: %s", e, exc_info=True)
            return LLMResponse(
                raw_text="", parsed_json=None, model_used=self.model_name,
                latency_ms=latency_ms, success=False, error=str(e)
            )
