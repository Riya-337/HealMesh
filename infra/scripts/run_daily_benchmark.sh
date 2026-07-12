#!/usr/bin/env bash
# HealMesh — Daily Benchmark Runner
# MUST be run before any integration/E2E tests that make LLM calls.
# The gemini-2.5-flash free tier allows 20 req/day. The benchmark needs all 20.
# Running E2E tests first will exhaust quota and cause 0 benchmark progress.
#
# Usage: ./infra/scripts/run_daily_benchmark.sh

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "============================================================"
echo "  HealMesh — Daily Benchmark Cycle"
echo "  $(date)"
echo "============================================================"
echo ""
echo "  IMPORTANT: This script intentionally runs the benchmark"
echo "  FIRST, before any LLM-consuming integration tests."
echo "  The gemini-2.5-flash free tier allows 20 req/day."
echo "  Do not run E2E/FR-3 tests before this script."
echo ""

cd "${ROOT_DIR}"

# Load environment
set -a
source .env
set +a

# Start healmesh-core
echo "==> Starting healmesh-core..."
cd healmesh-core
uvicorn main:app --host 127.0.0.1 --port 8000 > core_bench_daily.log 2>&1 &
CORE_PID=$!
cd "${ROOT_DIR}"

# Wait for core to become healthy — retry up to 15 times (15s total)
HEALTHY=0
for i in $(seq 1 15); do
    if curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; then
        HEALTHY=1
        break
    fi
    sleep 1
done

if [ "$HEALTHY" -eq 0 ]; then
    echo "ERROR: healmesh-core failed to start after 15s. Check healmesh-core/core_bench_daily.log"
    tail -20 healmesh-core/core_bench_daily.log
    kill $CORE_PID 2>/dev/null || true
    exit 1
fi

echo "==> healmesh-core healthy."
echo ""
echo "==> Running benchmark (quota-aware, checkpointed)..."
echo ""

python3 benchmark/run_benchmark.py
BENCH_EXIT=$?

echo ""
echo "==> Benchmark run complete. Shutting down healmesh-core..."
kill $CORE_PID 2>/dev/null || true

echo ""
echo "==> Checkpoint status:"
if [ -f benchmark/results/checkpoint.json ]; then
    python3 -c "
import json
with open('benchmark/results/checkpoint.json') as f:
    cp = json.load(f)
total = len(cp)
truncated = sum(1 for v in cp.values()
    if 'unavailable' in str(v.get('diagnosis', {}).get('root_cause', '')).lower())
real = total - truncated
passed = sum(1 for v in cp.values() if v.get('score', {}).get('passed'))
print(f'  Checkpointed: {total}/32 cases')
print(f'  Real diagnoses: {real}  (truncated/LLM-error: {truncated})')
print(f'  Passing so far: {passed}/{total}')
"
else
    echo "  No checkpoint file found."
fi

exit $BENCH_EXIT
