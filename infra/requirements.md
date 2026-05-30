# PRISM Infrastructure Requirements

## 💻 Local Developer Environment

### Core Tools
- **Docker Desktop**: Version 4.10+ (with Kubernetes enabled).
- **kubectl**: Version 1.24+ (command-line tool for K8s).
- **Helm**: Version 3.9+ (K8s package manager).
- **Git Bash / WSL**: For running `.sh` automation scripts.

### Hardware (Minimum)
- **CPU**: 4 Cores.
- **RAM**: 16GB total (allocate at least 6GB to Docker/Kubernetes).
- **Storage**: 20GB of free disk space for Persistent Volumes.

---

## ☁️ Kubernetes Cluster Configuration

The infrastructure is designed to run in a namespace named `prism`.

### Required Resources
- **Namespace**: `prism`
- **StorageClass**: Standard (provisioning `ReadWriteOnce` volumes).
- **NetworkPolicies**: Must support the `networking.k8s.io/v1` API.

---

## 🔑 External API Requirements

The following secrets must be populated in `infra/k8s/secrets.yaml` for full functionality:

| Secret Name | Purpose |
| :--- | :--- |
| `GEMINI_API_KEY` | Primary LLM for AI Diagnosis. |
| `OPENAI_API_KEY` | Secondary/Backup LLM. |
| `N8N_ENCRYPTION_KEY` | Securely stores n8n credentials. |
| `OPENCLAW_AUTH_TOKEN`| Secures the OpenClaw API gateway. |

---

## 📦 Container Images
The system currently uses these base images 
- `n8nio/n8n:latest`
- `ghcr.io/openclaw/openclaw:latest`
- `postgres:14-alpine`
- `redis:latest`
