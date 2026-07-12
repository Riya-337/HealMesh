# HealMesh — Migration Notes

Status: Draft v1  
Source of truth for this document: TDD §6 "What Carries Over From the Current Repo"

---

## Background

HealMesh originated as a hackathon prototype named **prism**. That prototype used n8n as
its orchestration layer and OpenClaw for LLM integration. The current healmesh repository
is a deliberate architectural rewrite, not an incremental migration — but several concrete
artifacts from the prototype were retained and adapted rather than discarded.

This document records exactly what carried over, what was retired, and why, per ADR-001
and TDD §6.

---

## What Carried Over (Retained and Adapted)

| Prototype artifact | Disposition |
|---|---|
| `infra/helm/prism/` | Renamed to `infra/helm/healmesh/`. Restructured from a multi-service chart (n8n, OpenClaw, Postgres, Redis) to a leaner chart (healmesh-core, healmesh-k8s, Postgres). Rebuilt incrementally as components are implemented. |
| Kubernetes namespace `prism` | Renamed to `healmesh`. The namespace itself and its RBAC approach were sound; only the name changed. |
| `backend/CONTRACTS.md` | Adapted into the formal incident/diagnosis JSON schema for `healmesh-core/schema/models.py`. The payload shape was a reasonable starting point and was preserved rather than redesigned from zero (per TDD §6). |
| `backend/migrations/001_remediation_incidents.sql` | Reviewed and adapted as the starting point for `infra/postgres/001_init.sql`. The table structure was adapted and append-only triggers were added in the same migration file. |
| `infra/scripts/remediate.sh` | Superseded by the in-process Remediation Executor (Phase 2+, TDD §3.3). The enum-to-action taxonomy this script encoded (`PATCH`, `REDEPLOY`, `SCALE`, `HELM_UPGRADE`) directly informed the closed-enum contract in `parser/action_parser.py`. The script itself is not used at runtime. |

---

## What Was Retired

| Prototype artifact | Disposition | ADR |
|---|---|---|
| `backend/workflows/prism-incident.json` (n8n workflow) | **Retired.** Logic re-implemented as `healmesh-core`. n8n is not a runtime dependency at any phase. | ADR-001 |
| OpenClaw HTTP integration | **Retired.** Replaced by direct LLM API calls via the provider's official SDK from `healmesh-core/diagnosis/llm_client.py`. | ADR-001 |

**Rationale for retirement (ADR-001):** The security-critical parsing step — schema validation
→ prompt construction → LLM call → closed-enum parse — must live in code the team fully
owns and can audit line by line. A third-party orchestration layer or HTTP integration makes
that path opaque and non-auditable.

---

## What Was Never Part of the Prototype

The following are **new** in healmesh, with no prototype equivalent:

- `healmesh-core/parser/action_parser.py` — closed-enum enforcement with full adversarial test coverage
- `healmesh-core/audit/logger.py` — append-only audit logger with no update/delete methods
- `healmesh-k8s/watcher/` — Go event watcher using client-go (prototype used Python)
- `infra/k8s/rbac-watcher.yaml` — read-only ClusterRole (prototype had no RBAC separation)
- All seven Constitution invariants, enforced from the first line of code

---

## Relationship to CONSTITUTION.md

CONSTITUTION.md Article 5 states that Article 2 (the seven invariants) is only changeable
via a DECISION_LOG.md entry with explicit reasoning reviewed by more than one person.
The invariants were **not** carried over from the prototype — the prototype violated several
of them (n8n = Invariant 2 violation; no audit log = Invariant 5 violation; no RBAC
separation = Invariant 3 violation). They are new constraints that the rewrite was designed
to satisfy from day one.
