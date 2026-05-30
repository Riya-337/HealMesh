# PRISM API & event contracts (Person B — Task 1)

This document is the **working agreement** between **Backend (n8n)**, **Middleware (OpenClaw/agents)**, **Frontend (dashboard)**, and **Infra**.  
**Person C must confirm** OpenClaw path(s), header names, and any fields the gateway adds or strips.

**MVP history:** incident audit trail = **n8n → Executions** (no custom DB). Optional SQL later lives under `migrations/`.

---

## 1. Runtime URLs (from Infra)

| Consumer | Base URL | Notes |
|----------|----------|--------|
| n8n → OpenClaw (in-cluster) | `http://openclaw` | Kubernetes Service `openclaw`, port **80** → pod **8080** (`prism` namespace). |
| External → n8n Webhook | `https://<n8n-host>/webhook/...` | Depends how n8n is exposed (LoadBalancer / Ingress). |

---

## 2. Auth — OpenClaw

- Secret: `OPENCLAW_AUTH_TOKEN` (see `infra/k8s/secrets.yaml`).
- **Proposed** client header (confirm with Person C / OpenClaw docs):

```http
Authorization: Bearer <OPENCLAW_AUTH_TOKEN>
Content-Type: application/json
```

If OpenClaw expects a different scheme (e.g. `X-API-Key`), **only the header line changes**; keep the same JSON bodies below.

---

## 3. Inbound: failure webhook → n8n

**Purpose:** CI, K8s hooks, or a small forwarder POSTs a normalized incident into n8n.

**Method:** `POST`  
**Path:** TBD in n8n (e.g. `/webhook/prism/incident`) — stable per environment.

### 3.1 Body schema (`application/json`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | string | yes | Contract version, e.g. `"1.0"`. |
| `incident_id` | string | yes | Unique id (UUID) for idempotency and DB rows. |
| `source` | string | yes | `"ci"` \| `"k8s"` \| `"manual"` \| `"data_pipeline"` (stretch). |
| `severity` | string | no | `"info"` \| `"warning"` \| `"critical"`. |
| `occurred_at` | string (ISO 8601) | yes | When the failure was detected. |
| `environment` | string | yes | e.g. `prism`, `staging`. |
| `namespace` | string | no | K8s namespace, e.g. `prism`. |
| `service` | string | no | Logical service or deployment name. |
| `deployment` | string | no | K8s Deployment name if known. |
| `pipeline` | object | no | CI metadata (see below). |
| `summary` | string | yes | Short human-readable summary. |
| `error_message` | string | no | Primary error line. |
| `logs` | string | no | Truncated log excerpt (UTF-8). |
| `artifacts` | object | no | URLs or pointers to logs (CI). |
| `context` | object | no | Free-form key/value for your stack. |

**`pipeline` (optional)**

| Field | Type | Description |
|-------|------|-------------|
| `provider` | string | e.g. `github`, `gitlab`. |
| `repo` | string | Repository identifier. |
| `run_id` | string | CI run id. |
| `commit` | string | Git SHA. |
| `workflow` | string | Workflow or job name. |

**Example (copy-paste):**

```json
{
  "schema_version": "1.0",
  "incident_id": "550e8400-e29b-41d4-a716-446655440000",
  "source": "ci",
  "severity": "critical",
  "occurred_at": "2026-05-07T12:34:56.000Z",
  "environment": "prism",
  "namespace": "prism",
  "service": "api",
  "deployment": "api",
  "pipeline": {
    "provider": "github",
    "repo": "org/prism",
    "run_id": "123456789",
    "commit": "a1b2c3d4",
    "workflow": "build-and-deploy"
  },
  "summary": "Maven dependency conflict: com.example:lib-a:2.0 vs lib-b:1.x",
  "error_message": "Could not resolve dependencies for project prism-api",
  "logs": "[ERROR] Failed to execute goal ... dependency convergence ...",
  "artifacts": {
    "build_log_url": "https://ci.example.com/run/123456789/log"
  },
  "context": {
    "branch": "main",
    "trigger": "push"
  }
}
```

---

## 4. Outbound: n8n → OpenClaw (diagnosis / remediation proposal)

**Purpose:** Send enriched failure context; receive structured diagnosis and proposed actions.

**Method:** `POST`  
**Path (PROVISIONAL — Person C MUST confirm):** `/v1/incidents/analyze`  
If your OpenClaw build uses another path, update this doc and n8n HTTP nodes together.

### 4.1 Request body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | string | yes | e.g. `"1.0"`. |
| `incident_id` | string | yes | Same as webhook. |
| `incident` | object | yes | The normalized payload (or subset) from §3. |
| `enrichment` | object | no | Extra fetches done in n8n (metrics, extra logs). |
| `requested_actions` | string[] | no | e.g. `["diagnose","propose_remediation"]` |

**Example (copy-paste):**

