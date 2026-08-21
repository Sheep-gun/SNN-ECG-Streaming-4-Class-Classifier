#!/usr/bin/env python3
"""Build a deterministic, function-preserving hold-driver downsize plan."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import tempfile
from pathlib import Path


SLOWEST = {
    "MX2X": "MX2XL",
    "AO22X": "AO22XL",
    "NOR2BX": "NOR2BXL",
    "OAI211X": "OAI211XL",
    "OAI22X": "OAI22XL",
    "NAND2X": "NAND2XL",
    "OAI2BB1X": "OAI2BB1XL",
    "NOR2X": "NOR2XL",
    "MXI2X": "MXI2XL",
    "OAI222X": "OAI222XL",
    "AOI21X": "AOI21XL",
    "OAI31X": "OAI31XL",
    "AND2X": "AND2XL",
}


def slower_cell(cell: str) -> str | None:
    if cell.startswith("CLKMX2X"):
        return None if cell == "CLKMX2X2" else "CLKMX2X2"
    for prefix, slowest in SLOWEST.items():
        if cell.startswith(prefix):
            return None if cell == slowest else slowest
    return None


def parse_driver_report(path: Path) -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        header = handle.readline().rstrip("\n")
        if header != "endpoint|term_ptr|net_name|connected_terms|connected_cells":
            raise ValueError("unexpected endpoint-driver report header")
        for line_number, raw in enumerate(handle, 2):
            parts = raw.rstrip("\n").split("|")
            if len(parts) != 5:
                raise ValueError(f"line {line_number}: expected 5 pipe fields")
            endpoint, terms, cells = parts[0], parts[3], parts[4]
            term_tokens = terms.replace("{", "").replace("}", "").split()
            cell_tokens = cells.replace("{", "").replace("}", "").split()
            if len(term_tokens) != len(cell_tokens) or len(term_tokens) < 2:
                raise ValueError(f"line {line_number}: term/cell list mismatch")
            pairs = list(zip(term_tokens, cell_tokens, strict=True))
            output_pin_names = {"Y", "Q", "QN", "Z", "ZN", "CO"}
            drivers = [
                (term, cell)
                for term, cell in pairs
                if term != endpoint and term.rsplit("/", 1)[-1] in output_pin_names
            ]
            if len(drivers) != 1:
                raise ValueError(
                    f"line {line_number}: expected one driver for {endpoint}, got {drivers}"
                )
            driver_pin, old_cell = drivers[0]
            new_cell = slower_cell(old_cell)
            if new_cell is not None:
                rows.append((endpoint, driver_pin.rsplit("/", 1)[0], old_cell, new_cell))
    if not rows:
        raise ValueError("no swappable hold-path drivers found")
    instances = [row[1] for row in rows]
    if len(instances) != len(set(instances)):
        raise ValueError("one driver instance appears in multiple plan rows")
    return rows


def atomic_write(path: Path, rows: list[tuple[str, str, str, str]]) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(["endpoint", "instance", "old_cell", "new_cell"])
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        payload = temp_path.read_bytes()
        os.replace(temp_path, path)
        return payload
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("driver_report", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--expected-count", type=int)
    args = parser.parse_args()
    rows = parse_driver_report(args.driver_report)
    if args.expected_count is not None and len(rows) != args.expected_count:
        raise SystemExit(
            f"swap count mismatch: expected {args.expected_count}, got {len(rows)}"
        )
    payload = atomic_write(args.output_csv, rows)
    print(
        f"HOLD_DRIVER_SWAP_PLAN: PASS count={len(rows)} "
        f"sha256={hashlib.sha256(payload).hexdigest()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
