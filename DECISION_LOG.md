# HealMesh — Decision Log

This file records every architecture decision that affects security invariants, technology choices, or phase gates. All entries are append-only.

---

## ADR-001: No Orchestration Middleware in the Diagnosis Path

**Date:** 2026-07-07  
**Status:** Accepted  

**Decision:** healmesh-core calls the LLM provider API directly using the provider's official SDK. No n8n, no LangChain, no LlamaIndex, no OpenClaw, no Zapier, no third-party agent gateway is introduced into the path from incident → LLM → parsed action.

**Rationale:** The security-critical parsing step must live in code the team fully owns and can audit line by line. A third-party orchestration layer makes that path opaque.

**Consequences:** healmesh-core is responsible for prompt construction, LLM invocation, and response parsing.

---

## ADR-002: LLM Provider — Google Gemini (Free Tier) for Phase 0/1

**Date:** 2026-07-07  
**Status:** Accepted  

**Decision:** Use Google Gemini (`gemini-2.0-flash-lite` model) via the `google-generativeai` Python SDK for Phase 0 and Phase 1. Switch to production model (Claude Sonnet or GPT-4o) once the benchmark phase (1.5) establishes accuracy requirements.

**Rationale:**
- Free tier available from Google AI Studio (no billing required for development)
- Supports structured output via function calling / response schema
- Easy to swap: the LLM client is isolated in `healmesh-core/diagnosis/llm_client.py`
- Avoids spend before diagnosis accuracy is proven

**Switch criteria:** If benchmark accuracy < 80% on Gemini free tier, evaluate Claude Sonnet or GPT-4o before accepting the shortfall.

---

## ADR-003: healmesh-k8s Language — Go (client-go)

**Date:** 2026-07-07  
**Status:** Accepted  

**Decision:** healmesh-k8s (Event Watcher + Remediation Executor in Phase 2+) is written in Go using the official `client-go` library.

**Rationale:**
- Go is the idiomatic language for Kubernetes operators and controllers
- `client-go` models the watch/informer pattern natively
- Strong typing enforces read/write code path separation at compile time

**Dual-language architecture:** healmesh-core (Python) and healmesh-k8s (Go) communicate via internal HTTP over TLS.

---

## ADR-004: Benchmark Dataset — Synthetic Cases Plus Real Incidents From Phase 1 (Phase 1.5)

**Date:** 2026-07-07  
**Status:** Accepted (revised 2026-07-08 — see rationale)

**Decision:** The Phase 1.5 benchmark dataset consists of:
1. **Hand-built synthetic cases** — a minimum of 30–50, spanning all five canonical failure types, constructed to guarantee coverage of edge cases that may not appear organically.
2. **Real incidents captured during Phase 1 development** — any incident records produced by the live system during Phase 1 integration testing that a human reviewer confirms as correctly labelled may be included in the benchmark set.

**Rationale for revision:** TESTING.md §5 and the Implementation Plan Phase 1.5 task table both specify that the benchmark "mix[es] hand-built synthetic cases … and real incidents captured during Phase 1 development." ADR-004 originally said synthetic-only because no production clusters existed at authoring time. Phase 1 development itself generates real incident records as a natural side effect of running the system against injected failures, making those records available for benchmarking without requiring anonymization of third-party data. The rationale for excluding real data (no production clusters) does not apply to self-generated test incidents. TESTING.md and the Implementation Plan are the correct source of truth here, and ADR-004 is updated accordingly.

**Constraints that remain unchanged:**
- The synthetic cases must still achieve coverage of all five failure types regardless of how many real incidents are available.
- Every case — synthetic or real — must have a human-reviewed ground-truth label before inclusion.
- Results are reported per failure type, not just as an aggregate (TESTING.md §5, CONSTITUTION.md Article 4).
- The benchmark set is versioned so results are comparable across model/prompt changes.

**Consequences:** Benchmark results must note which cases are synthetic and which are from real incidents, so the split is visible in the published report.

---

## ADR-005: Switch to Groq (Llama-3.1-8b-instant) for Phase 1/1.5

**Date:** 2026-07-11  
**Status:** Accepted (Supersedes ADR-002)

**Decision:** Switch the LLM provider from Google Gemini to Groq (using the `llama-3.1-8b-instant` model) for Phase 1 and Phase 1.5. This will be implemented via the official `groq` Python SDK, with configuration handled via `LLM_PROVIDER`, `GROQ_API_KEY`, and `GROQ_MODEL` environment variables.

**Rationale:**
- **Severe Quota Friction:** The Google Gemini free tier has a hard daily limit of 20 requests per project. Iterating on SRE prompt templates and fixing JSON truncation bugs took multiple days and consumed 6 separate API keys. This bottleneck made rapid development and deployment impractical.
- **Operational Switch, Not Accuracy-Driven:** This change is not driven by Gemini failing the accuracy gate, as a full 32-case benchmark suite could never complete within the 20 requests/day limit.
- **Reliable JSON Mode Support:** Groq's API and the `llama-3.1-8b-instant` model support native JSON Mode and Tool Calling, ensuring structured output compatibility with Pydantic schema validation.
- **High Rate Limits:** Groq's free-tier rate limits for the 8B model are significantly higher (14.4 million tokens/day), allowing the complete 32-case suite to run repeatedly without interruption.

**Consequences:**
- The codebase will support both `gemini` and `groq` backends via the `LLM_PROVIDER` environment variable.
- The prompt engine rules and schema validation remain identical, keeping the closed-enum parsing invariant (Constitution Article 2, Invariant 1) intact.
- The Phase 1.5 benchmark report will note that Groq was used for the evaluations.


