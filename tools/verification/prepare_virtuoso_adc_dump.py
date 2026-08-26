#!/usr/bin/env python3
"""Validate and normalize a Virtuoso/Spectre ADC dump for digital replay."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path


ADC_BITS = 12
ADC_MASK = (1 << ADC_BITS) - 1
ADC_SIGN = 1 << (ADC_BITS - 1)


class DumpError(ValueError):
    pass


def parse_integer(token: str) -> int:
    value = token.strip().replace("_", "")
    if not value:
        raise DumpError("empty ADC code")
    try:
        if value.lower().startswith("0x"):
            return int(value, 16)
        if any(ch in "abcdefABCDEF" for ch in value):
            return int(value, 16)
        return int(value, 10)
    except ValueError as exc:
        raise DumpError(f"invalid ADC code: {token!r}") from exc


def to_signed_bits(code: int, encoding: str) -> tuple[int, int]:
    if encoding == "offset_binary":
        if not 0 <= code <= ADC_MASK:
            raise DumpError(f"offset-binary code out of range: {code}")
        bits = code ^ ADC_SIGN
    elif encoding == "twos_complement":
        if -(1 << (ADC_BITS - 1)) <= code < (1 << (ADC_BITS - 1)):
            bits = code & ADC_MASK
        elif 0 <= code <= ADC_MASK:
            bits = code
        else:
            raise DumpError(f"two's-complement code out of range: {code}")
    else:
        raise DumpError(f"unsupported encoding: {encoding}")
    signed = bits if bits < ADC_SIGN else bits - (1 << ADC_BITS)
    return bits, signed


def parse_mem(path: Path, encoding: str) -> tuple[list[int], list[int], dict[str, object]]:
    bits_values: list[int] = []
    signed_values: list[int] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].split("//", 1)[0].strip()
        if not line:
            continue
        tokens = line.split()
        if len(tokens) != 1:
            raise DumpError(f"{path.name}:{line_number}: expected one ADC token")
        token = tokens[0].replace("_", "")
        if token.lower().startswith("0x"):
            token = token[2:]
        if not token or len(token) > 3 or any(ch not in "0123456789abcdefABCDEF" for ch in token):
            raise DumpError(
                f"{path.name}:{line_number}: MEM tokens must be 1-3 hexadecimal digits"
            )
        # A readmemh-style token such as 800 means hexadecimal 0x800, not
        # decimal 800.  CSV remains the human-facing decimal/0x input format.
        bits, signed = to_signed_bits(int(token, 16), encoding)
        bits_values.append(bits)
        signed_values.append(signed)
    if not bits_values:
        raise DumpError("ADC dump contains no samples")
    return bits_values, signed_values, {"cadence_checked": False}


def parse_csv_dump(
    path: Path,
    encoding: str,
    sample_rate_hz: int,
    cadence_tolerance_sec: Decimal,
) -> tuple[list[int], list[int], dict[str, object]]:
    bits_values: list[int] = []
    signed_values: list[int] = []
    times: list[Decimal] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise DumpError("CSV header is missing")
        normalized = {name.strip().lower(): name for name in reader.fieldnames}
        if "time_sec" not in normalized or "adc_code" not in normalized:
            raise DumpError("CSV requires time_sec and adc_code columns")
        for row_number, row in enumerate(reader, 2):
            try:
                time_value = Decimal(row[normalized["time_sec"]].strip())
            except (InvalidOperation, AttributeError) as exc:
                raise DumpError(f"{path.name}:{row_number}: invalid time_sec") from exc
            bits, signed = to_signed_bits(
                parse_integer(row[normalized["adc_code"]]), encoding
            )
            if times and time_value <= times[-1]:
                raise DumpError(
                    f"{path.name}:{row_number}: non-increasing or duplicate timestamp"
                )
            times.append(time_value)
            bits_values.append(bits)
            signed_values.append(signed)
    if not bits_values:
        raise DumpError("ADC CSV contains no samples")

    expected_period = Decimal(1) / Decimal(sample_rate_hz)
    worst_error = Decimal(0)
    for index in range(1, len(times)):
        error = abs((times[index] - times[index - 1]) - expected_period)
        worst_error = max(worst_error, error)
        if error > cadence_tolerance_sec:
            raise DumpError(
                f"cadence error at sample {index}: error={error} sec "
                f"tolerance={cadence_tolerance_sec} sec"
            )
    return bits_values, signed_values, {
        "cadence_checked": True,
        "first_time_sec": str(times[0]),
        "last_time_sec": str(times[-1]),
        "expected_period_sec": str(expected_period),
        "worst_period_error_sec": str(worst_error),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def normalize(args: argparse.Namespace) -> dict[str, object]:
    source = args.input.resolve()
    if not source.is_file():
        raise DumpError(f"input file not found: {source}")
    input_format = args.format
    if input_format == "auto":
        input_format = "csv" if source.suffix.lower() == ".csv" else "mem"

    tolerance = Decimal(args.cadence_tolerance_sec)
    if input_format == "csv":
        bits, signed, cadence = parse_csv_dump(
            source, args.encoding, args.sample_rate_hz, tolerance
        )
    elif input_format == "mem":
        bits, signed, cadence = parse_mem(source, args.encoding)
    else:
        raise DumpError(f"unsupported input format: {input_format}")

    if args.expected_samples is not None and len(bits) != args.expected_samples:
        raise DumpError(
            f"sample count mismatch: expected {args.expected_samples}, got {len(bits)}"
        )
    if args.require_cadence and not cadence["cadence_checked"]:
        raise DumpError("cadence validation requires CSV time_sec data")

    mem_payload = ("\n".join(f"{value:03x}" for value in bits) + "\n").encode("ascii")
    metadata = {
        "schema_version": 1,
        "source_name": source.name,
        "source_sha256": sha256_file(source),
        "input_format": input_format,
        "input_encoding": args.encoding,
        "output_encoding": "signed_twos_complement_12bit_hex",
        "sample_rate_hz": args.sample_rate_hz,
        "sample_count": len(bits),
        "signed_min": min(signed),
        "signed_max": max(signed),
        "output_sha256": hashlib.sha256(mem_payload).hexdigest(),
        **cadence,
    }
    atomic_write(args.output, mem_payload)
    atomic_write(
        args.metadata,
        (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return metadata


def self_test() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        csv_path = root / "adc.csv"
        csv_path.write_text(
            "time_sec,adc_code\n0.000,2048\n0.001,2049\n0.002,2047\n",
            encoding="utf-8",
        )
        args = argparse.Namespace(
            input=csv_path,
            output=root / "out.mem",
            metadata=root / "out.json",
            format="csv",
            encoding="offset_binary",
            sample_rate_hz=1000,
            cadence_tolerance_sec="0.000000001",
            expected_samples=3,
            require_cadence=True,
        )
        result = normalize(args)
        assert (root / "out.mem").read_text(encoding="ascii") == "000\n001\nfff\n"
        assert result["signed_min"] == -1 and result["signed_max"] == 1

        mem_path = root / "signed.mem"
        mem_path.write_text("000\n7ff\n800\nfff\n", encoding="utf-8")
        args.input = mem_path
        args.output = root / "signed_out.mem"
        args.metadata = root / "signed_out.json"
        args.format = "mem"
        args.encoding = "twos_complement"
        args.expected_samples = 4
        args.require_cadence = False
        result = normalize(args)
        assert result["signed_min"] == -2048 and result["signed_max"] == 2047

        bad_path = root / "bad.csv"
        bad_path.write_text(
            "time_sec,adc_code\n0.000,2048\n0.0012,2049\n", encoding="utf-8"
        )
        args.input = bad_path
        args.format = "csv"
        args.encoding = "offset_binary"
        args.expected_samples = 2
        args.require_cadence = True
        try:
            normalize(args)
        except DumpError:
            pass
        else:
            raise AssertionError("cadence failure did not fail closed")
    print("PREPARE_VIRTUOSO_ADC_DUMP_SELF_TEST_PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--format", choices=("auto", "csv", "mem"), default="auto")
    parser.add_argument(
        "--encoding", choices=("offset_binary", "twos_complement"), default="offset_binary"
    )
    parser.add_argument("--sample-rate-hz", type=int, default=1000)
    parser.add_argument("--cadence-tolerance-sec", default="0.000000001")
    parser.add_argument("--expected-samples", type=int)
    parser.add_argument("--require-cadence", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if not args.self_test and (args.input is None or args.output is None or args.metadata is None):
        parser.error("--input, --output, and --metadata are required")
    if args.sample_rate_hz <= 0:
        parser.error("--sample-rate-hz must be positive")
    if args.expected_samples is not None and args.expected_samples <= 0:
        parser.error("--expected-samples must be positive")
    return args


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0
    try:
        metadata = normalize(args)
    except DumpError as exc:
        raise SystemExit(f"VIRTUOSO_ADC_PREP_FAIL: {exc}") from exc
    print(
        "VIRTUOSO_ADC_PREP_PASS "
        f"samples={metadata['sample_count']} min={metadata['signed_min']} "
        f"max={metadata['signed_max']} sha256={metadata['output_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
