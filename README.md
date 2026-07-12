# HealMesh

> **Kubernetes failure detection and LLM-powered diagnosis.** HealMesh watches your cluster, detects failures, and delivers a plain-English root-cause diagnosis to Slack — in seconds, with zero risk to the cluster.

---

## Current Phase: Phase 0 → Phase 1 (Read-Only Diagnosis)

**What works today:**
- Event Watcher (Go) detects 5 canonical Kubernetes failure types
- Gemini LLM (free tier) produces plain-language diagnosis with confidence + suggested command
- Slack delivery of every diagnosis
- Append-only Postgres audit log of every incident and diagnosis

**What does NOT exist yet (by design):**
- Automated remediation (Phase 2 — requires Phase 1.5 benchmark gate first)
- Dashboard (Phase 3)
- SDK (Phase 4)

---

## Architecture

```
Kubernetes Cluster
    │ (watch API, read-only RBAC)
healmesh-k8s (Go)
  └── Event Watcher → assembles incident payload
    │ (internal HTTP/TLS)
healmesh-core (Python)
  ├── Schema Validator (Pydantic)
  ├── Diagnosis Prompt Engine → Gemini API (direct, no middleware)
  ├── Remediation Action Parser (closed enum — most critical component)
  ├── Audit Logger (append-only Postgres)
  └── Slack Notifier
    │
Slack Channel ← diagnosis: root cause, confidence, suggested command
```

The seven non-negotiable invariants: [`CONSTITUTION.md`](./CONSTITUTION.md)

---

## Quick Start (Local Development)

```bash
# 1. Configure
cp .env.example .env
# Edit .env with your Gemini API key, Slack tokens, Postgres credentials

# 2. Start Postgres
docker run -d --name healmesh-postgres \
  -e POSTGRES_DB=healmesh -e POSTGRES_USER=healmesh -e POSTGRES_PASSWORD=yourpass \
  -p 5432:5432 postgres:15

# 3. Run DB migration
psql -h localhost -U healmesh -d healmesh -f infra/postgres/001_init.sql

# 4. Run healmesh-core
cd healmesh-core && pip install -r requirements.txt
uvicorn main:app --reload

# 5. Run healmesh-k8s watcher
cd healmesh-k8s && go run ./cmd/watcher

# 6. Inject a test failure
bash infra/scripts/inject_failure.sh CrashLoopBackOff
```

---

## Testing

```bash
# Python unit tests (healmesh-core)
cd healmesh-core && pytest tests/ -v --cov=. --cov-report=term-missing

# Go unit tests (healmesh-k8s)
cd healmesh-k8s && go test ./...
```

---

## License

MIT
