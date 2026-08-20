#!/usr/bin/env python3
"""Build a deterministic, sanitized public package from local run-2 evidence.

The input is a locally retrieved *raw* run directory.  Only files named by the
explicit selection mapping below (or an explicitly supplied JSON mapping) may
cross the public boundary.  Netlists, SDF/SPEF/DEF, tool databases, PDK files,
waveform databases, and archives are rejected even if somebody adds them to a
mapping by mistake.

The builder writes into ``verification/asic_gpdk45_run2`` by default.  It
normalizes retained text to UTF-8/LF, redacts filesystem/user/host/license
identifiers, scans the completed package again, and creates deterministic
``SELECTION_MANIFEST.csv`` and ``CHECKSUMS.txt`` files.  No timestamp is put in
the output, so identical selected inputs and redaction options produce
identical bytes.

Mapping customization
---------------------
Edit ``DEFAULT_SELECTIONS`` for the stable run-2 raw-package layout, or pass a
JSON file with ``--mapping-json``.  A mapping file has this shape::

    {
      "selections": [
        {
          "sources": ["reports/core/ppa_summary.csv"],
          "destination": "core/results/ppa_summary.csv",
          "kind": "text",
          "required": true,
          "max_bytes": 2000000
        }
      ]
    }

``sources`` is an explicit ordered set of alternative relative paths.  Exactly
one candidate may exist.  Globs and directory copying are intentionally not
supported.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VERIFICATION_ROOT = REPOSITORY_ROOT / "verification"
DEFAULT_OUTPUT = VERIFICATION_ROOT / "asic_gpdk45_run2"

MAX_TEXT_BYTES = 2_000_000
MAX_GIF_BYTES = 5_000_000
ALLOWED_TEXT_SUFFIXES = {
    ".csv",
    ".json",
    ".log",
    ".manifest",
    ".md",
    ".rpt",
    ".txt",
    ".yaml",
    ".yml",
}
FORBIDDEN_SUFFIXES = {
    ".cdl",
    ".dat",
    ".db",
    ".def",
    ".do",
    ".enc",
    ".fsdb",
    ".gds",
    ".gz",
    ".lef",
    ".lib",
    ".netlist",
    ".nl",
    ".pdk",
    ".saif",
    ".sdc",
    ".sdf",
    ".shm",
    ".spef",
    ".sv",
    ".tar",
    ".tcf",
    ".tch",
    ".tcl",
    ".tgz",
    ".v",
    ".vcd",
    ".vh",
    ".zip",
}


@dataclass(frozen=True)
class Selection:
    """One explicit public-boundary file selection."""

    sources: tuple[str, ...]
    destination: str
    kind: str = "text"
    required: bool = True
    max_bytes: int = MAX_TEXT_BYTES


def select(
    source: str | Sequence[str],
    destination: str,
    *,
    kind: str = "text",
    required: bool = True,
    max_bytes: int | None = None,
) -> Selection:
    sources = (source,) if isinstance(source, str) else tuple(source)
    if max_bytes is None:
        max_bytes = MAX_GIF_BYTES if kind == "gif" else MAX_TEXT_BYTES
    return Selection(sources, destination, kind, required, max_bytes)


# This is the public evidence contract, not a filesystem discovery list.  The
# candidate lists are explicit alternatives for anticipated raw-package names.
# If the retrieved package uses another layout, update this tuple or provide a
# reviewed --mapping-json file.  Optional raw logs remain size-capped and pass
# through the same redaction and sensitive-token checks as required summaries.
DEFAULT_SELECTIONS: tuple[Selection, ...] = (
    select(("README_KR.md", "public/README_KR.md"), "README_KR.md"),
    select(("run_manifest.json", "public/run_manifest.json"), "run_manifest.json"),
    select(
        ("manifests/canonical_digital_36.manifest", "regression/canonical_digital_36.manifest"),
        "manifests/canonical_digital_36.manifest",
    ),
    select(
        ("manifests/raw_xmodel_4.manifest", "regression/raw_xmodel_4.manifest"),
        "manifests/raw_xmodel_4.manifest",
    ),
    select(
        ("manifests/manifest_audit.json", "regression/manifest_audit.json"),
        "manifests/manifest_audit.json",
    ),
    select(
        ("core/results/ppa_summary.csv", "reports/core/ppa_summary.csv"),
        "core/results/ppa_summary.csv",
    ),
    select(
        ("core/results/physical_checks.csv", "reports/core/physical_checks.csv"),
        "core/results/physical_checks.csv",
    ),
    select(
        ("core/reports/genus_summary.txt", "reports/core/genus_summary.txt"),
        "core/reports/genus_summary.txt",
    ),
    select(
        ("core/reports/innovus_summary.txt", "reports/core/innovus_summary.txt"),
        "core/reports/innovus_summary.txt",
    ),
    select(
        ("core/reports/ocv_assumption.txt", "reports/core/ocv_assumption.txt"),
        "core/reports/ocv_assumption.txt",
    ),
    select(
        ("axi/results/ppa_summary.csv", "reports/axi/ppa_summary.csv"),
        "axi/results/ppa_summary.csv",
    ),
    select(
        ("axi/results/physical_checks.csv", "reports/axi/physical_checks.csv"),
        "axi/results/physical_checks.csv",
    ),
    select(
        ("axi/reports/genus_summary.txt", "reports/axi/genus_summary.txt"),
        "axi/reports/genus_summary.txt",
    ),
    select(
        ("axi/reports/innovus_summary.txt", "reports/axi/innovus_summary.txt"),
        "axi/reports/innovus_summary.txt",
    ),
    select(
        ("regression/rtl36_results.csv", "results/rtl36_results.csv"),
        "regression/rtl36_results.csv",
    ),
    select(
        ("regression/raw4_results.csv", "results/raw4_results.csv"),
        "regression/raw4_results.csv",
    ),
    select(
        ("regression/regression_summary.csv", "results/regression_summary.csv"),
        "regression/regression_summary.csv",
    ),
    select(
        ("lec/equivalence_summary.csv", "reports/lec/equivalence_summary.csv"),
        "lec/equivalence_summary.csv",
    ),
    select(
        ("lec/result_summary.txt", "reports/lec/result_summary.txt"),
        "lec/result_summary.txt",
    ),
    select(
        ("lec/verification.rpt", "reports/lec/verification.rpt"),
        "lec/reports/verification.rpt",
        required=False,
    ),
    select(
        ("pg/attempt_summary.csv", "reports/pg/attempt_summary.csv"),
        "pg/attempt_summary.csv",
    ),
    select(
        ("pg/failure_reason.txt", "reports/pg/failure_reason.txt"),
        "pg/failure_reason.txt",
    ),
    select(
        ("power/activity_power_summary.csv", "reports/power/activity_power_summary.csv"),
        "power/activity_power_summary.csv",
    ),
    select(
        (
            "power/activity_annotation_summary.txt",
            "reports/power/activity_annotation_summary.txt",
        ),
        "power/activity_annotation_summary.txt",
    ),
    select(
        (
            "gate/gate_verification_summary.csv",
            "reports/gate/gate_verification_summary.csv",
        ),
        "gate/gate_verification_summary.csv",
    ),
    select(
        ("gate/x_pessimism_boundary.txt", "reports/gate/x_pessimism_boundary.txt"),
        "gate/x_pessimism_boundary.txt",
    ),
    select(
        ("sdf/sdf_pilot_summary.csv", "reports/sdf/sdf_pilot_summary.csv"),
        "sdf/sdf_pilot_summary.csv",
    ),
    select(
        ("figures/core_routed.gif", "core/figures/routed.gif"),
        "figures/core_routed.gif",
        kind="gif",
        required=False,
    ),
    select(
        ("figures/axi_routed.gif", "axi/figures/routed.gif"),
        "figures/axi_routed.gif",
        kind="gif",
        required=False,
    ),
    select(
        ("logs/rtl36_summary.log", "regression/logs/rtl36_summary.log"),
        "regression/logs/rtl36_summary.log",
        required=False,
    ),
    select(
        ("logs/raw4_summary.log", "regression/logs/raw4_summary.log"),
        "regression/logs/raw4_summary.log",
        required=False,
    ),
    select(
        ("logs/postroute_lec_summary.log", "lec/logs/postroute_lec_summary.log"),
        "lec/logs/postroute_lec_summary.log",
        required=False,
    ),
    select(
        (
            "gate/gate_verification_summary.log",
            "gate/logs/gate_verification_summary.log",
            "gate/sanitized_gate_summary.log",
        ),
        "gate/logs/gate_verification_summary.log",
        required=False,
    ),
    select(
        (
            "sdf/sdf_pilot_summary.log",
            "sdf/logs/sdf_pilot_summary.log",
            "sdf/sanitized_sdf_summary.log",
        ),
        "sdf/logs/sdf_pilot_summary.log",
        required=False,
    ),
)


class EvidenceBuildError(RuntimeError):
    """A fail-closed public-boundary violation."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_relative(value: str, label: str) -> PurePosixPath:
    if "\\" in value:
        value = value.replace("\\", "/")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise EvidenceBuildError(f"{label} must be a normalized relative path: {value!r}")
    return path


