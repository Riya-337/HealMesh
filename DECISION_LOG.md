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

---

## ADR-006: REDEPLOY Rollback Semantics (No Spec Rollback)

**Date:** 2026-07-12  
**Status:** Accepted  

**Decision:** A `REDEPLOY` action will NOT attempt to "rollback" (i.e., revert the restart annotation) upon health check failure. Instead, it will simply fail the health check and report that the redeploy did not resolve the issue, leaving the deployment in its current state.

**Rationale:** `REDEPLOY` does not modify the underlying `PodTemplateSpec` (other than injecting a restart annotation to force new pods). If the new pods fail to start, they are failing using the exact same spec as the old pods. Reverting the restart annotation would merely trigger *another* rollout of the exact same spec, creating a second wave of identical pods. This is inert at best and adds unnecessary churn at worst. A clean failure without rollback is the safest and most accurate reflection of the state.

**Consequences:** The execution skeleton for `REDEPLOY` natively omits the rollback patch step upon health check failure, diverging slightly from `SCALE` and `PATCH`. Test cases will explicitly assert this non-rollback behavior.

---

## ADR-007: HELM_UPGRADE Scope and Blast Radius Restriction (Rollback Only)

**Date:** 2026-07-12  
**Status:** Accepted  

**Decision:** The `HELM_UPGRADE` remediation action is strictly restricted to rolling back to a previous known-good revision. It **shall not** accept arbitrary chart configurations, `values.yaml` overrides, or forward upgrades to unseen chart versions (`target_version`). 

**Rationale:** Permitting an LLM to generate arbitrary YAML configurations or forward upgrades to unverified chart versions introduces a massive, unbounded blast radius, contradicting the project's core safety principle (Article 4, Invariant 4 - Secure by Default). Limiting the action strictly to revision rollbacks aligns the blast radius of `HELM_UPGRADE` with that of `REDEPLOY` and `SCALE`. 

**Consequences:** The `HelmUpgradeParams` struct in Go and the Pydantic schema in Python will explicitly forbid arbitrary value mappings and forward versions, restricting parameters to only three identifiers: `namespace`, `release_name`, and `target_revision` (required). HELM_UPGRADE is enabled but structurally treated as a rollback tool for now. An LLM instruction explicitly limits its use to reverting to prior stable revisions.

---

## ADR-009: Approver Authorization

**Date:** 2026-07-12
**Status:** Accepted

**Decision:** Rely on an explicit Slack User ID allowlist (configured via `APPROVER_ALLOWLIST` environment variable) before accepting a Slack interaction as an approved remediation. Unauthorized attempts are rejected, logged loudly with a warning, and permanently written to the audit database as `decision="rejected"`.

**Rationale:** Before full SSO integration, we need to guarantee that any random Slack member in the channel cannot click the "Approve" button and successfully trigger a cluster-mutating action. HMAC verification proves the message originated from Slack, but doesn't prove the user has appropriate permissions.

**Consequences:** Only specifically allowlisted Slack users can approve execution. Attempted approvals by non-allowlisted users skip the executor entirely.

---

## ADR-010: Execution-Rate Limiting

**Date:** 2026-07-12
**Status:** Accepted

**Decision:** Implement a sliding window execution-rate limiter directly within the Go executor (`healmesh-k8s/executor/handler.go`), tracking global executions and per-namespace executions over a 60-second window.

**Rationale:** To prevent cascading incident bursts (or abusive behavior) from overwhelming the Kubernetes API with parallel remediation attempts. The executor is fail-closed on rate limit: exceeding it blocks execution and writes a `failed` result to the database with `error_message="rate limit exceeded"`.

**IMPORTANT SAFETY CAVEAT:** The initial thresholds (5 executions per namespace per minute, 10 executions globally per minute) are a starting point for catching anomalous or abusive bursts, not a hard ceiling meant to constrain legitimate multi-deployment incident response. There is no real operational data to calibrate these numbers yet (no pilot customer or production traffic). These thresholds MUST be revisited and adjusted once real usage data exists.

**Consequences:** The executor maintains in-memory timestamp lists protected by a mutex, checking this state before checking idempotency or triggering execution.

---

## ADR-008: Executor Skeleton Refactor Timing

**Date:** 2026-07-12  
**Status:** Accepted  

**Decision:** The `HELM_UPGRADE` action will be built natively as a fourth data point alongside `SCALE`, `PATCH`, and `REDEPLOY`. The shared-skeleton refactor (extracting snapshot/health-check/rollback patterns) will be deferred until after `HELM_UPGRADE` is completed and proven. 

**Rationale:** `REDEPLOY` already broke the "always snapshot + rollback" assumption since it does not rollback upon failure. `HELM_UPGRADE` will likely introduce its own nuances (e.g., interacting with Helm state rather than just raw Kubernetes Deployments). Refactoring prematurely with incomplete abstractions leads to brittle code. Four solid, native implementations provide the necessary grounded context to build a robust, flexible abstraction later.

**Consequences:** `HELM_UPGRADE` implementation will proceed directly in its own file (`executor/helm_upgrade.go`) without waiting for a broader architectural refactor.

---

## ADR-011: HealPolicy CRD and Globally Uniform Authorization/Rate Limits

**Date:** 2026-07-14  
**Status:** Accepted  

**Decision:** The `HealPolicy` CRD controls which action types are permitted per namespace. It does **not** allow per-namespace overrides for the approver allowlist or rate limits, which remain globally uniform.

**Rationale:** Adding per-namespace authorization overrides would allow a compromised or malicious `HealPolicy` to weaken the list of who can approve actions in that namespace. This would undermine the uniform security floor established by ADR-009, violating the "Secure by default" invariant.

**Consequences:** The CRD schema only exposes `allowedActions`. All requests must still pass the global rate limits and approver checks before the policy engine evaluates the action.

---

## ADR-012: Webhook Structural Guarantee and Redundant Denylist

**Date:** 2026-07-14  
**Status:** Accepted  

**Decision:** A ValidatingAdmissionWebhook configured with `failurePolicy: Fail` will be deployed to strictly prevent `HealPolicy` creation/updating in denylisted namespaces (`kube-system`, `kube-public`, `healmesh`). The executor's own hardcoded denylist check will also remain fully intact.

**Rationale:** The OpenAPI schema for CRDs cannot restrict `metadata.namespace`. A webhook is required to structurally guarantee that a policy cannot exist in protected namespaces. The webhook must fail closed (`failurePolicy: Fail`), as a fail-open configuration would silently remove this structural guarantee during a webhook outage. The executor's hardcoded check remains in place because the webhook only guards future `CREATE`/`UPDATE` events and cannot retroactively catch a bad policy created during a partial-rollout gap or if the webhook was temporarily bypassed. Both layers are structurally necessary.

**Consequences:** `failurePolicy: Fail` is set on the webhook configuration. Executor code is unaffected and continues checking the denylist before any operation, in addition to checking the `HealPolicy`.
