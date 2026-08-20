#!/usr/bin/env python3
"""Build gate/RTL regression manifests from canonical and raw-XMODEL authorities."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-root", type=Path, required=True)
    parser.add_argument("--canonical-manifest-root", type=Path)
    parser.add_argument("--canonical-csv", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--raw-manifest-root", type=Path)
    parser.add_argument("--raw-input-csv", type=Path, required=True)
    parser.add_argument("--raw-golden-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_nonempty_lines(path: Path) -> int:
    with path.open("r", encoding="ascii") as handle:
        return sum(1 for line in handle if line.strip())


def manifest_line(
    case_id: int,
    expected_class: int,
    sample_count: int,
    membranes: tuple[int, int, int, int],
    path: Path,
) -> str:
    values = (case_id, expected_class, sample_count, *membranes, path.as_posix())
    return " ".join(str(value) for value in values)


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    audit_rows: list[dict[str, object]] = []

    canonical_lines: list[str] = []
    canonical_manifest_root = args.canonical_manifest_root or args.canonical_root
    for row in read_csv(args.canonical_csv):
        path = args.canonical_root / row["mem_path"]
        manifest_path = canonical_manifest_root / row["mem_path"]
        expected_sha = row["mem_sha256"].lower()
        actual_sha = sha256_file(path)
        sample_count = int(row["sample_count_expected"])
        actual_samples = count_nonempty_lines(path)
        if actual_sha != expected_sha or actual_samples != sample_count:
            raise RuntimeError(f"canonical input mismatch: {path}")
        membranes = tuple(
            int(row[name])
            for name in (
                "expected_final_mem_NSR",
                "expected_final_mem_CHF",
                "expected_final_mem_ARR",
                "expected_final_mem_AFF",
            )
        )
        canonical_lines.append(
            manifest_line(
                int(row["source_prediction_case_id"]),
                int(row["expected_final_pred"]),
                sample_count,
                membranes,
                manifest_path,
            )
        )
        audit_rows.append(
            {
                "cohort": "canonical_digital",
                "case_id": int(row["source_prediction_case_id"]),
                "source_path": path.as_posix(),
                "manifest_path": manifest_path.as_posix(),
                "samples": actual_samples,
                "sha256": actual_sha,
            }
        )

    raw_goldens = {int(row["case_id"]): row for row in read_csv(args.raw_golden_csv)}
    raw_lines: list[str] = []
    raw_manifest_root = args.raw_manifest_root or args.raw_root
    for row in read_csv(args.raw_input_csv):
        if row["status"] != "PRESENT_VALID":
            continue
        case_id = int(row["case_id_num"])
        golden = raw_goldens[case_id]
        rel = Path(row["xmodel_adc_file"]).name
        path = args.raw_root / rel
        manifest_path = raw_manifest_root / rel
        actual_sha = sha256_file(path)
        expected_sha = row["sha256"].lower()
        sample_count = int(row["sample_count"])
        actual_samples = count_nonempty_lines(path)
        if actual_sha != expected_sha or actual_samples != sample_count:
            raise RuntimeError(f"raw XMODEL input mismatch: {path}")
        membranes = tuple(
            int(golden[name])
            for name in (
                "final_mem_NSR",
                "final_mem_CHF",
                "final_mem_ARR",
                "final_mem_AFF",
            )
        )
        raw_lines.append(
            manifest_line(
                case_id,
                int(golden["final_pred_class"]),
                sample_count,
                membranes,
                manifest_path,
            )
        )
        audit_rows.append(
            {
                "cohort": "raw_xmodel",
                "case_id": case_id,
                "source_path": path.as_posix(),
                "manifest_path": manifest_path.as_posix(),
                "samples": actual_samples,
                "sha256": actual_sha,
            }
        )

    if len(canonical_lines) != 36 or len(raw_lines) != 4:
        raise RuntimeError(
            f"unexpected cohort sizes: canonical={len(canonical_lines)} raw={len(raw_lines)}"
        )

    canonical_path = args.output_dir / "canonical_digital_36.manifest"
    raw_path = args.output_dir / "raw_xmodel_4.manifest"
    canonical_path.write_text("\n".join(canonical_lines) + "\n", encoding="utf-8")
    raw_path.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")
    (args.output_dir / "manifest_audit.json").write_text(
        json.dumps(
            {
                "canonical_cases": len(canonical_lines),
                "raw_xmodel_cases": len(raw_lines),
                "rows": audit_rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"CANONICAL_MANIFEST={canonical_path}")
    print(f"RAW_XMODEL_MANIFEST={raw_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
