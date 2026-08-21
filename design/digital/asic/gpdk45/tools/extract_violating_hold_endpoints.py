#!/usr/bin/env python3
"""Extract unique violated hold endpoint pins from an Innovus timing report."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import os
import re
import tempfile
from pathlib import Path


PATH_HEADER = re.compile(r"^Path\s+\d+:\s+(VIOLATED|MET)\s+Hold Check")
EDGE_MARKER = re.compile(r"\s*\([v^]\)(?:\s+checked|\s*$)")


def read_text(path: Path) -> str:
    if path.suffix.lower() == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", errors="strict") as handle:
            return handle.read()
    return path.read_text(encoding="utf-8", errors="strict")


def extract_endpoints(text: str) -> list[str]:
    endpoints: list[str] = []
    seen: set[str] = set()
    violated = False
    capture: list[str] | None = None

    for raw_line in text.splitlines():
        header = PATH_HEADER.match(raw_line)
        if header:
            violated = header.group(1) == "VIOLATED"
            capture = None
            continue

        if violated and raw_line.startswith("Endpoint:"):
            capture = [raw_line.split("Endpoint:", 1)[1].strip()]
        elif capture is not None and raw_line and not raw_line.startswith(("Beginpoint:", "Path Groups:")):
            capture.append(raw_line.strip())

        if capture is None:
            continue
        joined = "".join(capture)
        marker = EDGE_MARKER.search(joined)
        if marker is None:
            continue
        pin = joined[: marker.start()].strip()
        capture = None
        if not pin.endswith("/D"):
            raise ValueError(f"unexpected violated hold endpoint: {pin!r}")
        if pin not in seen:
            seen.add(pin)
            endpoints.append(pin)

    if not endpoints:
        raise ValueError("no violated hold endpoints found")
    return endpoints


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-count", type=int)
    args = parser.parse_args()

    endpoints = extract_endpoints(read_text(args.report))
    if args.expected_count is not None and len(endpoints) != args.expected_count:
        raise SystemExit(
            f"endpoint count mismatch: expected {args.expected_count}, got {len(endpoints)}"
        )

    payload = ("\n".join(endpoints) + "\n").encode("utf-8")
    atomic_write(args.output, payload)
    print(
        "HOLD_ENDPOINTS: PASS "
        f"count={len(endpoints)} sha256={hashlib.sha256(payload).hexdigest()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
