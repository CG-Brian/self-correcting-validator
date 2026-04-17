"""
eval.py — Evaluation pipeline for self-correcting complaint ticket extractor.

This evaluation measures structured validity improvement, not semantic
benchmark accuracy. A "success" means the output passes schema + business-rule
validation, not that it matches a human-labeled ground truth.

Metrics:
  - total_cases
  - first_pass_successes / first_pass_rate
  - final_successes     / final_success_rate
  - rescued_by_correction
  - rescued_rate_among_successes
  - correction_lift
  - avg_attempts_on_success
  - error_distribution  (field:code level, final failures only)
  - bucket_breakdown    (per-bucket version of above)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.pipeline import run_self_correcting


# ─────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────

@dataclass
class CaseResult:
    index: int
    source_file: str             # originating filename — useful for combined analysis
    bucket: str
    text: str
    ok: bool
    attempts: int
    first_pass_ok: bool          # did attempt-1 pass?
    rescued: bool                # failed first-pass but recovered via retry
    errors: List[Dict[str, str]] # final errors (empty if ok)
    final: Optional[Dict]


@dataclass
class EvalMetrics:
    label: str
    total_cases: int
    first_pass_successes: int
    final_successes: int
    rescued_by_correction: int
    rescued_rate_among_successes: float  # % of successes that needed retry
    first_pass_rate: float
    final_success_rate: float
    correction_lift: float        # percentage-point lift
    avg_attempts_on_success: float
    error_distribution: Dict[str, int]   # "field:code" → count
    bucket_breakdown: Dict[str, Dict]    # bucket → sub-metrics


# ─────────────────────────────────────────────
# Core runner
# ─────────────────────────────────────────────

def run_eval(filepath: str | Path, max_attempts: int = 3) -> tuple[List[CaseResult], EvalMetrics]:
    path = Path(filepath)
    cases = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    results: List[CaseResult] = []

    for i, case in enumerate(cases):
        text   = case["text"]
        bucket = case.get("bucket", "unknown")

        print(f"  [{i+1:02d}/{len(cases)}] {bucket[:50]}", end=" ... ", flush=True)

        pipeline_out = run_self_correcting(text, max_attempts=max_attempts)

        trace          = pipeline_out["trace"]
        first_pass_ok  = len(trace) > 0 and trace[0]["ok"]
        ok             = pipeline_out["ok"]
        rescued        = (not first_pass_ok) and ok

        print("✓" if ok else "✗")

        results.append(CaseResult(
            index          = i,
            source_file    = path.name,
            bucket         = bucket,
            text           = text,
            ok             = ok,
            attempts       = pipeline_out["attempts"],
            first_pass_ok  = first_pass_ok,
            rescued        = rescued,
            errors         = pipeline_out["errors"],
            final          = pipeline_out["final"],
        ))

    metrics = compute_metrics(path.name, results)
    return results, metrics


# ─────────────────────────────────────────────
# Metrics computation
# ─────────────────────────────────────────────

def _sub_metrics(subset: List[CaseResult]) -> Dict:
    """Compute the core numeric metrics for any subset of results."""
    n = len(subset)
    if n == 0:
        return {"total": 0}

    fp  = sum(1 for r in subset if r.first_pass_ok)
    fin = sum(1 for r in subset if r.ok)
    fp_rate  = fp  / n
    fin_rate = fin / n
    lift     = fin_rate - fp_rate

    rescued    = fin - fp
    rescued_rate = round((rescued / fin * 100), 1) if fin > 0 else 0.0

    success_attempts = [r.attempts for r in subset if r.ok]
    avg_att = round(sum(success_attempts) / len(success_attempts), 2) if success_attempts else 0.0

    return {
        "total":                        n,
        "first_pass_successes":         fp,
        "final_successes":              fin,
        "rescued_by_correction":        rescued,
        "rescued_rate_among_successes": rescued_rate,
        "first_pass_rate":              round(fp_rate * 100, 1),
        "final_success_rate":           round(fin_rate * 100, 1),
        "correction_lift":              round(lift * 100, 1),
        "avg_attempts_on_success":      avg_att,
    }


def compute_metrics(label: str, results: List[CaseResult]) -> EvalMetrics:
    top = _sub_metrics(results)

    # Error distribution: field:code → count (only from failed final states)
    err_counter: Counter = Counter()
    for r in results:
        for e in r.errors:
            key = f"{e.get('field','?')}:{e.get('code','?')}"
            err_counter[key] += 1

    # Bucket breakdown
    by_bucket: Dict[str, List[CaseResult]] = defaultdict(list)
    for r in results:
        by_bucket[r.bucket].append(r)

    bucket_breakdown = {
        bkt: _sub_metrics(bkt_results)
        for bkt, bkt_results in sorted(by_bucket.items())
    }

    return EvalMetrics(
        label                        = label,
        total_cases                  = top["total"],
        first_pass_successes         = top["first_pass_successes"],
        final_successes              = top["final_successes"],
        rescued_by_correction        = top["rescued_by_correction"],
        rescued_rate_among_successes = top["rescued_rate_among_successes"],
        first_pass_rate              = top["first_pass_rate"],
        final_success_rate           = top["final_success_rate"],
        correction_lift              = top["correction_lift"],
        avg_attempts_on_success      = top["avg_attempts_on_success"],
        error_distribution           = dict(err_counter.most_common()),
        bucket_breakdown             = bucket_breakdown,
    )


# ─────────────────────────────────────────────
# Terminal output
# ─────────────────────────────────────────────

def print_summary(m: EvalMetrics) -> None:
    w = 55
    print()
    print("=" * w)
    print(f"  {m.label}")
    print("=" * w)
    print(f"  Total cases            : {m.total_cases}")
    print(f"  First-pass successes   : {m.first_pass_successes}  ({m.first_pass_rate}%)")
    print(f"  Final successes        : {m.final_successes}  ({m.final_success_rate}%)")
    print(f"  Rescued by correction  : {m.rescued_by_correction}  ({m.rescued_rate_among_successes}% of successes needed retry)")
    print(f"  Correction lift        : +{m.correction_lift}%p")
    print(f"  Avg attempts (success) : {m.avg_attempts_on_success}")

    if m.error_distribution:
        print()
        print("  Top errors (field:code):")
        for k, v in list(m.error_distribution.items())[:8]:
            print(f"    {k:<35} {v}")

    if m.bucket_breakdown:
        print()
        print("  Bucket breakdown:")
        print(f"  {'bucket':<45} {'total':>5}  {'1st%':>6}  {'fin%':>6}  {'lift':>7}")
        print("  " + "-" * 72)
        for bkt, sub in m.bucket_breakdown.items():
            if sub["total"] == 0:
                continue
            lift_str = f"+{sub['correction_lift']}%p" if sub["correction_lift"] >= 0 else f"{sub['correction_lift']}%p"
            print(
                f"  {bkt:<45} {sub['total']:>5}  "
                f"{sub['first_pass_rate']:>5.1f}%  "
                f"{sub['final_success_rate']:>5.1f}%  "
                f"{lift_str:>7}"
            )

    print("=" * w)


# ─────────────────────────────────────────────
# Save
# ─────────────────────────────────────────────

def save_summary(all_metrics: List[EvalMetrics], out_path: str | Path) -> None:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(m) for m in all_metrics]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n  Saved → {out_path}")


def save_failure_examples(results: List[CaseResult], out_path: str | Path) -> None:
    """Save final-failure cases to jsonl for post-hoc inspection."""
    failures = [r for r in results if not r.ok]
    if not failures:
        print("\n  No failures to save.")
        return
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in failures:
            record = {
                "source_file": r.source_file,
                "bucket":      r.bucket,
                "text":        r.text,
                "attempts":    r.attempts,
                "errors":      r.errors,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"  Saved {len(failures)} failure(s) → {out_path}")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main(files: Optional[List[str]] = None, max_attempts: int = 3) -> None:
    base = Path(__file__).parent.parent  # project root

    if files:
        targets = [(Path(f).stem, Path(f)) for f in files]
        combined = len(targets) > 1
    else:
        targets = [
            ("samples.jsonl",    base / "data" / "samples.jsonl"),
            ("hard_cases.jsonl", base / "data" / "hard_cases.jsonl"),
        ]
        combined = True

    all_results: List[CaseResult] = []
    all_metrics: List[EvalMetrics] = []

    for label, path in targets:
        if not path.exists():
            print(f"  [SKIP] {path} not found")
            continue
        print(f"\nRunning eval on: {path.name}")
        results, metrics = run_eval(path, max_attempts=max_attempts)
        print_summary(metrics)
        all_results.extend(results)
        all_metrics.append(metrics)

    # Combined
    if combined and len(all_metrics) > 1:
        combined_metrics = compute_metrics("combined", all_results)
        print_summary(combined_metrics)
        all_metrics.append(combined_metrics)

    save_summary(all_metrics, base / "eval" / "eval_summary.json")
    save_failure_examples(all_results, base / "eval" / "failure_examples.jsonl")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", nargs="*", help="specific jsonl file(s) to eval")
    parser.add_argument("--max-attempts", type=int, default=3)
    args = parser.parse_args()
    main(files=args.file, max_attempts=args.max_attempts)