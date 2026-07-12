#!/bin/bash
set -eo pipefail

echo "==> Cleaning up previous test state..."
docker rm -f healmesh-db || true
kubectl delete namespace healmesh-test --ignore-not-found=true
pkill -f "watcher_bin" || true
pkill -f "uvicorn main:app" || true

echo "==> Loading environment..."
set -a
source .env
set +a

echo "==> Setting up database..."
docker run --rm -v "$(pwd):/workspace" postgres:15 psql -h host.docker.internal -U healmesh -d healmesh -f /workspace/infra/postgres/001_init.sql || echo "Schema might already exist"
export PGPASSWORD=healmesh_local

echo "==> Starting healmesh-core..."
cd healmesh-core
pip install -r requirements.txt uvicorn httpx > /dev/null 2>&1
uvicorn main:app --port 8000 > core.log 2>&1 &
CORE_PID=$!
cd ..

echo "==> Setting up healmesh-k8s..."
export KUBECONFIG_PATH=$HOME/.kube/config
export WATCH_NAMESPACES=healmesh-test
cd healmesh-k8s
go mod tidy
go build -o watcher_bin cmd/watcher/main.go
./watcher_bin > watcher.log 2>&1 &
WATCHER_PID=$!
cd ..

echo "==> Waiting for services to start..."
sleep 5

echo "==> Injecting failure (CrashLoopBackOff)..."
START_TIME=$(date +%s%N)
./infra/scripts/inject_failure.sh CrashLoopBackOff

echo "==> Waiting for diagnosis to complete and Slack to be notified (max 30s)..."
for i in {1..30}; do
  if grep -q "Slack diagnosis delivered for incident" healmesh-core/core.log; then
    END_TIME=$(date +%s%N)
    echo "==> SUCCESS! Slack notification delivered."
    ELAPSED=$(( (END_TIME - START_TIME) / 1000000 ))
    echo "==> FR-3 Timing: $ELAPSED ms"
    break
  fi
  sleep 1
done

if ! grep -q "Slack diagnosis delivered for incident" healmesh-core/core.log; then
  echo "==> FAILURE: Slack notification not delivered within 30s."
  echo "--- core.log ---"
  cat healmesh-core/core.log
  echo "--- watcher.log ---"
  cat healmesh-k8s/watcher.log
fi

echo "==> Cleaning up..."
kill $CORE_PID
kill $WATCHER_PID
