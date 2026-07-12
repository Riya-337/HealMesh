#!/bin/bash
set -eo pipefail
export $(grep -v '^#' .env | xargs)

echo "==> Starting healmesh-core for Benchmark..."
cd healmesh-core
pip install -r requirements.txt uvicorn httpx > /dev/null 2>&1
uvicorn main:app --port 8000 > core_bench.log 2>&1 &
CORE_PID=$!
cd ..

sleep 3
echo "==> Running Benchmark Script for Today..."
python3 benchmark/run_benchmark.py || true

kill $CORE_PID
