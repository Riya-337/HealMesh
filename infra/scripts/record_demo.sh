#!/usr/bin/env bash
# HealMesh — Phase 1.5 End-to-End Demo Script
#
# Usage:
#   1. Start screen recording.
#   2. Run this script: ./infra/scripts/record_demo.sh
#   3. Show Slack side-by-side with the terminal to capture the notification.
#
# Requirements:
#   - .env configured with GEMINI_API_KEY and SLACK_BOT_TOKEN
#   - kind cluster running (healmesh-test)
#   - healmesh-core running

set -euo pipefail

echo "=== HealMesh End-to-End Demo ==="
echo ""
echo "1. Checking prerequisites..."
if [[ -z "${SLACK_BOT_TOKEN:-}" ]]; then
    echo "❌ SLACK_BOT_TOKEN not set. Export it or source .env before recording."
    exit 1
fi
if [[ -z "${GEMINI_API_KEY:-}" ]]; then
    echo "❌ GEMINI_API_KEY not set. Export it or source .env before recording."
    exit 1
fi

echo "✅ Prerequisites met."
echo ""
echo "2. Injecting a CrashLoopBackOff failure..."
kubectl create namespace healmesh-demo --dry-run=client -o yaml | kubectl apply -f - >/dev/null

kubectl apply -n healmesh-demo -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: demo-crashloop
spec:
  restartPolicy: Always
  containers:
  - name: crasher
    image: busybox:latest
    command: ["/bin/sh", "-c", "echo 'FATAL: database connection refused on port 5432'; exit 1"]
EOF

echo "✅ Pod deployed. Waiting for CrashLoopBackOff..."
sleep 15
kubectl get pod demo-crashloop -n healmesh-demo

echo ""
echo "3. Simulating Watcher Payload Transmission..."
curl -s -X POST "http://localhost:8000/incident" \
    -H "Content-Type: application/json" \
    -d '{
        "pod_name": "demo-crashloop",
        "namespace": "healmesh-demo",
        "failure_type": "CrashLoopBackOff",
        "detected_at": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
        "log_lines": ["FATAL: database connection refused on port 5432", "exit status 1"],
        "container_statuses": [{"name": "crasher", "image": "busybox:latest", "restart_count": 3}]
    }' > /dev/null

echo "✅ Payload sent to healmesh-core."
echo ""
echo "4. Check your Slack channel now!"
echo "The diagnosis should arrive in < 30 seconds."
echo ""
echo "Cleaning up..."
kubectl delete namespace healmesh-demo --ignore-not-found=true >/dev/null
echo "Demo complete."
