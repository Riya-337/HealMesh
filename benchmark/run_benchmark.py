#!/usr/bin/env python3
"""
healmesh — Phase 1.5 Benchmark Runner
======================================
Runs all synthetic benchmark cases against a live healmesh-core instance
and produces an accuracy report.

Usage:
    python3 run_benchmark.py [--url http://127.0.0.1:8000] [--output results/run_TIMESTAMP.json]

Phase gate:
    ≥80% keyword accuracy required before Phase 2 (automated remediation) begins.
    See CONSTITUTION.md Article 3.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# ── Config ──────────────────────────────────────────────────────────────────

CASES_DIR = Path(__file__).parent / "cases"
RESULTS_DIR = Path(__file__).parent / "results"
PHASE_GATE_ACCURACY = 0.80  # 80% minimum to proceed to Phase 2

# ── Case loading ─────────────────────────────────────────────────────────────

def load_all_cases() -> list[dict[str, Any]]:
    """Load all JSON benchmark cases from the cases/ directory tree."""
    cases = []
    for json_file in sorted(CASES_DIR.rglob("*.json")):
        with open(json_file) as f:
            case = json.load(f)
        case["_case_file"] = str(json_file.relative_to(CASES_DIR))
        case["_case_id"] = json_file.stem
        cases.append(case)
    return cases


# ── Scoring ──────────────────────────────────────────────────────────────────

CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


def score_case(case: dict, diagnosis: dict) -> dict[str, Any]:
    """
    Format a single benchmark case against the returned diagnosis for manual grading.
    
    NOTE: The 'expected' field in the test case is only used here to provide
    context for human grading. It is NEVER sent to the LLM or used in prompt construction.
    """
    expected = case["expected"]

    return {
        "root_cause_returned": diagnosis.get("root_cause", ""),
        "action_returned": diagnosis.get("action_type") or "NONE",
        "confidence_returned": (diagnosis.get("confidence") or "low").lower(),
        "keywords_expected": expected.get("root_cause_keywords", []),
        "action_expected": expected.get("action_type", "NONE"),
        "confidence_min_expected": expected.get("confidence_min", "low"),
    }


# ── API interaction ───────────────────────────────────────────────────────────

def submit_incident(client: httpx.Client, incident: dict) -> dict:
    """POST an incident to healmesh-core and return the full diagnosis.

    Uses the inline diagnosis returned in the POST response body — no
    follow-up GET /diagnoses call needed, so PostgreSQL is not required
    for benchmark runs.
    """
    resp = client.post("/incident", json=incident, timeout=60.0)
    resp.raise_for_status()
    result = resp.json()

    # Prefer the inline diagnosis included in the response body.
    inline = result.get("diagnosis")
    if inline and inline.get("root_cause"):
        # Normalise: benchmark scorer reads action_type from top-level key.
        inline["action_type"] = (
            inline.get("parsed_action", {}).get("action_type", "NONE")
        )
        return inline

    # Fallback: try to fetch from audit DB (requires PostgreSQL).
    diagnosis_id = result.get("diagnosis_id")
    if not diagnosis_id:
        return {"root_cause": "No diagnosis_id returned", "action_type": "NONE", "confidence": "low"}

    diag_resp = client.get(f"/diagnoses/{diagnosis_id}", timeout=10.0)
    if diag_resp.status_code == 404:
        list_resp = client.get("/diagnoses?limit=1", timeout=10.0)
        list_resp.raise_for_status()
        diagnoses = list_resp.json().get("diagnoses", [])
        if diagnoses:
            d = diagnoses[0]
            d["action_type"] = d.get("parsed_action", {}).get("action_type", "NONE")
            return d
        return {"root_cause": "Diagnosis not found", "action_type": "NONE", "confidence": "low"}

    diag_resp.raise_for_status()
    d = diag_resp.json()
    d["action_type"] = d.get("parsed_action", {}).get("action_type", "NONE")
    return d


# ── Report generation ─────────────────────────────────────────────────────────

def print_case_result(case_id: str, score: dict, index: int, total: int):
    print(f"  [{index:02d}/{total}] 📝 REVIEW  {case_id}")
    print(f"         Root Cause: {score['root_cause_returned']}")
    print(f"         Expected Action: {score['action_expected']}, Got: {score['action_returned']}")


def generate_report(cases: list, scores: list, run_meta: dict) -> dict:
    total = len(scores)

    report = {
        "run_id": run_meta["run_id"],
        "timestamp": run_meta["timestamp"],
        "healmesh_core_url": run_meta["url"],
        "total_cases": total,
        "results": scores,
    }
    return report


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="HealMesh Phase 1.5 Benchmark Runner")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="healmesh-core base URL")
    parser.add_argument("--output", default=None, help="Output JSON file path")
    parser.add_argument("--dry-run", action="store_true", help="Load cases only, don't call API")
    parser.add_argument("--delay", type=float, default=15.0,
                        help="Seconds between API calls (rate limiting)")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = args.output or str(RESULTS_DIR / f"run_{run_id}.json")

    print("=" * 60)
    print("  HealMesh — Phase 1.5 Benchmark Runner")
    print("=" * 60)

    # Load cases
    cases = load_all_cases()
    if not cases:
        print(f"ERROR: No benchmark cases found in {CASES_DIR}")
        sys.exit(1)

    print(f"\n  Cases found: {len(cases)}")
    print(f"  Target URL:  {args.url}")
    print(f"  Output:      {output_path}")
    print(f"  Phase gate:  ≥{PHASE_GATE_ACCURACY * 100:.0f}% accuracy\n")

    if args.dry_run:
        print("  DRY RUN — listing cases only:\n")
        for i, case in enumerate(cases, 1):
            print(f"  [{i:02d}] {case['_case_id']}  ({case['_case_file']})")
        print(f"\n  Total: {len(cases)} cases")
        return

    # Check healmesh-core is reachable
    try:
        with httpx.Client(base_url=args.url) as client:
            health = client.get("/health", timeout=5.0)
            health.raise_for_status()
            print(f"  healmesh-core: ✅ healthy ({args.url})\n")
    except Exception as e:
        print(f"  ERROR: Cannot reach healmesh-core at {args.url}: {e}")
        print("  Start it with: cd healmesh-core && uvicorn main:app --reload")
        sys.exit(1)

    checkpoint_path = RESULTS_DIR / "checkpoint.json"
    completed_cases = {}
    if checkpoint_path.exists():
        try:
            with open(checkpoint_path) as f:
                completed_cases = json.load(f)
            print(f"  Loaded checkpoint: {len(completed_cases)} cases already completed.\n")
        except Exception as e:
            print(f"  ERROR: Failed to load checkpoint: {e}")
            sys.exit(1)

    # Pre-flight quota check: test one call before committing to the full run.
    # This prevents burning all remaining daily quota on a run that will fail anyway.
    pending_cases = [c for c in cases if c["_case_id"] not in completed_cases]
    if pending_cases:
        print("  Pre-flight check: verifying LLM quota is available...")
        with httpx.Client(base_url=args.url) as probe_client:
            try:
                probe_diagnosis = submit_incident(probe_client, pending_cases[0]["incident"])
                if probe_diagnosis.get("root_cause") == "Diagnosis unavailable (LLM quota exhausted)":
                    print("  🛑 QUOTA EXHAUSTED — Daily LLM quota is used up. Re-run tomorrow after 00:00 UTC.")
                    print(f"  Checkpoint preserved: {len(completed_cases)}/32 cases banked.")
                    sys.exit(0)
                # First case ran OK — score it and mark it done
                first_score = score_case(pending_cases[0], probe_diagnosis)
                first_record = {
                    "case_id": pending_cases[0]["_case_id"],
                    "case_file": pending_cases[0]["_case_file"],
                    "score": first_score,
                    "diagnosis": probe_diagnosis,
                }
                completed_cases[pending_cases[0]["_case_id"]] = first_record
                with open(checkpoint_path, "w") as f:
                    json.dump(completed_cases, f, indent=2)
                print_case_result(pending_cases[0]["_case_id"], first_score,
                                  cases.index(pending_cases[0]) + 1, len(cases))
                print()
                time.sleep(args.delay)
            except Exception:
                pass  # Let the main loop handle errors case-by-case
        print()

    # Run benchmark
    scores = []
    print("  Running cases:\n")

    with httpx.Client(base_url=args.url) as client:
        for i, case in enumerate(cases, 1):
            case_id = case["_case_id"]
            
            if case_id in completed_cases:
                print(f"  [{i:02d}/{len(cases)}] ⏭️  SKIP  {case_id} (already completed)")
                scores.append(completed_cases[case_id])
                continue

            incident = case["incident"]
            diagnosis = None

            try:
                diagnosis = submit_incident(client, incident)
                
                # Check for quota failure from healmesh-core
                if diagnosis.get("root_cause") == "Diagnosis unavailable (LLM quota exhausted)":
                    print(f"  [{i:02d}/{len(cases)}] 🛑 QUOTA {case_id} — Daily LLM quota exhausted. Stopping cleanly.")
                    break
                    
                score = score_case(case, diagnosis)
            except httpx.HTTPStatusError as e:
                print(f"  [{i:02d}/{len(cases)}] ⚠️  HTTP {e.response.status_code}  {case_id}. Stopping cleanly to preserve results.")
                break
            except Exception as e:
                print(f"  [{i:02d}/{len(cases)}] ⚠️  ERROR  {case_id}: {e}. Stopping cleanly to preserve results.")
                break
            else:
                print_case_result(case_id, score, i, len(cases))

            result_record = {
                "case_id": case_id,
                "case_file": case["_case_file"],
                "score": score,
                "diagnosis": diagnosis,
            }
            scores.append(result_record)
            completed_cases[case_id] = result_record
            
            # Save checkpoint after every completion
            with open(checkpoint_path, "w") as f:
                json.dump(completed_cases, f, indent=2)

            # Rate limiting between calls
            if i < len(cases):
                time.sleep(args.delay)

    # Defer phase gate evaluation if not all cases completed
    if len(completed_cases) < len(cases):
        print("\n" + "=" * 60)
        print(f"  RUN PAUSED: {len(completed_cases)}/{len(cases)} cases completed.")
        print("  Quota limit reached or run interrupted. Re-run later to finish.")
        print("  Phase gate evaluation deferred until all 32 cases complete.")
        print("=" * 60)
        sys.exit(0)

    # Generate and save report
    run_meta = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "url": args.url,
    }
    report = generate_report(cases, scores, run_meta)

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    # Print summary
    print("\n" + "=" * 60)
    print("  BENCHMARK RESULTS (MANUAL GRADING REQUIRED)")
    print("=" * 60)
    print(f"  Total cases:      {report['total_cases']}")
    print(f"  Report saved:     {output_path}")
    print("=" * 60)
    print("\n  📝 Please manually review the results file and apply the grading rubric.")


if __name__ == "__main__":
    main()
