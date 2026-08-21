#!/usr/bin/env python3
"""Fail-closed parser for a locally retrieved GPDK045 run-2 raw tree.

The parser reads only explicit report/result paths and writes a structured
staging directory consumed by ``build_asic_gpdk45_run2_evidence.py``.  It does
not copy netlists, PDK files, databases, DEF/SDF/SPEF, SAIF/SHM, or raw tool
logs.  Numeric values are parsed from source reports; missing or conflicting
matches raise ``Run2SummaryError``.

The default layout is intentionally concrete.  A small override JSON may
replace known final-candidate directories, basenames, tags, or exact result
paths, for example::

    {
      "profiles": {
        "core": {
          "candidate_reports": "reports/drv_closure/core_final",
          "candidate_outputs": "outputs/drv_closure/core_final",
          "candidate_basename": "snn_ecg_asic_core_top_core_final",
          "final_checks": "reports/final_checks/core_final"
        },
        "axi": {
          "root": "axi_run",
          "candidate_reports": "reports/drv_closure/cts50_drv2",
          "candidate_outputs": "outputs/drv_closure/cts50_drv2",
          "candidate_basename": "snn_ecg_axi_asic_top_cts50_drv2",
          "final_checks": "reports/final_checks/cts50_drv2"
        }
      },
      "power": {
        "runs": {
          "accelerated_gap2": {"tag": "raw_aff_accelerated_access_seed11"},
          "active_wait_idle": {"tag": "prefix100_idle_access_seed11"},
          "literal_1ksps_prefix": {"tag": "prefix100_literal1ksps_access_seed11"}
        }
      }
    }

Unknown override keys, absolute paths, ``..`` traversal, an existing nonempty
staging directory, no-access ``direct`` power tags, or an ambiguous parsed
value are rejected.  The reviewed final mapping is stored beside this script
as ``asic_gpdk45_run2_final_override.json``.
"""

from __future__ import annotations

import argparse
import copy
import csv
import gzip
import hashlib
import io
import json
import re
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


class Run2SummaryError(RuntimeError):
    """A missing, ambiguous, or internally inconsistent run-2 artifact."""


MAX_TEXT_BYTES = 32 * 1024 * 1024
MAX_DEF_BYTES = 1024 * 1024 * 1024
KNOWN_CORE_ITER1_WIRE_UM = 836_058
KNOWN_CORE_ITER1_VIAS = 315_926
KNOWN_PG_CONNECTIVITY_VIOLATIONS = 171
KNOWN_PG_GEOMETRY_VIOLATIONS = 715
KNOWN_MAPPED_SEQUENTIAL_INSTANCES = 6_045
KNOWN_SDF_SEQUENTIAL_INSTANCES = 6_044
KNOWN_FORCED_RELEASE_NS = 10
KNOWN_MAPPED_SEEDS = (11, 22, 33)
KNOWN_SDF_SEED = 11
KNOWN_SDFNCAP_WARNINGS = 88
KNOWN_POWER_TAGS = {
    "accelerated_gap2": "raw_aff_accelerated_access_seed11",
    "active_wait_idle": "prefix100_idle_access_seed11",
    "literal_1ksps_prefix": "prefix100_literal1ksps_access_seed11",
}
KNOWN_OCV_FACTORS = {
    "slow_early": 0.95,
    "slow_late": 1.00,
    "fast_early": 1.00,
    "fast_late": 1.05,
}


DEFAULT_CONFIG: dict[str, Any] = {
    "def_reference": {
        "core_iter1_def": "outputs/closure/iter1/snn_ecg_asic_core_top_iter1.def"
    },
    "profiles": {
        "core": {
            "top": "snn_ecg_asic_core_top",
            "root": ".",
            "genus_reports": "reports/genus",
            "innovus_reports": "reports/innovus",
            "candidate_reports": "reports/closure/iter1",
            "candidate_outputs": "outputs/closure/iter1",
            "candidate_basename": "snn_ecg_asic_core_top_iter1",
            "final_checks": "reports/final_checks/core_iter1",
            "ocv_constraint_script": "source/repo/design/digital/asic/gpdk45/scripts/run_innovus.tcl",
        },
        "axi": {
            "top": "snn_ecg_axi_asic_top",
            "root": "axi",
            "genus_reports": "reports/genus",
            "innovus_reports": "reports/innovus",
            "candidate_reports": "reports/closure/iter1",
            "candidate_outputs": "outputs/closure/iter1",
            "candidate_basename": "snn_ecg_axi_asic_top_iter1",
            "final_checks": "reports/final_checks/axi_iter1",
            "ocv_constraint_script": "source/repo/design/digital/asic/gpdk45/scripts/run_innovus.tcl",
        },
    },
    "regression": {
        "rtl36_results": "regression/rtl36_results.csv",
        "raw4_results": "regression/raw4_results.csv",
        "canonical_manifest": "manifests/canonical_digital_36.manifest",
        "raw_manifest": "manifests/raw_xmodel_4.manifest",
        "manifest_audit": "manifests/manifest_audit.json",
    },
    "lec": {
        "core_result": "lec/core/result_summary.txt",
        "axi_result": "lec/axi/result_summary.txt",
    },
    "pg": {
        "run_log": "pg/pg_attempt.log",
        "assumptions": "pg/pg_assumptions.txt",
        "connectivity": "pg/connectivity_pg.rpt",
        "geometry": "pg/geometry_internal.rpt",
        "filler": "pg/check_filler.rpt",
        "expected_connectivity_violations": KNOWN_PG_CONNECTIVITY_VIOLATIONS,
        "expected_geometry_violations": KNOWN_PG_GEOMETRY_VIOLATIONS,
    },
    "gate": {
        "unmodified_four_state_result": "gate/unmodified_four_state_result.csv",
        "xpr_log": "gate/xpr.log",
        "mapped_seed_logs": {
            "seed11": "gate/mapped_seed11.log",
            "seed22": "gate/mapped_seed22.log",
            "seed33": "gate/mapped_seed33.log",
        },
    },
    "sdf": {
        "max_annotation_log": "sdf/max_annotation.log",
        "max_simulation_log": "sdf/max_simulation.log",
    },
    "power": {
        "prefix_manifest": "power/literal_prefix_manifest.json",
        "runs": {
            "accelerated_gap2": {
                "profile": "core",
                "tag": KNOWN_POWER_TAGS["accelerated_gap2"],
                "stimulus_log": "power/accelerated_gap2_stimulus.log",
                "launch_record": "provenance/access_activity_launch_records.json",
            },
            "active_wait_idle": {
                "profile": "core",
                "tag": KNOWN_POWER_TAGS["active_wait_idle"],
                "stimulus_log": "power/active_wait_idle_stimulus.log",
                "launch_record": "provenance/access_activity_launch_records.json",
            },
            "literal_1ksps_prefix": {
                "profile": "core",
                "tag": KNOWN_POWER_TAGS["literal_1ksps_prefix"],
                "stimulus_log": "power/literal_1ksps_stimulus.log",
                "launch_record": "provenance/access_activity_launch_records.json",
            },
        },
    },
}


REGRESSION_COLUMNS = {
    "case_id",
    "expected_class",
    "final_pred_class",
    "pass",
    "final_valid",
    "samples",
    "cycles",
    "expected_mem_nsr",
    "final_mem_nsr",
    "expected_mem_chf",
    "final_mem_chf",
    "expected_mem_arr",
    "final_mem_arr",
    "expected_mem_aff",
    "final_mem_aff",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path)
    parser.add_argument("--staging-dir", type=Path)
    parser.add_argument("--override-json", type=Path)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_relative(value: str, label: str, *, allow_dot: bool = False) -> str:
    value = value.replace("\\", "/")
    if allow_dot and value == ".":
        return value
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise Run2SummaryError(f"{label} must be a normalized relative path: {value!r}")
    return path.as_posix()


def deep_override(base: dict[str, Any], override: Mapping[str, Any], trail: str = "") -> None:
    for key, value in override.items():
        here = f"{trail}.{key}" if trail else key
        if key not in base:
            raise Run2SummaryError(f"unknown override key: {here}")
        current = base[key]
        if isinstance(current, dict):
            if not isinstance(value, Mapping):
                raise Run2SummaryError(f"override {here} must be an object")
            deep_override(current, value, here)
        else:
            if not isinstance(value, type(current)):
                raise Run2SummaryError(
                    f"override {here} must have type {type(current).__name__}"
                )
            base[key] = value


def load_config(path: Path | None) -> tuple[dict[str, Any], str | None]:
    config = copy.deepcopy(DEFAULT_CONFIG)
    override_hash = None
    if path is not None:
        try:
            raw = path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Run2SummaryError(f"cannot read override JSON {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise Run2SummaryError("override JSON root must be an object")
        deep_override(config, payload)
        override_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    for name, profile in config["profiles"].items():
        profile["root"] = normalized_relative(
            profile["root"], f"profiles.{name}.root", allow_dot=True
        )
        for key in (
            "genus_reports",
            "innovus_reports",
            "candidate_reports",
            "candidate_outputs",
            "final_checks",
            "ocv_constraint_script",
        ):
            profile[key] = normalized_relative(profile[key], f"profiles.{name}.{key}")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", profile["candidate_basename"]):
            raise Run2SummaryError(f"invalid candidate basename for {name}")

    def validate_paths(node: Mapping[str, Any], trail: str) -> None:
        for key, value in node.items():
            here = f"{trail}.{key}" if trail else key
            if isinstance(value, Mapping):
                validate_paths(value, here)
            elif isinstance(value, str) and key not in {
                "top",
                "tag",
                "profile",
                "candidate_basename",
            }:
                node[key] = normalized_relative(value, here)  # type: ignore[index]

    for section in ("def_reference", "regression", "lec", "pg", "gate", "sdf"):
        validate_paths(config[section], section)
    config["power"]["prefix_manifest"] = normalized_relative(
        config["power"]["prefix_manifest"], "power.prefix_manifest"
    )
    for key, run in config["power"]["runs"].items():
        if run["profile"] not in config["profiles"]:
            raise Run2SummaryError(f"power run {key} references unknown profile")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", run["tag"]):
            raise Run2SummaryError(f"invalid power tag for {key}")
        if "direct" in run["tag"].lower() or "_access_" not in run["tag"].lower():
            raise Run2SummaryError(
                f"power tag for {key} is not an access-enabled final tag: {run['tag']}"
            )
        run["stimulus_log"] = normalized_relative(
            run["stimulus_log"], f"power.runs.{key}.stimulus_log"
        )
        run["launch_record"] = normalized_relative(
            run["launch_record"], f"power.runs.{key}.launch_record"
        )
    return config, override_hash


class RawReader:
    def __init__(self, root: Path):
        self.root = root.resolve()
        if not self.root.is_dir():
            raise Run2SummaryError(f"raw root is not a directory: {self.root}")
        self.used: dict[str, str] = {}

    def path(self, relative: str, *, required: bool = True) -> Path | None:
        relative = normalized_relative(relative, "raw path", allow_dot=False)
        path = (self.root / PurePosixPath(relative)).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise Run2SummaryError(f"raw path escapes root: {relative}") from exc
        if not path.is_file():
            if required:
                raise Run2SummaryError(f"missing required raw file: {relative}")
            return None
        self.used[relative] = sha256_file(path)
        return path

    def text(
        self,
        relative: str,
        *,
        required: bool = True,
        max_bytes: int = MAX_TEXT_BYTES,
    ) -> str | None:
        path = self.path(relative, required=required)
        if path is None:
            return None
        if path.stat().st_size > max_bytes:
            raise Run2SummaryError(f"raw text exceeds {max_bytes} bytes: {relative}")
        try:
            return path.read_text(encoding="utf-8", errors="strict").replace("\r\n", "\n").replace("\r", "\n")
        except (OSError, UnicodeDecodeError) as exc:
            raise Run2SummaryError(f"cannot read UTF-8 raw text {relative}: {exc}") from exc

    def gzip_text(
        self,
        relative: str,
        *,
        required: bool = True,
        max_compressed_bytes: int = MAX_TEXT_BYTES,
        max_decompressed_bytes: int = MAX_TEXT_BYTES,
    ) -> str | None:
        """Read one explicit UTF-8 gzip report with compressed/output caps."""

        path = self.path(relative, required=required)
        if path is None:
            return None
        if path.stat().st_size > max_compressed_bytes:
            raise Run2SummaryError(
                f"raw gzip exceeds {max_compressed_bytes} compressed bytes: {relative}"
            )
        try:
            with gzip.open(path, "rb") as handle:
                payload = handle.read(max_decompressed_bytes + 1)
        except (OSError, EOFError) as exc:
            raise Run2SummaryError(f"cannot decompress raw gzip {relative}: {exc}") from exc
        if len(payload) > max_decompressed_bytes:
            raise Run2SummaryError(
                f"raw gzip exceeds {max_decompressed_bytes} decompressed bytes: {relative}"
            )
        try:
            return payload.decode("utf-8", errors="strict").replace("\r\n", "\n").replace("\r", "\n")
        except UnicodeDecodeError as exc:
            raise Run2SummaryError(f"cannot decode UTF-8 raw gzip {relative}: {exc}") from exc


class StageWriter:
    def __init__(self, root: Path):
        self.root = root.resolve()
        if self.root.exists() and any(self.root.iterdir()):
            raise Run2SummaryError(f"staging directory must be absent or empty: {self.root}")
        self.root.mkdir(parents=True, exist_ok=True)

    def text(self, relative: str, value: str) -> None:
        relative = normalized_relative(relative, "staging path")
        path = self.root / PurePosixPath(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        if value and not value.endswith("\n"):
            value += "\n"
        path.write_text(value, encoding="utf-8", newline="\n")

    def json(self, relative: str, value: Any) -> None:
        self.text(relative, json.dumps(value, indent=2, sort_keys=True) + "\n")

    def csv(self, relative: str, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})
        self.text(relative, buffer.getvalue())


def join_relative(*parts: str) -> str:
    result = PurePosixPath()
    for part in parts:
        if part == ".":
            continue
        result /= PurePosixPath(part)
    return normalized_relative(result.as_posix(), "joined raw path")


def unique_capture(
    text: str,
    patterns: Sequence[str],
    label: str,
    cast: type[int] | type[float] | type[str] = str,
) -> int | float | str:
    values: list[int | float | str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I | re.M):
            raw = match.group(1)
            values.append(cast(raw))
    unique = list(dict.fromkeys(values))
    if not unique:
        raise Run2SummaryError(f"missing value: {label}")
    if len(unique) != 1:
        raise Run2SummaryError(f"ambiguous value for {label}: {unique}")
    return unique[0]


def first_capture(
    text: str,
    patterns: Sequence[str],
    label: str,
    cast: type[int] | type[float] | type[str] = str,
) -> int | float | str:
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.M)
        if match:
            return cast(match.group(1))
    raise Run2SummaryError(f"missing value: {label}")


