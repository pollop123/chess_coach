"""Validate a teaching benchmark report against a checked-in regression gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def validate_report(report: dict[str, Any], gate: dict[str, Any]) -> list[str]:
    failures: list[str] = []

    for field, expected in gate.get("equals", {}).items():
        actual = report.get(field)
        if actual != expected:
            failures.append(f"{field}: expected {expected!r}, got {actual!r}")

    for field, threshold in gate.get("minimum", {}).items():
        actual = report.get(field)
        if not isinstance(actual, (int, float)) or actual < threshold:
            failures.append(f"{field}: expected >= {threshold}, got {actual!r}")

    for field, threshold in gate.get("maximum", {}).items():
        actual = report.get(field)
        if not isinstance(actual, (int, float)) or actual > threshold:
            failures.append(f"{field}: expected <= {threshold}, got {actual!r}")

    topic_metrics = report.get("by_topic")
    if not isinstance(topic_metrics, dict):
        failures.append("by_topic: expected an object")
        topic_metrics = {}
    for topic, thresholds in gate.get("topic_minimum", {}).items():
        actual_metrics = topic_metrics.get(topic)
        if not isinstance(actual_metrics, dict):
            failures.append(f"by_topic.{topic}: missing topic metrics")
            continue
        for field, threshold in thresholds.items():
            actual = actual_metrics.get(field)
            if not isinstance(actual, (int, float)) or actual < threshold:
                failures.append(
                    f"by_topic.{topic}.{field}: expected >= {threshold}, got {actual!r}"
                )

    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    parser.add_argument(
        "--gate",
        default=str(
            Path(__file__).resolve().parent
            / "calibration"
            / "teaching-smoke-gate.json"
        ),
    )
    args = parser.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    gate = json.loads(Path(args.gate).read_text(encoding="utf-8"))
    failures = validate_report(report, gate)
    if failures:
        print("Teaching accuracy regression gate failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Teaching accuracy regression gate passed: "
        f"top3={report['top1_in_oracle_top3_rate']:.1%}, "
        f"recall={report['oracle_best_recall_rate']:.1%}, "
        f"inversions={report['average_rank_inversion_rate']:.1%}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
