# HealMesh — Phase 1.5 Benchmark Dataset

This directory contains synthetic test cases for evaluating diagnosis accuracy.

**Status:** Empty — populate during Phase 1.5  
**Data type:** Synthetic only (see DECISION_LOG ADR-004)  
**Minimum cases:** 30–50 per failure type  

## Directory Structure (to be created in Phase 1.5)

```
benchmark/
├── README.md                  # This file
├── cases/
│   ├── crash_loop/            # CrashLoopBackOff synthetic cases
│   ├── oom_killed/            # OOMKilled synthetic cases
│   ├── image_pull/            # ImagePullBackOff synthetic cases
│   ├── failed_rollout/        # FailedRollout synthetic cases
│   └── quota_exceeded/        # ResourceQuotaExceeded synthetic cases
├── run_benchmark.py           # Benchmark runner script
└── results/                   # Benchmark run outputs (gitignored)
```

## Case Format

Each case is a JSON file matching `IncidentPayload` schema plus an expected ground truth:

```json
{
  "incident": { ... IncidentPayload fields ... },
  "expected": {
    "root_cause_keywords": ["OOM", "memory limit"],
    "confidence": "high",
    "action_type": "NONE"
  }
}
```

## Phase Gate

Phase 2 (automated remediation) requires ≥80% accuracy on this benchmark.