def parse_key_values(text: str, required: Sequence[str], label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in result and result[key] != value:
            raise Run2SummaryError(f"conflicting {label} key {key}")
        result[key] = value
    missing = [key for key in required if key not in result]
    if missing:
        raise Run2SummaryError(f"missing {label} keys: {missing}")
    return result


def parse_power_report(text: str, label: str) -> dict[str, float | str]:
    unit = unique_capture(
        text,
        [r"Power Units\s*=\s*1\s*([munp]?W)\b"],
        f"{label} power unit",
        str,
    )
    if unit != "mW":
        raise Run2SummaryError(f"unsupported {label} power unit: {unit}")
    result: dict[str, float | str] = {
        "unit": unit,
        "internal": float(unique_capture(text, [r"Total Internal Power:\s*([+-]?[0-9.]+)"], f"{label} internal", float)),
        "switching": float(unique_capture(text, [r"Total Switching Power:\s*([+-]?[0-9.]+)"], f"{label} switching", float)),
        "leakage": float(unique_capture(text, [r"Total Leakage Power:\s*([+-]?[0-9.]+)"], f"{label} leakage", float)),
        "total": float(unique_capture(text, [r"^Total Power:\s*([+-]?[0-9.]+)"], f"{label} total", float)),
    }
    component_sum = (
        float(result["internal"])
        + float(result["switching"])
        + float(result["leakage"])
    )
    if abs(component_sum - float(result["total"])) > 1e-6:
        raise Run2SummaryError(
            f"{label} power components do not sum to total: {component_sum} != {result['total']}"
        )
    return result


def parse_def_geometry(text: str, label: str) -> dict[str, float | int]:
    units = int(unique_capture(text, [r"^UNITS DISTANCE MICRONS\s+(\d+)\s*;"], f"{label} DBU", int))
    matches = re.findall(
        r"^DIEAREA\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*"
        r"\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*;",
        text,
        re.I | re.M,
    )
    if len(matches) != 1:
        raise Run2SummaryError(f"expected one DIEAREA in {label}, got {len(matches)}")
    x1, y1, x2, y2 = (int(value) for value in matches[0])
    width = abs(x2 - x1) / units
    height = abs(y2 - y1) / units
    return {
        "dbu_per_um": units,
        "die_width_um": width,
        "die_height_um": height,
        "die_area_um2": width * height,
    }


def parse_def_routes(text: str, label: str) -> dict[str, int | float]:
    """Count regular-net Manhattan routing and vias from an Innovus DEF.

    Only the ``NETS`` section is counted; ``SPECIALNETS`` is intentionally
    excluded.  Every ``+ ROUTED``/``NEW`` route statement starts an independent
    path.  ``*`` inherits the previous coordinate within that path.  RECT
    tuples are ignored for length, and via masters such as ``M3_M2_2x1_VH_W``
    are counted once per token.
    """

    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines) if re.match(r"^NETS\s+\d+\s*;", line.strip(), re.I)]
    ends = [index for index, line in enumerate(lines) if re.match(r"^END NETS\s*$", line.strip(), re.I)]
    if len(starts) != 1 or len(ends) != 1 or ends[0] <= starts[0]:
        raise Run2SummaryError(
            f"{label} must contain one ordered NETS/END NETS section"
        )

    total_dbu = 0
    via_count = 0
    route_statements = 0
    current: list[str] | None = None

    def finish(statement_parts: list[str] | None) -> None:
        nonlocal total_dbu, via_count, route_statements
        if not statement_parts:
            return
        statement = " ".join(statement_parts)
        route_statements += 1
        via_count += len(re.findall(r"\bM\d+_M\d+_[A-Za-z0-9_]+\b", statement))
        previous: tuple[int, int] | None = None
        for raw_group in re.findall(r"\(([^()]*)\)", statement):
            tokens = raw_group.split()
            if len(tokens) not in {2, 3}:
                # RECT (dx1 dy1 dx2 dy2) and other non-point tuples.
                continue
            x_token, y_token = tokens[0], tokens[1]
            if x_token == "*":
                if previous is None:
                    raise Run2SummaryError(f"{label} unresolved first-coordinate '*' in {statement}")
                x = previous[0]
            else:
                try:
                    x = int(x_token)
                except ValueError as exc:
                    raise Run2SummaryError(f"{label} invalid x coordinate {x_token!r}") from exc
            if y_token == "*":
                if previous is None:
                    raise Run2SummaryError(f"{label} unresolved first-coordinate '*' in {statement}")
                y = previous[1]
            else:
                try:
                    y = int(y_token)
                except ValueError as exc:
                    raise Run2SummaryError(f"{label} invalid y coordinate {y_token!r}") from exc
            if previous is not None:
                if (x != previous[0]) and (y != previous[1]):
                    raise Run2SummaryError(
                        f"{label} non-Manhattan segment {previous} -> {(x, y)}"
                    )
                total_dbu += abs(x - previous[0]) + abs(y - previous[1])
            previous = (x, y)

    for line in lines[starts[0] + 1 : ends[0]]:
        stripped = line.strip()
        route_start = re.match(r"^(?:\+\s+ROUTED|NEW)\s+\S+\b(.*)$", stripped, re.I)
        if route_start:
            finish(current)
            current = [stripped]
            continue
        if current is not None:
            if stripped.startswith(("+", "-")) or stripped == ";":
                finish(current)
                current = None
            elif stripped:
                current.append(stripped)
    finish(current)
    if route_statements == 0:
        raise Run2SummaryError(f"{label} contains no ROUTED/NEW statements")
    units = int(
        unique_capture(
            text,
            [r"^UNITS DISTANCE MICRONS\s+(\d+)\s*;"],
            f"{label} DBU",
            int,
        )
    )
    return {
        "wire_dbu": total_dbu,
        "wire_um": total_dbu / units,
        "via_count": via_count,
        "route_statements": route_statements,
    }


def validate_def_reference(config: Mapping[str, str], reader: RawReader) -> dict[str, int | float]:
    relative = config["core_iter1_def"]
    text = reader.text(relative, max_bytes=MAX_DEF_BYTES)
    assert text is not None
    result = parse_def_routes(text, "known core iter1 DEF")
    rounded_wire_um = int(float(result["wire_um"]) + 0.5)
    if rounded_wire_um != KNOWN_CORE_ITER1_WIRE_UM or int(result["via_count"]) != KNOWN_CORE_ITER1_VIAS:
        raise Run2SummaryError(
            "DEF route parser cross-check failed: "
            f"got wire={result['wire_um']}um (rounded {rounded_wire_um}) "
            f"vias={result['via_count']}, "
            f"expected wire={KNOWN_CORE_ITER1_WIRE_UM}um vias={KNOWN_CORE_ITER1_VIAS}"
        )
    return {
        **result,
        "rounded_wire_um": rounded_wire_um,
        "expected_wire_um": KNOWN_CORE_ITER1_WIRE_UM,
        "expected_vias": KNOWN_CORE_ITER1_VIAS,
        "status": "PASS",
        "evidence": relative,
    }


def parse_genus(profile: str, top: str, reader: RawReader, root: str, reports: str) -> dict[str, Any]:
    qor_rel = join_relative(root, reports, "qor_mapped.rpt")
    check_rel = join_relative(root, reports, "check_design_unresolved.rpt")
    qor = reader.text(qor_rel)
    check = reader.text(check_rel)
    assert qor is not None and check is not None
    module = str(unique_capture(qor, [r"^\s*Module:\s*(\S+)"], f"{profile} Genus module"))
    if module != top:
        raise Run2SummaryError(f"{profile} Genus module mismatch: {module} != {top}")
    if "No unresolved references" not in check or "No empty modules" not in check:
        raise Run2SummaryError(f"{profile} Genus unresolved/empty check did not pass")
    slack = float(
        unique_capture(
            qor,
            [r"^\s*\S+\s+([+-]?[0-9.]+)\s+[+-]?[0-9.]+\s+\d+\s*$"],
            f"{profile} mapped slack ps",
            float,
        )
    )
    return {
        "leaf_cells": int(unique_capture(qor, [r"Leaf Instance Count\s+(\d+)"], f"{profile} leaf cells", int)),
        "sequential_cells": int(unique_capture(qor, [r"Sequential Instance Count\s+(\d+)"], f"{profile} sequential cells", int)),
        "cell_area_um2": float(unique_capture(qor, [r"^\s*Cell Area\s+([0-9.]+)"], f"{profile} mapped area", float)),
        "setup_slack_ns": slack / 1000.0,
        "unresolved_references": 0,
        "empty_modules": 0,
        "qor_report": qor_rel,
        "check_report": check_rel,
    }


def parse_report_count(text: str, kind: str, label: str) -> int:
    patterns: dict[str, list[str]] = {
        "drc": [
            r"Total number of DRC violations\s*=\s*(\d+)",
            r"Total Violations\s*[:=]\s*(\d+)",
        ],
        "connectivity": [
            r"(\d+)\s+Problem\(s\)",
            r"total\s+(\d+)\s+(?:connectivity\s+)?problems",
        ],
        "placement": [
            r"Total placement violations\s*[:=]\s*(\d+)",
            r"checkPlace[^\n]*?violations\s*[:=]\s*(\d+)",
            r"Total violations\s*[:=]\s*(\d+)",
            r"Total errors\s*[:=]\s*(\d+)",
        ],
    }
    if kind == "connectivity" and re.search(r"No (?:connectivity )?problems", text, re.I):
        return 0
    if kind == "drc" and re.search(r"No DRC violations were found", text, re.I):
        return 0
    if kind == "placement" and re.search(r"No placement violations", text, re.I):
        return 0
    if kind == "placement" and re.search(r"placement checks?\s+(?:passed|clean)", text, re.I):
        return 0
    if kind == "placement":
        unplaced = re.findall(r"^\*info:\s*Unplaced\s*=\s*(\d+)\s*$", text, re.I | re.M)
        if len(set(unplaced)) == 1:
            return int(unplaced[0])
    return int(unique_capture(text, patterns[kind], label, int))


def parse_signal_connectivity(text: str, label: str) -> dict[str, int]:
    total = parse_report_count(text, "connectivity", label)
    unrouted_pg = set(
        re.findall(r"^Net\s+(VDD|VSS):\s+no routing\s*$", text, re.I | re.M)
    )
    pg_count = len({name.upper() for name in unrouted_pg})
    if pg_count > total:
        raise Run2SummaryError(f"{label} PG no-route count exceeds total")
    signal_problems = total - pg_count
    return {
        "reported_problems": total,
        "unrouted_pg_nets": pg_count,
        "signal_problems_excluding_pg": signal_problems,
    }


def parse_ccopt(text: str, label: str) -> dict[str, Any]:
    count = int(
        unique_capture(
            text,
            [r"Found a total of\s+(\d+)\s+clock tree pins with a slew violation"],
            f"{label} slew count",
            int,
        )
    )
    targets: list[float] = []
    achieved: list[float] = []
    for match in re.finditer(
        r"^\S+\s+[+-]?[0-9.]+\s+([0-9.]+)\s+([0-9.]+)\s+[YN]\s+[YN]",
        text,
        re.M,
    ):
        targets.append(float(match.group(1)))
        achieved.append(float(match.group(2)))
    for match in re.finditer(
        r"^(?:Trunk|Leaf)\s+([0-9.]+)\s+\d+\s+"
        r"[0-9.]+\s+[0-9.]+\s+[0-9.]+\s+([0-9.]+)\s+",
        text,
        re.M,
    ):
        targets.append(float(match.group(1)))
        achieved.append(float(match.group(2)))
    if count > 0 and not targets:
        raise Run2SummaryError(f"{label} has slew violations but no target/achieved rows")
    if len(set(targets)) > 1:
        raise Run2SummaryError(f"ambiguous {label} slew targets: {sorted(set(targets))}")
    return {
        "slew_violations": count,
        "slew_target_ns": targets[0] if targets else "",
        "slew_worst_ns": max(achieved) if achieved else "",
    }


def parse_time_design_hold_summary(text: str, label: str) -> dict[str, int | float]:
    """Parse the aggregate ``all`` column from an Innovus hold summary."""

    def first_column(row_label: str, cast: type[int] | type[float]) -> int | float:
        return unique_capture(
            text,
            [rf"^\|\s*{re.escape(row_label)}\s*\|\s*([+-]?[0-9.]+)\s*\|"],
            f"{label} {row_label}",
            cast,
        )

    return {
        "wns_ns": float(first_column("WNS (ns):", float)),
        "tns_ns": float(first_column("TNS (ns):", float)),
        "violating_paths": int(first_column("Violating Paths:", int)),
        "all_paths": int(first_column("All Paths:", int)),
        "density_percent": float(
            unique_capture(
                text,
                [r"^Density:\s*([0-9.]+)%"],
                f"{label} density",
                float,
            )
        ),
    }


def parse_max_transition_report(text: str, label: str) -> dict[str, int | float | str]:
    """Count violating nets/terminals and worst slack in a timeDesign tran report."""

    current_net: str | None = None
    violating_nets: set[str] = set()
    violating_terminals = 0
    worst_slack: float | None = None
    slack_pair = re.compile(r"([+-]?[0-9.]+)r/([+-]?[0-9.]+)f")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "*")):
            continue
        if not line[:1].isspace():
            if re.fullmatch(r"\S+", stripped):
                current_net = stripped
            continue
        pairs = slack_pair.findall(line)
        if len(pairs) != 3:
            continue
        if current_net is None:
            raise Run2SummaryError(f"{label} terminal row has no preceding net")
        rise_slack, fall_slack = (float(value) for value in pairs[2])
        terminal_worst = min(rise_slack, fall_slack)
        if terminal_worst < 0:
            violating_terminals += 1
            violating_nets.add(current_net)
            worst_slack = terminal_worst if worst_slack is None else min(worst_slack, terminal_worst)

    if re.search(r"there is\s+0\s+max_tran violation in the design", text):
        if violating_nets or violating_terminals or worst_slack is not None:
            raise Run2SummaryError(
                f"{label} reports zero max-transition violations but contains negative rows"
            )
        return {
            "violating_nets": 0,
            "violating_terminals": 0,
            "worst_slack_ns": "",
        }

    reported = int(
        unique_capture(
            text,
            [r"there are\s+(\d+)\s+max_tran violations in the design"],
            f"{label} reported max-transition violations",
            int,
        )
    )
    real = int(
        unique_capture(
            text,
            [r"(\d+)\s+violations are real\s*\(remark R\)"],
            f"{label} real max-transition violations",
            int,
        )
    )
    if reported != real or reported != violating_terminals:
        raise Run2SummaryError(
            f"{label} max-transition count mismatch: report={reported} "
            f"real={real} parsed_terminals={violating_terminals}"
        )
    if reported and worst_slack is None:
        raise Run2SummaryError(f"{label} has violations but no parsed negative slack")
    return {
        "violating_nets": len(violating_nets),
        "violating_terminals": violating_terminals,
        "worst_slack_ns": "" if worst_slack is None else worst_slack,
    }


