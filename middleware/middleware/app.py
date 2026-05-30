from fastapi import FastAPI, Header, HTTPException, Body
from pydantic import BaseModel
import yaml
import os
import json
from groq import Groq
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi.middleware.cors import CORSMiddleware
import subprocess

app = FastAPI(title="PRISM OpenClaw Middleware")

# Add CORS support for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for incidents (Mocking a DB for the hackathon)
INCIDENTS = [
    {
        "id": "ERR-992",
        "service": "payment-gateway",
        "cluster": "prod-eu-west",
        "severity": "critical",
        "status": "pending",
        "agent": "k8s-healer-v3",
        "diagnosis": "Helm chart value 'replicaCount' exceeded available cluster quota.",
        "rootCause": "Quota exceeded · ResourceQuota/compute-prod",
        "confidence": 0.94,
        "oldYaml": "replicas: 10",
        "newYaml": "replicas: 3",
        "environment": "production"
    },
    {
        "id": "ERR-991",
        "service": "ml-inference",
        "cluster": "prod-us-east",
        "severity": "warning",
        "status": "pending",
        "agent": "cicd-doctor-v2",
        "diagnosis": "Detected version mismatch in requirements.txt.",
        "rootCause": "Dependency conflict · pandas 2.x vs torch 2.1.0",
        "confidence": 0.88,
        "oldYaml": "pandas==2.2.1",
        "newYaml": "pandas==1.5.3",
        "environment": "staging"
    }
]

# Initialize Groq Client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama3-70b-8192"

# Load Agents and Policies
def load_config(path):
    with open(path, 'r') as f:
        return yaml.safe_load(f)

DIAGNOSIS_AGENT = load_config('agents/diagnosis.yaml')
REMEDIATION_AGENT = load_config('agents/remediation.yaml')
POLICIES = load_config('policies.yaml')

@app.get("/v1/health")
async def health():
    return {"status": "ok", "agents": ["diagnosis", "remediation"]}

@app.get("/v1/incidents")
async def list_incidents():
    return INCIDENTS

@app.post("/v1/incidents/{incident_id}/approve")
async def approve_incident(incident_id: str):
    for incident in INCIDENTS:
        if incident["id"] == incident_id:
            incident["status"] = "resolved"
            # In a real scenario, we would trigger remediate.sh here
            # subprocess.run(["bash", "../infra/scripts/remediate.sh", "PATCH", incident['service'], "prism", incident['newYaml']])
            return {"status": "success", "message": f"Incident {incident_id} approved and remediated."}
    raise HTTPException(status_code=404, detail="Incident not found")

@app.post("/v1/incidents/{incident_id}/reject")
async def reject_incident(incident_id: str):
    for incident in INCIDENTS:
        if incident["id"] == incident_id:
            incident["status"] = "rejected"
            return {"status": "success", "message": f"Incident {incident_id} rejected."}
    raise HTTPException(status_code=404, detail="Incident not found")

@app.post("/v1/incidents/analyze")
async def analyze_incident(payload: dict = Body(...), authorization: str = Header(None)):
    # 1. Simple Auth Mock (Replace with actual validation)
    token = os.getenv("OPENCLAW_AUTH_TOKEN", "prism-secret")
    if authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="Invalid or missing auth token")

    incident = payload.get("incident", {})
    incident_id = payload.get("incident_id")

    # 2. Execute Diagnosis Agent
    diagnosis_prompt = f"{DIAGNOSIS_AGENT['system_prompt']}\n\nIncident Payload: {json.dumps(incident)}"
    diagnosis_response = client.chat.completions.create(
        messages=[{"role": "user", "content": diagnosis_prompt}],
        model=MODEL,
    )
    diagnosis_text = diagnosis_response.choices[0].message.content

    # 3. Policy Engine Logic
    requires_approval = False
    block_reason = ""
    
    # Check Prod Gate
    if incident.get('environment') == 'production' or incident.get('namespace') == 'production':
        requires_approval = True
        block_reason = "Policy: Manual approval required for production namespace."
    
    # Check Severity Gate
    if incident.get('severity') == 'critical':
        requires_approval = True
        block_reason = "Policy: Critical incidents require human sign-off."

    # 4. Execute Remediation Agent
    remediation_prompt = f"{REMEDIATION_AGENT['system_prompt']}\n\nDiagnosis: {diagnosis_text}\n\nIncident: {json.dumps(incident)}"
    remediation_response = client.chat.completions.create(
        messages=[{"role": "user", "content": remediation_prompt}],
        model=MODEL,
        response_format={"type": "json_object"}
    )
    try:
        remediation = json.loads(remediation_response.choices[0].message.content)
    except:
        remediation = {
            "action": "HUMAN_REQUIRED",
            "target": incident.get("deployment", "unknown"),
            "namespace": incident.get("namespace", "prism"),
            "payload": "Error parsing AI response"
        }

    # Override action if high risk
    if requires_approval:
        remediation["action"] = "HUMAN_REQUIRED"

    return {
        "schema_version": "1.0",
        "incident_id": incident_id,
        "diagnosis": diagnosis_text,
        "confidence": 0.85,
        "remediation": remediation,
        "policy_flags": {
            "requires_approval": requires_approval,
            "block_reason": block_reason
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8082)
