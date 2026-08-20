#!/usr/bin/env python3
"""Normalize an access-enabled Xcelium SAIF for deterministic Innovus import.

Xcelium ``dumpsaif`` can leave ``DESIGN`` blank, retain a testbench wrapper,
and print escaped multidimensional array names as multiple whitespace-separated
atoms.  Innovus then reports large numbers of SAIF syntax errors.  This tool
performs only the required structural normalization and publishes the result
with an atomic same-directory replace.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mmap
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


COPY_CHUNK_BYTES = 1024 * 1024
MAX_LINE_BYTES = 16 * 1024 * 1024
DEFAULT_MINIMUM_BYTES = 64
SAFE_INSTANCE_NAME = re.compile(r"^[A-Za-z_$][A-Za-z0-9_.$-]*$")
STATISTIC_FORM = re.compile(r"\(\s*(T0|T1|TX|TZ|TC|IG)\s+(\d+)\s*\)")
SECTION_LINE = re.compile(r"^\s*\((NET|PORT)\s*$")


class SaifNormalizeError(RuntimeError):
    """A structural, naming, or atomic-publication contract violation."""


@dataclass
class Atom:
    value: str
    start: int
    end: int


@dataclass
class FormSpan:
    head: str
    depth: int
    start: int
    end: int | None = None
    value: str | None = None
    value_start: int | None = None
    value_end: int | None = None


@dataclass
class InstanceSpan:
    name: str
    depth: int
    start: int
    name_start: int
    name_end: int
    end: int | None = None


@dataclass
class ScanResult:
    size: int
    root_form: FormSpan
    design_form: FormSpan
    instances: list[InstanceSpan]


@dataclass
class NormalizeResult:
    input_size: int
    output_size: int
    input_sha256: str
    output_sha256: str
    normalized_signal_names: int
    signal_entries: int
    full_x_entries: int
    full_z_entries: int
    retained_partial_tx: int
    dropped_full_x: int
    dropped_full_z: int
    full_xz_mode: str


@dataclass
class ActivityStats:
    signal_entries: int = 0
    full_x_entries: int = 0
    full_z_entries: int = 0
    partial_tx_entries: int = 0
    dropped_full_x: int = 0
    dropped_full_z: int = 0
    problematic_names: int = 0


@dataclass
class _OpenForm:
    form: FormSpan
    instance: InstanceSpan | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-saif", type=Path)
    parser.add_argument("--output-saif", type=Path)
    parser.add_argument("--top")
    parser.add_argument("--tb-instance")
    parser.add_argument("--dut-instance")
    parser.add_argument("--minimum-bytes", type=int, default=DEFAULT_MINIMUM_BYTES)
    parser.add_argument(
        "--drop-full-xz",
        action="store_true",
        help="explicitly drop only entries fully X or Z for the complete DURATION",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(COPY_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _skip_space(data: mmap.mmap, position: int, size: int) -> int:
    while position < size and data[position] in b" \t\r\n":
        position += 1
    return position


def _decode_quoted(data: mmap.mmap, start: int, size: int) -> Atom:
    position = start + 1
    output = bytearray()
    while position < size:
        value = data[position]
        if value == ord('"'):
            try:
                decoded = output.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise SaifNormalizeError(f"non-UTF-8 quoted atom at byte {start}") from exc
            return Atom(decoded, start, position + 1)
        if value == ord("\\"):
            position += 1
            if position >= size:
                raise SaifNormalizeError(f"unterminated quoted escape at byte {start}")
            escaped = data[position]
            if escaped in (ord('"'), ord("\\")):
                output.append(escaped)
            elif escaped == ord("n"):
                output.append(ord("\n"))
            elif escaped == ord("r"):
                output.append(ord("\r"))
            elif escaped == ord("t"):
                output.append(ord("\t"))
            else:
                output.extend((ord("\\"), escaped))
            position += 1
            continue
        output.append(value)
        position += 1
    raise SaifNormalizeError(f"unterminated quoted atom at byte {start}")


def _parse_atom(data: mmap.mmap, position: int, size: int) -> Atom | None:
    position = _skip_space(data, position, size)
    if position >= size or data[position] in (ord("("), ord(")")):
        return None
    if data[position] == ord('"'):
        return _decode_quoted(data, position, size)

    start = position
    while position < size:
        value = data[position]
        if value in b" \t\r\n()":
            break
        if value == ord("\\") and position + 1 < size:
            position += 2
        else:
            position += 1
    if position == start:
        return None
    try:
        decoded = data[start:position].decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise SaifNormalizeError(f"non-UTF-8 atom at byte {start}") from exc
    return Atom(decoded, start, position)


def _validate_design_scalar(data: mmap.mmap, form: FormSpan) -> None:
    if form.end is None:
        raise SaifNormalizeError("DESIGN form was not closed")
    raw = data[form.start : form.end].decode("utf-8", errors="strict")
    pattern = re.compile(
        r'^\(\s*DESIGN(?:\s+(?:"(?:\\.|[^"\\])*"|[^\s()]+))?\s*\)$',
        re.S,
    )
    if not pattern.fullmatch(raw):
        raise SaifNormalizeError("DESIGN must contain zero or one scalar value")


def scan_saif(path: Path) -> ScanResult:
    """Scan S-expression structure without loading the complete SAIF into RAM."""

    try:
        size = path.stat().st_size
    except OSError as exc:
        raise SaifNormalizeError(f"cannot stat SAIF {path}: {exc}") from exc
    if size <= 0:
        raise SaifNormalizeError(f"SAIF is empty: {path}")

    roots: list[FormSpan] = []
    designs: list[FormSpan] = []
    instances: list[InstanceSpan] = []
    stack: list[_OpenForm] = []
    with path.open("rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
        if data.find(b"\x00") != -1:
            raise SaifNormalizeError("SAIF contains a NUL byte")
        position = 0
        while position < size:
            value = data[position]
            if value in b" \t\r\n":
                position += 1
                continue
            if value == ord(";"):
                newline = data.find(b"\n", position + 1)
                position = size if newline == -1 else newline + 1
                continue
            if value == ord('"'):
                atom = _decode_quoted(data, position, size)
                if not stack:
                    raise SaifNormalizeError(f"atom outside SAIFILE at byte {position}")
                position = atom.end
                continue
            if value == ord("("):
                depth = len(stack)
                head_atom = _parse_atom(data, position + 1, size)
                if head_atom is None:
                    raise SaifNormalizeError(f"empty S-expression at byte {position}")
                form = FormSpan(head_atom.value, depth, position)
                instance: InstanceSpan | None = None
                if depth == 0:
                    roots.append(form)
                if head_atom.value.upper() == "DESIGN" and depth == 1:
                    scalar = _parse_atom(data, head_atom.end, size)
                    if scalar is not None:
                        form.value = scalar.value
                        form.value_start = scalar.start
                        form.value_end = scalar.end
                    designs.append(form)
                if head_atom.value.upper() == "INSTANCE":
                    first_name_atom = _parse_atom(data, head_atom.end, size)
                    if first_name_atom is None:
                        raise SaifNormalizeError(f"INSTANCE lacks a name at byte {position}")
                    name_atom = first_name_atom
                    if data[first_name_atom.start] == ord('"'):
                        second_name_atom = _parse_atom(data, first_name_atom.end, size)
                        if second_name_atom is None:
                            raise SaifNormalizeError(
                                f"typed INSTANCE lacks an instance name at byte {position}"
                            )
                        name_atom = second_name_atom
                    if depth <= 2:
                        instance = InstanceSpan(
                            name=name_atom.value,
                            depth=depth,
                            start=position,
                            name_start=first_name_atom.start,
                            name_end=name_atom.end,
                        )
                        instances.append(instance)
                stack.append(_OpenForm(form=form, instance=instance))
                position += 1
                continue
            if value == ord(")"):
                if not stack:
                    raise SaifNormalizeError(f"unmatched ')' at byte {position}")
                opened = stack.pop()
                opened.form.end = position + 1
                if opened.instance is not None:
                    opened.instance.end = position + 1
                position += 1
                continue

            atom = _parse_atom(data, position, size)
            if atom is None:
                raise SaifNormalizeError(f"invalid token at byte {position}")
            if not stack:
                raise SaifNormalizeError(f"atom outside SAIFILE at byte {position}")
            position = atom.end

        if stack:
            opened = stack[-1].form
            raise SaifNormalizeError(
                f"unclosed {opened.head} S-expression from byte {opened.start}"
            )
        if len(roots) != 1 or roots[0].head.upper() != "SAIFILE":
            raise SaifNormalizeError("SAIF must contain exactly one outer SAIFILE form")
        if len(designs) != 1:
            raise SaifNormalizeError(f"SAIF must contain exactly one DESIGN form, got {len(designs)}")
        _validate_design_scalar(data, designs[0])

    return ScanResult(size=size, root_form=roots[0], design_form=designs[0], instances=instances)


def _require_safe_name(value: str, label: str) -> None:
    if not SAFE_INSTANCE_NAME.fullmatch(value):
        raise SaifNormalizeError(f"{label} is not a safe SAIF atom: {value!r}")


def _select_input_spans(
    scan: ScanResult,
    *,
    tb_instance: str,
    dut_instance: str,
) -> tuple[InstanceSpan, InstanceSpan]:
    design = scan.design_form.value
    if design not in (None, ""):
        raise SaifNormalizeError(
            f"input DESIGN must be blank before normalization, got {design!r}"
        )
    roots = [instance for instance in scan.instances if instance.depth == 1]
    if len(roots) != 1:
        raise SaifNormalizeError(f"expected exactly one outer INSTANCE, got {len(roots)}")
    outer = roots[0]
    if outer.name != tb_instance:
        raise SaifNormalizeError(
            f"outer INSTANCE mismatch: {outer.name!r} != {tb_instance!r}"
        )
    direct_duts = [
        instance
        for instance in scan.instances
        if instance.depth == 2
        and instance.name == dut_instance
        and instance.start > outer.start
        and instance.end is not None
        and outer.end is not None
        and instance.end < outer.end
    ]
    if len(direct_duts) != 1:
        raise SaifNormalizeError(
            f"expected exactly one direct DUT INSTANCE {dut_instance!r}, got {len(direct_duts)}"
        )
    dut = direct_duts[0]
    if outer.end is None or dut.end is None:
        raise SaifNormalizeError("selected INSTANCE span is not closed")
    if not (
        scan.design_form.end is not None
        and scan.design_form.end < outer.start < dut.start < dut.end < outer.end
    ):
        raise SaifNormalizeError("DESIGN/TB/DUT spans are not strictly nested and ordered")
    return outer, dut


def _validate_instance_body_starts_with_form(path: Path, instance: InstanceSpan) -> None:
    if instance.end is None:
        raise SaifNormalizeError(f"INSTANCE {instance.name!r} is not closed")
    with path.open("rb") as handle, mmap.mmap(
        handle.fileno(), 0, access=mmap.ACCESS_READ
    ) as data:
        position = _skip_space(data, instance.name_end, len(data))
        if position >= instance.end or data[position] not in (ord("("), ord(")")):
            raise SaifNormalizeError(
                f"INSTANCE {instance.name!r} body must start with a child form or close"
            )


def _paren_delta(line: str) -> int:
    delta = 0
    quoted = False
    escaped = False
    position = 0
    while position < len(line):
        character = line[position]
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
            position += 1
            continue
        if character == ";":
            break
        if character == '"':
            quoted = True
        elif character == "\\" and position + 1 < len(line):
            position += 2
            continue
        elif character == "(":
            delta += 1
        elif character == ")":
            delta -= 1
        position += 1
    if quoted:
        raise SaifNormalizeError("quoted SAIF atom crosses a physical line")
    return delta


def _has_problematic_bracket_escape(encoded_name: str) -> bool:
    return re.search(r"\\+[\[\]]", encoded_name) is not None


def _normalize_encoded_signal_name(encoded_name: str) -> str:
    joined = re.sub(r"\s+", "", encoded_name)
    normalized = re.sub(r"^\\+", "", joined)
    normalized = re.sub(r"\\+([\[\]])", r"\1", normalized)
    if "\\" in normalized:
        raise SaifNormalizeError(
            f"unsupported residual escape in Xcelium signal name: {encoded_name!r}"
        )
    dimensions = re.findall(r"\[([^\[\]\s()\"]+)\]", normalized)
    base = re.sub(r"\[[^\[\]\s()\"]+\]", "", normalized)
    if (
        not dimensions
        or not base
        or any(character in base for character in "[]()\" \t\r\n")
        or normalized != base + "".join(f"[{index}]" for index in dimensions)
    ):
        raise SaifNormalizeError(
            f"unsupported escaped-bracket signal name: {encoded_name!r}"
        )
    return normalized


def _process_signal_entry(
    entry: str,
    *,
    duration: int,
    drop_full_xz: bool,
    transform_names: bool,
    stats: ActivityStats,
) -> tuple[str | None, int]:
    statistic_matches = list(STATISTIC_FORM.finditer(entry))
    if not statistic_matches:
        raise SaifNormalizeError("NET/PORT child lacks SAIF T0/T1/TX/TZ/TC statistics")
    open_index = entry.find("(")
    if open_index < 0:
        raise SaifNormalizeError("signal entry lacks opening parenthesis")
    first_stat = statistic_matches[0]
    name_region = entry[open_index + 1 : first_stat.start()]
    encoded_name = name_region.strip()
    if not encoded_name:
        raise SaifNormalizeError("signal entry lacks a name")

    values: dict[str, int] = {}
    for match in statistic_matches:
        key = match.group(1)
        value = int(match.group(2))
        if key in values and values[key] != value:
            raise SaifNormalizeError(f"conflicting {key} statistics for {encoded_name!r}")
        values[key] = value
    missing = [key for key in ("T0", "T1", "TC") if key not in values]
    if missing:
        raise SaifNormalizeError(f"signal entry {encoded_name!r} lacks statistics {missing}")

    stats.signal_entries += 1
    tx = values.get("TX", 0)
    tz = values.get("TZ", 0)
    full_x = values["T0"] == values["T1"] == values["TC"] == 0 and tx == duration
    full_z = values["T0"] == values["T1"] == values["TC"] == 0 and tz == duration
    if full_x:
        stats.full_x_entries += 1
    if full_z:
        stats.full_z_entries += 1
    if 0 < tx < duration:
        stats.partial_tx_entries += 1

    problematic = _has_problematic_bracket_escape(encoded_name)
    if problematic:
        stats.problematic_names += 1
    normalized_count = 0
    if transform_names and problematic:
        normalized_name = _normalize_encoded_signal_name(encoded_name)
        leading = re.match(r"\s*", name_region).group(0)  # type: ignore[union-attr]
        trailing = re.search(r"\s*$", name_region).group(0)  # type: ignore[union-attr]
        entry = (
            entry[: open_index + 1]
            + leading
            + json.dumps(normalized_name, ensure_ascii=True)
            + trailing
            + entry[first_stat.start() :]
        )
        normalized_count = 1

    if drop_full_xz and (full_x or full_z):
        stats.dropped_full_x += int(full_x)
        stats.dropped_full_z += int(full_z)
        return None, normalized_count
    return entry, normalized_count


class _SaifStreamProcessor:
    """Process complete direct NET/PORT child forms, including multiline names."""

    def __init__(
        self,
        output: BinaryIO | None,
        *,
        duration: int,
        drop_full_xz: bool,
        transform_names: bool,
    ):
        self.output = output
        self.duration = duration
        self.drop_full_xz = drop_full_xz
        self.transform_names = transform_names
        self.buffer = bytearray()
        self.normalized_signal_names = 0
        self.stats = ActivityStats()
        self.depth = 0
        self.section_depth: int | None = None
        self.entry_depth: int | None = None
        self.entry_parts: list[str] = []
        self.entry_bytes = 0

    def _write(self, text: str) -> None:
        if self.output is not None:
            self.output.write(text.encode("utf-8"))

    def _finish_entry(self) -> None:
        entry = "".join(self.entry_parts)
        processed, changed = _process_signal_entry(
            entry,
            duration=self.duration,
            drop_full_xz=self.drop_full_xz,
            transform_names=self.transform_names,
            stats=self.stats,
        )
        self.normalized_signal_names += changed
        if processed is not None:
            self._write(processed)
        self.entry_depth = None
        self.entry_parts.clear()
        self.entry_bytes = 0

    def _consume_line(self, line: str, *, newline: bool) -> None:
        logical = line + ("\n" if newline else "")
        before = self.depth
        delta = _paren_delta(line)
        stripped = line.strip()

        if self.entry_depth is not None:
            self.entry_parts.append(logical)
            self.entry_bytes += len(logical.encode("utf-8"))
            if self.entry_bytes > MAX_LINE_BYTES:
                raise SaifNormalizeError(
                    f"one NET/PORT signal entry exceeds {MAX_LINE_BYTES} bytes"
                )
            self.depth += delta
            if self.depth < self.entry_depth:
                raise SaifNormalizeError("signal entry closes outside its NET/PORT section")
            if self.depth == self.entry_depth:
                self._finish_entry()
            return

        section_prefix = re.match(r"^\s*\((NET|PORT)\b", line)
        if section_prefix and not SECTION_LINE.fullmatch(line):
            raise SaifNormalizeError(
                "inline NET/PORT content is unsupported; refusing partial name normalization"
            )
        if self.section_depth is not None and before == self.section_depth + 1:
            if stripped.startswith("("):
                self.entry_depth = before
                self.entry_parts = [logical]
                self.entry_bytes = len(logical.encode("utf-8"))
                self.depth += delta
                if self.depth < self.entry_depth:
                    raise SaifNormalizeError("invalid direct NET/PORT child structure")
                if self.depth == self.entry_depth:
                    self._finish_entry()
                return

        self._write(logical)
        if SECTION_LINE.fullmatch(line):
            if self.section_depth is not None:
                raise SaifNormalizeError("nested NET/PORT sections are unsupported")
            self.section_depth = before
        self.depth += delta
        if self.depth < 0:
            raise SaifNormalizeError("streaming SAIF depth became negative")
        if self.section_depth is not None and self.depth == self.section_depth:
            self.section_depth = None

    def feed(self, payload: bytes) -> None:
        self.buffer.extend(payload)
        if len(self.buffer) > MAX_LINE_BYTES and b"\n" not in self.buffer:
            raise SaifNormalizeError(f"SAIF line exceeds {MAX_LINE_BYTES} bytes")
        while True:
            index = self.buffer.find(b"\n")
            if index < 0:
                break
            raw = bytes(self.buffer[:index])
            del self.buffer[: index + 1]
            if raw.endswith(b"\r"):
                raw = raw[:-1]
            try:
                line = raw.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise SaifNormalizeError("SAIF contains a non-UTF-8 line") from exc
            self._consume_line(line, newline=True)

    def finish(self) -> None:
        if self.buffer:
            raw = bytes(self.buffer)
            if raw.endswith(b"\r"):
                raw = raw[:-1]
            try:
                line = raw.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise SaifNormalizeError("SAIF contains a non-UTF-8 final line") from exc
            self._consume_line(line, newline=False)
            self.buffer.clear()
        if self.entry_depth is not None:
            raise SaifNormalizeError("unterminated NET/PORT signal entry")
        if self.section_depth is not None:
            raise SaifNormalizeError("unterminated NET/PORT section")


def _emit_range(
    source: BinaryIO,
    writer: _SaifStreamProcessor,
    start: int,
    end: int,
) -> None:
    if start < 0 or end < start:
        raise SaifNormalizeError(f"invalid copy range: {start}:{end}")
    source.seek(start)
    remaining = end - start
    while remaining:
        chunk = source.read(min(COPY_CHUNK_BYTES, remaining))
        if not chunk:
            raise SaifNormalizeError(f"unexpected EOF in copy range {start}:{end}")
        writer.feed(chunk)
        remaining -= len(chunk)


def _read_duration(path: Path) -> int:
    values: set[int] = set()
    try:
        with path.open("r", encoding="utf-8", errors="strict", newline=None) as handle:
            for line in handle:
                match = re.fullmatch(r"\s*\(DURATION\s+(\d+)\s*\)\s*", line)
                if match:
                    values.add(int(match.group(1)))
    except (OSError, UnicodeDecodeError) as exc:
        raise SaifNormalizeError(f"cannot read SAIF DURATION: {exc}") from exc
    if len(values) != 1 or next(iter(values)) <= 0:
        raise SaifNormalizeError(f"SAIF must contain one positive DURATION, got {values}")
    return next(iter(values))


def _scan_activity_stats(path: Path, *, duration: int) -> ActivityStats:
    processor = _SaifStreamProcessor(
        None,
        duration=duration,
        drop_full_xz=False,
        transform_names=False,
    )
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(COPY_CHUNK_BYTES), b""):
                processor.feed(chunk)
        processor.finish()
    except OSError as exc:
        raise SaifNormalizeError(f"cannot scan SAIF activity entries: {exc}") from exc
    return processor.stats


def _validate_output_structure(
    path: Path,
    *,
    top: str,
    minimum_bytes: int,
    duration: int,
    drop_full_xz: bool,
) -> tuple[ScanResult, ActivityStats]:
    size = path.stat().st_size
    if size < minimum_bytes:
        raise SaifNormalizeError(
            f"normalized SAIF is too small: {size} < minimum {minimum_bytes} bytes"
        )
    scan = scan_saif(path)
    if scan.design_form.value != top:
        raise SaifNormalizeError(
            f"normalized DESIGN mismatch: {scan.design_form.value!r} != {top!r}"
        )
    roots = [instance for instance in scan.instances if instance.depth == 1]
    if len(roots) != 1 or roots[0].name != top:
        raise SaifNormalizeError(
            f"normalized root INSTANCE must be exactly {top!r}, got {[item.name for item in roots]}"
        )
    _validate_instance_body_starts_with_form(path, roots[0])
    activity = _scan_activity_stats(path, duration=duration)
    if activity.signal_entries <= 0:
        raise SaifNormalizeError("normalized SAIF contains no NET/PORT signal entries")
    if activity.problematic_names:
        raise SaifNormalizeError(
            f"normalized SAIF retains {activity.problematic_names} escaped-bracket signal names"
        )
    if drop_full_xz and (activity.full_x_entries or activity.full_z_entries):
        raise SaifNormalizeError(
            "drop-full-xz output retains fully-X/Z signal entries: "
            f"X={activity.full_x_entries} Z={activity.full_z_entries}"
        )
    return scan, activity


def normalize_saif(
    input_saif: Path,
    output_saif: Path,
    *,
    top: str,
    tb_instance: str,
    dut_instance: str,
    minimum_bytes: int = DEFAULT_MINIMUM_BYTES,
    force: bool = False,
    drop_full_xz: bool = False,
) -> NormalizeResult:
    if minimum_bytes <= 0:
        raise SaifNormalizeError("minimum_bytes must be positive")
    for value, label in (
        (top, "top"),
        (tb_instance, "tb_instance"),
        (dut_instance, "dut_instance"),
    ):
        _require_safe_name(value, label)

    input_path = input_saif.resolve(strict=True)
    output_path = output_saif.resolve(strict=False)
    if input_path == output_path:
        raise SaifNormalizeError("input and output SAIF paths must differ")
    if not input_path.is_file():
        raise SaifNormalizeError(f"input SAIF is not a regular file: {input_path}")
    input_size = input_path.stat().st_size
    if input_size < minimum_bytes:
        raise SaifNormalizeError(
            f"input SAIF is too small: {input_size} < minimum {minimum_bytes} bytes"
        )
    if output_path.exists() and not force:
        raise SaifNormalizeError(f"output already exists; pass --force to replace: {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot: Path | None = None
    temporary: Path | None = None
    try:
        with input_path.open("rb") as original:
            snapshot_fd, snapshot_name = tempfile.mkstemp(
                prefix=f".{output_path.name}.input-snapshot-",
                suffix=".tmp",
                dir=output_path.parent,
            )
            snapshot = Path(snapshot_name)
            input_digest = hashlib.sha256()
            snapshot_size = 0
            with os.fdopen(snapshot_fd, "wb") as snapshot_handle:
                for chunk in iter(lambda: original.read(COPY_CHUNK_BYTES), b""):
                    snapshot_handle.write(chunk)
                    input_digest.update(chunk)
                    snapshot_size += len(chunk)
                snapshot_handle.flush()
                os.fsync(snapshot_handle.fileno())
        if snapshot_size != input_size:
            raise SaifNormalizeError(
                f"input SAIF changed size while snapshotting: {input_size} -> {snapshot_size}"
            )
        input_hash = input_digest.hexdigest()
        input_scan = scan_saif(snapshot)
        duration = _read_duration(snapshot)
        outer, dut = _select_input_spans(
            input_scan, tb_instance=tb_instance, dut_instance=dut_instance
        )
        _validate_instance_body_starts_with_form(snapshot, outer)
        _validate_instance_body_starts_with_form(snapshot, dut)
        if input_scan.design_form.end is None or outer.end is None or dut.end is None:
            raise SaifNormalizeError("required input span is incomplete")

        output_fd, temporary_name = tempfile.mkstemp(
            prefix=f".{output_path.name}.partial-",
            suffix=".tmp",
            dir=output_path.parent,
        )
        temporary = Path(temporary_name)
        with snapshot.open("rb") as source, os.fdopen(output_fd, "wb") as destination:
            writer = _SaifStreamProcessor(
                destination,
                duration=duration,
                drop_full_xz=drop_full_xz,
                transform_names=True,
            )
            _emit_range(source, writer, 0, input_scan.design_form.start)
            writer.feed(f'(DESIGN "{top}")'.encode("utf-8"))
            _emit_range(
                source,
                writer,
                input_scan.design_form.end,
                outer.start,
            )
            writer.feed(f"(INSTANCE {top}".encode("utf-8"))
            _emit_range(source, writer, dut.name_end, dut.end)
            _emit_range(source, writer, outer.end, input_scan.size)
            writer.finish()
            destination.flush()
            os.fsync(destination.fileno())

        _, output_activity = _validate_output_structure(
            temporary,
            top=top,
            minimum_bytes=minimum_bytes,
            duration=duration,
            drop_full_xz=drop_full_xz,
        )
        output_size = temporary.stat().st_size
        output_hash = sha256_file(temporary)
        if input_hash == output_hash:
            raise SaifNormalizeError("normalized SAIF is byte-identical to input")
        if writer.stats.problematic_names != writer.normalized_signal_names:
            raise SaifNormalizeError(
                "not every problematic escaped-bracket name was normalized: "
                f"seen={writer.stats.problematic_names} normalized={writer.normalized_signal_names}"
            )
        if not drop_full_xz:
            if (
                output_activity.signal_entries != writer.stats.signal_entries
                or output_activity.full_x_entries != writer.stats.full_x_entries
                or output_activity.full_z_entries != writer.stats.full_z_entries
                or writer.stats.dropped_full_x
                or writer.stats.dropped_full_z
            ):
                raise SaifNormalizeError("preserve-mode X/Z activity counts changed")
        elif (
            writer.stats.dropped_full_x != writer.stats.full_x_entries
            or writer.stats.dropped_full_z != writer.stats.full_z_entries
        ):
            raise SaifNormalizeError("drop-full-xz mode did not drop every fully-X/Z entry")

        if force:
            os.replace(temporary, output_path)
        else:
            try:
                os.link(temporary, output_path)
            except FileExistsError as exc:
                raise SaifNormalizeError(
                    f"output appeared during normalization; refusing replacement: {output_path}"
                ) from exc
            temporary.unlink()
        return NormalizeResult(
            input_size=snapshot_size,
            output_size=output_size,
            input_sha256=input_hash,
            output_sha256=output_hash,
            normalized_signal_names=writer.normalized_signal_names,
            signal_entries=writer.stats.signal_entries,
            full_x_entries=writer.stats.full_x_entries,
            full_z_entries=writer.stats.full_z_entries,
            retained_partial_tx=output_activity.partial_tx_entries,
            dropped_full_x=writer.stats.dropped_full_x,
            dropped_full_z=writer.stats.dropped_full_z,
            full_xz_mode="drop" if drop_full_xz else "preserve",
        )
    except Exception:
        raise
    finally:
        for candidate in (temporary, snapshot):
            if candidate is not None:
                try:
                    candidate.unlink(missing_ok=True)
                except OSError:
                    pass


def _synthetic_saif(*, design: str = "", duplicate_dut: bool = False) -> str:
    design_atom = f'"{design}"' if design else ""
    duplicate = (
        "    (INSTANCE \"snn_ecg_asic_core_top\" dut\n"
        "      (NET\n"
        "        (duplicate (T0 1) (T1 0) (TX 0) (TC 0) (IG 0))\n"
        "      )\n"
        "    )\n"
        if duplicate_dut
        else ""
    )
    return (
        "(SAIFILE\n"
        "  (SAIFVERSION \"2.0\")\n"
        "  (DIRECTION \"backward\")\n"
        f"  (DESIGN {design_atom})\n"
        "  (DIVIDER /)\n"
        "  (TIMESCALE 1 ps)\n"
        "  (DURATION 1000)\n"
        "  (INSTANCE tb_power\n"
        "    (NET\n"
        "      (tb_only (T0 500) (T1 500) (TX 0) (TC 100) (IG 0))\n"
        "    )\n"
        "    (INSTANCE helper\n"
        "      (NET\n"
        "        (helper_only (T0 1) (T1 0) (TX 0) (TC 0) (IG 0))\n"
        "      )\n"
        "    )\n"
        "    (INSTANCE \"snn_ecg_asic_core_top\" dut\n"
        "      (NET\n"
        "        (clk (T0 500) (T1 500) (TX 0) (TC 100) (IG 0))\n"
        r"        (\bank_count[0] \[15\] (T0 700) (T1 300) (TX 0) (TC 8) (IG 0))" "\n"
        r"        (\\state\[2\] \\[3\] (T0 800) (T1 200) (TX 0) (TC 4) (IG 0))" "\n"
        r"        (\multiline[0]" "\n"
        r"          \[2\] (T0 900) (T1 100) (TX 0) (TZ 0) (TC 2) (IG 0))" "\n"
        r"        (\c24_mem_aff[0]_109218 (T0 600) (T1 400) (TX 0) (TZ 0) (TC 3) (IG 0))" "\n"
        "        (full_x (T0 0) (T1 0) (TX 1000) (TZ 0) (TC 0) (IG 0))\n"
        "        (full_z (T0 0) (T1 0) (TX 0) (TZ 1000) (TC 0) (IG 0))\n"
        "        (partial_tx (T0 990) (T1 0) (TX 10) (TZ 0) (TC 0) (IG 0))\n"
        "      )\n"
        "      (INSTANCE u_core\n"
        "        (NET\n"
        "          (state (T0 600) (T1 400) (TX 0) (TC 3) (IG 0))\n"
        "        )\n"
        "      )\n"
        "    )\n"
        f"{duplicate}"
        "  )\n"
        ")\n"
    )


def self_test() -> None:
    def check(condition: bool, message: str) -> None:
        if not condition:
            raise AssertionError(message)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "xcelium.saif"
        first = root / "innovus_first.saif"
        second = root / "innovus_second.saif"
        source.write_text(_synthetic_saif(), encoding="utf-8", newline="\n")

        result = normalize_saif(
            source,
            first,
            top="snn_ecg_asic_core_top",
            tb_instance="tb_power",
            dut_instance="dut",
        )
        check(result.normalized_signal_names == 3, "expected three normalized names")
        check(result.full_xz_mode == "preserve", "default must preserve full X/Z")
        check(result.full_x_entries == 1, "expected one fully-X entry")
        check(result.full_z_entries == 1, "expected one fully-Z entry")
        check(result.retained_partial_tx == 1, "partial startup TX must be retained")
        check(result.dropped_full_x == result.dropped_full_z == 0, "preserve mode dropped X/Z")
        text = first.read_text(encoding="utf-8")
        check('(DESIGN "snn_ecg_asic_core_top")' in text, "DESIGN was not replaced")
        check("(INSTANCE snn_ecg_asic_core_top" in text, "DUT was not promoted")
        check(
            "tb_power" not in text and "tb_only" not in text and "helper_only" not in text,
            "testbench siblings leaked into output",
        )
        check('("bank_count[0][15]" ' in text, "same-line multidimensional name failed")
        check('("state[2][3]" ' in text, "escaped multidimensional name failed")
        check('("multiline[0][2]" ' in text, "multiline dimension continuation failed")
        check(
            r"\c24_mem_aff[0]_109218" in text,
            "valid ordinary leading-backslash name was changed",
        )
        preserve_stats = _scan_activity_stats(first, duration=1000)
        check(preserve_stats.problematic_names == 0, "problematic name survived")

        repeated = normalize_saif(
            source,
            second,
            top="snn_ecg_asic_core_top",
            tb_instance="tb_power",
            dut_instance="dut",
        )
        check(result.output_sha256 == repeated.output_sha256, "output hash is nondeterministic")
        check(first.read_bytes() == second.read_bytes(), "output bytes are nondeterministic")

        dropped = root / "innovus_drop_xz.saif"
        drop_result = normalize_saif(
            source,
            dropped,
            top="snn_ecg_asic_core_top",
            tb_instance="tb_power",
            dut_instance="dut",
            drop_full_xz=True,
        )
        check(drop_result.full_xz_mode == "drop", "drop mode not recorded")
        check(drop_result.dropped_full_x == 1, "fully-X entry was not dropped")
        check(drop_result.dropped_full_z == 1, "fully-Z entry was not dropped")
        check(drop_result.retained_partial_tx == 1, "partial TX was incorrectly dropped")
        dropped_text = dropped.read_text(encoding="utf-8")
        check("(full_x " not in dropped_text, "fully-X entry remains")
        check("(full_z " not in dropped_text, "fully-Z entry remains")
        check("(partial_tx " in dropped_text, "partial TX entry was removed")

        try:
            normalize_saif(
                source,
                source,
                top="snn_ecg_asic_core_top",
                tb_instance="tb_power",
                dut_instance="dut",
            )
        except SaifNormalizeError:
            pass
        else:
            raise AssertionError("input==output must fail")

        nonblank = root / "nonblank.saif"
        nonblank_output = root / "nonblank_out.saif"
        nonblank.write_text(_synthetic_saif(design="wrong_top"), encoding="utf-8")
        try:
            normalize_saif(
                nonblank,
                nonblank_output,
                top="snn_ecg_asic_core_top",
                tb_instance="tb_power",
                dut_instance="dut",
            )
        except SaifNormalizeError:
            pass
        else:
            raise AssertionError("nonblank input DESIGN must fail")
        check(not nonblank_output.exists(), "nonblank-DESIGN output was published")

        duplicate = root / "duplicate.saif"
        duplicate_output = root / "duplicate_out.saif"
        duplicate.write_text(_synthetic_saif(duplicate_dut=True), encoding="utf-8")
        try:
            normalize_saif(
                duplicate,
                duplicate_output,
                top="snn_ecg_asic_core_top",
                tb_instance="tb_power",
                dut_instance="dut",
            )
        except SaifNormalizeError:
            pass
        else:
            raise AssertionError("duplicate direct DUT must fail")
        check(not duplicate_output.exists(), "duplicate-DUT output was published")

        inline = root / "inline.saif"
        inline_output = root / "inline_out.saif"
        inline.write_text(
            _synthetic_saif().replace(
                "      (NET\n        (clk (T0 500) (T1 500) (TX 0) (TC 100) (IG 0))\n",
                "      (NET (clk (T0 500) (T1 500) (TX 0) (TC 100) (IG 0))\n",
                1,
            ),
            encoding="utf-8",
        )
        try:
            normalize_saif(
                inline,
                inline_output,
                top="snn_ecg_asic_core_top",
                tb_instance="tb_power",
                dut_instance="dut",
            )
        except SaifNormalizeError:
            pass
        else:
            raise AssertionError("inline NET content must fail closed")
        check(not inline_output.exists(), "inline-NET output was published")

        unexpected = root / "unexpected_instance_atom.saif"
        unexpected_output = root / "unexpected_instance_atom_out.saif"
        unexpected.write_text(
            _synthetic_saif().replace(
                "    (INSTANCE \"snn_ecg_asic_core_top\" dut\n",
                "    (INSTANCE \"snn_ecg_asic_core_top\" dut unexpected\n",
                1,
            ),
            encoding="utf-8",
        )
        try:
            normalize_saif(
                unexpected,
                unexpected_output,
                top="snn_ecg_asic_core_top",
                tb_instance="tb_power",
                dut_instance="dut",
            )
        except SaifNormalizeError:
            pass
        else:
            raise AssertionError("unexpected INSTANCE body atom must fail")
        check(not unexpected_output.exists(), "malformed-INSTANCE output was published")

        unbalanced = root / "unbalanced.saif"
        protected_output = root / "protected.saif"
        unbalanced.write_text(_synthetic_saif()[:-3], encoding="utf-8")
        protected_output.write_text("preserve-existing-output\n", encoding="utf-8")
        try:
            normalize_saif(
                unbalanced,
                protected_output,
                top="snn_ecg_asic_core_top",
                tb_instance="tb_power",
                dut_instance="dut",
                force=True,
            )
        except SaifNormalizeError:
            pass
        else:
            raise AssertionError("unbalanced SAIF must fail")
        check(
            protected_output.read_text(encoding="utf-8") == "preserve-existing-output\n",
            "failed forced conversion damaged existing output",
        )

        try:
            normalize_saif(
                source,
                first,
                top="snn_ecg_asic_core_top",
                tb_instance="tb_power",
                dut_instance="dut",
            )
        except SaifNormalizeError:
            pass
        else:
            raise AssertionError("existing output without --force must fail")

        check(not list(root.glob(".*.tmp")), "temporary file leaked from self-test")

    print(
        "NORMALIZE_XCELIUM_SAIF_SELF_TEST_PASS "
        "normalized_signal_names=3 full_x=1 full_z=1 partial_tx=1"
    )


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0
    missing = [
        name
        for name in ("input_saif", "output_saif", "top", "tb_instance", "dut_instance")
        if getattr(args, name) is None
    ]
    if missing:
        raise SaifNormalizeError(
            "missing required arguments unless --self-test is used: " + ", ".join(missing)
        )
    result = normalize_saif(
        args.input_saif,
        args.output_saif,
        top=args.top,
        tb_instance=args.tb_instance,
        dut_instance=args.dut_instance,
        minimum_bytes=args.minimum_bytes,
        force=args.force,
        drop_full_xz=args.drop_full_xz,
    )
    print(f"INPUT_SAIF={args.input_saif.resolve()}")
    print(f"OUTPUT_SAIF={args.output_saif.resolve()}")
    print(f"INPUT_BYTES={result.input_size}")
    print(f"OUTPUT_BYTES={result.output_size}")
    print(f"INPUT_SHA256={result.input_sha256}")
    print(f"OUTPUT_SHA256={result.output_sha256}")
    print(f"NORMALIZED_SIGNAL_NAMES={result.normalized_signal_names}")
    print(f"SIGNAL_ENTRIES={result.signal_entries}")
    print(f"FULL_X_ENTRIES={result.full_x_entries}")
    print(f"FULL_Z_ENTRIES={result.full_z_entries}")
    print(f"RETAINED_PARTIAL_TX={result.retained_partial_tx}")
    print(f"DROPPED_FULL_X={result.dropped_full_x}")
    print(f"DROPPED_FULL_Z={result.dropped_full_z}")
    print(f"FULL_XZ_MODE={result.full_xz_mode}")
    print("NORMALIZE_XCELIUM_SAIF_PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SaifNormalizeError, OSError) as exc:
        print(f"NORMALIZE_XCELIUM_SAIF_FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