def parse_ocv_factors(
    constraint_text: str,
    slow_report: str,
    fast_report: str,
    label: str,
) -> dict[str, float]:
    """Read the fixed global derates from the executed Innovus source script."""

    rows = re.findall(
        r"^\s*set_timing_derate\s+-early\s+([0-9.]+)\s+"
        r"-late\s+([0-9.]+)\s+-delay_corner\s+(slow_delay|fast_delay)\s*$",
        constraint_text,
        re.M,
    )
    by_corner: dict[str, tuple[float, float]] = {}
    for early, late, corner in rows:
        pair = (float(early), float(late))
        if corner in by_corner and by_corner[corner] != pair:
            raise Run2SummaryError(f"conflicting {label} derates for {corner}")
        by_corner[corner] = pair
    if set(by_corner) != {"slow_delay", "fast_delay"}:
        raise Run2SummaryError(f"{label} must define exactly slow_delay and fast_delay derates")
    result = {
        "slow_early": by_corner["slow_delay"][0],
        "slow_late": by_corner["slow_delay"][1],
        "fast_early": by_corner["fast_delay"][0],
        "fast_late": by_corner["fast_delay"][1],
    }
    if result != KNOWN_OCV_FACTORS:
        raise Run2SummaryError(f"{label} OCV factor contract mismatch: {result}")

    if "-delay_corner slow_delay" not in slow_report:
        raise Run2SummaryError(f"{label} slow derate report is not for slow_delay")
    if "-delay_corner fast_delay" not in fast_report:
        raise Run2SummaryError(f"{label} fast derate report is not for fast_delay")
    slow_values = {
        float(value)
        for value in re.findall(
            r"^(?:Cell Delay|Net Delay Static|Net Delay Dynamic)\s+([0-9.]+)",
            slow_report,
            re.M,
        )
    }
    if slow_values != {result["slow_early"]}:
        raise Run2SummaryError(
            f"{label} slow derate report does not corroborate slow early factor: {slow_values}"
        )
    return result


def summarize_profile(
    name: str,
    cfg: Mapping[str, str],
    reader: RawReader,
    writer: StageWriter,
) -> dict[str, Any]:
    root = cfg["root"]
    top = cfg["top"]
    genus = parse_genus(name, top, reader, root, cfg["genus_reports"])

    report_base = join_relative(root, cfg["candidate_reports"])
    output_base = join_relative(root, cfg["candidate_outputs"])
    checks_base = join_relative(root, cfg["final_checks"])
    area_rel = join_relative(report_base, "area.rpt")
    setup_rel = join_relative(report_base, "timing_setup.rpt")
    hold_rel = join_relative(report_base, "timing_hold.rpt")
    power_rel = join_relative(report_base, "power_vectorless.rpt")
    hold_summary_rel = join_relative(
        report_base,
        "time_design_hold",
        f"{top}_postRoute_hold.summary.gz",
    )
    transition_rel = join_relative(
        report_base,
        "time_design_setup",
        f"{top}_postRoute.tran.gz",
    )
    def_rel = join_relative(output_base, f"{cfg['candidate_basename']}.def")
    ccopt_rel = join_relative(checks_base, "ccopt_clock_trees_60ps.rpt")
    drc_rel = join_relative(checks_base, "internal_route_drc.rpt")
    conn_rel = join_relative(checks_base, "connectivity_signal.rpt")
    place_rel = join_relative(checks_base, "check_place.rpt")

    area_text = reader.text(area_rel)
    setup_text = reader.text(setup_rel)
    hold_text = reader.text(hold_rel)
    power_text = reader.text(power_rel)
    hold_summary_text = reader.gzip_text(hold_summary_rel)
    transition_text = reader.gzip_text(transition_rel)
    def_text = reader.text(def_rel, max_bytes=MAX_DEF_BYTES)
    ccopt_text = reader.text(ccopt_rel)
    drc_text = reader.text(drc_rel)
    conn_text = reader.text(conn_rel)
    place_text = reader.text(place_rel)
    assert all(
        value is not None
        for value in (
            area_text,
            setup_text,
            hold_text,
            power_text,
            def_text,
            ccopt_text,
            drc_text,
            conn_text,
            place_text,
        )
    )

    area_matches = re.findall(
        rf"^\s*{re.escape(top)}\s+(\d+)\s+([0-9.]+)\s*$",
        area_text,
        re.M,
    )
    if len(area_matches) != 1:
        raise Run2SummaryError(f"expected one {name} area row for {top}, got {area_matches}")
    instances = int(area_matches[0][0])
    cell_area = float(area_matches[0][1])
    setup_wns = float(first_capture(setup_text, [r"Slack Time\s+([+-]?[0-9.]+)"], f"{name} setup WNS", float))
    hold_wns = float(first_capture(hold_text, [r"Slack Time\s+([+-]?[0-9.]+)"], f"{name} hold WNS", float))
    hold_summary = parse_time_design_hold_summary(
        hold_summary_text or "", f"{name} timeDesign hold summary"
    )
    if abs(float(hold_summary["wns_ns"]) - hold_wns) > 1e-12:
        raise Run2SummaryError(
            f"{name} hold WNS mismatch: path report={hold_wns} "
            f"summary={hold_summary['wns_ns']}"
        )
    max_transition = parse_max_transition_report(
        transition_text or "", f"{name} timeDesign transition report"
    )
    geometry = parse_def_geometry(def_text, f"{name} candidate DEF")
    routing = parse_def_routes(def_text, f"{name} candidate DEF")
    power = parse_power_report(power_text, f"{name} vectorless")
    ccopt = parse_ccopt(ccopt_text, f"{name} final CCOpt")
    drc_count = parse_report_count(drc_text, "drc", f"{name} DRC count")
    connectivity = parse_signal_connectivity(
        conn_text, f"{name} connectivity count"
    )
    placement_count = parse_report_count(
        place_text, "placement", f"{name} placement count"
    )

    ppa_rows = [
        ("genus_syn_map", "cell_count", genus["leaf_cells"], "count", genus["qor_report"], "mapped leaf cells"),
        ("genus_syn_map", "sequential_cells", genus["sequential_cells"], "count", genus["qor_report"], "scan-free mapped sequential cells"),
        ("genus_syn_map", "cell_area", genus["cell_area_um2"], "um2", genus["qor_report"], "timing-library cell area"),
        ("genus_syn_map", "setup_slack", genus["setup_slack_ns"], "ns", genus["qor_report"], "pre-route mapped report"),
        ("postroute_candidate", "instance_count", instances, "count", area_rel, "candidate standard-cell instances"),
        ("postroute_candidate", "cell_area", cell_area, "um2", area_rel, "candidate standard-cell area"),
        ("postroute_candidate", "die_width", geometry["die_width_um"], "um", def_rel, "derived from DEF DBU and DIEAREA"),
        ("postroute_candidate", "die_height", geometry["die_height_um"], "um", def_rel, "derived from DEF DBU and DIEAREA"),
        ("postroute_candidate", "die_area", geometry["die_area_um2"], "um2", def_rel, "padless block boundary"),
        ("postroute_candidate", "placement_density", hold_summary["density_percent"], "percent", hold_summary_rel, "timeDesign reported placeable-area density"),
        ("postroute_candidate", "routed_wire_length", routing["wire_um"], "um", def_rel, "regular NETS Manhattan length; SPECIALNETS excluded"),
        ("postroute_candidate", "via_count", routing["via_count"], "count", def_rel, "regular NETS via-master tokens"),
        ("postroute_candidate", "setup_wns", setup_wns, "ns", setup_rel, "explicit first/worst path"),
        ("postroute_candidate", "hold_wns", hold_wns, "ns", hold_rel, "explicit first/worst path"),
        ("postroute_candidate", "hold_tns", hold_summary["tns_ns"], "ns", hold_summary_rel, "timeDesign aggregate all-path summary"),
        ("postroute_candidate", "hold_violating_paths", hold_summary["violating_paths"], "count", hold_summary_rel, "timeDesign aggregate all-path summary"),
        ("postroute_candidate", "max_transition_violating_nets", max_transition["violating_nets"], "count", transition_rel, "nets with at least one negative transition slack"),
        ("postroute_candidate", "max_transition_violating_terminals", max_transition["violating_terminals"], "count", transition_rel, "report terminal count cross-checked against summary"),
        ("postroute_candidate", "max_transition_worst_slack", max_transition["worst_slack_ns"], "ns", transition_rel, "worst parsed rise/fall transition slack"),
        ("postroute_candidate", "clock_slew_violations", ccopt["slew_violations"], "count", ccopt_rel, "final CCOpt report"),
        ("postroute_candidate", "power_internal", power["internal"], power["unit"], power_rel, "vectorless candidate report"),
        ("postroute_candidate", "power_switching", power["switching"], power["unit"], power_rel, "vectorless candidate report"),
        ("postroute_candidate", "power_leakage", power["leakage"], power["unit"], power_rel, "vectorless candidate report"),
        ("postroute_candidate", "power_total", power["total"], power["unit"], power_rel, "vectorless candidate report"),
    ]
    writer.csv(
        f"{name}/results/ppa_summary.csv",
        ("profile", "stage", "metric", "value", "unit", "evidence", "limitation"),
        (
            {
                "profile": name,
                "stage": stage,
                "metric": metric,
                "value": value,
                "unit": unit,
                "evidence": evidence,
                "limitation": limitation,
            }
            for stage, metric, value, unit, evidence, limitation in ppa_rows
        ),
    )

    physical_rows = [
        ("unresolved_references", "PASS", 0, genus["check_report"], "Genus elaboration"),
        ("empty_modules", "PASS", 0, genus["check_report"], "Genus elaboration"),
        ("placement", "PASS" if placement_count == 0 else "FAIL", placement_count, place_rel, "internal checkPlace only"),
        ("signal_connectivity_excluding_pg", "PASS" if connectivity["signal_problems_excluding_pg"] == 0 else "FAIL", connectivity["signal_problems_excluding_pg"], conn_rel, "regular connectivity after separately reporting VDD/VSS no-route entries"),
        ("unrouted_pg_nets", "NOT_COMPLETED" if connectivity["unrouted_pg_nets"] else "PASS", connectivity["unrouted_pg_nets"], conn_rel, "VDD/VSS are signal-only checkpoint omissions, not implemented PG"),
        ("internal_route_drc", "PASS" if drc_count == 0 else "FAIL", drc_count, drc_rel, "not foundry DRC"),
        ("setup_timing", "PASS" if setup_wns >= 0 else "FAIL", setup_wns, setup_rel, "does not include hold/DRV closure"),
        ("hold_timing", "PASS" if hold_wns >= 0 else "FAIL", hold_wns, hold_rel, "candidate hold report"),
        ("hold_tns", "PASS" if float(hold_summary["tns_ns"]) >= 0 else "FAIL", hold_summary["tns_ns"], hold_summary_rel, f"{hold_summary['violating_paths']} violating paths"),
        ("hold_violating_paths", "PASS" if int(hold_summary["violating_paths"]) == 0 else "FAIL", hold_summary["violating_paths"], hold_summary_rel, "aggregate all-path hold count"),
        ("max_transition_nets", "PASS" if int(max_transition["violating_nets"]) == 0 else "FAIL", max_transition["violating_nets"], transition_rel, f"{max_transition['violating_terminals']} violating terminals"),
        ("max_transition_terminals", "PASS" if int(max_transition["violating_terminals"]) == 0 else "FAIL", max_transition["violating_terminals"], transition_rel, f"worst slack {max_transition['worst_slack_ns']} ns"),
        ("clock_slew", "PASS" if ccopt["slew_violations"] == 0 else "FAIL", ccopt["slew_violations"], ccopt_rel, "CCOpt engineering target"),
    ]
    writer.csv(
        f"{name}/results/physical_checks.csv",
        ("profile", "check", "status", "value", "evidence", "limitation"),
        (
            {
                "profile": name,
                "check": check,
                "status": status,
                "value": value,
                "evidence": evidence,
                "limitation": limitation,
            }
            for check, status, value, evidence, limitation in physical_rows
        ),
    )

    writer.text(
        f"{name}/reports/genus_summary.txt",
        "\n".join(
            [
                f"profile={name}",
                f"top={top}",
                f"mapped_leaf_cells={genus['leaf_cells']}",
                f"mapped_sequential_cells={genus['sequential_cells']}",
                f"mapped_cell_area_um2={genus['cell_area_um2']}",
                f"mapped_setup_slack_ns={genus['setup_slack_ns']}",
                "unresolved_references=0",
                "empty_modules=0",
                f"qor_evidence={genus['qor_report']}",
                f"elaboration_evidence={genus['check_report']}",
            ]
        ),
    )
    writer.text(
        f"{name}/reports/innovus_summary.txt",
        "\n".join(
            [
                f"profile={name}",
                f"top={top}",
                f"candidate_basename={cfg['candidate_basename']}",
                f"instances={instances}",
                f"cell_area_um2={cell_area}",
                f"def_dbu_per_um={geometry['dbu_per_um']}",
                f"die_width_um={geometry['die_width_um']}",
                f"die_height_um={geometry['die_height_um']}",
                f"placement_density_percent={hold_summary['density_percent']}",
                f"routed_wire_length_um={routing['wire_um']}",
                f"via_count={routing['via_count']}",
                f"route_statements={routing['route_statements']}",
                f"setup_wns_ns={setup_wns}",
                f"hold_wns_ns={hold_wns}",
                f"hold_tns_ns={hold_summary['tns_ns']}",
                f"hold_violating_paths={hold_summary['violating_paths']}",
                f"max_transition_violating_nets={max_transition['violating_nets']}",
                f"max_transition_violating_terminals={max_transition['violating_terminals']}",
                f"max_transition_worst_slack_ns={max_transition['worst_slack_ns']}",
                f"clock_slew_violations={ccopt['slew_violations']}",
                f"clock_slew_target_ns={ccopt['slew_target_ns']}",
                f"clock_slew_worst_ns={ccopt['slew_worst_ns']}",
                f"internal_route_drc={drc_count}",
                f"regular_connectivity_reported_problems={connectivity['reported_problems']}",
                f"signal_connectivity_problems_excluding_pg={connectivity['signal_problems_excluding_pg']}",
                f"unrouted_pg_nets={connectivity['unrouted_pg_nets']}",
                f"placement_violations={placement_count}",
                f"vectorless_total_{power['unit']}={power['total']}",
                f"candidate_report_dir={report_base}",
                f"final_checks_dir={checks_base}",
            ]
        ),
    )

    slow_rel = join_relative(root, cfg["innovus_reports"], "timing_derate_slow.rpt")
    fast_rel = join_relative(root, cfg["innovus_reports"], "timing_derate_fast.rpt")
    ocv_script_rel = cfg["ocv_constraint_script"]
    slow = reader.text(slow_rel)
    fast = reader.text(fast_rel)
    ocv_script = reader.text(ocv_script_rel)
    assert slow is not None and fast is not None and ocv_script is not None
    ocv = parse_ocv_factors(ocv_script, slow, fast, f"{name} OCV")
    writer.text(
        f"{name}/reports/ocv_assumption.txt",
        "\n".join(
            [
                f"profile={name}",
                "type=fixed global engineering derate",
                f"slow_early={ocv['slow_early']}",
                f"slow_late={ocv['slow_late']}",
                f"fast_early={ocv['fast_early']}",
                f"fast_late={ocv['fast_late']}",
                f"constraint_script={ocv_script_rel}",
                f"constraint_script_sha256={reader.used[ocv_script_rel]}",
                f"slow_derate_report={slow_rel}",
                f"slow_derate_sha256={reader.used[slow_rel]}",
                f"fast_derate_report={fast_rel}",
                f"fast_derate_sha256={reader.used[fast_rel]}",
                "boundary=engineering derates with shared QRC technology; not foundry signoff corners",
            ]
        ),
    )

    return {
        "top": top,
        "genus": genus,
        "instances": instances,
        "cell_area_um2": cell_area,
        "geometry": geometry,
        "routing": routing,
        "setup_wns_ns": setup_wns,
        "hold_wns_ns": hold_wns,
        "hold_summary": hold_summary,
        "max_transition": max_transition,
        "ocv": ocv,
        "clock": ccopt,
        "drc": drc_count,
        "connectivity": connectivity,
        "placement": placement_count,
        "vectorless_power": power,
    }


