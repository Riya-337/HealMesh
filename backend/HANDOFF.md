# PRISM backend handoff (Person B → C & D)

## Person C (OpenClaw / middleware)

**Please read and confirm or revise:**

- [`CONTRACTS.md`](./CONTRACTS.md) — **§2 Auth**, **§4.1 request**, **§4.2 response**, **§4.3 errors**, plus the JSON examples in §4.
- n8n workflow: [`workflows/prism-incident.json`](./workflows/prism-incident.json)  
  - Node **`OpenClawAnalyze`** is a **disabled** HTTP Request placeholder:  
    `POST http://openclaw/v1/incidents/analyze` with `Authorization: Bearer {{ $env.OPENCLAW_AUTH_TOKEN }}`  
  - When your API is ready: confirm **URL**, **header scheme**, and **request/response JSON**. We will **enable** the node and adjust **`MapOpenClawOrStub`** only if your response shape differs from §4.2 (we detect `diagnosis` + `incident_id`).

**Reply with:** final path(s), auth header example, one sample **200** response JSON, and error JSON if non-standard.

---

## Person D (infra / remediation)

**Please confirm:**

- How n8n (pod `prism-remediator`) should invoke [`infra/scripts/remediate.sh`](../infra/scripts/remediate.sh) or equivalent when `openclaw.remediation.action` is `PATCH` / `REDEPLOY` / `SCALE` / `HELM_UPGRADE` (Job, sidecar script path, etc.).
- Production **n8n base URL** for webhooks (LoadBalancer / Ingress) so CI or demos can `POST` incidents.

---

## Prove the workflow (anyone with n8n)

1. n8n → **Workflows** → **⋯** → **Import from File** → `backend/workflows/prism-incident.json`.
2. **Save** → toggle **Active**.
3. Open **`IncidentWebhook`** → copy **Production** URL (contains `/webhook/.../prism/incident`).
4. POST the sample body below (`Content-Type: application/json`).
5. Expect **HTTP 200** and JSON with `ok`, `incident`, `openclaw`, `_source: "stub"` (OpenClaw node stays disabled).
6. n8n → **Executions** → open latest run → check outputs.

### Sample `curl` (replace URL)

```bash
curl -sS -X POST "https://YOUR-N8N-HOST/webhook/XXXX/prism/incident" ^
  -H "Content-Type: application/json" ^
  -d "{\"schema_version\":\"1.0\",\"incident_id\":\"550e8400-e29b-41d4-a716-446655440000\",\"source\":\"ci\",\"occurred_at\":\"2026-05-07T12:34:56.000Z\",\"environment\":\"prism\",\"namespace\":\"prism\",\"summary\":\"Test incident from HANDOFF.md\"}"
```

(PowerShell: use ``curl.exe`` or `Invoke-RestMethod` — see below.)

### PowerShell one-liner

```powershell
$body = @{
  schema_version = "1.0"
  incident_id    = "550e8400-e29b-41d4-a716-446655440000"
  source           = "ci"
  occurred_at      = "2026-05-07T12:34:56.000Z"
  environment      = "prism"
  namespace        = "prism"
  summary          = "Test incident from HANDOFF.md"
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://YOUR-N8N-HOST/webhook/XXXX/prism/incident" -Method Post -Body $body -ContentType "application/json"
```
