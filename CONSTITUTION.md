# HealMesh — Constitution

Status: Draft v1  
Authority: This is the canonical source for the project's non-negotiable principles. If any document conflicts with this one, this one wins.

---

## Article 1 — Purpose

HealMesh exists to shorten the time between "something in the cluster is broken" and "a human understands why," and, later, to safely close a narrow set of well-understood fixes — **never to replace human judgment on anything ambiguous or high-blast-radius.**

---

## Article 2 — The Seven Invariants

1. **The LLM never produces an executed command.** Output is always forced into a closed, typed enum before anything downstream sees it. Unparseable output means no automated action, never a best guess.

2. **No orchestration middleman between the core logic and the LLM API.** Direct SDK calls only.

3. **Read and write are architecturally separate**, with separate code paths and separate identities.

4. **Secure by default, opt-in to widen.** Every new namespace, action type, or integration starts at the narrowest permission.

5. **The audit trail is append-only at the code level** — no delete or update method exists for audit records.

6. **The hardcoded namespace denylist is enforced in code**, inside the executor itself, cannot be overridden by any configuration, policy, or LLM output.

7. **Anything beyond `SCALE` always requires human approval, permanently.**

---

## Article 3 — Sequencing Discipline

- Diagnosis before remediation.
- A benchmark (≥80% accuracy gate) before Phase 2.
- One action type (`SCALE`) before `PATCH`, `REDEPLOY`, `HELM_UPGRADE`.
- Breadth (Dashboard, SDK, multi-cluster) only with a real, named driver.

Deadline pressure is not a valid reason to skip a phase gate.

---

## Article 4 — Honesty as a Design Principle

- Accuracy claims are reported exactly as measured.
- The system is never described as "fully autonomous."
- Weak spots are surfaced, not smoothed over.

---

## Article 5 — Who Can Change What

- Article 2: only changeable via `DECISION_LOG.md` entry with explicit reasoning, reviewed by more than one person. An AI agent must never modify this article.
- Article 3: adjustable per real constraints, but phase gates follow the same bar as Article 2.

---

## Article 6 — Relationship to Other Documents

| Document | Role |
|---|---|
| `AGENTS.md` | Operationalizes Article 2 for AI coding agents |
| `docs/TDD.md` | Implements Articles 2 and 3 at the component level |
| `docs/PRD.md` | Implements Articles 1 and 3 as product scope |
| `docs/TESTING.md` | Verifies Article 2 is true in the shipped system |
| `DECISION_LOG.md` | Record of any change to this document |
| `MIGRATION.md` | Migration notes from prototype |