def parse_bool(value: str, label: str) -> bool:
    value = value.strip().lower()
    if value in {"1", "true", "pass", "passed"}:
        return True
    if value in {"0", "false", "fail", "failed"}:
        return False
    raise Run2SummaryError(f"invalid boolean {label}: {value!r}")


def read_regression(reader: RawReader, relative: str, expected_rows: int) -> tuple[list[str], list[dict[str, str]], dict[str, Any]]:
    text = reader.text(relative)
    assert text is not None
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows or set(rows[0]) != REGRESSION_COLUMNS:
        raise Run2SummaryError(f"regression columns mismatch in {relative}")
    if len(rows) != expected_rows:
        raise Run2SummaryError(
            f"regression row count mismatch in {relative}: {len(rows)} != {expected_rows}"
        )
    case_ids = [row["case_id"] for row in rows]
    if len(case_ids) != len(set(case_ids)):
        raise Run2SummaryError(f"duplicate case_id in {relative}")
    passed = sum(parse_bool(row["pass"], f"{relative}:{row['case_id']}") for row in rows)
    for row in rows:
        for name in ("samples", "cycles"):
            if int(row[name]) <= 0:
                raise Run2SummaryError(f"nonpositive {name} in {relative}:{row['case_id']}")
    return list(rows[0].keys()), rows, {
        "cases": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "status": "PASS" if passed == len(rows) else "FAIL",
    }


def summarize_regression(config: Mapping[str, str], reader: RawReader, writer: StageWriter) -> dict[str, Any]:
    canonical_manifest = reader.text(config["canonical_manifest"])
    raw_manifest = reader.text(config["raw_manifest"])
    audit_text = reader.text(config["manifest_audit"])
    assert canonical_manifest is not None and raw_manifest is not None and audit_text is not None
    if len([line for line in canonical_manifest.splitlines() if line.strip()]) != 36:
        raise Run2SummaryError("canonical manifest is not 36 rows")
    if len([line for line in raw_manifest.splitlines() if line.strip()]) != 4:
        raise Run2SummaryError("raw manifest is not 4 rows")
    try:
        audit = json.loads(audit_text)
    except json.JSONDecodeError as exc:
        raise Run2SummaryError(f"invalid manifest audit JSON: {exc}") from exc
    if audit.get("canonical_cases") != 36 or audit.get("raw_xmodel_cases") != 4:
        raise Run2SummaryError("manifest audit cohort counts are not 36/4")

    writer.text("manifests/canonical_digital_36.manifest", canonical_manifest)
    writer.text("manifests/raw_xmodel_4.manifest", raw_manifest)
    writer.json("manifests/manifest_audit.json", audit)

    summary: dict[str, Any] = {}
    summary_rows: list[dict[str, Any]] = []
    for cohort, key, expected in (
        ("canonical_digital_36", "rtl36_results", 36),
        ("raw_xmodel_4", "raw4_results", 4),
    ):
        fields, rows, item = read_regression(reader, config[key], expected)
        writer.csv(
            "regression/rtl36_results.csv" if expected == 36 else "regression/raw4_results.csv",
            fields,
            rows,
        )
        summary[cohort] = item
        summary_rows.append({"cohort": cohort, **item, "evidence": config[key]})
    writer.csv(
        "regression/regression_summary.csv",
        ("cohort", "cases", "passed", "failed", "status", "evidence"),
        summary_rows,
    )
    return summary


def summarize_lec(config: Mapping[str, str], reader: RawReader, writer: StageWriter) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    text_sections: list[str] = []
    result: dict[str, Any] = {}
    for profile, key in (("core", "core_result"), ("axi", "axi_result")):
        text = reader.text(config[key])
        assert text is not None
        values = parse_key_values(
            text, ("total", "non_equivalent", "abort", "unknown"), f"{profile} LEC"
        )
        numeric = {name: int(values[name]) for name in ("total", "non_equivalent", "abort", "unknown")}
        if numeric["total"] <= 0:
            raise Run2SummaryError(f"{profile} LEC has no compare points")
        status = (
            "PASS"
            if numeric["non_equivalent"] == numeric["abort"] == numeric["unknown"] == 0
            else "FAIL"
        )
        item = {"profile": profile, **numeric, "status": status, "evidence": config[key]}
        rows.append(item)
        result[profile] = item
        text_sections.extend(
            [
                f"[{profile}]",
                *(f"{name}={numeric[name]}" for name in ("total", "non_equivalent", "abort", "unknown")),
                f"status={status}",
                f"evidence={config[key]}",
                "",
            ]
        )
    writer.csv(
        "lec/equivalence_summary.csv",
        ("profile", "total", "non_equivalent", "abort", "unknown", "status", "evidence"),
        rows,
    )
    writer.text("lec/result_summary.txt", "\n".join(text_sections))
    return result


def error_lines(text: str) -> list[str]:
    result: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.search(
            r"(?:\*\*ERROR:|^ERROR\s*:|^ERROR\s+(?!Limit\b)|invalid command|TCL ERROR)",
            stripped,
            re.I,
        ):
            if stripped not in result:
                result.append(stripped)
    return result


def parse_pg_connectivity(text: str, label: str) -> int:
    categories = [
        int(value)
        for value in re.findall(r"^\s*(\d+)\s+Problem\(s\)\s+\(IMPVFC-", text, re.M)
    ]
    total = int(
        unique_capture(
            text,
            [r"^\s*(\d+)\s+total info\(s\) created\.\s*$"],
            f"{label} total",
            int,
        )
    )
    if not categories or sum(categories) != total:
        raise Run2SummaryError(
            f"{label} category/total mismatch: categories={categories} total={total}"
        )
    return total


def parse_pg_geometry(text: str, label: str) -> int:
    blocks = re.findall(r"Begin Summary \.\.\.(.*?)End Summary", text, re.S)
    if len(blocks) != 1:
        raise Run2SummaryError(f"expected one {label} final summary block")
    components = [
        int(value)
        for _, value in re.findall(
            r"^\s*(Cells|SameNet|Wiring|Antenna|Short|Overlap)\s*:\s*(\d+)\s*$",
            blocks[0],
            re.M,
        )
    ]
    if len(components) != 6:
        raise Run2SummaryError(f"{label} final summary is incomplete")
    total = int(
        unique_capture(
            text,
            [r"Verification Complete\s*:\s*(\d+)\s+Viols\."],
            f"{label} total",
            int,
        )
    )
    if sum(components) != total:
        raise Run2SummaryError(
            f"{label} component/total mismatch: components={components} total={total}"
        )
    return total


def summarize_pg(config: Mapping[str, Any], reader: RawReader, writer: StageWriter) -> dict[str, Any]:
    log = reader.text(config["run_log"])
    assert log is not None
    errors = error_lines(log)
    assumptions = reader.text(config["assumptions"])
    connectivity = reader.text(config["connectivity"])
    geometry = reader.text(config["geometry"])
    filler = reader.text(config["filler"], required=False)
    assert assumptions is not None and connectivity is not None and geometry is not None
    connectivity_count = parse_pg_connectivity(connectivity, "PG connectivity")
    geometry_count = parse_pg_geometry(geometry, "PG geometry")
    expected_connectivity = int(config["expected_connectivity_violations"])
    expected_geometry = int(config["expected_geometry_violations"])
    if connectivity_count != expected_connectivity or geometry_count != expected_geometry:
        raise Run2SummaryError(
            "PG final contract mismatch: "
            f"connectivity={connectivity_count}/{expected_connectivity} "
            f"geometry={geometry_count}/{expected_geometry}"
        )
    status = "FAILED" if errors or connectivity_count or geometry_count else "COMPLETED_EXPLORATORY"
    rows: list[dict[str, Any]] = [
        {
            "check": "run_status",
            "status": status,
            "value": len(errors),
            "evidence": config["run_log"],
            "limitation": "geometry-only exploratory PG; no IR/EM signoff",
        }
    ]
    assumption_values = parse_key_values(
        assumptions,
        ("scope", "ir_em_analyzed", "top_pg_pads_or_sources"),
        "PG assumptions",
    )
    for key, value in sorted(assumption_values.items()):
        rows.append(
            {
                "check": key,
                "status": "OBSERVED",
                "value": value,
                "evidence": config["assumptions"],
                "limitation": "reported script assumption",
            }
        )
    rows.extend(
        [
            {
                "check": "pg_connectivity",
                "status": "FAIL" if connectivity_count else "PASS",
                "value": connectivity_count,
                "evidence": config["connectivity"],
                "limitation": "internal special-net connectivity only",
            },
            {
                "check": "pg_geometry",
                "status": "FAIL" if geometry_count else "PASS",
                "value": geometry_count,
                "evidence": config["geometry"],
                "limitation": "obsolete internal verifyGeometry; not foundry DRC",
            },
        ]
    )
    for check, text, evidence in (
        ("filler_report_present", filler, config["filler"]),
    ):
        rows.append(
            {
                "check": check,
                "status": "OBSERVED" if text is not None else "NOT_COMPLETED",
                "value": 1 if text is not None else 0,
                "evidence": evidence,
                "limitation": "presence only; not foundry signoff",
            }
        )
    writer.csv(
        "pg/attempt_summary.csv",
        ("check", "status", "value", "evidence", "limitation"),
        rows,
    )
    writer.text(
        "pg/failure_reason.txt",
        "\n".join(errors) if errors else "No recognized tool error; exploratory PG script completed.",
    )
    return {
        "status": status,
        "errors": errors,
        "assumptions": assumption_values,
        "connectivity_violations": connectivity_count,
        "geometry_violations": geometry_count,
    }


def marker_status(text: str, label: str) -> dict[str, Any]:
    fail_markers = re.findall(r"\bASIC_[A-Z0-9_]*FAIL[A-Z0-9_]*\b", text)
    pass_markers = re.findall(r"\bASIC_[A-Z0-9_]*PASS\b", text)
    done_markers = re.findall(r"\bASIC_[A-Z0-9_]*DONE\b", text)
    unknown_count = len(re.findall(r"\bASIC_[A-Z0-9_]*UNKNOWN\b", text))
    if fail_markers:
        status = "FAIL"
    elif pass_markers:
        status = "PASS"
    elif done_markers:
        status = "OBSERVED_ONLY"
    else:
        raise Run2SummaryError(f"no recognized PASS/FAIL/DONE marker in {label}")
    delayed = ""
    matches = re.findall(r"delayed_transitions=(\d+)", text)
    if matches:
        if len(set(matches)) != 1:
            raise Run2SummaryError(f"ambiguous delayed transition count in {label}")
        delayed = int(matches[0])
    return {
        "status": status,
        "pass_markers": len(pass_markers),
        "fail_markers": len(fail_markers),
        "done_markers": len(done_markers),
        "unknown_markers": unknown_count,
        "delayed_transitions": delayed,
    }


def parse_unmodified_gate_result(text: str, label: str) -> dict[str, Any]:
    rows = list(csv.DictReader(io.StringIO(text)))
    if len(rows) != 1 or set(rows[0]) != REGRESSION_COLUMNS:
        raise Run2SummaryError(f"{label} must contain exactly one canonical regression row")
    row = rows[0]
    if parse_bool(row["pass"], f"{label} pass") or not parse_bool(
        row["final_valid"], f"{label} final_valid"
    ):
        raise Run2SummaryError(f"{label} does not preserve the observed output-X failure")
    unknown_fields = [
        row[name].strip().lower()
        for name in (
            "final_pred_class",
            "final_mem_nsr",
            "final_mem_chf",
            "final_mem_arr",
            "final_mem_aff",
        )
    ]
    if unknown_fields != ["x"] * len(unknown_fields):
        raise Run2SummaryError(f"{label} expected X on prediction and membrane outputs")
    if int(row["samples"]) != 1_800_000:
        raise Run2SummaryError(f"{label} is not a full 1.8M-sample raw case")
    return {"case_id": row["case_id"], "samples": int(row["samples"]), "result": "output_X"}


def parse_xpr_unavailable(text: str, label: str) -> dict[str, str]:
    if not re.search(r"Xcelium_Xpessimism_App.*license checkout failed", text, re.I):
        raise Run2SummaryError(f"{label} lacks XPR license-checkout failure")
    if not re.search(r"\*F,NOLICN:.*Unable to checkout license", text, re.I):
        raise Run2SummaryError(f"{label} lacks the fatal XPR NOLICN marker")
    return {"status": "NOT_RUN", "result": "license_unavailable"}


def parse_forced_gate_seed(text: str, label: str) -> dict[str, Any]:
    if re.search(r"ASIC_MANIFEST_FAIL|\*F,[A-Z0-9_]+|Simulation interrupted", text):
        raise Run2SummaryError(f"{label} contains a fatal/fail/interrupted marker")
    seed = int(
        unique_capture(
            text,
            [r"SVSEED set from command line:\s*(\d+)"],
            f"{label} seed",
            int,
        )
    )
    stimulus = parse_manifest_markers(text, label)
    overall = re.findall(r"ASIC_MANIFEST_PASS\s+pass=(\d+)\s+total=(\d+)", text)
    if len(overall) != 1 or tuple(map(int, overall[0])) != (1, 1):
        raise Run2SummaryError(f"{label} lacks the exact one-case manifest PASS summary")
    if stimulus["cases"] != 1 or stimulus["passed"] != 1 or stimulus["samples"] != 1_800_000:
        raise Run2SummaryError(f"{label} is not an exact full raw one-case PASS")
    summaries = re.findall(
        r"GPDK45_GATE_POWERUP_SUMMARY\s+initialized_instances=(\d+)\s+"
        r"zeros=(\d+)\s+ones=(\d+)\s+release_ns=(\d+)\s+release_unknown=(\d+)",
        text,
    )
    if len(summaries) != 1:
        raise Run2SummaryError(f"{label} must contain one forced-powerup summary")
    initialized, zeros, ones, release_ns, release_unknown = map(int, summaries[0])
    if zeros + ones != initialized:
        raise Run2SummaryError(f"{label} zero/one initialized coverage does not sum")
    x_summaries = re.findall(
        r"GPDK45_GATE_X_SUMMARY\s+initial_unknown=(\d+)\s+runtime_x_transitions=(\d+)",
        text,
    )
    if len(x_summaries) != 1:
        raise Run2SummaryError(f"{label} must contain one X-monitor summary")
    initial_unknown, runtime_x = map(int, x_summaries[0])
    return {
        "seed": seed,
        "initialized_instances": initialized,
        "zeros": zeros,
        "ones": ones,
        "release_ns": release_ns,
        "release_unknown": release_unknown,
        "initial_unknown": initial_unknown,
        "runtime_x_transitions": runtime_x,
        "samples": stimulus["samples"],
        "status": "CONDITIONAL_PASS",
    }


