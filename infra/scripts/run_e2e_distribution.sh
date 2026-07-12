#!/bin/bash
set -eo pipefail
export $(grep -v '^#' .env | xargs)

echo "==> Cleaning up previous test state..."
kubectl delete namespace healmesh-test --ignore-not-found=true
pkill -f "watcher_bin" || true
pkill -f "uvicorn main:app" || true

echo "==> Setting up database..."
docker run --rm -v "$(pwd):/workspace" -e PGPASSWORD=healmesh_local postgres:15 psql -h host.docker.internal -U healmesh -d healmesh -f /workspace/infra/postgres/001_init.sql > /dev/null 2>&1 || true

echo "==> Starting healmesh-core..."
cd healmesh-core
uvicorn main:app --port 8000 > core.log 2>&1 &
CORE_PID=$!
cd ..

echo "==> Setting up healmesh-k8s..."
export KUBECONFIG_PATH=$HOME/.kube/config
export WATCH_NAMESPACES=healmesh-test
cd healmesh-k8s
./watcher_bin > watcher.log 2>&1 &
WATCHER_PID=$!
cd ..

sleep 5

# Arrays of failures to test
# 15 CrashLoopBackOff, 2 of each of the rest
FAILURES=()
for i in {1..15}; do FAILURES+=("CrashLoopBackOff"); done
for f in OOMKilled ImagePullBackOff FailedRollout ResourceQuotaExceeded; do
  for i in {1..2}; do FAILURES+=("$f"); done
done

LATENCIES=()

echo "==> Starting E2E distribution test (${#FAILURES[@]} injections total)..."
for i in "${!FAILURES[@]}"; do
  FAIL_TYPE=${FAILURES[$i]}
  echo "[Iteration $((i+1))/${#FAILURES[@]}] Injecting $FAIL_TYPE..."
  
  # Inject and measure
  START_TIME=$(date +%s%N)
  ./infra/scripts/inject_failure.sh "$FAIL_TYPE" > /dev/null 2>&1
  
  SUCCESS=false
  for wait in {1..45}; do
    if grep -q "Slack diagnosis delivered for incident" healmesh-core/core.log; then
      END_TIME=$(date +%s%N)
      ELAPSED=$(( (END_TIME - START_TIME) / 1000000 ))
      LATENCIES+=($ELAPSED)
      echo "    -> SUCCESS: $ELAPSED ms"
      SUCCESS=true
      # Clear core.log so we don't match the same line on next iteration
      > healmesh-core/core.log
      break
    fi
    sleep 1
  done

  if [ "$SUCCESS" = false ]; then
    echo "    -> FAILURE: Slack notification not delivered within 45s."
  fi

  # Cleanup injection before next
  kubectl delete namespace healmesh-test > /dev/null 2>&1
  # Sleep to avoid LLM rate limit
  echo "    -> Waiting 15s for rate limit..."
  sleep 15
done

# Calculate p95 using python
echo "==> Calculating p95..."
python3 -c "
import sys, numpy as np
latencies = [int(x) for x in sys.argv[1:]]
if not latencies:
    print('No successful latencies recorded.')
    sys.exit(1)
print(f'Total Samples: {len(latencies)}')
print(f'Min: {min(latencies)} ms')
print(f'Max: {max(latencies)} ms')
print(f'Median: {np.median(latencies):.2f} ms')
print(f'p95: {np.percentile(latencies, 95):.2f} ms')
" "${LATENCIES[@]}"

echo "==> Cleaning up..."
kill $CORE_PID
kill $WATCHER_PID
