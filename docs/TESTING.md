# HealMesh — Testing Strategy

Status: Draft v1
Authority: This document outlines the rigorous testing standards required for the HealMesh project, particularly emphasizing the separation of concerns and the strict security invariants defined in CONSTITUTION.md and AGENTS.md.

---

## 1. Overview

HealMesh components are tested in isolation, followed by integration tests in a live Kubernetes cluster (e.g., kind or minikube). Tests are shipped alongside the code they test. Write capability must be accompanied by a test in the same PR.

---

## 2. Unit Testing & Coverage Bars

### 2.1 The Remediation Action Parser (CRITICAL)

The `action_parser.py` module is the single most security-critical component in HealMesh (Constitution Article 2, Invariant 1). It enforces the closed enum and protects downstream execution from arbitrary LLM output.

**Coverage Requirement:**
- **100% branch coverage** is strictly required for `healmesh-core/parser/action_parser.py`.
- Any change to the parser must be accompanied by a corresponding test in `tests/test_parser.py`.
- Any coverage drop below 100% is considered a build failure.

### 2.2 The Audit Logger

The audit logger must maintain append-only semantics. Tests must use reflection to ensure no `update()` or `delete()` methods exist on audit-logging classes.

### 2.3 The Watcher (Go)

The Go watcher (`healmesh-k8s/watcher/`) must be tested to ensure it accurately detects the 5 supported failure types (`CrashLoopBackOff`, `OOMKilled`, `ImagePullBackOff`, `FailedRollout`, `ResourceQuotaExceeded`).

---

## 3. Phase 1.5: End-to-End Timing (FR-3)

A core non-functional requirement (FR-3) is that the time elapsed from failure detection in the cluster to the delivery of the Slack diagnosis notification is minimal.

- **Target:** ≤ 30s p95 latency.
- **Measurement:** Injected failure -> detection -> LLM diagnosis -> Slack delivery.
- Must be measured via a real end-to-end integration test against a live cluster.

---

## 4. Phase 1.5: Benchmark & Accuracy Gate

The Phase 1.5 accuracy gate evaluates the AI diagnosis quality.

- **Target:** ≥ 80% accuracy per failure type before Phase 2 (Automated Remediation) can begin.
- **Dataset:** 30–50 synthetic cases across the 5 failure types.
- **Rules:** The benchmark script (`run_benchmark.py`) must handle API quota limits gracefully (saving state) and report true accuracy without conflating API errors with diagnosis failures.

---

## 5. Kubernetes Integration Tests

### 5.1 RBAC Negative Testing

The `healmesh-watcher` component is strictly read-only.
- **Requirement:** Tests must verify that any attempt by the watcher service account to perform write verbs (`create`, `update`, `patch`, `delete`) on Kubernetes resources is denied by the cluster's RBAC enforcement.

### 5.2 Failure Injection

Integration tests will use `infra/scripts/inject_failure.sh` to inject the 5 failure types against the cluster and confirm the end-to-end flow.

---

## 6. Phase 2 (Future): The Executor

*(To be authored in Phase 2)*
The Executor (`healmesh-k8s/executor/`) is the only component with write privileges. It must enforce the hardcoded namespace denylist (`kube-system`, `kube-public`, `healmesh`) before any action.

---

## 7. Slack Integration & Security

When adding inbound Slack webhooks (e.g., for Phase 2 approval interactions or interactive buttons):

- **HMAC Signature Verification Requirement:** HMAC signature verification MUST be active on the webhook handler.
- **Parsing Order:** The handler must reject invalid signatures (HTTP 401) **before** any payload parsing, JSON decoding, or Pydantic validation occurs. This prevents arbitrary data from entering the application context.
- **Secrets:** `SLACK_SIGNING_SECRET` and `SLACK_BOT_TOKEN` must be strictly loaded from environment variables and must never be logged.