def summarize_gate(config: Mapping[str, Any], reader: RawReader, writer: StageWriter) -> dict[str, Any]:
    unmodified_text = reader.text(config["unmodified_four_state_result"])
    xpr_text = reader.text(config["xpr_log"])
    assert unmodified_text is not None and xpr_text is not None
    unmodified = parse_unmodified_gate_result(
        unmodified_text, config["unmodified_four_state_result"]
    )
    xpr = parse_xpr_unavailable(xpr_text, config["xpr_log"])

    seed_results: list[dict[str, Any]] = []
    for _, relative in sorted(config["mapped_seed_logs"].items()):
        text = reader.text(relative)
        assert text is not None
        item = parse_forced_gate_seed(text, relative)
        item["evidence"] = relative
        seed_results.append(item)
    if tuple(sorted(item["seed"] for item in seed_results)) != KNOWN_MAPPED_SEEDS:
        raise Run2SummaryError(f"mapped gate seed set mismatch: {seed_results}")
    for item in seed_results:
        if (
            item["initialized_instances"] != KNOWN_MAPPED_SEQUENTIAL_INSTANCES
            or item["release_ns"] != KNOWN_FORCED_RELEASE_NS
            or item["release_unknown"] != 0
            or item["initial_unknown"] != 0
            or item["runtime_x_transitions"] != 0
        ):
            raise Run2SummaryError(f"mapped gate final contract mismatch for seed {item['seed']}: {item}")

    rows: list[dict[str, Any]] = [
        {
            "check": "unmodified_four_state_full_raw_case0",
            "seed": "",
            "status": "FAIL",
            "result": unmodified["result"],
            "sequential_covered": "",
            "sequential_expected": "",
            "release_ns": "",
            "release_unknowns": "",
            "initial_unknowns": "",
            "runtime_x_transitions": "",
            "evidence": config["unmodified_four_state_result"],
            "claim_boundary": "unmodified four-state full raw result remained X",
        },
        {
            "check": "XPR_mode",
            "seed": "",
            "status": xpr["status"],
            "result": xpr["result"],
            "sequential_covered": "",
            "sequential_expected": "",
            "release_ns": "",
            "release_unknowns": "",
            "initial_unknowns": "",
            "runtime_x_transitions": "",
            "evidence": config["xpr_log"],
            "claim_boundary": "XPR analysis could not execute without the app license",
        },
    ]
    for item in sorted(seed_results, key=lambda row: row["seed"]):
        rows.append(
            {
                "check": "forced_two_state_mapped_full_raw_case0",
                "seed": item["seed"],
                "status": item["status"],
                "result": "exact_PASS",
                "sequential_covered": item["initialized_instances"],
                "sequential_expected": KNOWN_MAPPED_SEQUENTIAL_INSTANCES,
                "release_ns": item["release_ns"],
                "release_unknowns": item["release_unknown"],
                "initial_unknowns": item["initial_unknown"],
                "runtime_x_transitions": item["runtime_x_transitions"],
                "evidence": item["evidence"],
                "claim_boundary": "testbench-conditioned finite-seed initialization sensitivity",
            }
        )
    rows.append(
        {
            "check": "forced_two_state_sequential_coverage",
            "seed": ",".join(str(seed) for seed in KNOWN_MAPPED_SEEDS),
            "status": "CONDITIONAL_PASS",
            "result": f"{KNOWN_MAPPED_SEQUENTIAL_INSTANCES}/{KNOWN_MAPPED_SEQUENTIAL_INSTANCES}_releaseX0",
            "sequential_covered": KNOWN_MAPPED_SEQUENTIAL_INSTANCES,
            "sequential_expected": KNOWN_MAPPED_SEQUENTIAL_INSTANCES,
            "release_ns": KNOWN_FORCED_RELEASE_NS,
            "release_unknowns": 0,
            "initial_unknowns": 0,
            "runtime_x_transitions": 0,
            "evidence": ";".join(item["evidence"] for item in seed_results),
            "claim_boundary": "aggregate of three testbench-conditioned finite-seed runs",
        }
    )
    writer.csv(
        "gate/gate_verification_summary.csv",
        (
            "check",
            "seed",
            "status",
            "result",
            "sequential_covered",
            "sequential_expected",
            "release_ns",
            "release_unknowns",
            "initial_unknowns",
            "runtime_x_transitions",
            "evidence",
            "claim_boundary",
        ),
        rows,
    )
    writer.text(
        "gate/x_pessimism_boundary.txt",
        "\n".join(
            [
                "unmodified_four_state_result=output_X",
                "xpr_status=license_unavailable",
                f"forced_mapped_seeds={','.join(str(seed) for seed in KNOWN_MAPPED_SEEDS)}",
                f"forced_mapped_sequential_coverage={KNOWN_MAPPED_SEQUENTIAL_INSTANCES}/{KNOWN_MAPPED_SEQUENTIAL_INSTANCES}",
                "forced_mapped_release_unknowns=0",
                "boundary=Forced initialization is a testbench-conditioned sampled sensitivity experiment.",
                "boundary=Finite seeds do not prove unmodified GLS, reset robustness, or physical power-up state.",
                "boundary=Zero monitored release X does not prove absence of every internal X state.",
            ]
        ),
    )
    return {
        "unmodified_four_state": unmodified,
        "xpr": xpr,
        "mapped_seeds": seed_results,
        "mapped_sequential_coverage": f"{KNOWN_MAPPED_SEQUENTIAL_INSTANCES}/{KNOWN_MAPPED_SEQUENTIAL_INSTANCES}",
        "mapped_release_unknowns": 0,
    }


def sdf_severities(text: str) -> dict[str, Any]:
    codes = re.findall(r"\*([EWF]),([A-Z0-9_]+)", text, re.I)
    counts = {"error": 0, "warning": 0, "fatal": 0}
    names: dict[str, int] = {}
    for severity, code in codes:
        key = {"E": "error", "W": "warning", "F": "fatal"}[severity.upper()]
        counts[key] += 1
        names[code.upper()] = names.get(code.upper(), 0) + 1
    return {**counts, "codes": ";".join(f"{name}:{count}" for name, count in sorted(names.items()))}


def parse_disabled_sdf_tchecks(text: str, label: str) -> dict[str, int | bool]:
    matches = re.findall(
        r"No\. of Tchecks\s*=\s*(\d+)\s+"
        r"No\. of Disabled Tchecks\s*=\s*(\d+)\s+"
        r"Annotated\s*=\s*([0-9.]+)%\s*\((\d+)/(\d+)\)",
        text,
    )
    if len(matches) != 1:
        raise Run2SummaryError(f"{label} must contain one SDF timing-check statistic")
    total, disabled, percent, annotated, denominator = matches[0]
    total_i = int(total)
    disabled_i = int(disabled)
    if (
        total_i <= 0
        or disabled_i != total_i
        or float(percent) != 0.0
        or int(annotated) != 0
        or int(denominator) != 0
    ):
        raise Run2SummaryError(
            f"{label} does not prove all SDF timing checks disabled: {matches[0]}"
        )
    return {"total": total_i, "disabled": disabled_i, "all_disabled": True}


def summarize_sdf(config: Mapping[str, str], reader: RawReader, writer: StageWriter) -> dict[str, Any]:
    annotation_rel = config["max_annotation_log"]
    simulation_rel = config["max_simulation_log"]
    annotation = reader.text(annotation_rel)
    simulation = reader.text(simulation_rel)
    assert annotation is not None and simulation is not None
    if "sdf" not in annotation.lower() or not re.search(
        r"MTM control:\s+MAXIMUM", simulation
    ):
        raise Run2SummaryError("MAX-SDF pilot lacks MAXIMUM annotation evidence")
    severity = sdf_severities(annotation)
    sdfncap = len(re.findall(r"\*W,SDFNCAP\b", annotation, re.I))
    if (
        severity["error"]
        or severity["fatal"]
        or severity["warning"] != sdfncap
        or sdfncap != KNOWN_SDFNCAP_WARNINGS
    ):
        raise Run2SummaryError(
            f"MAX-SDF annotation contract mismatch: severity={severity} SDFNCAP={sdfncap}"
        )
    sim = parse_forced_gate_seed(simulation, simulation_rel)
    tchecks = parse_disabled_sdf_tchecks(simulation, simulation_rel)
    if (
        sim["seed"] != KNOWN_SDF_SEED
        or sim["initialized_instances"] != KNOWN_SDF_SEQUENTIAL_INSTANCES
        or sim["release_ns"] != KNOWN_FORCED_RELEASE_NS
        or sim["release_unknown"] != 0
        or sim["initial_unknown"] != 0
        or sim["runtime_x_transitions"] != 0
    ):
        raise Run2SummaryError(f"MAX-SDF final contract mismatch: {sim}")
    item = {
        "corner": "max",
        "status": "CONDITIONAL_PASS",
        "seed": sim["seed"],
        "result": f"{KNOWN_SDF_SEQUENTIAL_INSTANCES}/{KNOWN_SDF_SEQUENTIAL_INSTANCES}_exact_PASS",
        "sequential_covered": sim["initialized_instances"],
        "sequential_expected": KNOWN_SDF_SEQUENTIAL_INSTANCES,
        "release_ns": sim["release_ns"],
        "release_unknowns": sim["release_unknown"],
        "timing_checks_disabled": tchecks["all_disabled"],
        "disabled_timing_checks": tchecks["disabled"],
        "sdfncap_warnings": sdfncap,
        "annotation_errors": severity["error"],
        "annotation_fatals": severity["fatal"],
        "annotation_codes": severity["codes"],
        "annotation_evidence": annotation_rel,
        "simulation_evidence": simulation_rel,
        "claim_boundary": "single-seed forced-initialization MAX-SDF pilot with timing checks disabled",
    }
    writer.csv(
        "sdf/sdf_pilot_summary.csv",
        (
            "corner",
            "status",
            "seed",
            "result",
            "sequential_covered",
            "sequential_expected",
            "release_ns",
            "release_unknowns",
            "timing_checks_disabled",
            "disabled_timing_checks",
            "sdfncap_warnings",
            "annotation_errors",
            "annotation_fatals",
            "annotation_codes",
            "annotation_evidence",
            "simulation_evidence",
            "claim_boundary",
        ),
        (item,),
    )
    return {"max": item}


def parse_prefix_marker(text: str, label: str) -> dict[str, int]:
    begin = re.findall(
        r"ASIC_POWER_PREFIX_WINDOW_BEGIN mode=(\d+) samples=(\d+) "
        r"cycles_per_sample=(\d+) window_cycles=(\d+)",
        text,
    )
    end = re.findall(
        r"ASIC_POWER_PREFIX_WINDOW_END mode=(\d+) accepted=(\d+) window_cycles=(\d+)",
        text,
    )
    if len(begin) != 1 or len(end) != 1:
        raise Run2SummaryError(f"expected one prefix begin/end marker in {label}")
    mode, samples, cycles_per_sample, window_cycles = map(int, begin[0])
    end_mode, accepted, end_cycles = map(int, end[0])
    if mode != end_mode or window_cycles != end_cycles:
        raise Run2SummaryError(f"prefix marker mismatch in {label}")
    return {
        "mode": mode,
        "samples": samples,
        "accepted": accepted,
        "cycles_per_sample": cycles_per_sample,
        "window_cycles": window_cycles,
    }


def parse_manifest_markers(text: str, label: str) -> dict[str, int]:
    rows = re.findall(
        r"ASIC_MANIFEST_CASE case=\d+ pass=(\d+) pred=\d+ expected=\d+ "
        r"samples=(\d+) cycles=(\d+)",
        text,
    )
    if not rows:
        raise Run2SummaryError(f"no manifest case markers in {label}")
    passed = sum(int(row[0]) for row in rows)
    return {
        "cases": len(rows),
        "passed": passed,
        "samples": sum(int(row[1]) for row in rows),
        "cycles": sum(int(row[2]) for row in rows),
    }


def parse_mapped_activity_boundary(text: str, label: str) -> dict[str, Any]:
    """Validate functional/X markers in an untouched mapped-gate console."""

    if re.search(r"ASIC_(?:MANIFEST|POWER_PREFIX)_FAIL|\*F,[A-Z0-9_]+|Simulation interrupted", text):
        raise Run2SummaryError(f"{label} contains a fatal/fail/interrupted marker")
    seed = int(
        unique_capture(
            text,
            [r"SVSEED set from command line:\s*(\d+)"],
            f"{label} seed",
            int,
        )
    )
    summaries = re.findall(
        r"GPDK45_GATE_POWERUP_SUMMARY\s+initialized_instances=(\d+)\s+"
        r"zeros=(\d+)\s+ones=(\d+)\s+release_ns=(\d+)\s+release_unknown=(\d+)",
        text,
    )
    if len(summaries) != 1:
        raise Run2SummaryError(f"{label} must contain one mapped power-up summary")
    initialized, zeros, ones, release_ns, release_unknown = map(int, summaries[0])
    if zeros + ones != initialized:
        raise Run2SummaryError(f"{label} mapped power-up zero/one coverage does not sum")
    x_summaries = re.findall(
        r"GPDK45_GATE_X_SUMMARY\s+initial_unknown=(\d+)\s+runtime_x_transitions=(\d+)",
        text,
    )
    if len(x_summaries) != 1:
        raise Run2SummaryError(f"{label} must contain one mapped X-monitor summary")
    initial_unknown, runtime_x = map(int, x_summaries[0])
    if (
        seed != 11
        or initialized != KNOWN_MAPPED_SEQUENTIAL_INSTANCES
        or release_ns != KNOWN_FORCED_RELEASE_NS
        or release_unknown != 0
        or initial_unknown != 0
        or runtime_x != 0
    ):
        raise Run2SummaryError(
            f"{label} mapped activity boundary mismatch: seed={seed} initialized={initialized} "
            f"release_ns={release_ns} releaseX={release_unknown} "
            f"initialX={initial_unknown} runtimeX={runtime_x}"
        )
    if "Simulation complete via $finish" not in text:
        raise Run2SummaryError(f"{label} lacks normal Xcelium completion")
    return {
        "seed": seed,
        "initialized_instances": initialized,
        "release_ns": release_ns,
        "release_unknown": release_unknown,
        "initial_unknown": initial_unknown,
        "runtime_x_transitions": runtime_x,
    }


