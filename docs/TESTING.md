# HealMesh — Testing Strategy

Status: Draft v1
Authority: This document is the canonical reference for how HealMesh components are tested. It operationalizes the invariants defined in CONSTITUTION.md.

---

## 1. Coverage Bars & Requirements

Code that cannot be tested cannot be trusted to operate on a production cluster. Coverage must be enforced strictly via CI.

- **Remediation Action Parser (`healmesh-core/parser/action_parser.py`)**: 100% Branch Coverage. (Critical invariant: enforces the closed enum).
- **Executor (`healmesh-k8s/executor/`)**: 100% Branch Coverage. (Critical invariant: enforces the namespace denylist and approval gating).
- **Audit Logger (`healmesh-core/audit/logger.py`)**: 100% Statement Coverage. Must verify append-only semantics via reflection (no `update`/`delete` methods).
- **Schema Validator (`healmesh-core/schema/`)**: 90% Statement Coverage.
- **Event Watcher (`healmesh-k8s/watcher/`)**: 80% Statement Coverage.
- **Approval Workflow Engine (`healmesh-core/approval/`)**: 90% Branch Coverage.
- **HealPolicy CRD**: E2E validation tests required for all admission controller webhooks (Phase 3+).

---

## 2. Unit Testing Methodology

Unit tests are isolated. They mock external dependencies (Kubernetes API, LLM Provider, Slack API, PostgreSQL).
- Python (healmesh-core): `pytest`, `pytest-cov`, `pytest-asyncio`.
- Go (healmesh-k8s): `go test`, table-driven tests (`assert` / `require`).
Write capability (Executor) must be accompanied by a test in the exact same PR.

---

## 3. Integration Testing Methodology

Integration tests run against a local `kind` or `minikube` cluster, connecting the Python core and Go components.
- **Database**: Ephemeral PostgreSQL containers.
- **Event Flow**: Tests must assert that a generated Kubernetes event reaches the core and generates a parsed `Diagnosis` object.
- **Timing (FR-3)**: End-to-End latency from failure injection to Slack notification delivery MUST be ≤ 30s p95 across all failure types.

---

## 4. Security Testing Methodology

Security testing ensures the structural invariants are physically enforced.

- **RBAC Negative Tests**: Integration tests MUST verify that the `healmesh-watcher` ServiceAccount is denied write verbs (`create`, `update`, `patch`, `delete`) by the cluster.
- **Denylist Evasion Tests**: Tests must attempt to trick the Executor into mutating `kube-system`, `kube-public`, or `healmesh` namespaces and verify strict rejection.
- **Parser Fuzzing**: The `action_parser.py` must be fuzzed with malformed LLM responses to ensure it securely defaults to `NONE`.

---

## 5. Benchmark Methodology (Phase 1.5)

Before Phase 2 (Automated Remediation) can begin, the AI diagnosis quality must be proven.

- **Gate**: ≥ 80% accuracy per failure type.
- **Dataset**: 30–50 synthetic cases across the 5 canonical failure types (CrashLoopBackOff, OOMKilled, ImagePullBackOff, FailedRollout, ResourceQuotaExceeded).
- **Tooling**: `benchmark/run_benchmark.py` must handle API quota limits gracefully (checkpointing progress) and report true accuracy (conflating an API error with a wrong diagnosis is prohibited).

---

## 6. Chaos & Failure-Injection Testing

HealMesh must be resilient to infrastructure turbulence.
- **Scripted Injections**: `infra/scripts/inject_failure.sh` is used to deterministically trigger the 5 canonical failure types.
- **Resilience**: The watcher must auto-reconnect if the Kubernetes API server restarts. The core must retry LLM calls on 429s with exponential backoff (up to 3 retries) before emitting a generic diagnosis failure.

---

## 7. CI/CD Merge Gates & Integrations

All PRs must pass the automated merge gates.

- **Slack HMAC Verification**: Any inbound webhook (e.g., `POST /slack/actions`) MUST enforce HMAC-SHA256 signature verification *before* any payload parsing occurs. Unsigned or expired (old timestamp) requests must be rejected immediately (HTTP 401).
- **Secrets Management**: `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, and `GEMINI_API_KEY` must never be logged. They must be loaded exclusively via environment variables. (Vault integration deferred to Phase 2).
- **Build**: No PR may merge if it reduces coverage below the bars defined in Section 1.
