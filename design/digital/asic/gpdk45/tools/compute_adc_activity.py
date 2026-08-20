#!/usr/bin/env python3
"""Compute primary-input activity from a 12-bit ECG hex stream."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_mem", type=Path)
    parser.add_argument("--gap-cycles", type=int, default=2)
    parser.add_argument("--csv-out", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.gap_cycles < 0:
        raise ValueError("gap-cycles must be non-negative")

    ones = [0] * 12
    toggles = [0] * 12
    sample_count = 0
    previous: int | None = None

    with args.input_mem.open("r", encoding="ascii") as stream:
        for raw_line in stream:
            line = raw_line.strip()
            if not line:
                continue
            value = int(line, 16) & 0xFFF
            for bit in range(12):
                ones[bit] += (value >> bit) & 1
            if previous is not None:
                changed = previous ^ value
                for bit in range(12):
                    toggles[bit] += (changed >> bit) & 1
            previous = value
            sample_count += 1

    if sample_count < 2:
        raise ValueError("input stream must contain at least two samples")

    cycles_per_sample = args.gap_cycles + 1
    rows = []
    for bit in range(12):
        transition_per_sample = toggles[bit] / (sample_count - 1)
        rows.append(
            {
                "bit": bit,
                "one_probability": ones[bit] / sample_count,
                "transitions": toggles[bit],
                "transition_per_accepted_sample": transition_per_sample,
                "transition_per_clock_cycle": transition_per_sample
                / cycles_per_sample,
            }
        )

    args.csv_out.parent.mkdir(parents=True, exist_ok=True)
    with args.csv_out.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "input": args.input_mem.name,
        "sample_count": sample_count,
        "gap_cycles": args.gap_cycles,
        "cycles_per_sample": cycles_per_sample,
        "mean_one_probability": sum(row["one_probability"] for row in rows)
        / len(rows),
        "mean_transition_per_accepted_sample": sum(
            row["transition_per_accepted_sample"] for row in rows
        )
        / len(rows),
        "mean_transition_per_clock_cycle": sum(
            row["transition_per_clock_cycle"] for row in rows
        )
        / len(rows),
    }
    args.json_out.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