```json
{
  "schema_version": "1.0",
  "incident_id": "550e8400-e29b-41d4-a716-446655440000",
  "incident": {
    "schema_version": "1.0",
    "incident_id": "550e8400-e29b-41d4-a716-446655440000",
    "source": "k8s",
    "severity": "warning",
    "occurred_at": "2026-05-07T12:40:00.000Z",
    "environment": "prism",
    "namespace": "prism",
    "deployment": "n8n",
    "summary": "Rollout failed: ImagePullBackOff",
    "error_message": "Back-off pulling image \"wrong:tag\"",
    "logs": "Events: Failed to pull image ..."
  },
  "enrichment": {
    "fetched_at": "2026-05-07T12:41:00.000Z",
    "pod_events": "optional excerpt"
  },
  "requested_actions": ["diagnose", "propose_remediation"]
}
```

### 4.2 Response body (success, HTTP 200)

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | Response contract version. |
| `incident_id` | string | Echo. |
| `diagnosis` | string | Human-readable root-cause narrative. |
| `confidence` | number | 0–1 if available. |
| `remediation` | object | Machine-usable next steps (see below). |
| `policy_flags` | object | Optional hints from middleware (see below). |
| `raw_model_output` | string | no | Optional, for audit; may be omitted in prod. |

**`remediation`**

| Field | Type | Description |
|-------|------|-------------|
| `action` | string | Align with `infra/scripts/remediate.sh`: `PATCH` \| `REDEPLOY` \| `SCALE` \| `HELM_UPGRADE` \| `NONE` \| `HUMAN_REQUIRED`. |
| `target` | string | Deployment name or Helm release name (per script semantics). |
| `namespace` | string | K8s namespace. |
| `payload` | string | For `PATCH`: JSON patch string; for `SCALE`: replica count; for `HELM_UPGRADE`: `--set` style fragment per script. |
| `proposed_files` | object | Optional map `filename → content` (YAML/Dockerfile) for UI / GitOps. |

**`policy_flags` (optional)**

| Field | Type | Description |
|-------|------|-------------|
| `requires_approval` | boolean | If true, n8n should not auto-apply. |
| `block_reason` | string | Why auto-apply is blocked. |

**Example (copy-paste):**

```json
{
  "schema_version": "1.0",
  "incident_id": "550e8400-e29b-41d4-a716-446655440000",
  "diagnosis": "Deployment references an image tag that does not exist in the registry. Correct the image in the Deployment or fix the registry credentials.",
  "confidence": 0.82,
  "remediation": {
    "action": "PATCH",
    "target": "n8n",
    "namespace": "prism",
    "payload": "[{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/image\",\"value\":\"n8nio/n8n:1.0.0\"}]",
    "proposed_files": {
      "deployment.patch.json": "[{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/image\",\"value\":\"n8nio/n8n:1.0.0\"}]"
    }
  },
  "policy_flags": {
    "requires_approval": true,
    "block_reason": "Image change in production namespace"
  }
}
```

### 4.3 Errors

| HTTP | Meaning |
|------|---------|
| 400 | Invalid body / unknown `schema_version`. |
| 401 / 403 | Auth failure. |
| 429 | Rate limit — n8n should retry with backoff. |
| 502 / 503 | Upstream model/gateway — retry with backoff. |

Error body (proposed): `{ "error": string, "code"?: string, "incident_id"?: string }`.

---

## 5. Inbound: approval callback → n8n (Frontend → Backend)

**Purpose:** Person A’s UI approves or rejects a pending remediation.

**Method:** `POST`  
**Path:** TBD (e.g. `/webhook/prism/approval`).

### Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | string | yes | e.g. `"1.0"`. |
| `incident_id` | string | yes | Matches stored incident. |
| `decision` | string | yes | `"approve"` \| `"reject"`. |
| `actor` | string | no | User id or email. |
| `comment` | string | no | Reason. |

**Example (copy-paste):**

```json
{
  "schema_version": "1.0",
  "incident_id": "550e8400-e29b-41d4-a716-446655440000",
  "decision": "approve",
  "actor": "reviewer@example.com",
  "comment": "Verified tag exists in registry; proceed with patch."
}
```

---

## 6. Sign-off checklist

- [ ] Person C: OpenClaw **path**, **auth header**, and any **required** extra fields.
- [ ] Person D: Confirmed **namespace**, **deployment names**, and how n8n **invokes** `remediate.sh` (or equivalent).
- [ ] Person A: Approval webhook path and **CORS** if browser calls it (prefer backend proxy).
- [ ] Person B: Workflow JSON exported to `workflows/`; **MVP** audit trail = n8n **Executions** (custom DB / `migrations/` optional later).

---

## 7. Changelog

| Version | Date | Notes |
|---------|------|--------|
| 1.0 | 2026-05-07 | Initial draft for Task 1. |
| 1.1 | 2026-05-07 | MVP: execution view; contracts live at `backend/CONTRACTS.md`. |
