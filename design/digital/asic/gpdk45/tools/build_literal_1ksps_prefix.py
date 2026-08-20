#!/usr/bin/env python3
"""Build a hashed raw-ECG prefix for matched literal-1-kSPS power windows."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


HEX_SAMPLE = re.compile(r"^[0-9a-fA-F]{1,3}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-mem", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--clock-hz", type=int, default=100_000_000)
    parser.add_argument("--sample-rate-hz", type=int, default=1_000)
    parser.add_argument("--case-id", default="unspecified")
    parser.add_argument("--class-label", default="unspecified")
    parser.add_argument("--tag")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    if args.samples <= 0:
        raise ValueError("--samples must be positive")
    if args.clock_hz <= 0 or args.sample_rate_hz <= 0:
        raise ValueError("clock and sample rates must be positive")
    if args.clock_hz % args.sample_rate_hz:
        raise ValueError("clock_hz must be an integer multiple of sample_rate_hz")

    cycles_per_sample = args.clock_hz // args.sample_rate_hz
    if cycles_per_sample <= 1:
        raise ValueError("cycles_per_sample must exceed one")

    prefix: list[str] = []
    total_nonempty = 0
    with args.input_mem.open("r", encoding="ascii") as handle:
        for line_number, line in enumerate(handle, start=1):
            sample = line.strip()
            if not sample:
                continue
            total_nonempty += 1
            if len(prefix) < args.samples:
                if not HEX_SAMPLE.fullmatch(sample):
                    raise ValueError(
                        f"invalid signed-12-bit hex sample at line {line_number}: {sample!r}"
                    )
                prefix.append(sample.lower())

    if len(prefix) != args.samples:
        raise ValueError(
            f"input contains only {len(prefix)} samples, requested {args.samples}"
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    tag = args.tag or args.input_mem.stem
    prefix_name = f"{tag}_prefix_{args.samples}.mem"
    prefix_path = args.output_dir / prefix_name
    prefix_path.write_text("\n".join(prefix) + "\n", encoding="ascii")

    window_cycles = args.samples * cycles_per_sample
    manifest = {
        "schema_version": 1,
        "experiment": "literal_1ksps_raw_prefix_matched_idle",
        "case_id": args.case_id,
        "class_label": args.class_label,
        "source_mem_name": args.input_mem.name,
        "source_mem_sha256": sha256_file(args.input_mem),
        "source_nonempty_samples": total_nonempty,
        "prefix_mem_name": prefix_name,
        "prefix_mem_sha256": sha256_file(prefix_path),
        "prefix_samples": args.samples,
        "clock_hz": args.clock_hz,
        "sample_rate_hz": args.sample_rate_hz,
        "cycles_per_sample": cycles_per_sample,
        "intervening_clocks_per_sample": cycles_per_sample - 1,
        "adc_data_idle_policy": "hold last accepted sample while sample_valid is low",
        "window_cycles": window_cycles,
        "window_seconds": window_cycles / args.clock_hz,
        "matched_modes": {
            "active_wait_idle": "MODE=0; started core; no accepted samples",
            "literal_1ksps_prefix": "MODE=1; one accepted raw sample per period",
        },
        "power_decomposition": {
            "idle_baseline": "leakage plus always-on 100 MHz clock and active-wait state activity",
            "sample_increment": "literal-prefix average minus matched active-wait idle average",
        },
        "reaches_60000_sample_snapshot": args.samples >= 60_000,
        "reaches_30_snapshot_decision": args.samples >= 1_800_000,
        "claim_boundary": (
            "Short prefix activity only; not a full snapshot, final decision, "
            "energy-per-decision, or 30-minute workload result."
        ),
    }
    manifest_path = args.output_dir / f"{tag}_prefix_{args.samples}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"PREFIX_MEM={prefix_path}")
    print(f"PREFIX_MANIFEST={manifest_path}")
    print(
        "LITERAL_WINDOW="
        f"{args.samples} samples, {cycles_per_sample} clocks/sample, "
        f"{window_cycles} clocks, {manifest['window_seconds']:.9f} s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
