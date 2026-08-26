#!/usr/bin/env python3
"""Normalize analog ADC dumps and replay them through core + AXI RTL."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from prepare_virtuoso_adc_dump import DumpError, normalize


REPO = Path(__file__).resolve().parents[2]
RTL_DIR = REPO / "design" / "digital" / "rtl"
FILE_LIST = (
    REPO
    / "design"
    / "digital"
    / "asic"
    / "gpdk45"
    / "axi_profile"
    / "scripts"
    / "xcelium_virtuoso_e2e_rtl.f"
)
DEFAULT_MANIFEST = (
    REPO
    / "design"
    / "digital"
    / "asic"
    / "gpdk45"
    / "axi_profile"
    / "manifests"
    / "representative_xmodel4.csv"
)
CANONICAL_SAMPLES = 1_800_000
PASS_MARKER = "VIRTUOSO_AXI_E2E_PASS"
REQUIRED_FIELDS = (
    "case_id",
    "case_name",
    "expected_class",
    "sample_count",
    "expected_mem_nsr",
    "expected_mem_chf",
    "expected_mem_arr",
    "expected_mem_aff",
    "input_path",
    "input_format",
    "input_encoding",
)


def slash(path: Path) -> str:
    return os.fspath(path.resolve()).replace("\\", "/")


def find_vivado_tool(name: str) -> Path:
    configured = shutil.which(name) or shutil.which(name + ".bat")
    if configured:
        return Path(configured)
    return Path(r"C:\Xilinx\Vivado\2020.2\bin") / f"{name}.bat"


def resolve_input(raw: str, manifest: Path) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path.resolve()
    for candidate in (manifest.parent / path, REPO / path):
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"input_path not found: {raw}")


def parse_manifest(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or ())
        missing = [field for field in REQUIRED_FIELDS if field not in fields]
        if missing:
            raise ValueError(f"manifest fields missing: {', '.join(missing)}")
        raw_rows = list(reader)
    if not raw_rows:
        raise ValueError("manifest contains no cases")

    rows: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    seen_names: set[str] = set()
    for line_number, raw in enumerate(raw_rows, 2):
        try:
            case_id = int(raw["case_id"])
            expected_class = int(raw["expected_class"])
            sample_count = int(raw["sample_count"])
            membranes = {
                key: int(raw[f"expected_mem_{key}"])
                for key in ("nsr", "chf", "arr", "aff")
            }
        except ValueError as exc:
            raise ValueError(f"manifest line {line_number}: invalid integer") from exc
        name = raw["case_name"].strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            raise ValueError(
                f"manifest line {line_number}: case_name must be whitespace-free ASCII"
            )
        if case_id in seen_ids or name in seen_names:
            raise ValueError(f"manifest line {line_number}: duplicate case id or name")
        if expected_class not in range(4):
            raise ValueError(f"manifest line {line_number}: expected_class must be 0..3")
        if sample_count != CANONICAL_SAMPLES:
            raise ValueError(
                f"manifest line {line_number}: AXI top requires {CANONICAL_SAMPLES} samples"
            )
        input_format = raw["input_format"].strip().lower()
        input_encoding = raw["input_encoding"].strip().lower()
        if input_format not in {"csv", "mem", "auto"}:
            raise ValueError(f"manifest line {line_number}: invalid input_format")
        if input_encoding not in {"offset_binary", "twos_complement"}:
            raise ValueError(f"manifest line {line_number}: invalid input_encoding")
        seen_ids.add(case_id)
        seen_names.add(name)
        rows.append(
            {
                "case_id": case_id,
                "case_name": name,
                "expected_class": expected_class,
                "sample_count": sample_count,
                **{f"expected_mem_{key}": value for key, value in membranes.items()},
                "input_path": resolve_input(raw["input_path"].strip(), path),
                "input_format": input_format,
                "input_encoding": input_encoding,
            }
        )
    return rows


def parse_file_list() -> tuple[list[Path], list[Path]]:
    include_dirs: list[Path] = []
    sources: list[Path] = []
    for raw in FILE_LIST.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("+incdir+"):
            include_dirs.append((REPO / line[len("+incdir+") :]).resolve())
        else:
            sources.append((REPO / line).resolve())
    missing = [path for path in include_dirs + sources if not path.exists()]
    if missing:
        raise FileNotFoundError(f"RTL file-list entries missing: {missing}")
    return include_dirs, sources


def sanitize(text: str, work: Path) -> str:
    replacements = (
        (str(work.resolve()), "<SIM_WORK>"),
        (slash(work), "<SIM_WORK>"),
        (str(REPO.resolve()), "<REPOSITORY_ROOT>"),
        (slash(REPO), "<REPOSITORY_ROOT>"),
        (str(Path.home()), "<USER_HOME>"),
        (slash(Path.home()), "<USER_HOME>"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    # Tool banners occasionally leave a space before a newline.  Normalize
    # those so persisted evidence remains git-diff clean and portable.
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines) + ("\n" if text.endswith(("\n", "\r")) else "")


def run_command(command: list[str], work: Path, label: str) -> str:
    proc = subprocess.run(
        command,
        cwd=work,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    )
    output = proc.stdout
    (work / f"{label}.log").write_text(output, encoding="utf-8")
    if proc.returncode != 0:
        tail = "\n".join(output.splitlines()[-30:])
        raise RuntimeError(f"{label} failed ({proc.returncode})\n{tail}")
    return output


def stage_inputs(rows: list[dict[str, Any]], work: Path) -> list[dict[str, Any]]:
    input_dir = work / "inputs"
    input_dir.mkdir()
    staged_rows: list[dict[str, Any]] = []
    for row in rows:
        staged_mem = input_dir / f"case_{row['case_id']:03d}.mem"
        staged_metadata = input_dir / f"case_{row['case_id']:03d}.json"
        args = argparse.Namespace(
            input=row["input_path"],
            output=staged_mem,
            metadata=staged_metadata,
            format=row["input_format"],
            encoding=row["input_encoding"],
            sample_rate_hz=1000,
            cadence_tolerance_sec="0.000000001",
            expected_samples=row["sample_count"],
            # CSV is the signed-off analog handoff because it proves the 1 kSPS
            # cadence.  MEM remains supported for established digital fixtures.
            require_cadence=(
                row["input_format"] == "csv"
                or (
                    row["input_format"] == "auto"
                    and row["input_path"].suffix.lower() == ".csv"
                )
            ),
        )
        try:
            metadata = normalize(args)
        except DumpError as exc:
            raise ValueError(f"{row['case_name']}: {exc}") from exc
        staged_rows.append(
            {
                **row,
                "staged_mem": staged_mem,
                "metadata": metadata,
            }
        )
    return staged_rows


def write_sim_manifest(rows: list[dict[str, Any]], work: Path) -> Path:
    path = work / "sim_manifest.txt"
    lines = []
    for row in rows:
        lines.append(
            " ".join(
                str(value)
                for value in (
                    row["case_id"],
                    row["expected_class"],
                    row["sample_count"],
                    row["expected_mem_nsr"],
                    row["expected_mem_chf"],
                    row["expected_mem_arr"],
                    row["expected_mem_aff"],
                    row["case_name"],
                    row["staged_mem"].relative_to(work).as_posix(),
                )
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
    return path


def write_wrapper(work: Path) -> Path:
    path = work / "tb_virtuoso_adc_e2e_runner.v"
    path.write_text(
        """`timescale 1ns/1ps
module tb_virtuoso_adc_e2e_runner;
  tb_snn_ecg_axi_virtuoso_e2e #(
    .MANIFEST_FILE("sim_manifest.txt"),
    .RESULT_CSV("raw_results.csv"),
    .SAMPLE_GAP_CYCLES(2)
  ) tb();
endmodule
""",
        encoding="ascii",
        newline="\n",
    )
    return path


def run_xsim(work: Path, include_dirs: list[Path], sources: list[Path], wrapper: Path) -> dict[str, str]:
    tools = {name: find_vivado_tool(name) for name in ("xvlog", "xelab", "xsim")}
    missing = [str(path) for path in tools.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Vivado simulator tools not found: {missing}")
    project = work / "sources.prj"
    project.write_text(
        "".join(f'verilog work "{slash(path)}"\n' for path in sources + [wrapper]),
        encoding="utf-8",
        newline="\n",
    )
    xvlog_command = [str(tools["xvlog"]), "--nolog"]
    for directory in include_dirs:
        xvlog_command += ["-i", slash(directory)]
    xvlog_command += ["-prj", slash(project)]
    compile_log = run_command(xvlog_command, work, "compile")
    elaborate_log = run_command(
        [
            str(tools["xelab"]),
            "--nolog",
            "-debug",
            "typical",
            "tb_virtuoso_adc_e2e_runner",
            "-s",
            "tb_virtuoso_adc_e2e_runner",
        ],
        work,
        "elaborate",
    )
    (work / "run.tcl").write_text("run all\nquit\n", encoding="ascii")
    simulation_log = run_command(
        [
            str(tools["xsim"]),
            "tb_virtuoso_adc_e2e_runner",
            "--nolog",
            "-tclbatch",
            "run.tcl",
        ],
        work,
        "simulation",
    )
    return {
        "compile": compile_log,
        "elaborate": elaborate_log,
        "simulation": simulation_log,
    }


def run_xrun(
    executable: Path, work: Path, include_dirs: list[Path], sources: list[Path], wrapper: Path
) -> dict[str, str]:
    if not executable.is_file():
        raise FileNotFoundError(executable)
    file_list = work / "xrun_sources.f"
    file_list.write_text(
        "".join(f'+incdir+"{slash(path)}"\n' for path in include_dirs)
        + "".join(f'"{slash(path)}"\n' for path in sources + [wrapper]),
        encoding="utf-8",
        newline="\n",
    )
    simulation_log = run_command(
        [
            str(executable),
            "-64bit",
            "-f",
            slash(file_list),
            "-top",
            "tb_virtuoso_adc_e2e_runner",
            "-R",
        ],
        work,
        "simulation",
    )
    return {"simulation": simulation_log}


def read_results(path: Path, expected_cases: int) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError("simulator did not create raw_results.csv")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != expected_cases:
        raise RuntimeError(f"result case count mismatch: expected {expected_cases}, got {len(rows)}")
    if any(row.get("case_pass") != "1" for row in rows):
        failed = [row.get("case_name", "?") for row in rows if row.get("case_pass") != "1"]
        raise RuntimeError(f"RTL harness reported failed cases: {failed}")
    return rows


def write_evidence(
    result_dir: Path,
    manifest: Path,
    simulator: str,
    rows: list[dict[str, Any]],
    results: list[dict[str, str]],
    logs: dict[str, str],
    work: Path,
) -> None:
    result_dir.mkdir(parents=True, exist_ok=True)
    with (result_dir / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)

    provenance_fields = (
        "case_id",
        "case_name",
        "source_name",
        "source_sha256",
        "input_format",
        "input_encoding",
        "output_encoding",
        "output_sha256",
        "sample_rate_hz",
        "sample_count",
        "signed_min",
        "signed_max",
        "cadence_checked",
        "worst_period_error_sec",
    )
    provenance: list[dict[str, Any]] = []
    for row in rows:
        metadata = row["metadata"]
        provenance.append(
            {
                "case_id": row["case_id"],
                "case_name": row["case_name"],
                **{field: metadata.get(field, "") for field in provenance_fields[2:]},
            }
        )
    with (result_dir / "input_provenance.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=provenance_fields)
        writer.writeheader()
        writer.writerows(provenance)

    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit = "UNKNOWN"
    summary = {
        "schema_version": 1,
        "status": "PASS",
        "simulator": simulator,
        "manifest_name": manifest.name,
        "git_commit_before_harness_changes": commit,
        "case_count": len(results),
        "passed_case_count": len(results),
        "samples_per_case": CANONICAL_SAMPLES,
        "sample_gap_cycles": 2,
        "checks": [
            "input normalization and exact sample count",
            "CSV 1 kSPS cadence when CSV is supplied",
            "AXI accepted and consumed sample counts",
            "AXI versus direct-core final class",
            "AXI versus direct-core four final membranes",
            "both paths versus manifest expected outputs",
        ],
    }
    (result_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (result_dir / "SUMMARY_KR.md").write_text(
        "# ADC-디지털 E2E 하네스 실행 결과\n\n"
        f"- 상태: **PASS**\n"
        f"- 시뮬레이터: `{simulator}`\n"
        f"- 입력 manifest: `{manifest.name}`\n"
        f"- 검증 case: {len(results)}/{len(results)} PASS\n"
        f"- case당 입력: {CANONICAL_SAMPLES:,} samples\n"
        "- 검사 경로: 같은 ADC code를 direct core와 AXI4-Stream wrapper에 동시 입력\n"
        "- 판정: 두 경로의 class, 4개 membrane, AXI accepted/consumed가 모두 일치\n\n"
        "이 결과는 입력 파일에 기록된 ADC code부터 디지털 RTL 출력까지의 검증이다. "
        "Virtuoso 회로가 실제로 생성한 CSV를 사용한 경우에만 아날로그 회로까지 포함한 ETE 증거가 된다.\n",
        encoding="utf-8",
    )
    for label, text in logs.items():
        (result_dir / f"{label}.log").write_text(sanitize(text, work), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--simulator", choices=("xsim", "xrun"), default="xsim")
    parser.add_argument("--xrun", type=Path, default=Path("xrun"))
    parser.add_argument("--result-dir", type=Path)
    parser.add_argument("--keep-work", type=Path)
    parser.add_argument(
        "--case-id",
        type=int,
        action="append",
        help="run only this manifest case id; repeat to select multiple cases",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = args.manifest.resolve()
    result_dir = (
        args.result_dir.resolve()
        if args.result_dir
        else REPO / "verification" / "virtuoso_adc_e2e" / "results" / manifest.stem
    )
    rows = parse_manifest(manifest)
    if args.case_id:
        selected = set(args.case_id)
        rows = [row for row in rows if row["case_id"] in selected]
        found = {row["case_id"] for row in rows}
        missing = sorted(selected - found)
        if missing:
            raise ValueError(f"requested case ids not in manifest: {missing}")
    include_dirs, sources = parse_file_list()

    if args.keep_work:
        work = args.keep_work.resolve()
        if work.exists() and any(work.iterdir()):
            raise RuntimeError(f"--keep-work directory must be empty: {work}")
        work.mkdir(parents=True, exist_ok=True)
        temporary = None
    else:
        temporary = tempfile.TemporaryDirectory(prefix="snn_virtuoso_e2e_")
        work = Path(temporary.name).resolve()

    try:
        staged = stage_inputs(rows, work)
        write_sim_manifest(staged, work)
        wrapper = write_wrapper(work)
        if args.simulator == "xsim":
            logs = run_xsim(work, include_dirs, sources, wrapper)
        else:
            executable = args.xrun
            if not executable.is_absolute():
                found = shutil.which(os.fspath(executable))
                if not found:
                    raise FileNotFoundError(executable)
                executable = Path(found)
            logs = run_xrun(executable, work, include_dirs, sources, wrapper)
        if PASS_MARKER not in logs["simulation"]:
            raise RuntimeError(f"simulator log does not contain {PASS_MARKER}")
        results = read_results(work / "raw_results.csv", len(rows))
        write_evidence(result_dir, manifest, args.simulator, staged, results, logs, work)
    finally:
        if temporary is not None:
            temporary.cleanup()

    print(
        f"VIRTUOSO_ADC_E2E_RUN_PASS simulator={args.simulator} "
        f"cases={len(rows)} result_dir={result_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
