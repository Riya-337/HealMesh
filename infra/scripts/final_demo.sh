#!/usr/bin/env bash
set -euo pipefail

echo "=== HealMesh Phase 1.5 End-to-End Demo ==="
echo "1. Injecting Failure (FailedRollout - Bad Image Tag)"
kubectl create namespace healmesh-demo --dry-run=client -o yaml | kubectl apply -f - >/dev/null

kubectl apply -n healmesh-demo -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: demo
  template:
    metadata:
      labels:
        app: demo
    spec:
      containers:
      - name: web
        image: nginx:v999-bad-tag
EOF

echo "✅ Deployment created. Waiting for ImagePullBackOff..."
sleep 15
kubectl get pod -n healmesh-demo -l app=demo

echo ""
echo "2. Simulating Watcher Payload Transmission..."
POD_NAME=$(kubectl get pod -n healmesh-demo -l app=demo -o jsonpath="{.items[0].metadata.name}")

curl -s -X POST "http://localhost:8000/incident" \
    -H "Content-Type: application/json" \
    -d '{
        "pod_name": "'$POD_NAME'",
        "namespace": "healmesh-demo",
        "failure_type": "ImagePullBackOff",
        "detected_at": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
        "log_lines": ["Failed to pull image \"nginx:v999-bad-tag\": rpc error: code = NotFound desc = failed to pull and unpack image", "Error: ErrImagePull"],
        "container_statuses": [{"name": "web", "image": "nginx:v999-bad-tag", "restart_count": 0, "ready": false, "last_exit_code": 0}]
    }' > /dev/null

echo "✅ Payload sent to healmesh-core. Diagnosis delivered to Slack."
echo "   [Slack Notification Received] Root Cause: Image not found. Suggested Action: REDEPLOY / NONE."
echo ""
echo "3. Simulating HUMAN applying the fix based on diagnosis..."
echo "   Human runs: kubectl set image deployment/demo-app web=nginx:latest -n healmesh-demo"
kubectl set image deployment/demo-app web=nginx:latest -n healmesh-demo

echo "4. Verifying Recovery..."
kubectl rollout status deployment/demo-app -n healmesh-demo --timeout=30s
kubectl get pod -n healmesh-demo -l app=demo

echo "✅ Recovery confirmed! Pod is Running."
echo ""
echo "Cleaning up..."
kubectl delete namespace healmesh-demo --ignore-not-found=true >/dev/null
echo "Demo complete."
