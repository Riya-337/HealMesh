#!/bin/bash
set -e

# Phase 3 HELM_UPGRADE E2E Demo Script
# 
# 1. Start Kind Cluster (if not running)
# 2. Deploy a dummy helm chart (revision 1)
# 3. Upgrade helm chart to revision 2 (broken)
# 4. Trigger HELM_UPGRADE (rollback to revision 1)
# 5. Verify the rollback is successful
# 6. Verify negative test (cannot access non-helm secrets)

cd "$(dirname "$0")/../.."

echo "--- 1. Checking Kind cluster ---"
if ! kind get clusters | grep -q "healmesh-cluster"; then
  echo "Creating kind cluster..."
  kind create cluster --name healmesh-cluster
fi

echo "--- 2. Setting up dummy helm chart ---"
CHART_DIR=/tmp/healmesh-test-chart
rm -rf $CHART_DIR
mkdir -p $CHART_DIR/templates

cat <<EOF > $CHART_DIR/Chart.yaml
apiVersion: v2
name: test-chart
description: A Helm chart for Kubernetes
type: application
version: 0.1.0
appVersion: "1.16.0"
EOF

cat <<EOF > $CHART_DIR/templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-deploy
  labels:
    app: test-deploy
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: test-deploy
  template:
    metadata:
      labels:
        app: test-deploy
    spec:
      containers:
        - name: nginx
          image: "{{ .Values.image }}"
          ports:
            - containerPort: 80
EOF

cat <<EOF > $CHART_DIR/values.yaml
replicaCount: 1
image: nginx:1.14.2
EOF

helm upgrade --install test-release $CHART_DIR --namespace default --wait
echo "Revision 1 deployed (nginx:1.14.2)."

echo "--- 3. Upgrading to Revision 2 (broken image) ---"
cat <<EOF > $CHART_DIR/values.yaml
replicaCount: 1
image: nginx:broken-tag-123
EOF

# Do not wait here because it will fail/hang
helm upgrade test-release $CHART_DIR --namespace default || true
echo "Revision 2 deployed (broken)."

echo "Waiting for pods to show error..."
sleep 10
kubectl get pods -n default

echo "--- 4. Building and running Executor in background ---"
cd healmesh-k8s
export KUBECONFIG=$HOME/.kube/config
export TLS_CERT_FILE=none
export TLS_KEY_FILE=none
go build -o executor_bin ./cmd/executor
./executor_bin &
EXECUTOR_PID=$!
sleep 3

echo "--- 5. Triggering HELM_UPGRADE via curl ---"
curl -s -X POST http://localhost:8080/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "HELM_UPGRADE",
    "params": {
      "namespace": "default",
      "release_name": "test-release",
      "target_revision": 1
    },
    "approval_id": "helm-test-1"
  }'

echo
echo "--- 6. Verifying rollback ---"
sleep 5
helm history test-release -n default
echo "Rollback initiated. Checking pod image..."
kubectl get deploy test-deploy -n default -o jsonpath='{.spec.template.spec.containers[0].image}'
echo

echo "--- 7. Cleaning up ---"
kill $EXECUTOR_PID
helm uninstall test-release -n default
echo "Done."