def validate_selection(selection: Selection) -> None:
    if not selection.sources:
        raise EvidenceBuildError(f"selection has no source candidates: {selection.destination}")
    destination = normalized_relative(selection.destination, "destination")
    for source in selection.sources:
        normalized_relative(source, "source")
    if selection.kind not in {"text", "gif"}:
        raise EvidenceBuildError(f"unsupported kind {selection.kind!r}: {destination}")
    suffix = destination.suffix.lower()
    if suffix in FORBIDDEN_SUFFIXES:
        raise EvidenceBuildError(f"forbidden output suffix {suffix}: {destination}")
    if selection.kind == "gif" and suffix != ".gif":
        raise EvidenceBuildError(f"GIF selection must end in .gif: {destination}")
    if selection.kind == "text" and suffix not in ALLOWED_TEXT_SUFFIXES:
        raise EvidenceBuildError(f"text selection has non-allowlisted suffix {suffix}: {destination}")
    hard_limit = MAX_GIF_BYTES if selection.kind == "gif" else MAX_TEXT_BYTES
    if selection.max_bytes <= 0 or selection.max_bytes > hard_limit:
        raise EvidenceBuildError(
            f"max_bytes exceeds hard {selection.kind} limit ({hard_limit}): {destination}"
        )


def validate_mapping(selections: Sequence[Selection]) -> None:
    if not selections:
        raise EvidenceBuildError("selection mapping is empty")
    destinations: dict[str, str] = {}
    sources_seen: set[str] = set()
    for selection in selections:
        validate_selection(selection)
        dest_key = selection.destination.replace("\\", "/").casefold()
        if dest_key in destinations:
            raise EvidenceBuildError(
                f"case-insensitive destination collision: {destinations[dest_key]!r} and "
                f"{selection.destination!r}"
            )
        destinations[dest_key] = selection.destination
        for source in selection.sources:
            source_key = source.replace("\\", "/").casefold()
            if source_key in sources_seen:
                raise EvidenceBuildError(f"source candidate is mapped more than once: {source}")
            sources_seen.add(source_key)


