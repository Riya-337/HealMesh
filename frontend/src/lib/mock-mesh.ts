export type IncidentSeverity = "critical" | "warning" | "info";
export type IncidentStatus = "pending" | "deploying" | "resolved" | "rejected";

export interface Incident {
  id: string;
  service: string;
  cluster: string;
  severity: IncidentSeverity;
  status: IncidentStatus;
  createdAt: string;
  agent: string;
  diagnosis: string;
  rootCause: string;
  oldYaml: string;
  newYaml: string;
  confidence: number;
}

export const initialIncidents: Incident[] = [
  {
    id: "ERR-992",
    service: "payment-gateway",
    cluster: "prod-eu-west",
    severity: "critical",
    status: "pending",
    createdAt: new Date(Date.now() - 1000 * 42).toISOString(),
    agent: "k8s-healer-v3",
    diagnosis:
      "Helm chart value 'replicaCount' exceeded available cluster quota. Proposed fix scales replicas to match current node capacity.",
    rootCause: "Quota exceeded · ResourceQuota/compute-prod",
    confidence: 0.94,
    oldYaml:
      "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: payment-gateway\nspec:\n  replicas: 10\n  template:\n    spec:\n      containers:\n        - image: payments:v2.4.1\n          resources:\n            requests:\n              cpu: \"2\"\n              memory: 4Gi",
    newYaml:
      "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: payment-gateway\nspec:\n  replicas: 3\n  template:\n    spec:\n      containers:\n        - image: payments:v2.4.1\n          resources:\n            requests:\n              cpu: \"1\"\n              memory: 2Gi",
  },
  {
    id: "ERR-991",
    service: "ml-inference",
    cluster: "prod-us-east",
    severity: "warning",
    status: "pending",
    createdAt: new Date(Date.now() - 1000 * 180).toISOString(),
    agent: "cicd-doctor-v2",
    diagnosis:
      "Detected version mismatch in requirements.txt. Proposing downgrade of pandas to 1.5.3 to satisfy torch==2.1.0 dependency.",
    rootCause: "Dependency conflict · pandas 2.x vs torch 2.1.0",
    confidence: 0.88,
    oldYaml:
      "# requirements.txt\nfastapi==0.110.0\ntorch==2.1.0\npandas==2.2.1\nnumpy==1.26.0",
    newYaml:
      "# requirements.txt\nfastapi==0.110.0\ntorch==2.1.0\npandas==1.5.3\nnumpy==1.24.4",
  },
];

export const auditEntries = [
  { id: "ERR-988", service: "auth-svc", action: "Patched Dockerfile base image", agent: "cicd-doctor-v2", duration: "12s", status: "resolved" },
  { id: "ERR-987", service: "billing-api", action: "Rewrote ingress.yaml host rule", agent: "k8s-healer-v3", duration: "9s", status: "resolved" },
  { id: "ERR-986", service: "search-indexer", action: "Scaled HPA min replicas", agent: "k8s-healer-v3", duration: "6s", status: "resolved" },
  { id: "ERR-985", service: "notifier", action: "Reverted faulty Helm release", agent: "rollback-agent", duration: "21s", status: "resolved" },
  { id: "ERR-984", service: "ml-inference", action: "Pinned CUDA driver version", agent: "cicd-doctor-v2", duration: "44s", status: "rejected" },
  { id: "ERR-983", service: "data-stream", action: "Rebuilt schema migration", agent: "data-steward", duration: "18s", status: "resolved" },
];

export const agentChatter = [
  { agent: "k8s-healer-v3", channel: "#ops-mesh", message: "Drift detected in prod-eu-west. Rebalancing replicas.", time: "08:21:04" },
  { agent: "cicd-doctor-v2", channel: "#ci-cd", message: "Resolved dependency conflict in build #4421.", time: "08:19:51" },
  { agent: "openclaw-router", channel: "#agent-bus", message: "Routing failure ERR-992 → k8s-healer-v3 (confidence 0.94).", time: "08:18:42" },
  { agent: "data-steward", channel: "#data-pipes", message: "Schema drift on events.v3 — auto-generated ETL patch.", time: "08:14:11" },
  { agent: "rollback-agent", channel: "#ops-mesh", message: "Stable revision restored on notifier-svc.", time: "08:09:02" },
];
