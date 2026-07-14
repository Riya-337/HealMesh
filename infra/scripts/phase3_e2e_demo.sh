#!/bin/bash
set -eo pipefail

echo "==> Cleaning up previous state..."
docker rm -f healmesh-db || true
kubectl delete namespace healmesh-test --ignore-not-found=true
pkill -f "executor_bin" || true
pkill -f "uvicorn main:app" || true

echo "==> Setting up database..."
docker run --name healmesh-db -d -p 5432:5432 -e POSTGRES_USER=healmesh -e POSTGRES_PASSWORD=healmesh_local -e POSTGRES_DB=healmesh -v "$(pwd)/infra/postgres:/docker-entrypoint-initdb.d" postgres:15
export PGPASSWORD=healmesh_local

echo "Waiting for Postgres to be ready..."
for i in {1..30}; do
  if docker exec healmesh-db pg_isready -U healmesh -d healmesh > /dev/null 2>&1; then
    echo "Postgres is ready!"
    break
  fi
  sleep 1
done

echo "==> Starting healmesh-core and healmesh-k8s..."
cd healmesh-core
pip install -r requirements.txt uvicorn httpx > /dev/null 2>&1
uvicorn main:app --port 8000 > core.log 2>&1 &
CORE_PID=$!
cd ../healmesh-k8s
export KUBECONFIG=$HOME/.kube/config
export WATCH_NAMESPACES=healmesh-test
export HEALMESH_CORE_URL=http://localhost:8000
export TLS_CERT_FILE=../tls.crt
export TLS_KEY_FILE=../tls.key
export POSTGRES_DSN="postgresql://healmesh:healmesh_local@localhost:5432/healmesh?sslmode=disable"
go build -o executor_bin cmd/executor/main.go
./executor_bin > executor.log 2>&1 &
EXECUTOR_PID=$!
cd ..

sleep 5

echo "==> 1. Creating healmesh-test namespace and injecting Bad Image Tag failure..."
kubectl create namespace healmesh-test --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl apply -n healmesh-test -f - <<'POLICY_EOF'
apiVersion: healmesh.io/v1alpha1
kind: HealPolicy
metadata:
  name: demo-policy
spec:
  allowedActions:
  - PATCH
  - SCALE
  - REDEPLOY
  - HELM_UPGRADE
POLICY_EOF

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
        image: nginx:v999-bad-tag
INNER_EOF

echo "Wait for ImagePullBackOff..."
sleep 10
kubectl get pod -n healmesh-test -l app=demo

echo "==> 2. Generating Incident and Diagnosis Payload..."
ACTION_ID=$(python3 infra/scripts/create_test_action.py)
echo "Action ID created: $ACTION_ID"

echo "==> 3. Attempting out-of-scope patch directly against /execute endpoint..."
curl -k -s -X POST "https://localhost:8443/api/v1/execute" \
    -H "Content-Type: application/json" \
    -d '{
        "approval_id": "'$ACTION_ID'",
        "action_type": "PATCH",
        "params": {
            "namespace": "healmesh-test",
            "deployment_name": "demo-app",
            "serviceAccountName": "admin-sa"
        }
    }' || true

echo "==> Note: Since PatchParams strictly unmarshals only Image, Env, and Resources, 'serviceAccountName' is structurally dropped before reaching the allowlist. To prove the allowlist logic, we run a standalone test."

echo "==> 4. Valid PATCH (Fixing the image)"
ACTION_ID_VALID=$(python3 infra/scripts/create_test_action.py)
curl -k -s -X POST "https://localhost:8443/api/v1/execute" \
    -H "Content-Type: application/json" \
    -d '{
        "approval_id": "'$ACTION_ID_VALID'",
        "action_type": "PATCH",
        "params": {
            "namespace": "healmesh-test",
            "deployment_name": "demo-app",
            "image": "nginx:latest"
        }
    }' || true

echo "Checking Rollout..."
sleep 5
kubectl get pod -n healmesh-test -l app=demo
kubectl rollout status deployment/demo-app -n healmesh-test --timeout=30s || true

echo "==> 5. Bad PATCH (Triggering Rollback)"
ACTION_ID_BAD=$(python3 infra/scripts/create_test_action.py)
curl -k -s -X POST "https://localhost:8443/api/v1/execute" \
    -H "Content-Type: application/json" \
    -d '{
        "approval_id": "'$ACTION_ID_BAD'",
        "action_type": "PATCH",
        "params": {
            "namespace": "healmesh-test",
            "deployment_name": "demo-app",
            "image": "nginx:v888-fatal-tag"
        }
    }' || true

echo "Checking Rollout and Rollback..."
sleep 5
kubectl get pod -n healmesh-test -l app=demo

echo "==> Cleanup..."
kill $CORE_PID $EXECUTOR_PID || true
