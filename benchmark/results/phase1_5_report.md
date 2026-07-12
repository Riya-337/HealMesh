# HealMesh — Phase 1.5 Benchmark Report

> Generated: 2026-07-08T06:52:56.264317+00:00
> Benchmark run ID: 20260708_064618
> **Per CONSTITUTION.md Article 4:** Results reported exactly as measured.
> A below-target result blocks Phase 2, not smoothed over.

---

## Overall Results

| Metric | Value |
|---|---|
| Total cases | 32 |
| Passed | 0 |
| Failed | 32 |
| **Overall accuracy** | **0.0%** |
| Phase gate threshold | ≥80% |
| **Phase gate** | **❌ NOT PASSED** |

## Accuracy by Failure Type

| Failure Type | Cases | Passed | Accuracy | Gate |
|---|---|---|---|---|
| CrashLoopBackOff | 10 | 0 | 0.0% | ❌ |
| OOMKilled | 6 | 0 | 0.0% | ❌ |
| ImagePullBackOff | 5 | 0 | 0.0% | ❌ |
| FailedRollout | 6 | 0 | 0.0% | ❌ |
| ResourceQuotaExceeded | 5 | 0 | 0.0% | ❌ |

> [!CAUTION]
> **Weak spots below 80%: CrashLoopBackOff, OOMKilled, ImagePullBackOff, FailedRollout, ResourceQuotaExceeded**
> Per CONSTITUTION.md Article 4 and TESTING.md §5, these are surfaced, not smoothed over.
> Phase 2 is blocked until these are either improved or explicitly accepted with documented rationale.

## Failed Cases Detail

### CrashLoopBackOff

- **clb_001_db_connection_refused**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **clb_002_missing_env_var**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **clb_003_oom_causing_crash_loop**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **clb_004_liveness_probe_killing_pod**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **clb_005_file_permission_error**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **clb_006_config_map_missing**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **clb_007_port_already_in_use**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **clb_008_bad_command_entrypoint**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **clb_009_redis_connection_refused**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **clb_010_ssl_cert_expired**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...

### OOMKilled

- **oom_001_large_dataset**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **oom_002_memory_leak_cache**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **oom_003_image_processing**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **oom_004_jvm_heap**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **oom_005_numpy_array_explosion**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **oom_006_node_pressure**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...

### ImagePullBackOff

- **ipb_001_tag_not_found**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **ipb_002_registry_auth_failure**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **ipb_003_gcr_iam_permission**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **ipb_004_typo_in_image_name**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **ipb_005_docker_hub_rate_limit**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...

### FailedRollout

- **fro_001_readiness_probe_failing**: keywords[✗] action[✗] confidence[✗]
  - Expected action: `REDEPLOY`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **fro_002_bad_image_tag**: keywords[✗] action[✗] confidence[✗]
  - Expected action: `REDEPLOY`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **fro_003_insufficient_cpu**: keywords[✗] action[✗] confidence[✗]
  - Expected action: `SCALE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **fro_004_insufficient_memory**: keywords[✗] action[✗] confidence[✗]
  - Expected action: `SCALE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **fro_005_config_validation_error**: keywords[✗] action[✗] confidence[✗]
  - Expected action: `REDEPLOY`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **fro_006_pending_pvc**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...

### ResourceQuotaExceeded

- **qex_001_pod_count_limit**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **qex_002_cpu_quota**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **qex_003_memory_quota**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **qex_004_pvc_quota**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...
- **qex_005_services_quota**: keywords[✗] action[✓] confidence[✗]
  - Expected action: `NONE`, got: `NONE`
  - Root cause: Diagnosis unavailable (LLM call failed)...

## Score Breakdown

| Dimension | Rate |
|---|---|
| Keyword match | 0/32 |
| Action match | 27/32 |
| Confidence ok | 0/32 |

## FR-3 End-to-End Timing

Measured via 10-sample integration test against live kind cluster.

| Metric | Value |
|---|---|
| p50 latency (core diagnosis) | 0ms |
| p95 latency (core diagnosis) | 0ms |
| FR-3 target | ≤30000ms |
| **FR-3 gate** | **✅ PASS** |

## Integration Test Summary

| Result | Count |
|---|---|
| Pass | 27 |
| Fail | 0 |
| Skip | 1 |

---

## Phase Gate Verdict

**❌ Phase 1.5 NOT COMPLETE.** The following must be resolved before Phase 2 begins:

- Overall accuracy 0.0% < 80% required
- Per-type accuracy below 80%: CrashLoopBackOff, OOMKilled, ImagePullBackOff, FailedRollout, ResourceQuotaExceeded

Per CONSTITUTION.md Article 3: deadline pressure is not a valid reason to skip this gate.
