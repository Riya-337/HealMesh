# 🚀 OpenClaw Middleware Setup Guide

This guide explains how to set up, configure, and run the PRISM OpenClaw Middleware service and its AI agents.

## 📁 Directory Structure
- `middleware/app.py`: The FastAPI application orchestrating agents and policies.
- `middleware/agents/`: YAML files defining the AI personas and system prompts.
- `middleware/policies.yaml`: Safety gates and enforcement rules.
- `middleware/Dockerfile`: Container configuration.

---

## 🛠️ 1. Configure AI Agents
The agents are defined in the `agents/` folder. You can tune their behavior by modifying the `system_prompt` in these files:

1.  **Diagnosis Agent** (`agents/diagnosis.yaml`):
    - **Role**: SRE expert focused on identifying root causes.
    - **Edit this to**: Change how it analyzes logs or which specific failures (e.g., specific Maven errors) it should prioritize.
2.  **Remediation Agent** (`agents/remediation.yaml`):
    - **Role**: K8s remediation expert.
    - **Edit this to**: Adjust the safety thresholds for auto-remediation or update the `kubectl` command formats.

---

## ⚙️ 2. Environment Variables
Before running the service, set the following environment variables:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `OPENCLAW_AUTH_TOKEN` | Bearer token for n8n -> Middleware auth | `prism-secret` |
| `GROQ_API_KEY` | Your Groq API Key (Llama3-70b) | (Required for AI calls) |

---

## 🏃 3. Running the Middleware

### Option A: Using Docker Compose (Recommended)
This is the easiest way to run the service in a containerized environment.

```bash
cd middleware
docker-compose up --build -d
```

### Option B: Running Locally (Manual)
Use this for rapid development and testing.

```bash
cd middleware
pip install -r requirements.txt
python app.py
```
The service will be available at `http://localhost:8080`.

---

## 🔗 4. Integration with n8n

1. **Import Workflow**: Import `backend/workflows/prism-incident-v2.json` into n8n.
2. **Update URLs**: Ensure the `OpenClawAnalyze` node points to `http://openclaw:8080/v1/incidents/analyze` (if in Docker) or your local URL.
3. **Set Auth**: Ensure the `OPENCLAW_AUTH_TOKEN` in n8n matches the one in your middleware environment.

---

## ✅ 5. Verifying the Setup
Run a health check to ensure the agents are loaded correctly:

```bash
curl http://localhost:8080/v1/health
```
**Expected Response:**
```json
{
  "status": "ok", 
  "agents": ["diagnosis", "remediation"]
}
```

---

## 🛡️ 6. Modifying Policies
You can add or remove safety gates in `policies.yaml`. For example, to require approval for all `staging` environment deployments, add:

```yaml
- id: staging-gate
  name: "Staging Guard"
  condition: "incident.environment == 'staging'"
  action: "SET_APPROVAL_REQUIRED"
```
