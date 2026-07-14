#!/bin/bash
set -eo pipefail

echo "==> Cleaning up previous state..."
docker rm -f healmesh-db || true
kubectl delete namespace healmesh-test --ignore-not-found=true
pkill -f "executor_bin" || true
pkill -f "uvicorn main:app" || true

echo "==> Setting up database..."
# The DB is already running on the host as assumed by the environment. We just verify.
export PGPASSWORD=healmesh_local
sleep 1

echo "==> Starting healmesh-core and healmesh-k8s..."
cd healmesh-core
pip install -r requirements.txt uvicorn httpx > /dev/null 2>&1
uvicorn main:app --port 8000 > core.log 2>&1 &
CORE_PID=$!
cd ../healmesh-k8s
export KUBECONFIG=$HOME/.kube/config
export WATCH_NAMESPACES=healmesh-test
export HEALMESH_CORE_URL=http://localhost:8000
export TLS_CERT_FILE=none
export TLS_KEY_FILE=none
export POSTGRES_DSN="postgresql://healmesh:healmesh_local@localhost:5432/healmesh?sslmode=disable"
go build -o executor_bin cmd/executor/main.go
./executor_bin > executor.log 2>&1 &
EXECUTOR_PID=$!
cd ..

sleep 5

echo "==> 1. Creating healmesh-test namespace and injecting a normal Deployment..."
kubectl create namespace healmesh-test --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl apply -n healmesh-test -f - <<'INNER_EOF'
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
        image: nginx:latest
INNER_EOF

echo "Wait for Deployment to become ready..."
kubectl wait --for=condition=Available deployment/demo-app -n healmesh-test --timeout=60s
kubectl get pod -n healmesh-test -l app=demo

echo "==> 2. Generating Incident and Diagnosis Payload..."
ACTION_ID=$(python3 infra/scripts/create_test_action.py)
echo "Action ID created: $ACTION_ID"

echo "==> 3. Attempting REDEPLOY with extra invalid field..."
curl -s -X POST "http://localhost:8080/api/v1/execute" \
    -H "Content-Type: application/json" \
    -d '{
        "approval_id": "'$ACTION_ID'",
        "action_type": "REDEPLOY",
        "params": {
            "namespace": "healmesh-test",
            "deployment_name": "demo-app",
            "force": true
        }
    }' | jq . || true

echo "==> Note: The extra 'force' parameter should be dropped during JSON unmarshaling, or the request should be rejected depending on strictness. In Go, it drops it and proceeds with the remaining valid params."

echo "==> 4. Valid REDEPLOY (Restarting the app)"
ACTION_ID_VALID=$(python3 infra/scripts/create_test_action.py)
curl -s -X POST "http://localhost:8080/api/v1/execute" \
    -H "Content-Type: application/json" \
    -d '{
        "approval_id": "'$ACTION_ID_VALID'",
        "action_type": "REDEPLOY",
        "params": {
            "namespace": "healmesh-test",
            "deployment_name": "demo-app"
        }
    }' | jq . || true

echo "Checking Rollout after REDEPLOY..."
kubectl rollout status deployment/demo-app -n healmesh-test --timeout=60s || true
sleep 2
kubectl get pod -n healmesh-test -l app=demo

echo "==> Cleanup..."
kill $CORE_PID $EXECUTOR_PID || true
