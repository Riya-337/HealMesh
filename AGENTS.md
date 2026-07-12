# AGENTS.md — AI Context File for HealMesh

Status: Draft v1  
Audience: Any AI coding agent working in this repository. **Read this file in full before writing or editing any code.**

---

## 0. What This Project Is

HealMesh watches a Kubernetes cluster, detects a fixed set of common failure types, uses Google Gemini (free tier, see DECISION_LOG ADR-002) to produce a plain-language root-cause diagnosis, and — only from Phase 2 onward, with explicit human approval — executes a narrow, pre-defined remediation action.

Full detail: `docs/PRD.md`, `docs/TDD.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/TESTING.md`

---

## 1. Non-Negotiable Invariants (Do Not Relax — Ever)

1. **LLM output → closed enum ONLY.** `PATCH | REDEPLOY | SCALE | HELM_UPGRADE | NONE`. Unparseable → `NONE`. No LLM text reaches a shell or kubectl call directly.

2. **No orchestration middleman.** Direct SDK calls only. No n8n, LangChain, LlamaIndex, OpenClaw.

3. **Read and write are separate code paths with separate identities.** `healmesh-k8s/watcher/` and `healmesh-k8s/executor/` must never share functions, classes, or service accounts.

4. **Secure by default, opt-in to widen.** No convenience defaults that grant broader access.

5. **Audit records are append-only in code.** No `update()` or `delete()` on audit-logging classes.

6. **Hardcoded namespace denylist** (`kube-system`, `kube-public`, `healmesh`) enforced in code inside the executor.

7. **Human approval is required for every remediation action in every currently-defined phase — including `SCALE`.** No action type (`PATCH`, `REDEPLOY`, `SCALE`, `HELM_UPGRADE`) may be auto-executed. Per PRD Phase 2 scope and CONSTITUTION.md Article 2.7, even `SCALE` requires explicit human approval at launch of Phase 2 and remains approval-gated until a future phase explicitly removes that requirement via a DECISION_LOG entry.

---

## 2. Repository Layout

```
healmesh/
├── healmesh-core/          # Python: schema validation, LLM calls, parser, audit
│   ├── schema/             # Pydantic models
│   ├── diagnosis/          # Prompt templates + Gemini client
│   ├── parser/             # Closed enum enforcement (most critical)
│   ├── approval/           # Approval workflow (Phase 2+)
│   ├── audit/              # Append-only logger
│   ├── surface/slack/      # Slack integration
│   └── tests/
├── healmesh-k8s/           # Go: Event Watcher (read-only) + Executor (write, Phase 2+)
│   ├── watcher/            # get/list/watch only
│   ├── executor/           # write path, Phase 2+
│   ├── cmd/watcher/        # main entry point
│   └── tests/
├── surface/                # Slack (v1), Dashboard (v3+), SDK (v4+)
├── infra/
│   ├── helm/healmesh/
│   ├── k8s/                # RBAC, namespace, network policies
│   ├── postgres/           # SQL migrations
│   └── scripts/
├── docs/                   # PRD, TDD, ARCHITECTURE, IMPLEMENTATION_PLAN, TESTING
├── benchmark/              # Phase 1.5 benchmark set
├── AGENTS.md
├── CONSTITUTION.md
├── DECISION_LOG.md
└── MIGRATION.md            # Prototype-to-healmesh migration history (TDD §6)
```

**Import rule:** `healmesh-k8s/watcher/` must never import from `healmesh-k8s/executor/`, and vice versa.

---

## 3. Coding Conventions

- **Python 3.11+** for healmesh-core (Pydantic v2, `google-generativeai` SDK — no LangChain/LlamaIndex)
- **Go 1.22+** for healmesh-k8s (`client-go` — no shell outs)
- **Strict typing** in `healmesh-core/parser/` and `healmesh-k8s/executor/`
- **No shelling out** — no `subprocess`, `os.system`, or shell command strings
- **Secrets via env vars** — never hardcoded, never in committed `.env`, never logged
- **Tests ship with code** — write capability = test in same PR

---

## 4. What NOT To Do

- Do not simplify the Remediation Action Parser to accept broader input shapes
- Do not add bypass flags (`--force`, `--skip-approval`, `DEBUG_AUTO_EXECUTE`)
- Do not implement Phase 3/4 features (Dashboard, SDK, HealPolicy) early
- Do not reintroduce n8n, OpenClaw, or LangChain
- Do not write parser, executor, or audit logger without accompanying tests

---

## 5. When in Doubt

If a request conflicts with Section 1, explain which invariant is implicated and propose the smallest change that accomplishes the goal without crossing it.
