#!/usr/bin/env python3
"""
healmesh — Phase 1.5 Final Report Generator
============================================
Assembles the benchmark results, integration test results, and FR-3 timing
into a single Phase 1.5 report per CONSTITUTION.md Article 4 (honesty requirement)
and TESTING.md §5 (benchmark reporting standard).

Usage:
    python3 benchmark/generate_phase1_5_report.py \
        --benchmark-result benchmark/results/run_YYYYMMDD_HHMMSS.json \
        --integration-result benchmark/integration_results/integration_YYYYMMDD_HHMMSS.json \
        --output benchmark/results/phase1_5_report.md
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PHASE_GATE_ACCURACY = 0.80  # from PRD §9, CONSTITUTION.md Article 3


def load_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def build_per_type_breakdown(results: list[dict]) -> dict[str, dict]:
    """Group benchmark results by failure type."""
    by_type: dict[str, dict] = {}
    for r in results:
        case_id = r.get("case_id", "")
        # Determine type from case_id prefix
        if case_id.startswith("clb"):
            ft = "CrashLoopBackOff"
        elif case_id.startswith("oom"):
            ft = "OOMKilled"
        elif case_id.startswith("ipb"):
            ft = "ImagePullBackOff"
        elif case_id.startswith("fro"):
            ft = "FailedRollout"
        elif case_id.startswith("qex"):
            ft = "ResourceQuotaExceeded"
        else:
            ft = "Unknown"

        if ft not in by_type:
            by_type[ft] = {"total": 0, "passed": 0, "failed_cases": []}
        by_type[ft]["total"] += 1
        score = r.get("score", {})
        if score.get("passed"):
            by_type[ft]["passed"] += 1
        else:
            by_type[ft]["failed_cases"].append({
                "case_id": case_id,
                "keyword_match": score.get("keyword_match"),
                "action_match": score.get("action_match"),
                "confidence_ok": score.get("confidence_ok"),
                "root_cause_returned": (score.get("root_cause_returned") or "")[:120],
                "action_returned": score.get("action_returned"),
                "action_expected": score.get("action_expected"),
            })
    return by_type


def render_report(bm: dict, it: dict | None, output_path: str) -> None:
    total = bm.get("total_cases", 0)
    passed = bm.get("passed", 0)
    accuracy = bm.get("accuracy", 0.0)
    accuracy_pct = bm.get("accuracy_pct", "N/A")
    gate_passed = bm.get("phase_gate_passed", False)
    gate_icon = "✅" if gate_passed else "❌"

    per_type = build_per_type_breakdown(bm.get("results", []))

    # FR-3 data from integration results
    fr3 = {}
    if it:
        fr3 = it.get("fr3_timing_ms", {})

    now = datetime.now(timezone.utc).isoformat()

    lines = [
        "# HealMesh — Phase 1.5 Benchmark Report",
        "",
        f"> Generated: {now}",
        f"> Benchmark run ID: {bm.get('run_id', 'N/A')}",
        "> **Per CONSTITUTION.md Article 4:** Results reported exactly as measured.",
        "> A below-target result blocks Phase 2, not smoothed over.",
        "",
        "---",
        "",
        "## Overall Results",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total cases | {total} |",
        f"| Passed | {passed} |",
        f"| Failed | {total - passed} |",
        f"| **Overall accuracy** | **{accuracy_pct}** |",
        f"| Phase gate threshold | ≥80% |",
        f"| **Phase gate** | **{gate_icon} {'PASSED' if gate_passed else 'NOT PASSED'}** |",
        "",
    ]

    # Per failure type table
    lines += [
        "## Accuracy by Failure Type",
        "",
        "| Failure Type | Cases | Passed | Accuracy | Gate |",
        "|---|---|---|---|---|",
    ]

    all_types = ["CrashLoopBackOff", "OOMKilled", "ImagePullBackOff", "FailedRollout", "ResourceQuotaExceeded"]
    for ft in all_types:
        data = per_type.get(ft, {"total": 0, "passed": 0, "failed_cases": []})
        t = data["total"]
        p = data["passed"]
        acc = (p / t) if t > 0 else 0.0
        acc_str = f"{acc*100:.1f}%" if t > 0 else "N/A"
        gate = "✅" if acc >= PHASE_GATE_ACCURACY else "❌"
        lines.append(f"| {ft} | {t} | {p} | {acc_str} | {gate} |")

    lines += [""]

    # Weak spots (per CONSTITUTION.md Article 4 — surface weak spots)
    weak = [ft for ft in all_types
            if per_type.get(ft, {}).get("total", 0) > 0
            and per_type.get(ft, {}).get("passed", 0) / per_type[ft]["total"] < PHASE_GATE_ACCURACY]

    if weak:
        lines += [
            "> [!CAUTION]",
            f"> **Weak spots below 80%: {', '.join(weak)}**",
            "> Per CONSTITUTION.md Article 4 and TESTING.md §5, these are surfaced, not smoothed over.",
            "> Phase 2 is blocked until these are either improved or explicitly accepted with documented rationale.",
            "",
        ]
    else:
        lines += [
            "> [!NOTE]",
            "> All failure types meet the ≥80% accuracy threshold.",
            "",
        ]

    # Failed cases detail
    any_failures = any(per_type.get(ft, {}).get("failed_cases") for ft in all_types)
    if any_failures:
        lines += ["## Failed Cases Detail", ""]
        for ft in all_types:
            failed = per_type.get(ft, {}).get("failed_cases", [])
            if failed:
                lines += [f"### {ft}", ""]
                for fc in failed:
                    kw = "✓" if fc["keyword_match"] else "✗"
                    act = "✓" if fc["action_match"] else "✗"
                    conf = "✓" if fc["confidence_ok"] else "✗"
                    lines += [
                        f"- **{fc['case_id']}**: keywords[{kw}] action[{act}] confidence[{conf}]",
                        f"  - Expected action: `{fc['action_expected']}`, got: `{fc['action_returned']}`",
                        f"  - Root cause: {fc['root_cause_returned'][:100]}...",
                    ]
                lines += [""]

    # Breakdown metrics
    breakdown = bm.get("breakdown", {})
    lines += [
        "## Score Breakdown",
        "",
        f"| Dimension | Rate |",
        f"|---|---|",
        f"| Keyword match | {breakdown.get('keyword_match_rate', 'N/A')} |",
        f"| Action match | {breakdown.get('action_match_rate', 'N/A')} |",
        f"| Confidence ok | {breakdown.get('confidence_ok_rate', 'N/A')} |",
        "",
    ]

    # FR-3 timing
    lines += [
        "## FR-3 End-to-End Timing",
        "",
        "Measured via 10-sample integration test against live kind cluster.",
        "",
    ]
    if fr3:
        p50 = fr3.get("p50", "N/A")
        p95 = fr3.get("p95", "N/A")
        target = fr3.get("target_ms", 30000)
        fr3_pass = isinstance(p95, int) and p95 <= target
        fr3_icon = "✅" if fr3_pass else "❌"
        lines += [
            f"| Metric | Value |",
            f"|---|---|",
            f"| p50 latency (core diagnosis) | {p50}ms |",
            f"| p95 latency (core diagnosis) | {p95}ms |",
            f"| FR-3 target | ≤{target}ms |",
            f"| **FR-3 gate** | **{fr3_icon} {'PASS' if fr3_pass else 'NOT MET'}** |",
            "",
        ]
        if not fr3_pass:
            lines += [
                "> [!WARNING]",
                f"> FR-3 p95={p95}ms exceeds the 30s target. Investigate LLM latency or Gemini quota throttling.",
                "",
            ]
    else:
        lines += [
            "> [!WARNING]",
            "> No integration test results provided — FR-3 timing unverified.",
            "> Run `infra/scripts/phase1_5_integration_test.sh` to measure.",
            "",
        ]

    # Integration test summary
    if it:
        ip = it.get("pass", 0)
        if_ = it.get("fail", 0)
        is_ = it.get("skip", 0)
        lines += [
            "## Integration Test Summary",
            "",
            f"| Result | Count |",
            f"|---|---|",
            f"| Pass | {ip} |",
            f"| Fail | {if_} |",
            f"| Skip | {is_} |",
            "",
        ]
        if if_ > 0:
            lines += [
                "> [!CAUTION]",
                f"> {if_} integration test(s) failed. Review `benchmark/integration_results/` for details.",
                "",
            ]

    # Phase gate verdict
    lines += [
        "---",
        "",
        "## Phase Gate Verdict",
        "",
    ]

    blockers = []
    if not gate_passed:
        blockers.append(f"Overall accuracy {accuracy_pct} < 80% required")
    if weak:
        blockers.append(f"Per-type accuracy below 80%: {', '.join(weak)}")
    if not fr3 or (fr3 and isinstance(fr3.get("p95"), int) and fr3["p95"] > fr3.get("target_ms", 30000)):
        blockers.append("FR-3 timing unverified or exceeds target")
    if it and it.get("fail", 0) > 0:
        blockers.append(f"{it['fail']} integration test(s) failed")

    if not blockers:
        lines += [
            "**✅ Phase 1.5 COMPLETE.** All gates passed.",
            "",
            "Per CONSTITUTION.md Article 3 and the Implementation Plan cross-phase rules,",
            "Phase 2 execution-capable work may begin. The benchmark report has been",
            "reviewed and documents accuracy per failure type as required by TESTING.md §5.",
            "",
            "**Conditions for Phase 2 start:**",
            "- [ ] This report reviewed by full team (TESTING.md §8)",
            "- [ ] End-to-end demo recording artifact exists",
            "- [ ] Credentials migrated to Vault before any write-capable component ships",
        ]
    else:
        lines += [
            "**❌ Phase 1.5 NOT COMPLETE.** The following must be resolved before Phase 2 begins:",
            "",
        ]
        for b in blockers:
            lines.append(f"- {b}")
        lines += [
            "",
            "Per CONSTITUTION.md Article 3: deadline pressure is not a valid reason to skip this gate.",
        ]

    report = "\n".join(lines) + "\n"

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(report)

    print(report)
    print(f"\nReport saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="HealMesh Phase 1.5 Report Generator")
    parser.add_argument("--benchmark-result", required=True, help="Path to run_benchmark.py JSON output")
    parser.add_argument("--integration-result", default=None, help="Path to integration test JSON output")
    parser.add_argument("--output", default="benchmark/results/phase1_5_report.md")
    args = parser.parse_args()

    bm = load_json(args.benchmark_result)
    it = load_json(args.integration_result) if args.integration_result else None

    render_report(bm, it, args.output)


if __name__ == "__main__":
    main()