def parse_access_launch_record(
    text: str,
    *,
    tag: str,
    stimulus_log: str,
    stimulus_sha256: str,
    top: str,
    label: str,
) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise Run2SummaryError(f"invalid {label} JSON: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise Run2SummaryError(f"{label} must have schema_version 1")
    runs = payload.get("runs")
    if not isinstance(runs, dict) or tag not in runs or not isinstance(runs[tag], dict):
        raise Run2SummaryError(f"{label} lacks one object for tag {tag}")
    record = runs[tag]
    required = (
        "command",
        "seed",
        "force_release_ns",
        "dump_scope",
        "top",
        "stimulus_log",
        "stimulus_log_sha256",
        "normalization_full_xz_mode",
    )
    missing = [key for key in required if key not in record]
    if missing:
        raise Run2SummaryError(f"{label}:{tag} lacks keys: {missing}")
    command = record["command"]
    if not isinstance(command, str):
        raise Run2SummaryError(f"{label}:{tag} command must be a string")
    if not re.search(r"(?:^|\s)-access\s+\+rwc(?:\s|$)", command):
        raise Run2SummaryError(f"{label}:{tag} lacks -access +rwc")
    if not re.search(r"(?:^|\s)-delay_mode\s+zero(?:\s|$)", command):
        raise Run2SummaryError(f"{label}:{tag} lacks -delay_mode zero")
    scope = str(record["dump_scope"])
    if (
        int(record["seed"]) != 11
        or int(record["force_release_ns"]) != KNOWN_FORCED_RELEASE_NS
        or record["top"] != top
        or not scope.endswith(f".{top}")
        or record["stimulus_log"] != stimulus_log
        or record["stimulus_log_sha256"] != stimulus_sha256
        or record["normalization_full_xz_mode"] != "preserve"
    ):
        raise Run2SummaryError(f"{label}:{tag} launch/provenance contract mismatch")
    return {
        "seed": 11,
        "force_release_ns": KNOWN_FORCED_RELEASE_NS,
        "dump_scope": scope,
        "top": top,
        "access": "+rwc",
        "delay_mode": "zero",
        "normalization_full_xz_mode": "preserve",
    }


def parse_innovus_activity_annotation(text: str, label: str) -> dict[str, str]:
    rejected = (
        r"Parse Error",
        r"scope[^\n]*(?:mismatch|not found|does not exist)",
        r"(?:cannot|unable to)[^\n]*scope",
    )
    for pattern in rejected:
        if re.search(pattern, text, re.I):
            raise Run2SummaryError(f"{label} contains rejected activity annotation text: {pattern}")
    if len(re.findall(r"^Begin Processing SAIF file\s*$", text, re.M)) != 1:
        raise Run2SummaryError(f"{label} lacks one SAIF processing start")
    if len(re.findall(r"^Ended Processing SAIF file:", text, re.M)) != 1:
        raise Run2SummaryError(f"{label} lacks one SAIF processing completion")
    if len(re.findall(r"'read_activity_file' finished successfully\.", text)) != 1:
        raise Run2SummaryError(f"{label} lacks one successful read_activity_file completion")
    return {"status": "PASS", "method": "normalized_direct_xcelium_saif"}


def summarize_power(
    config: Mapping[str, Any],
    profiles: Mapping[str, Mapping[str, Any]],
    reader: RawReader,
    writer: StageWriter,
) -> dict[str, Any]:
    prefix_text = reader.text(config["prefix_manifest"])
    assert prefix_text is not None
    try:
        prefix_manifest = json.loads(prefix_text)
    except json.JSONDecodeError as exc:
        raise Run2SummaryError(f"invalid power prefix manifest: {exc}") from exc
    for key in (
        "prefix_samples",
        "clock_hz",
        "sample_rate_hz",
        "cycles_per_sample",
        "window_cycles",
        "window_seconds",
        "reaches_60000_sample_snapshot",
        "reaches_30_snapshot_decision",
        "adc_data_idle_policy",
        "claim_boundary",
    ):
        if key not in prefix_manifest:
            raise Run2SummaryError(f"power prefix manifest lacks {key}")
    if prefix_manifest["reaches_60000_sample_snapshot"] or prefix_manifest["reaches_30_snapshot_decision"]:
        raise Run2SummaryError("short-prefix manifest unexpectedly reaches snapshot/decision")
    clock_hz = int(prefix_manifest["clock_hz"])
    sample_rate_hz = int(prefix_manifest["sample_rate_hz"])
    if clock_hz <= 0 or sample_rate_hz <= 0 or clock_hz % sample_rate_hz:
        raise Run2SummaryError("prefix manifest has invalid clock/sample-rate ratio")
    if clock_hz // sample_rate_hz != int(prefix_manifest["cycles_per_sample"]):
        raise Run2SummaryError("prefix manifest cycles_per_sample is inconsistent")
    if int(prefix_manifest["prefix_samples"]) * int(prefix_manifest["cycles_per_sample"]) != int(prefix_manifest["window_cycles"]):
        raise Run2SummaryError("prefix manifest window_cycles is inconsistent")
    expected_seconds = int(prefix_manifest["window_cycles"]) / clock_hz
    if abs(float(prefix_manifest["window_seconds"]) - expected_seconds) > 1e-12:
        raise Run2SummaryError("prefix manifest window_seconds is inconsistent")

    rows: list[dict[str, Any]] = []
    result: dict[str, Any] = {}
    for name, run in config["runs"].items():
        profile = run["profile"]
        profile_cfg = DEFAULT_CONFIG["profiles"][profile]
        # Use the caller's resolved profile root, not the module constant.
        profile_cfg = profiles[profile]  # type: ignore[assignment]
        root = str(profile_cfg["root"])
        top = str(profile_cfg["top"])
        tag = run["tag"]
        power_status_rel = join_relative(root, "reports/activity_power", tag, "activity_power_status.txt")
        annotation_rel = join_relative(root, "reports/activity_power", tag, "activity_annotation.rpt")
        power_rel = join_relative(root, "reports/activity_power", tag, "power_detailed.rpt")
        stimulus_rel = run["stimulus_log"]
        launch_rel = run["launch_record"]

        power_status = parse_key_values(
            reader.text(power_status_rel) or "",
            (
                "status",
                "activity_format",
                "extraction_status",
                "activity_delay_model",
                "unannotated_default_activity",
            ),
            f"{name} power",
        )
        annotation = reader.text(annotation_rel)
        power_text = reader.text(power_rel)
        stimulus = reader.text(stimulus_rel)
        launch_text = reader.text(launch_rel)
        assert (
            annotation is not None
            and power_text is not None
            and stimulus is not None
            and launch_text is not None
        )
        if (
            int(power_status["status"]) != 0
            or int(power_status["extraction_status"]) != 0
            or power_status["activity_format"].upper() != "SAIF"
            or power_status["activity_delay_model"].lower() != "zero"
            or float(power_status["unannotated_default_activity"]) != 0.0
        ):
            raise Run2SummaryError(f"{name} activity power status/format is not successful SAIF")
        annotation_status = parse_innovus_activity_annotation(
            annotation, f"{name} Innovus activity annotation"
        )
        mapped_boundary = parse_mapped_activity_boundary(stimulus, stimulus_rel)
        launch = parse_access_launch_record(
            launch_text,
            tag=tag,
            stimulus_log=stimulus_rel,
            stimulus_sha256=reader.used[stimulus_rel],
            top=top,
            label=launch_rel,
        )
        if (
            mapped_boundary["seed"] != launch["seed"]
            or mapped_boundary["release_ns"] != launch["force_release_ns"]
        ):
            raise Run2SummaryError(f"{name} launch record disagrees with functional console")
        power = parse_power_report(power_text, name)

        if name == "accelerated_gap2":
            stim = parse_manifest_markers(stimulus, stimulus_rel)
            overall = re.findall(
                r"ASIC_MANIFEST_PASS\s+pass=(\d+)\s+total=(\d+)", stimulus
            )
            if (
                stim["passed"] != stim["cases"]
                or stim["cases"] != 1
                or stim["samples"] != 1_800_000
                or len(overall) != 1
                or tuple(map(int, overall[0])) != (1, 1)
            ):
                raise Run2SummaryError("accelerated activity stimulus has failed manifest cases")
            cadence = "seed-conditioned zero-delay mapped-gate accelerated full-record replay"
            sample_count = stim["samples"]
            window_cycles = stim["cycles"]
            window_seconds = ""
        else:
            stim = parse_prefix_marker(stimulus, stimulus_rel)
            stim_marker = marker_status(stimulus, stimulus_rel)
            if stim_marker["status"] != "PASS":
                raise Run2SummaryError(f"{name} stimulus did not finish with PASS")
            expected_mode = 0 if name == "active_wait_idle" else 1
            if stim["mode"] != expected_mode:
                raise Run2SummaryError(f"{name} prefix MODE mismatch")
            if stim["samples"] != int(prefix_manifest["prefix_samples"]):
                raise Run2SummaryError(f"{name} prefix sample-count mismatch")
            if stim["cycles_per_sample"] != int(prefix_manifest["cycles_per_sample"]):
                raise Run2SummaryError(f"{name} cycles-per-sample mismatch")
            if stim["window_cycles"] != int(prefix_manifest["window_cycles"]):
                raise Run2SummaryError(f"{name} window-cycle mismatch")
            expected_accepted = 0 if expected_mode == 0 else stim["samples"]
            if stim["accepted"] != expected_accepted:
                raise Run2SummaryError(f"{name} accepted-count mismatch")
            cadence = (
                "active-wait idle matched window"
                if expected_mode == 0
                else "literal 1 kSPS short raw prefix"
            )
            sample_count = stim["accepted"]
            window_cycles = stim["window_cycles"]
            window_seconds = prefix_manifest["window_seconds"]

        item = {
            "profile": profile,
            "tag": tag,
            "mode": name,
            "status": "PASS",
            "internal_mw": power["internal"],
            "switching_mw": power["switching"],
            "leakage_mw": power["leakage"],
            "total_mw": power["total"],
            "sample_count": sample_count,
            "window_cycles": window_cycles,
            "window_seconds": window_seconds,
            "cadence": cadence,
            "stimulus_seed": mapped_boundary["seed"],
            "mapped_sequential_coverage": f"{mapped_boundary['initialized_instances']}/{KNOWN_MAPPED_SEQUENTIAL_INSTANCES}",
            "release_unknowns": mapped_boundary["release_unknown"],
            "initial_unknowns": mapped_boundary["initial_unknown"],
            "runtime_x_transitions": mapped_boundary["runtime_x_transitions"],
            "xcelium_access": launch["access"],
            "delay_mode": launch["delay_mode"],
            "dump_scope": launch["dump_scope"],
            "normalization_full_xz_mode": launch["normalization_full_xz_mode"],
            "activity_annotation_status": annotation_status["status"],
            "unannotated_report_status": power_status.get(
                "unannotated_report_status", "NOT_REPORTED"
            ),
            "stimulus_evidence": stimulus_rel,
            "launch_evidence": launch_rel,
            "power_evidence": power_rel,
            "annotation_evidence": annotation_rel,
            "claim_boundary": (
                "seed-conditioned zero-delay mapped-gate accelerated activity; not unmodified GLS, wall-time 1 kSPS, or silicon power"
                if name == "accelerated_gap2"
                else "seed-conditioned zero-delay mapped-gate short prefix only; not unmodified GLS, snapshot, decision, or energy/decision"
            ),
        }
        rows.append(item)
        result[name] = item

    idle = result["active_wait_idle"]
    literal = result["literal_1ksps_prefix"]
    if idle["profile"] != literal["profile"] or idle["window_cycles"] != literal["window_cycles"]:
        raise Run2SummaryError("idle/literal power windows are not matched")
    delta = {
        "profile": literal["profile"],
        "tag": f"{literal['tag']}_minus_{idle['tag']}",
        "mode": "literal_minus_active_wait_idle",
        "status": "DERIVED_MATCHED_WINDOW",
        "internal_mw": round(float(literal["internal_mw"]) - float(idle["internal_mw"]), 8),
        "switching_mw": round(float(literal["switching_mw"]) - float(idle["switching_mw"]), 8),
        "leakage_mw": round(float(literal["leakage_mw"]) - float(idle["leakage_mw"]), 8),
        "total_mw": round(float(literal["total_mw"]) - float(idle["total_mw"]), 8),
        "sample_count": literal["sample_count"],
        "window_cycles": literal["window_cycles"],
        "window_seconds": literal["window_seconds"],
        "cadence": "matched literal prefix minus matched active-wait idle",
        "stimulus_seed": literal["stimulus_seed"],
        "mapped_sequential_coverage": literal["mapped_sequential_coverage"],
        "release_unknowns": 0,
        "initial_unknowns": 0,
        "runtime_x_transitions": 0,
        "xcelium_access": literal["xcelium_access"],
        "delay_mode": literal["delay_mode"],
        "dump_scope": f"idle:{idle['dump_scope']};literal:{literal['dump_scope']}",
        "normalization_full_xz_mode": "preserve",
        "activity_annotation_status": "PASS_BOTH",
        "unannotated_report_status": (
            f"idle:{idle['unannotated_report_status']};"
            f"literal:{literal['unannotated_report_status']}"
        ),
        "stimulus_evidence": f"{idle['stimulus_evidence']};{literal['stimulus_evidence']}",
        "launch_evidence": f"{idle['launch_evidence']};{literal['launch_evidence']}",
        "power_evidence": f"{idle['power_evidence']};{literal['power_evidence']}",
        "annotation_evidence": f"{idle['annotation_evidence']};{literal['annotation_evidence']}",
        "claim_boundary": "incremental short-prefix estimate; not pure clock power or energy/decision",
    }
    rows.append(delta)
    result["literal_minus_active_wait_idle"] = delta

    fields = (
        "profile",
        "tag",
        "mode",
        "status",
        "internal_mw",
        "switching_mw",
        "leakage_mw",
        "total_mw",
        "sample_count",
        "window_cycles",
        "window_seconds",
        "cadence",
        "stimulus_seed",
        "mapped_sequential_coverage",
        "release_unknowns",
        "initial_unknowns",
        "runtime_x_transitions",
        "xcelium_access",
        "delay_mode",
        "dump_scope",
        "normalization_full_xz_mode",
        "activity_annotation_status",
        "unannotated_report_status",
        "stimulus_evidence",
        "launch_evidence",
        "power_evidence",
        "annotation_evidence",
        "claim_boundary",
    )
    writer.csv("power/activity_power_summary.csv", fields, rows)
    writer.text(
        "power/activity_annotation_summary.txt",
        "\n".join(
            [
                *(f"{name}: tag={item['tag']} status={item['status']} annotation={item['annotation_evidence']}" for name, item in result.items() if name != "literal_minus_active_wait_idle"),
                f"prefix_manifest={config['prefix_manifest']}",
                f"prefix_manifest_sha256={reader.used[config['prefix_manifest']]}",
                "method=direct Xcelium mapped-gate -access +rwc, normalized SAIF, Innovus zero-delay activity annotation",
                "boundary=all activity runs use testbench-conditioned seed 11 initialization with 6045/6045 coverage and release X 0",
                "boundary=executed normalization preserved fully-X/Z entries; unannotated default is 0.0 and matched idle/literal retains identical X/Z populations",
                "boundary=unannotated_report_status is retained as diagnostic metadata and is not an annotation-coverage PASS",
                "boundary=active-wait idle contains leakage, clock, and idle-state activity; it is not pure clock-tree power",
                "boundary=literal-minus-idle is a short-prefix matched-window delta, not full-decision energy",
            ]
        ),
    )
    return result


def build_summary(raw_root: Path, staging_dir: Path, config: dict[str, Any], override_hash: str | None) -> dict[str, Any]:
    raw_root = raw_root.resolve()
    staging_dir = staging_dir.resolve()
    try:
        staging_dir.relative_to(raw_root)
    except ValueError:
        pass
    else:
        raise Run2SummaryError("staging directory must not be inside raw root")

    reader = RawReader(raw_root)
    writer = StageWriter(staging_dir)
    def_parser_crosscheck = validate_def_reference(config["def_reference"], reader)
    profiles = {
        name: summarize_profile(name, cfg, reader, writer)
        for name, cfg in config["profiles"].items()
    }
    regression = summarize_regression(config["regression"], reader, writer)
    lec = summarize_lec(config["lec"], reader, writer)
    pg = summarize_pg(config["pg"], reader, writer)
    gate = summarize_gate(config["gate"], reader, writer)
    sdf = summarize_sdf(config["sdf"], reader, writer)
    power = summarize_power(config["power"], config["profiles"], reader, writer)

    manifest = {
        "schema_version": 1,
        "raw_root_name": raw_root.name,
        "override_sha256": override_hash,
        "resolved_config": config,
        "def_parser_crosscheck": def_parser_crosscheck,
        "profiles": profiles,
        "regression": regression,
        "lec": lec,
        "pg": pg,
        "gate": gate,
        "sdf": sdf,
        "power": power,
        "raw_inputs": [
            {"path": path, "sha256": digest}
            for path, digest in sorted(reader.used.items())
        ],
        "claim_boundary": [
            "Parsed engineering evidence only; no unparsed metric is inferred.",
            "SDF/gate pilots do not replace full functional regression.",
            "Literal-1-kSPS prefix power does not represent a snapshot or final decision.",
            "Executed direct-SAIF normalization preserved fully-X/Z signal entries; unannotated default activity was 0.0, and matched idle/literal runs retain the same X/Z population.",
            "PG checks are exploratory and not IR/EM or foundry signoff.",
        ],
    }
    writer.json("run_manifest.json", manifest)
    writer.text(
        "README_KR.md",
        "\n".join(
            [
                "# GPDK045 run-2 parser staging",
                "",
                "이 디렉터리는 raw run tree의 명시된 report/result만 fail-closed 방식으로 파싱한 public-builder 입력이다.",
                "수치는 run_manifest.json과 각 CSV/TXT에 있으며 raw netlist, PDK, DEF/SDF/SPEF, SAIF/SHM은 포함하지 않는다.",
                "",
                f"core_candidate={config['profiles']['core']['candidate_basename']}",
                f"axi_candidate={config['profiles']['axi']['candidate_basename']}",
                f"canonical_regression_status={regression['canonical_digital_36']['status']}",
                f"raw4_regression_status={regression['raw_xmodel_4']['status']}",
                f"core_lec_status={lec['core']['status']}",
                f"axi_lec_status={lec['axi']['status']}",
                f"pg_status={pg['status']}",
                "",
                "경계: short gate/SDF pilot는 full regression이 아니며 literal prefix power는 snapshot/decision power가 아니다.",
            ]
        ),
    )
    return manifest


def build_summary_atomic(
    raw_root: Path,
    staging_dir: Path,
    config: dict[str, Any],
    override_hash: str | None,
) -> dict[str, Any]:
    """Publish the staging tree only after every required parser succeeds."""

    raw_root = raw_root.resolve()
    target = staging_dir.resolve()
    if target.exists():
        raise Run2SummaryError(f"atomic staging target must not already exist: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.relative_to(raw_root)
    except ValueError:
        pass
    else:
        raise Run2SummaryError("staging directory must not be inside raw root")

    with tempfile.TemporaryDirectory(
        prefix=f".{target.name}.partial-", dir=target.parent
    ) as temporary:
        temporary_path = Path(temporary)
        manifest = build_summary(raw_root, temporary_path, config, override_hash)
        temporary_path.replace(target)
    return manifest


def synthetic_power_report(internal: float, switching: float, leakage: float) -> str:
    total = internal + switching + leakage
    return (
        "* Power Units = 1mW\n"
        f"Total Internal Power: {internal:.6f}\n"
        f"Total Switching Power: {switching:.6f}\n"
        f"Total Leakage Power: {leakage:.6f}\n"
        f"Total Power: {total:.6f}\n"
    )


def self_test() -> None:
    global KNOWN_CORE_ITER1_WIRE_UM, KNOWN_CORE_ITER1_VIAS
    # Parser-level synthetic snippets cover success, missing, and ambiguity.
    assert unique_capture("Cell Area 12.5\nCell Area 12.5\n", [r"Cell Area\s+([0-9.]+)"], "area", float) == 12.5
    try:
        unique_capture("Cell Area 12.5\nCell Area 13.0\n", [r"Cell Area\s+([0-9.]+)"], "area", float)
    except Run2SummaryError:
        pass
    else:
        raise AssertionError("ambiguous values must fail")
    try:
        unique_capture("no metric\n", [r"Cell Area\s+([0-9.]+)"], "area", float)
    except Run2SummaryError:
        pass
    else:
        raise AssertionError("missing values must fail")

    power = parse_power_report(synthetic_power_report(1.0, 0.5, 0.01), "synthetic")
    assert abs(float(power["total"]) - 1.51) < 1e-9
    geometry = parse_def_geometry(
        "UNITS DISTANCE MICRONS 2000 ;\nDIEAREA ( 0 0 ) ( 842000 836380 ) ;\n",
        "synthetic",
    )
    assert geometry["die_width_um"] == 421.0
    assert geometry["die_height_um"] == 418.19
    routed = parse_def_routes(
        "UNITS DISTANCE MICRONS 1000 ;\n"
        "NETS 1 ;\n"
        "- n1\n"
        "  + ROUTED Metal2 ( 0 0 ) ( 1000 * ) ( * 2000 ) M2_M1_VH\n"
        "    NEW Metal3 ( 1000 2000 ) ( 3000 * ) M3_M2_2x1_VH_W\n"
        "    NEW Metal2 ( 3000 2000 ) RECT ( -80 -370 80 0 )\n"
        " ;\n"
        "END NETS\n",
        "synthetic",
    )
    assert routed["wire_dbu"] == 5000
    assert routed["wire_um"] == 5.0
    assert routed["via_count"] == 2
    try:
        parse_def_routes(
            "UNITS DISTANCE MICRONS 1000 ;\nNETS 1 ;\n"
            "- n + ROUTED Metal2 ( 0 0 ) ( 10 10 ) ;\nEND NETS\n",
            "diagonal",
        )
    except Run2SummaryError:
        pass
    else:
        raise AssertionError("non-Manhattan DEF segment must fail")
    ccopt = parse_ccopt(
        "Found a total of 2 clock tree pins with a slew violation.\n"
        "slow_delay:setup.late 0.002 0.060 0.062 N N auto pin/A\n",
        "synthetic",
    )
    assert ccopt["slew_violations"] == 2 and ccopt["slew_worst_ns"] == 0.062
    hold_summary = parse_time_design_hold_summary(
        "| WNS (ns):| -0.016 | -0.016 | 0.894 |\n"
        "| TNS (ns):| -0.518 | -0.518 | 0.000 |\n"
        "| Violating Paths:| 107 | 107 | 0 |\n"
        "| All Paths:| 6287 | 6246 | 237 |\n"
        "Density: 83.215%\n",
        "synthetic",
    )
    assert hold_summary["tns_ns"] == -0.518
    assert hold_summary["violating_paths"] == 107
    transition = parse_max_transition_report(
        "# Net / InstPin MaxTranTime TranTime TranSlack CellPort Remark\n"
        "net_a\n"
        "  pin/A 0.280r/0.280f 0.756r/0.228f -0.476r/0.052f BUFX2/A R\n"
        "  pin/Y 0.280r/0.280f 0.756r/0.228f -0.476r/0.052f NOR4X1/Y R\n"
        "*info: there are 2 max_tran violations in the design.\n"
        "*info: 2 violations are real (remark R).\n",
        "synthetic",
    )
    assert transition == {
        "violating_nets": 1,
        "violating_terminals": 2,
        "worst_slack_ns": -0.476,
    }
    ocv = parse_ocv_factors(
        "set_timing_derate -early 0.95 -late 1.00 -delay_corner slow_delay\n"
        "set_timing_derate -early 1.00 -late 1.05 -delay_corner fast_delay\n",
        "Command: report_timing_derate -delay_corner slow_delay\n"
        "Cell Delay 0.950 --\nNet Delay Static 0.950 --\nNet Delay Dynamic 0.950 --\n",
        "Command: report_timing_derate -delay_corner fast_delay\n",
        "synthetic",
    )
    assert ocv == KNOWN_OCV_FACTORS
    assert parse_pg_connectivity(
        "78 Problem(s) (IMPVFC-96)\n1 Problem(s) (IMPVFC-200)\n"
        "40 Problem(s) (IMPVFC-92)\n52 Problem(s) (IMPVFC-94)\n"
        "171 total info(s) created.\n",
        "synthetic",
    ) == 171
    assert parse_pg_geometry(
        "Begin Summary ...\nCells: 0\nSameNet: 0\nWiring: 180\n"
        "Antenna: 0\nShort: 535\nOverlap: 0\nEnd Summary\n"
        "Verification Complete : 715 Viols. 0 Wrngs.\n",
        "synthetic",
    ) == 715
    assert marker_status("ASIC_GATE_16S_PASS delayed_transitions=3\n", "synthetic")["status"] == "PASS"
    assert marker_status("ASIC_GATE_16S_FAIL_COUNT 1\n", "synthetic")["status"] == "FAIL"
    sev = sdf_severities("SDF annotation\n*W,SDFWARN warning\n*E,SDFBAD error\n")
    assert sev["warning"] == 1 and sev["error"] == 1
    assert parse_disabled_sdf_tchecks(
        "No. of Tchecks = 24188 No. of Disabled Tchecks = 24188 "
        "Annotated = 0.00% (0/0)\n",
        "synthetic",
    )["all_disabled"]
    prefix = parse_prefix_marker(
        "ASIC_POWER_PREFIX_WINDOW_BEGIN mode=1 samples=100 cycles_per_sample=100000 window_cycles=10000000\n"
        "ASIC_POWER_PREFIX_WINDOW_END mode=1 accepted=100 window_cycles=10000000\n",
        "synthetic",
    )
    assert prefix["accepted"] == 100 and prefix["window_cycles"] == 10_000_000
    manifest = parse_manifest_markers(
        "ASIC_MANIFEST_CASE case=1 pass=1 pred=0 expected=0 samples=1800000 cycles=5401263\n",
        "synthetic",
    )
    assert manifest["cases"] == 1 and manifest["samples"] == 1_800_000

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        regression_path = root / "regression.csv"
        regression_row = {
            "case_id": "1",
            "expected_class": "0",
            "final_pred_class": "0",
            "pass": "1",
            "final_valid": "1",
            "samples": "1800000",
            "cycles": "5401263",
            "expected_mem_nsr": "1",
            "final_mem_nsr": "1",
            "expected_mem_chf": "2",
            "final_mem_chf": "2",
            "expected_mem_arr": "3",
            "final_mem_arr": "3",
            "expected_mem_aff": "4",
            "final_mem_aff": "4",
        }
        with regression_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=sorted(REGRESSION_COLUMNS))
            writer.writeheader()
            writer.writerow(regression_row)
        reader = RawReader(root)
        _, _, regression = read_regression(reader, "regression.csv", 1)
        assert regression["status"] == "PASS" and regression["passed"] == 1
        lec = parse_key_values(
            "total=10\nnon_equivalent=0\nabort=0\nunknown=0\n",
            ("total", "non_equivalent", "abort", "unknown"),
            "synthetic LEC",
        )
        assert lec["total"] == "10"
        assert error_lines("**ERROR: (PG-1): no legal ring\n")
        try:
            reader.text("missing.rpt")
        except Run2SummaryError:
            pass
        else:
            raise AssertionError("missing explicit path must fail")
        try:
            normalized_relative("../escape", "synthetic")
        except Run2SummaryError:
            pass
        else:
            raise AssertionError("path traversal must fail")

    final_override = Path(__file__).with_name("asic_gpdk45_run2_final_override.json")
    final_config, final_override_hash = load_config(final_override)
    assert final_override_hash is not None
    assert final_config["profiles"]["axi"]["root"] == "axi_run"
    assert (
        final_config["profiles"]["axi"]["candidate_reports"]
        == "reports/drv_closure/cts50_drv2"
    )
    assert (
        final_config["profiles"]["axi"]["candidate_outputs"]
        == "outputs/drv_closure/cts50_drv2"
    )
    assert (
        final_config["profiles"]["axi"]["final_checks"]
        == "reports/final_checks/cts50_drv2"
    )
    assert {
        name: run["tag"] for name, run in final_config["power"]["runs"].items()
    } == KNOWN_POWER_TAGS
    with tempfile.TemporaryDirectory() as temp:
        rejected = Path(temp) / "direct.json"
        rejected.write_text(
            json.dumps(
                {
                    "power": {
                        "runs": {
                            "accelerated_gap2": {
                                "tag": "raw_aff_accelerated_direct_seed11"
                            }
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        try:
            load_config(rejected)
        except Run2SummaryError:
            pass
        else:
            raise AssertionError("no-access direct power tags must be rejected")

    # End-to-end synthetic raw tree exercises every staging category.  The
    # locked DEF reference totals are temporarily reduced for this fixture.
    old_wire = KNOWN_CORE_ITER1_WIRE_UM
    old_vias = KNOWN_CORE_ITER1_VIAS
    KNOWN_CORE_ITER1_WIRE_UM = 5
    KNOWN_CORE_ITER1_VIAS = 2
    try:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            raw = base / "raw"
            stage = base / "stage"
            raw.mkdir()
            config, override_hash = load_config(None)

            def write(relative: str, text: str) -> None:
                path = raw / PurePosixPath(relative)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")

            def write_gzip(relative: str, text: str) -> None:
                path = raw / PurePosixPath(relative)
                path.parent.mkdir(parents=True, exist_ok=True)
                with gzip.open(path, "wb") as handle:
                    handle.write(text.encode("utf-8"))

            synthetic_def = (
                "UNITS DISTANCE MICRONS 1000 ;\n"
                "DIEAREA ( 0 0 ) ( 10000 20000 ) ;\n"
                "NETS 1 ;\n"
                "- n1\n"
                "  + ROUTED Metal2 ( 0 0 ) ( 1000 * ) ( * 2000 ) M2_M1_VH\n"
                "    NEW Metal3 ( 1000 2000 ) ( 3000 * ) M3_M2_2x1_VH_W\n"
                " ;\nEND NETS\n"
            )
            write(
                config["profiles"]["core"]["ocv_constraint_script"],
                "set_timing_derate -early 0.95 -late 1.00 -delay_corner slow_delay\n"
                "set_timing_derate -early 1.00 -late 1.05 -delay_corner fast_delay\n",
            )
            for profile, cfg in config["profiles"].items():
                root = "" if cfg["root"] == "." else f"{cfg['root']}/"
                top = cfg["top"]
                genus_dir = f"{root}{cfg['genus_reports']}"
                write(
                    f"{genus_dir}/qor_mapped.rpt",
                    f"Module: {top}\ncore_clk 10000.0\n"
                    "core_clk 2500.0 0.0 0\n"
                    "Leaf Instance Count 10\nSequential Instance Count 4\n"
                    "Cell Area 20.5\n",
                )
                write(
                    f"{genus_dir}/check_design_unresolved.rpt",
                    f"No unresolved references in design '{top}'\n"
                    f"No empty modules in design '{top}'\n",
                )
                innovus_dir = f"{root}{cfg['innovus_reports']}"
                write(
                    f"{innovus_dir}/timing_derate_slow.rpt",
                    "Command: report_timing_derate -delay_corner slow_delay\n"
                    "Cell Delay 0.950 --\nNet Delay Static 0.950 --\n"
                    "Net Delay Dynamic 0.950 --\n",
                )
                write(
                    f"{innovus_dir}/timing_derate_fast.rpt",
                    "Command: report_timing_derate -delay_corner fast_delay\n",
                )
                report_dir = f"{root}{cfg['candidate_reports']}"
                output_dir = f"{root}{cfg['candidate_outputs']}"
                checks_dir = f"{root}{cfg['final_checks']}"
                write(f"{report_dir}/area.rpt", f"{top} 12 22.5\n")
                write(f"{report_dir}/timing_setup.rpt", "Path 1\nSlack Time 1.25\n")
                write(f"{report_dir}/timing_hold.rpt", "Path 1\nSlack Time -0.10\n")
                write(f"{report_dir}/power_vectorless.rpt", synthetic_power_report(1.0, 0.5, 0.01))
                write_gzip(
                    f"{report_dir}/time_design_hold/{top}_postRoute_hold.summary.gz",
                    "| WNS (ns):| -0.10 | -0.10 | 0.50 |\n"
                    "| TNS (ns):| -0.20 | -0.20 | 0.00 |\n"
                    "| Violating Paths:| 2 | 2 | 0 |\n"
                    "| All Paths:| 10 | 8 | 2 |\nDensity: 80.125%\n",
                )
                write_gzip(
                    f"{report_dir}/time_design_setup/{top}_postRoute.tran.gz",
                    "# Net / InstPin MaxTranTime TranTime TranSlack CellPort Remark\n"
                    "net_a\n"
                    "  pin/A 0.280r/0.280f 0.306r/0.200f -0.026r/0.080f BUF/A R\n"
                    "  pin/Y 0.280r/0.280f 0.306r/0.200f -0.026r/0.080f BUF/Y R\n"
                    "*info: there are 2 max_tran violations in the design.\n"
                    "*info: 2 violations are real (remark R).\n",
                )
                write(f"{output_dir}/{cfg['candidate_basename']}.def", synthetic_def)
                write(
                    f"{checks_dir}/ccopt_clock_trees_60ps.rpt",
                    "Found a total of 2 clock tree pins with a slew violation.\n"
                    "slow_delay:setup.late 0.002 0.060 0.062 N N auto pin/A\n",
                )
                write(f"{checks_dir}/internal_route_drc.rpt", "Total number of DRC violations = 0\n")
                write(f"{checks_dir}/connectivity_signal.rpt", "0 Problem(s)\n")
                write(f"{checks_dir}/check_place.rpt", "Total placement violations: 0\n")

            # Manifests and exact regression CSVs.
            write(config["regression"]["canonical_manifest"], "\n".join(f"{i} row" for i in range(36)) + "\n")
            write(config["regression"]["raw_manifest"], "\n".join(f"{i} row" for i in range(4)) + "\n")
            write(
                config["regression"]["manifest_audit"],
                json.dumps({"canonical_cases": 36, "raw_xmodel_cases": 4}) + "\n",
            )

            def regression_csv(count: int) -> str:
                buffer = io.StringIO(newline="")
                fields = sorted(REGRESSION_COLUMNS)
                output = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
                output.writeheader()
                for index in range(count):
                    output.writerow(
                        {
                            "case_id": index,
                            "expected_class": 0,
                            "final_pred_class": 0,
                            "pass": 1,
                            "final_valid": 1,
                            "samples": 1_800_000,
                            "cycles": 5_401_263,
                            "expected_mem_nsr": 1,
                            "final_mem_nsr": 1,
                            "expected_mem_chf": 2,
                            "final_mem_chf": 2,
                            "expected_mem_arr": 3,
                            "final_mem_arr": 3,
                            "expected_mem_aff": 4,
                            "final_mem_aff": 4,
                        }
                    )
                return buffer.getvalue()

            write(config["regression"]["rtl36_results"], regression_csv(36))
            write(config["regression"]["raw4_results"], regression_csv(4))

            for key in ("core_result", "axi_result"):
                write(
                    config["lec"][key],
                    "total=10\nnon_equivalent=0\nabort=0\nunknown=0\n",
                )

            write(config["pg"]["run_log"], "PG exploratory run completed\n")
            write(
                config["pg"]["assumptions"],
                "scope=exploratory geometry only\n"
                "ir_em_analyzed=false\ntop_pg_pads_or_sources=false\n",
            )
            write(
                config["pg"]["connectivity"],
                "78 Problem(s) (IMPVFC-96)\n"
                "1 Problem(s) (IMPVFC-200)\n"
                "40 Problem(s) (IMPVFC-92)\n"
                "52 Problem(s) (IMPVFC-94)\n"
                "171 total info(s) created.\n",
            )
            write(
                config["pg"]["geometry"],
                "Begin Summary ...\nCells: 0\nSameNet: 0\nWiring: 180\n"
                "Antenna: 0\nShort: 535\nOverlap: 0\nEnd Summary\n"
                "Verification Complete : 715 Viols. 0 Wrngs.\n",
            )
            write(config["pg"]["filler"], "filler report\n")

            gate_buffer = io.StringIO(newline="")
            gate_writer = csv.DictWriter(
                gate_buffer, fieldnames=sorted(REGRESSION_COLUMNS), lineterminator="\n"
            )
            gate_writer.writeheader()
            gate_writer.writerow(
                {
                    "case_id": 9,
                    "expected_class": 3,
                    "final_pred_class": "x",
                    "pass": 0,
                    "final_valid": 1,
                    "samples": 1_800_000,
                    "cycles": 5_401_263,
                    "expected_mem_nsr": 0,
                    "final_mem_nsr": "x",
                    "expected_mem_chf": 0,
                    "final_mem_chf": "x",
                    "expected_mem_arr": 0,
                    "final_mem_arr": "x",
                    "expected_mem_aff": 30,
                    "final_mem_aff": "x",
                }
            )
            write(config["gate"]["unmodified_four_state_result"], gate_buffer.getvalue())
            write(
                config["gate"]["xpr_log"],
                "Xcelium_Xpessimism_App 23.00 - license checkout failed\n"
                "xmsim: *F,NOLICN: Unable to checkout license for the simulation.\n",
            )
            for seed, relative in zip(
                KNOWN_MAPPED_SEEDS,
                sorted(config["gate"]["mapped_seed_logs"].values()),
            ):
                write(
                    relative,
                    f"SVSEED set from command line: {seed}\n"
                    "ASIC_MANIFEST_CASE case=9 pass=1 pred=3 expected=3 "
                    "samples=1800000 cycles=5401263\n"
                    "ASIC_MANIFEST_PASS pass=1 total=1\n"
                    "GPDK45_GATE_POWERUP_SUMMARY initialized_instances=6045 "
                    "zeros=3000 ones=3045 release_ns=10 release_unknown=0\n"
                    "GPDK45_GATE_X_SUMMARY initial_unknown=0 runtime_x_transitions=0\n",
                )

            write(
                config["sdf"]["max_annotation_log"],
                "SDF MAXIMUM annotation\n"
                + "".join("*W,SDFNCAP synthetic warning\n" for _ in range(88)),
            )
            write(
                config["sdf"]["max_simulation_log"],
                "MTM control: MAXIMUM\n"
                "No. of Tchecks = 24188 No. of Disabled Tchecks = 24188 "
                "Annotated = 0.00% (0/0)\n"
                "SVSEED set from command line: 11\n"
                "ASIC_MANIFEST_CASE case=9 pass=1 pred=3 expected=3 "
                "samples=1800000 cycles=5401263\n"
                "ASIC_MANIFEST_PASS pass=1 total=1\n"
                "GPDK45_GATE_POWERUP_SUMMARY initialized_instances=6044 "
                "zeros=3000 ones=3044 release_ns=10 release_unknown=0\n"
                "GPDK45_GATE_X_SUMMARY initial_unknown=0 runtime_x_transitions=0\n",
            )

            prefix_manifest = {
                "prefix_samples": 100,
                "clock_hz": 100_000_000,
                "sample_rate_hz": 1_000,
                "cycles_per_sample": 100_000,
                "window_cycles": 10_000_000,
                "window_seconds": 0.1,
                "reaches_60000_sample_snapshot": False,
                "reaches_30_snapshot_decision": False,
                "adc_data_idle_policy": "hold last accepted sample",
                "claim_boundary": "short prefix only",
            }
            write(config["power"]["prefix_manifest"], json.dumps(prefix_manifest) + "\n")
            launch_runs: dict[str, Any] = {}
            launch_paths: set[str] = set()
            for name, run in config["power"]["runs"].items():
                cfg = config["profiles"][run["profile"]]
                root = "" if cfg["root"] == "." else f"{cfg['root']}/"
                tag = run["tag"]
                write(
                    f"{root}reports/activity_power/{tag}/activity_annotation.rpt",
                    "Begin Processing SAIF file\n"
                    "Ended Processing SAIF file: (cpu=0:00:01, real=0:00:01)\n"
                    "'read_activity_file' finished successfully.\n",
                )
                write(
                    f"{root}reports/activity_power/{tag}/activity_power_status.txt",
                    "status=0\nactivity_format=SAIF\nextraction_status=0\n"
                    "activity_delay_model=zero\nunannotated_default_activity=0.0\n"
                    "unannotated_report_status=1\n",
                )
                values = {
                    "accelerated_gap2": (1.5, 0.5, 0.01),
                    "active_wait_idle": (1.0, 0.2, 0.01),
                    "literal_1ksps_prefix": (1.1, 0.25, 0.01),
                }[name]
                write(
                    f"{root}reports/activity_power/{tag}/power_detailed.rpt",
                    synthetic_power_report(*values),
                )
                if name == "accelerated_gap2":
                    stimulus = (
                        "COMMAND=xrun -access +rwc -delay_mode zero\n"
                        "SVSEED set from command line: 11\n"
                        "ASIC_MANIFEST_CASE case=1 pass=1 pred=0 expected=0 "
                        "samples=1800000 cycles=5401263\n"
                        "ASIC_MANIFEST_PASS pass=1 total=1\n"
                    )
                else:
                    mode = 0 if name == "active_wait_idle" else 1
                    accepted = 0 if mode == 0 else 100
                    stimulus = (
                        "COMMAND=xrun -access +rwc -delay_mode zero\n"
                        "SVSEED set from command line: 11\n"
                        f"ASIC_POWER_PREFIX_WINDOW_BEGIN mode={mode} samples=100 "
                        "cycles_per_sample=100000 window_cycles=10000000\n"
                        f"ASIC_POWER_PREFIX_WINDOW_END mode={mode} accepted={accepted} "
                        "window_cycles=10000000\n"
                        f"ASIC_POWER_PREFIX_PASS mode={mode}\n"
                    )
                stimulus += (
                    "GPDK45_GATE_POWERUP_SUMMARY initialized_instances=6045 "
                    "zeros=3000 ones=3045 release_ns=10 release_unknown=0\n"
                    "GPDK45_GATE_X_SUMMARY initial_unknown=0 runtime_x_transitions=0\n"
                    "Simulation complete via $finish(1)\n"
                )
                write(run["stimulus_log"], stimulus)
                launch_paths.add(run["launch_record"])
                launch_runs[tag] = {
                    "command": "xrun -access +rwc -delay_mode zero",
                    "seed": 11,
                    "force_release_ns": 10,
                    "dump_scope": (
                        "tb_snn_ecg_asic_core_manifest.snn_ecg_asic_core_top"
                        if name == "accelerated_gap2"
                        else "tb_snn_ecg_asic_power_prefix.snn_ecg_asic_core_top"
                    ),
                    "top": "snn_ecg_asic_core_top",
                    "stimulus_log": run["stimulus_log"],
                    "stimulus_log_sha256": sha256_file(
                        raw / PurePosixPath(run["stimulus_log"])
                    ),
                    "normalization_full_xz_mode": "preserve",
                }
            assert len(launch_paths) == 1
            write(
                next(iter(launch_paths)),
                json.dumps({"schema_version": 1, "runs": launch_runs}) + "\n",
            )

            manifest = build_summary_atomic(raw, stage, config, override_hash)
            assert manifest["def_parser_crosscheck"]["status"] == "PASS"
            assert manifest["profiles"]["axi"]["routing"]["via_count"] == 2
            assert manifest["profiles"]["axi"]["hold_summary"] == {
                "wns_ns": -0.1,
                "tns_ns": -0.2,
                "violating_paths": 2,
                "all_paths": 10,
                "density_percent": 80.125,
            }
            assert manifest["profiles"]["axi"]["max_transition"] == {
                "violating_nets": 1,
                "violating_terminals": 2,
                "worst_slack_ns": -0.026,
            }
            assert manifest["profiles"]["core"]["ocv"] == KNOWN_OCV_FACTORS
            assert manifest["regression"]["canonical_digital_36"]["status"] == "PASS"
            assert manifest["lec"]["axi"]["status"] == "PASS"
            assert manifest["pg"]["connectivity_violations"] == 171
            assert manifest["pg"]["geometry_violations"] == 715
            assert manifest["gate"]["mapped_sequential_coverage"] == "6045/6045"
            assert manifest["gate"]["mapped_release_unknowns"] == 0
            assert [row["seed"] for row in manifest["gate"]["mapped_seeds"]] == [11, 22, 33]
            assert manifest["sdf"]["max"]["sequential_covered"] == 6044
            assert manifest["sdf"]["max"]["release_unknowns"] == 0
            assert manifest["sdf"]["max"]["timing_checks_disabled"] is True
            assert manifest["sdf"]["max"]["sdfncap_warnings"] == 88
            assert manifest["power"]["literal_minus_active_wait_idle"]["status"] == "DERIVED_MATCHED_WINDOW"
            for relative in (
                "core/results/ppa_summary.csv",
                "axi/results/physical_checks.csv",
                "regression/regression_summary.csv",
                "lec/equivalence_summary.csv",
                "pg/attempt_summary.csv",
                "gate/gate_verification_summary.csv",
                "sdf/sdf_pilot_summary.csv",
                "power/activity_power_summary.csv",
                "run_manifest.json",
            ):
                assert (stage / relative).is_file(), relative
    finally:
        KNOWN_CORE_ITER1_WIRE_UM = old_wire
        KNOWN_CORE_ITER1_VIAS = old_vias

    print("SUMMARIZE_ASIC_GPDK45_RUN2_SELF_TEST_PASS")


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.raw_root is None or args.staging_dir is None:
        raise Run2SummaryError("--raw-root and --staging-dir are required unless --self-test is used")
    config, override_hash = load_config(args.override_json)
    manifest = build_summary_atomic(args.raw_root, args.staging_dir, config, override_hash)
    print(f"RUN2_STAGING={args.staging_dir.resolve()}")
    print(f"RAW_INPUTS={len(manifest['raw_inputs'])}")
    print("RUN2_SUMMARY_PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Run2SummaryError as exc:
        print(f"RUN2_SUMMARY_FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