def selections_to_json(selections: Sequence[Selection]) -> str:
    payload = {
        "selections": [
            {
                "sources": list(item.sources),
                "destination": item.destination,
                "kind": item.kind,
                "required": item.required,
                "max_bytes": item.max_bytes,
            }
            for item in selections
        ]
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def load_mapping(path: Path) -> tuple[Selection, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceBuildError(f"cannot read mapping JSON {path}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("selections"), list):
        raise EvidenceBuildError("mapping JSON must contain a selections array")
    selections: list[Selection] = []
    allowed_keys = {"sources", "destination", "kind", "required", "max_bytes"}
    for index, raw in enumerate(payload["selections"]):
        if not isinstance(raw, dict) or set(raw) - allowed_keys:
            raise EvidenceBuildError(f"invalid selection object at index {index}")
        sources = raw.get("sources")
        if not isinstance(sources, list) or not sources or not all(isinstance(item, str) for item in sources):
            raise EvidenceBuildError(f"selection {index} sources must be a non-empty string array")
        destination = raw.get("destination")
        if not isinstance(destination, str):
            raise EvidenceBuildError(f"selection {index} destination must be a string")
        kind = raw.get("kind", "text")
        required = raw.get("required", True)
        max_bytes = raw.get("max_bytes", MAX_GIF_BYTES if kind == "gif" else MAX_TEXT_BYTES)
        if not isinstance(kind, str) or not isinstance(required, bool) or not isinstance(max_bytes, int):
            raise EvidenceBuildError(f"selection {index} has invalid kind/required/max_bytes types")
        selections.append(Selection(tuple(sources), destination, kind, required, max_bytes))
    result = tuple(selections)
    validate_mapping(result)
    return result


IPV4_PATTERN = re.compile(
    r"(?<![\d.])(?:25[0-5]|2[0-4]\d|1?\d?\d)"
    r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?![\d.])"
)
EMAIL_PATTERN = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
USER_AT_HOST_PATTERN = re.compile(
    r"(?i)(?<![A-Z0-9_.-])[A-Z][A-Z0-9_.-]{2,}@[A-Z][A-Z0-9_.-]{2,}(?![A-Z0-9_.-])"
)
WINDOWS_ABSOLUTE_PATTERN = re.compile(
    r"(?i)(?<![A-Z0-9_])[A-Z]:(?:\\+|/+)[^\s\"'<>;,\)\]\}]+"
)
UNC_PATTERN = re.compile(r"\\\\[^\s\\/]+[\\/][^\s\"'<>;,\)\]\}]+")
CADENCE_TOOL_PATTERN = re.compile(
    r"(?i)(?<![A-Z0-9_])/(?:ho"
    r"me/tools/cadence|opt/cadence|tools/cadence)"
    r"(?:/[^\s\"'<>;,\)\]\}]*)?"
)
HOME_USER_PATTERN = re.compile(r"(?i)/ho" r"me/([^/\s\"']+)")
UNIX_SENSITIVE_PATH_PATTERN = re.compile(
    r"(?i)(?<![:A-Z0-9_])/(?:home|tmp|opt|net|nfs|mnt|scratch|work|proj|projects|"
    r"tools|eda|apps|software)/[^\s\"'<>;,\)\]\}]*"
)
LICENSE_VALUE_PATTERN = re.compile(
    r"(?i)\b((?:CDS|LM)_LIC(?:ENSE)?_FILE\s*[:=]\s*)[^\s\"'<>;,]+"
)
LICENSE_SERVER_PATTERN = re.compile(r"(?<![A-Z0-9_.-])\d{2,6}@[A-Z0-9_.-]+", re.I)
HOST_CONTEXT_PATTERN = re.compile(
    r"(?i)\b((?:(?:host\s+id|hostname)\s*[:=]?\s*|host\s*[:=]\s*))"
    r"(?!<HOST>)([A-Z0-9_.-]+)"
)


def literal_variants(value: str) -> tuple[str, ...]:
    variants = {value}
    variants.add(value.replace("\\", "/"))
    variants.add(value.replace("/", "\\"))
    variants.add(value.replace("\\", "\\\\"))
    return tuple(sorted((item for item in variants if item), key=len, reverse=True))


def redact_text(
    original: str,
    explicit_tokens: Sequence[str],
    remote_roots: Sequence[str],
) -> tuple[str, int, tuple[str, ...]]:
    text = original.replace("\r\n", "\n").replace("\r", "\n")
    redactions = 0
    discovered_tokens: set[str] = set()

    for match in HOME_USER_PATTERN.finditer(text):
        username = match.group(1)
        if username.casefold() != "tools":
            discovered_tokens.add(username)
    for match in HOST_CONTEXT_PATTERN.finditer(text):
        candidate = match.group(2)
        if candidate and not candidate.startswith("<"):
            discovered_tokens.add(candidate)

    # Redact structured license values before standalone explicit tokens.  If
    # a host token were replaced first, a value such as ``27000@lic-host``
    # would otherwise retain its port and punctuation around a placeholder.
    text, count = LICENSE_VALUE_PATTERN.subn(r"\1<LICENSE_SERVER>", text)
    redactions += count
    text, count = LICENSE_SERVER_PATTERN.subn("<LICENSE_SERVER>", text)
    redactions += count

    for value in (*remote_roots, *explicit_tokens):
        if len(value) < 3:
            raise EvidenceBuildError("redaction tokens and remote roots must be at least 3 characters")
        for variant in literal_variants(value):
            pattern = re.compile(re.escape(variant), re.I)
            text, count = pattern.subn("<REDACTED>", text)
            redactions += count

    text, count = CADENCE_TOOL_PATTERN.subn("<CADENCE_TOOL_PATH>", text)
    redactions += count
    text, count = WINDOWS_ABSOLUTE_PATTERN.subn("<LOCAL_PATH>", text)
    redactions += count
    text, count = UNC_PATTERN.subn("<UNC_PATH>", text)
    redactions += count
    text, count = UNIX_SENSITIVE_PATH_PATTERN.subn("<REMOTE_PATH>", text)
    redactions += count
    text, count = HOST_CONTEXT_PATTERN.subn(r"\1<HOST>", text)
    redactions += count
    text, count = IPV4_PATTERN.subn("<IP_ADDRESS>", text)
    redactions += count
    text, count = EMAIL_PATTERN.subn("<EMAIL>", text)
    redactions += count
    text, count = USER_AT_HOST_PATTERN.subn("<USER_AT_HOST>", text)
    redactions += count

    # User and host tokens discovered before path/context replacement can also
    # appear independently in command echoes or report banners.
    for token in sorted(discovered_tokens, key=len, reverse=True):
        if len(token) < 3:
            continue
        pattern = re.compile(rf"(?<![A-Z0-9_]){re.escape(token)}(?![A-Z0-9_])", re.I)
        text, count = pattern.subn("<REDACTED_ID>", text)
        redactions += count

    if text and not text.endswith("\n"):
        text += "\n"
    return text, redactions, tuple(sorted(discovered_tokens, key=str.casefold))


REMAINING_SENSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Windows absolute path", WINDOWS_ABSOLUTE_PATTERN),
    ("UNC path", UNC_PATTERN),
    ("Cadence tool path", CADENCE_TOOL_PATTERN),
    ("remote absolute path", UNIX_SENSITIVE_PATH_PATTERN),
    ("IPv4 address", IPV4_PATTERN),
    ("email address", EMAIL_PATTERN),
    ("user-at-host identifier", USER_AT_HOST_PATTERN),
    ("license server", LICENSE_SERVER_PATTERN),
    (
        "unredacted host context",
        HOST_CONTEXT_PATTERN,
    ),
)


def scan_sensitive(text: str, explicit_tokens: Sequence[str], label: str) -> list[str]:
    errors: list[str] = []
    for name, pattern in REMAINING_SENSITIVE_PATTERNS:
        match = pattern.search(text)
        if match:
            errors.append(f"{label}: remaining {name}: {match.group(0)[:120]!r}")
    for token in explicit_tokens:
        if token and token.casefold() in text.casefold():
            errors.append(f"{label}: explicit sensitive token remains: {token!r}")
    return errors


def scan_binary_sensitive(data: bytes, explicit_tokens: Sequence[str], label: str) -> list[str]:
    """Scan printable metadata embedded in an allowlisted binary such as GIF."""

    printable = b"\n".join(re.findall(rb"[\x20-\x7e]{4,}", data)).decode(
        "ascii", errors="ignore"
    )
    return scan_sensitive(printable, explicit_tokens, label)


def scan_for_forbidden_payload(text: str, label: str) -> list[str]:
    errors: list[str] = []
    if re.search(r"(?i)\bmodule\s+[A-Za-z_\\][^;\n]*\(", text) and re.search(
        r"(?i)\bendmodule\b", text
    ):
        errors.append(f"{label}: selected text appears to contain a forbidden Verilog netlist")
    if re.search(r"(?im)^\s*\.subckt\b", text) and re.search(r"(?im)^\s*\.ends\b", text):
        errors.append(f"{label}: selected text appears to contain a forbidden SPICE/CDL netlist")
    if (
        re.search(r"(?im)^\s*VERSION\s+[^;]+;", text)
        and re.search(r"(?im)^\s*DIEAREA\b", text)
        and re.search(r"(?im)^\s*COMPONENTS\b", text)
    ):
        errors.append(f"{label}: selected text appears to contain a forbidden DEF payload")
    signatures = (
        ("SDF", re.compile(r"(?i)\(DELAYFILE\b")),
        ("SPEF", re.compile(r"(?im)^\s*\*SPEF\b")),
        ("Liberty", re.compile(r"(?is)\blibrary\s*\([^\n]+\)\s*\{.*\bcell\s*\(")),
    )
    for name, pattern in signatures:
        if pattern.search(text):
            errors.append(f"{label}: selected text appears to contain a forbidden {name} payload")
    return errors


def validate_structured_text(path: Path, text: str) -> None:
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            raise EvidenceBuildError(f"sanitized JSON is invalid ({path}): {exc}") from exc
    elif suffix == ".csv":
        try:
            rows = list(csv.reader(io.StringIO(text, newline="")))
        except csv.Error as exc:
            raise EvidenceBuildError(f"sanitized CSV is invalid ({path}): {exc}") from exc
        if not rows or not rows[0] or any(len(row) != len(rows[0]) for row in rows):
            raise EvidenceBuildError(f"sanitized CSV has an inconsistent column schema: {path}")


def resolve_selected_source(raw_root: Path, selection: Selection) -> tuple[Path, str] | None:
    matches: list[tuple[Path, str]] = []
    for source_text in selection.sources:
        relative = normalized_relative(source_text, "source")
        candidate = raw_root.joinpath(*relative.parts)
        if candidate.exists():
            matches.append((candidate, relative.as_posix()))
    if len(matches) > 1:
        raise EvidenceBuildError(
            f"ambiguous source alternatives for {selection.destination}: "
            + ", ".join(item[1] for item in matches)
        )
    if not matches:
        if selection.required:
            raise EvidenceBuildError(
                f"required source missing for {selection.destination}: {list(selection.sources)!r}"
            )
        return None
    source, relative_text = matches[0]
    if source.is_symlink() or not source.is_file():
        raise EvidenceBuildError(f"selected source must be a regular non-symlink file: {relative_text}")
    resolved = source.resolve()
    if not resolved.is_relative_to(raw_root):
        raise EvidenceBuildError(f"selected source escapes raw root: {relative_text}")
    source_suffix = source.suffix.lower()
    if source_suffix in FORBIDDEN_SUFFIXES:
        raise EvidenceBuildError(f"forbidden source suffix: {relative_text}")
    if selection.kind == "gif" and source_suffix != ".gif":
        raise EvidenceBuildError(f"GIF selection has a non-GIF source: {relative_text}")
    if selection.kind == "text" and source_suffix not in ALLOWED_TEXT_SUFFIXES:
        raise EvidenceBuildError(
            f"text selection has a non-allowlisted source suffix {source_suffix}: {relative_text}"
        )
    return source, relative_text


def process_selection(
    raw_root: Path,
    staging: Path,
    selection: Selection,
    explicit_tokens: Sequence[str],
    remote_roots: Sequence[str],
) -> dict[str, object] | None:
    resolved = resolve_selected_source(raw_root, selection)
    if resolved is None:
        return None
    source, source_relative = resolved
    size = source.stat().st_size
    if size == 0 or size > selection.max_bytes:
        raise EvidenceBuildError(
            f"selected source size {size} is outside 1..{selection.max_bytes}: {source_relative}"
        )
    destination_relative = normalized_relative(selection.destination, "destination")
    path_errors = scan_sensitive(
        destination_relative.as_posix(), (*explicit_tokens, *remote_roots), "destination path"
    )
    if path_errors:
        raise EvidenceBuildError("\n".join(path_errors))
    destination = staging.joinpath(*destination_relative.parts)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_hash = sha256_file(source)
    redaction_count = 0
    discovered_tokens: tuple[str, ...] = ()

    if selection.kind == "gif":
        data = source.read_bytes()
        if not data.startswith((b"GIF87a", b"GIF89a")):
            raise EvidenceBuildError(f"selected .gif has invalid magic: {source_relative}")
        errors = scan_binary_sensitive(
            data, (*explicit_tokens, *remote_roots), source_relative
        )
        if errors:
            raise EvidenceBuildError("\n".join(errors))
        destination.write_bytes(data)
    else:
        try:
            original = source.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            raise EvidenceBuildError(f"selected text is not strict UTF-8: {source_relative}") from exc
        sanitized, redaction_count, discovered_tokens = redact_text(
            original, explicit_tokens, remote_roots
        )
        errors = scan_sensitive(
            sanitized,
            (*explicit_tokens, *remote_roots, *discovered_tokens),
            source_relative,
        )
        errors.extend(scan_for_forbidden_payload(sanitized, source_relative))
        if errors:
            raise EvidenceBuildError("\n".join(errors))
        validate_structured_text(destination, sanitized)
        destination.write_text(sanitized, encoding="utf-8", newline="\n")

    return {
        "destination": destination_relative.as_posix(),
        "source_relative": source_relative,
        "source_sha256": source_hash,
        "public_sha256": sha256_file(destination),
        "public_size_bytes": destination.stat().st_size,
        "redaction_count": redaction_count,
    }


def write_selection_manifest(staging: Path, rows: Sequence[dict[str, object]]) -> None:
    path = staging / "SELECTION_MANIFEST.csv"
    fields = [
        "destination",
        "source_relative",
        "source_sha256",
        "public_sha256",
        "public_size_bytes",
        "redaction_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: str(row["destination"]).casefold()))


def iter_public_files(staging: Path, include_checksums: bool = True) -> Iterable[Path]:
    for path in sorted(
        (item for item in staging.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(staging).as_posix().casefold(),
    ):
        if not include_checksums and path.name == "CHECKSUMS.txt":
            continue
        yield path


def validate_public_tree(staging: Path, explicit_tokens: Sequence[str]) -> None:
    errors: list[str] = []
    for path in iter_public_files(staging):
        relative = path.relative_to(staging).as_posix()
        errors.extend(scan_sensitive(relative, explicit_tokens, f"public path {relative}"))
        suffix = path.suffix.lower()
        if suffix in FORBIDDEN_SUFFIXES:
            errors.append(f"{relative}: forbidden suffix in public tree")
            continue
        if suffix == ".gif":
            data = path.read_bytes()
            if not data.startswith((b"GIF87a", b"GIF89a")):
                errors.append(f"{relative}: invalid GIF")
            errors.extend(scan_binary_sensitive(data, explicit_tokens, relative))
            continue
        if suffix not in ALLOWED_TEXT_SUFFIXES:
            errors.append(f"{relative}: non-allowlisted public file type")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"{relative}: public text is not UTF-8")
            continue
        errors.extend(scan_sensitive(text, explicit_tokens, relative))
        errors.extend(scan_for_forbidden_payload(text, relative))
        try:
            validate_structured_text(path, text)
        except EvidenceBuildError as exc:
            errors.append(str(exc))
    if errors:
        raise EvidenceBuildError("public-tree validation failed:\n" + "\n".join(errors))


def write_checksums(staging: Path) -> None:
    path = staging / "CHECKSUMS.txt"
    lines = [
        f"{sha256_file(item)}  {item.relative_to(staging).as_posix()}"
        for item in iter_public_files(staging, include_checksums=False)
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def resolve_output(path: Path) -> Path:
    if path.is_absolute():
        output = path.resolve(strict=False)
    else:
        output = (REPOSITORY_ROOT / path).resolve(strict=False)
    verification = VERIFICATION_ROOT.resolve()
    if output == verification or not output.is_relative_to(verification):
        raise EvidenceBuildError(f"output must be a child of {verification}: {output}")
    return output


def install_staging(staging: Path, output: Path, replace: bool) -> None:
    if output.exists() and not replace:
        raise EvidenceBuildError(f"output exists; review it and pass --replace explicitly: {output}")
    backup = output.parent / f".{output.name}.backup-{os.getpid()}"
    if backup.exists():
        raise EvidenceBuildError(f"unexpected backup path exists: {backup}")
    if output.exists():
        output.rename(backup)
    try:
        staging.rename(output)
    except Exception:
        if backup.exists() and not output.exists():
            backup.rename(output)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def run_self_test() -> None:
    """Exercise the public-summary paths and hard forbidden-format boundary."""

    validate_mapping(DEFAULT_SELECTIONS)
    by_destination = {item.destination: item for item in DEFAULT_SELECTIONS}
    required_public_summaries = {
        "power/activity_power_summary.csv",
        "power/activity_annotation_summary.txt",
        "gate/gate_verification_summary.csv",
        "gate/x_pessimism_boundary.txt",
        "sdf/sdf_pilot_summary.csv",
    }
    optional_summary_logs = {
        "gate/logs/gate_verification_summary.log",
        "sdf/logs/sdf_pilot_summary.log",
    }
    missing = sorted((required_public_summaries | optional_summary_logs) - set(by_destination))
    if missing:
        raise EvidenceBuildError(f"self-test mapping lacks new public paths: {missing}")
    for destination in required_public_summaries:
        item = by_destination[destination]
        if not item.required or item.kind != "text":
            raise EvidenceBuildError(
                f"self-test expected required text selection: {destination}"
            )
    for destination in optional_summary_logs:
        item = by_destination[destination]
        if item.required or item.kind != "text":
            raise EvidenceBuildError(
                f"self-test expected optional text selection: {destination}"
            )

    with tempfile.TemporaryDirectory(prefix="asic-run2-evidence-selftest-") as temporary:
        root = Path(temporary)
        raw_root = root / "raw"
        staging = root / "staging"
        raw_root.mkdir()
        staging.mkdir()

        # Build each new summary through its first explicit source path.  This
        # verifies both the source mapping and the normalized public path.
        for destination in sorted(required_public_summaries | optional_summary_logs):
            selection = by_destination[destination]
            source_relative = normalized_relative(selection.sources[0], "self-test source")
            source = raw_root.joinpath(*source_relative.parts)
            source.parent.mkdir(parents=True, exist_ok=True)
            if source.suffix.lower() == ".csv":
                source.write_text("metric,value\nself_test,1\n", encoding="utf-8", newline="\n")
            else:
                source.write_text("self_test=pass\n", encoding="utf-8", newline="\n")
            result = process_selection(raw_root, staging, selection, (), ())
            if result is None or result["destination"] != destination:
                raise EvidenceBuildError(
                    f"self-test selection did not produce expected destination: {destination}"
                )
            if not staging.joinpath(*PurePosixPath(destination).parts).is_file():
                raise EvidenceBuildError(f"self-test public summary missing: {destination}")

        # A reviewed mapping cannot smuggle these raw payload types through a
        # harmless-looking .txt destination.
        for suffix in (".saif", ".shm", ".v", ".netlist", ".sdf"):
            source = raw_root / f"forbidden{suffix}"
            source.write_bytes(b"forbidden raw payload")
            selection = select(source.name, f"blocked/{suffix[1:]}.txt")
            try:
                resolve_selected_source(raw_root, selection)
            except EvidenceBuildError as exc:
                if "forbidden source suffix" not in str(exc):
                    raise
            else:
                raise EvidenceBuildError(
                    f"self-test allowed forbidden raw source suffix: {suffix}"
                )

        # The same formats are blocked on the public destination side.
        for suffix in (".saif", ".shm", ".v", ".netlist", ".sdf"):
            try:
                validate_selection(select("safe.txt", f"blocked/output{suffix}"))
            except EvidenceBuildError as exc:
                if "forbidden output suffix" not in str(exc):
                    raise
            else:
                raise EvidenceBuildError(
                    f"self-test allowed forbidden public suffix: {suffix}"
                )

        validate_public_tree(staging, ())

    print(
        "ASIC_GPDK45_RUN2_EVIDENCE: SELF_TEST_PASS "
        f"required_summaries={len(required_public_summaries)} "
        f"optional_logs={len(optional_summary_logs)} forbidden_formats=5"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_root", nargs="?", type=Path, help="locally retrieved raw run-2 directory")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--mapping-json", type=Path, help="reviewed exact selection mapping; replaces defaults")
    parser.add_argument("--remote-root", action="append", default=[], help="exact remote root to redact")
    parser.add_argument("--redact-token", action="append", default=[], help="additional username/host/token")
    parser.add_argument("--replace", action="store_true", help="atomically replace an existing output")
    parser.add_argument("--dry-run", action="store_true", help="validate/build staging, then discard it")
    parser.add_argument("--print-default-mapping", action="store_true")
    parser.add_argument("--self-test", action="store_true", help="test new summary mappings and hard blocks")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return 0
    if args.print_default_mapping:
        sys.stdout.write(selections_to_json(DEFAULT_SELECTIONS))
        return 0
    if args.raw_root is None:
        raise EvidenceBuildError("raw_root is required unless --print-default-mapping is used")

    raw_root = args.raw_root.resolve()
    if not raw_root.is_dir():
        raise EvidenceBuildError(f"raw_root is not a directory: {raw_root}")
    output = resolve_output(args.output)
    selections = load_mapping(args.mapping_json.resolve()) if args.mapping_json else DEFAULT_SELECTIONS
    validate_mapping(selections)

    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.parent / f".{output.name}.staging-{os.getpid()}"
    stale_work = sorted(
        (*output.parent.glob(f".{output.name}.staging-*"),
         *output.parent.glob(f".{output.name}.backup-*"))
    )
    if stale_work:
        raise EvidenceBuildError(
            "stale staging/backup paths require manual review: "
            + ", ".join(str(path) for path in stale_work)
        )
    if staging.exists():
        raise EvidenceBuildError(f"staging path already exists: {staging}")
    staging.mkdir()

    try:
        rows: list[dict[str, object]] = []
        for selection in sorted(selections, key=lambda item: item.destination.casefold()):
            result = process_selection(
                raw_root,
                staging,
                selection,
                args.redact_token,
                args.remote_root,
            )
            if result is not None:
                rows.append(result)
        if not rows:
            raise EvidenceBuildError("selection mapping copied no files")
        write_selection_manifest(staging, rows)
        validate_public_tree(staging, (*args.redact_token, *args.remote_root))
        write_checksums(staging)
        validate_public_tree(staging, (*args.redact_token, *args.remote_root))

        if args.dry_run:
            print(f"ASIC_GPDK45_RUN2_EVIDENCE: DRY_RUN_PASS files={len(rows)}")
            shutil.rmtree(staging)
            return 0
        install_staging(staging, output, args.replace)
        print(f"ASIC_GPDK45_RUN2_EVIDENCE: PASS files={len(rows)} output={output}")
        return 0
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceBuildError as exc:
        print(f"ASIC_GPDK45_RUN2_EVIDENCE: FAIL\n- {exc}", file=sys.stderr)
        raise SystemExit(1)
