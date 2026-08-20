#!/usr/bin/env python3
"""Validate canonical files, metrics, figures, and claim boundaries."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

REQUIRED = [
    "README.md", "START_HERE_KR.md", "REPRODUCIBILITY_KR.md", "WORKSPACE_INVENTORY_KR.md",
    "docs/SYSTEM_OVERVIEW_KR.md", "docs/DATASET_AND_EVALUATION_KR.md",
    "docs/FEATURE_SELECTION_AND_ANNOTATION_KR.md", "docs/DIGITAL_ARCHITECTURE_KR.md",
    "docs/HARDWARE_IMPLEMENTATION_KR.md", "docs/INTEGRATION_VERIFICATION_KR.md",
    "docs/LIMITATIONS_AND_CLAIM_BOUNDARY_KR.md", "docs/RELATED_WORK_HOLTER_ECG_KR.md",
    "reports/INTEGRATED_TECHNICAL_REPORT_KR.md",
    "reports/INTEGRATED_TECHNICAL_REPORT_EVIDENCE_MAP.csv",
    "INTEGRATION_AUDIT.md", "LICENSE_OR_PROVENANCE.md",
    "project_registry/claim_registry.csv", "project_registry/global_metrics.yaml",
    "project_registry/upstream_commits.yaml",
    "project_registry/artifact_manifest.csv",
    "project_registry/external_reference_registry.csv", "project_registry/unresolved_artifacts.csv",
    "verification/timing_optimization/RTL_TIMING_OPTIMIZATION_HISTORY_KR.md",
    "verification/xmodel_rtl_acceptance_36case/output_equivalence_36case.csv",
    "verification/xmodel_rtl_e2e/overall_summary.csv",
    "design/digital/rtl/snn_ecg_30min_final_top.v",
    "design/digital/reports/final/final_metrics.json",
    "design/digital/reports/final/board_replay_36_batch_summary.json",
    "models/digital_equivalence/results/accelerator_benefit_summary.csv",
    "models/digital_equivalence/results/power_energy_summary.csv",
    "tables/asic_gpdk45_run2_ppa.csv",
    "tables/asic_gpdk45_run2_verification.csv",
    "verification/asic_gpdk45_run2/README_KR.md",
    "verification/asic_gpdk45_run2/run_manifest.json",
    "verification/asic_gpdk45_run2/SELECTION_MANIFEST.csv",
    "verification/asic_gpdk45_run2/CHECKSUMS.txt",
    "verification/asic_gpdk45_run2/core/results/ppa_summary.csv",
    "verification/asic_gpdk45_run2/core/results/physical_checks.csv",
    "verification/asic_gpdk45_run2/axi/results/ppa_summary.csv",
    "verification/asic_gpdk45_run2/axi/results/physical_checks.csv",
    "verification/asic_gpdk45_run2/regression/regression_summary.csv",
    "verification/asic_gpdk45_run2/lec/equivalence_summary.csv",
    "verification/asic_gpdk45_run2/pg/attempt_summary.csv",
    "verification/asic_gpdk45_run2/gate/gate_verification_summary.csv",
    "verification/asic_gpdk45_run2/gate/x_pessimism_boundary.txt",
    "verification/asic_gpdk45_run2/sdf/sdf_pilot_summary.csv",
    "verification/asic_gpdk45_run2/power/activity_power_summary.csv",
    "verification/asic_gpdk45_run2/power/activity_annotation_summary.txt",
    "figures/FIGURE_INDEX.md",
    "vivado/microblaze/SNN_ECG_MB_FULL_REPLAY.xpr",
    "vivado/pure_rtl/project/SNN_ECG_PURE_RTL_VISUALIZATION.xpr",
]
PUBLIC_TEXT = [
    "README.md", "START_HERE_KR.md", "REPRODUCIBILITY_KR.md",
    "reports/INTEGRATED_TECHNICAL_REPORT_KR.md",
]


def load_json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def run_checker(path: str) -> tuple[bool, str]:
    result = subprocess.run([PYTHON, str(ROOT / path)], cwd=ROOT, text=True, capture_output=True)
    return result.returncode == 0, result.stdout + result.stderr


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_csv_rows(path: str) -> list[dict[str, str]]:
    with (ROOT / path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    errors: list[str] = []
    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            errors.append(f"missing required artifact: {rel}")

    manifest_path = ROOT / "project_registry/artifact_manifest.csv"
    if manifest_path.exists():
        with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
            manifest_rows = list(csv.DictReader(handle))
        manifest_by_path = {row.get("path", ""): row for row in manifest_rows}
        current_files: list[str] = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or path == manifest_path:
                continue
            rel = path.relative_to(ROOT)
            if any(part in {".git", "tmp", "__pycache__", ".pytest_cache", ".mypy_cache"} for part in rel.parts):
                continue
            current_files.append(rel.as_posix())
        if set(manifest_by_path) != set(current_files):
            missing = sorted(set(current_files) - set(manifest_by_path))
            stale = sorted(set(manifest_by_path) - set(current_files))
            errors.append(f"artifact manifest path mismatch: missing={missing[:5]}, stale={stale[:5]}")
        else:
            for rel in current_files:
                row = manifest_by_path[rel]
                path = ROOT / rel
                if row.get("sha256") != file_sha256(path) or row.get("size_bytes") != str(path.stat().st_size):
                    errors.append(f"artifact manifest hash/size mismatch: {rel}")
                    break

    metrics_path = ROOT / "design/digital/reports/final/final_metrics.json"
    if metrics_path.exists():
        raw = metrics_path.read_text(encoding="utf-8")
        for token in ["80.56", "80.44", "9719", "5038", "8.184", "12494", "8494", "0.097"]:
            if token not in raw:
                errors.append(f"final_metrics.json lacks expected token: {token}")

    compact = ROOT / "verification/xmodel_rtl_acceptance_36case/output_equivalence_36case.csv"
    if compact.exists():
        with compact.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if len(rows) != 36 or not all(row.get("pred_match", "").lower() == "true" and row.get("mem_match", "").lower() == "true" for row in rows):
            errors.append("compact XMODEL/RTL acceptance is not 36/36")

    raw_audit = ROOT / "verification/xmodel_rtl_e2e/overall_summary.csv"
    if raw_audit.exists():
        with raw_audit.open(encoding="utf-8-sig", newline="") as handle:
            audit = {row["metric"]: row for row in csv.DictReader(handle)}
        present = audit.get("actual_xmodel_adc_files_present_valid", {})
        if present.get("pass_count") != "4" or present.get("required_count") != "36":
            errors.append("raw-dump audit scope must remain explicitly 4/36")

    run2_ppa_path = ROOT / "tables/asic_gpdk45_run2_ppa.csv"
    if run2_ppa_path.exists():
        rows = load_csv_rows("tables/asic_gpdk45_run2_ppa.csv")
        by_metric = {(row["scope"], row["stage"], row["metric"]): row for row in rows}
        expected = {
            ("gpdk045_run2_core", "mapping", "scan_free_mapped_cells"): ("36565", "OBSERVED"),
            ("gpdk045_run2_core", "mapping", "mapped_cell_area"): ("94421.754", "OBSERVED"),
            ("gpdk045_run2_core", "mapping", "sequential_cells"): ("6045", "OBSERVED"),
            ("gpdk045_run2_core", "mapping", "setup_slack"): ("3.3509", "PASS"),
            ("gpdk045_run2_core", "postroute", "instances"): ("42958", "OBSERVED"),
            ("gpdk045_run2_core", "postroute", "cell_area"): ("120287.898", "OBSERVED"),
            ("gpdk045_run2_core", "postroute", "die_width"): ("422.800", "OBSERVED"),
            ("gpdk045_run2_core", "postroute", "die_height"): ("419.900", "OBSERVED"),
            ("gpdk045_run2_core", "postroute", "die_area"): ("177533.720", "OBSERVED"),
            ("gpdk045_run2_core", "postroute", "placement_density"): ("82.775", "OBSERVED"),
            ("gpdk045_run2_core", "timing", "setup_WNS"): ("2.469", "PASS"),
            ("gpdk045_run2_core", "timing", "hold_WNS"): ("-0.008", "FAIL"),
            ("gpdk045_run2_core", "timing", "hold_TNS"): ("-0.094", "FAIL"),
            ("gpdk045_run2_core", "timing", "hold_violating_paths"): ("37", "FAIL"),
            ("gpdk045_run2_core", "timing", "max_transition_violating_nets"): ("3", "FAIL"),
            ("gpdk045_run2_core", "timing", "clock_slew_violations_at_60ps"): ("0", "PASS"),
            ("gpdk045_run2_core", "route", "internal_DRC_violations"): ("0", "PASS"),
            ("gpdk045_run2_core", "power", "vectorless_total_power"): ("3.71626492", "ESTIMATE"),
            ("gpdk045_run2_axi", "mapping", "scan_free_mapped_cells"): ("37293", "OBSERVED"),
            ("gpdk045_run2_axi", "mapping", "mapped_cell_area"): ("96548.994", "OBSERVED"),
            ("gpdk045_run2_axi", "mapping", "sequential_cells"): ("6244", "OBSERVED"),
            ("gpdk045_run2_axi", "mapping", "setup_slack"): ("3.3498", "PASS"),
            ("gpdk045_run2_axi", "postroute", "instances"): ("43901", "OBSERVED"),
            ("gpdk045_run2_axi", "postroute", "cell_area"): ("123650.100", "OBSERVED"),
            ("gpdk045_run2_axi", "postroute", "die_width"): ("426.200", "OBSERVED"),
            ("gpdk045_run2_axi", "postroute", "die_height"): ("425.030", "OBSERVED"),
            ("gpdk045_run2_axi", "postroute", "die_area"): ("181147.786", "OBSERVED"),
            ("gpdk045_run2_axi", "postroute", "placement_density"): ("83.215", "OBSERVED"),
            ("gpdk045_run2_axi", "timing", "setup_WNS"): ("2.781", "PASS"),
            ("gpdk045_run2_axi", "timing", "hold_WNS"): ("-0.016", "FAIL"),
            ("gpdk045_run2_axi", "timing", "hold_TNS"): ("-0.518", "FAIL"),
            ("gpdk045_run2_axi", "timing", "hold_violating_paths"): ("107", "FAIL"),
            ("gpdk045_run2_axi", "timing", "max_transition_violating_nets"): ("73", "FAIL"),
            ("gpdk045_run2_axi", "timing", "clock_slew_violations_at_60ps"): ("0", "PASS"),
            ("gpdk045_run2_axi", "route", "internal_DRC_violations"): ("0", "PASS"),
            ("gpdk045_run2_axi", "power", "vectorless_total_power"): ("3.69335598", "ESTIMATE"),
            ("gpdk045_run2_common", "timing", "OCV_derate_assumption"): ("5", "ASSUMED"),
            ("gpdk045_run2_core_activity", "accelerated_gap2", "internal_power"): ("1.52085678", "ESTIMATE"),
            ("gpdk045_run2_core_activity", "accelerated_gap2", "switching_power"): ("0.50045621", "ESTIMATE"),
            ("gpdk045_run2_core_activity", "accelerated_gap2", "leakage_power"): ("0.00404773", "ESTIMATE"),
            ("gpdk045_run2_core_activity", "accelerated_gap2", "total_power"): ("2.02536072", "ESTIMATE"),
            ("gpdk045_run2_core_activity", "active_wait_idle", "internal_power"): ("1.48928157", "ESTIMATE"),
            ("gpdk045_run2_core_activity", "active_wait_idle", "switching_power"): ("0.41750333", "ESTIMATE"),
            ("gpdk045_run2_core_activity", "active_wait_idle", "leakage_power"): ("0.00405502", "ESTIMATE"),
            ("gpdk045_run2_core_activity", "active_wait_idle", "total_power"): ("1.91083992", "ESTIMATE"),
            ("gpdk045_run2_core_activity", "literal_1ksps_prefix", "internal_power"): ("1.48928212", "ESTIMATE"),
            ("gpdk045_run2_core_activity", "literal_1ksps_prefix", "switching_power"): ("0.41750554", "ESTIMATE"),
            ("gpdk045_run2_core_activity", "literal_1ksps_prefix", "leakage_power"): ("0.00405312", "ESTIMATE"),
            ("gpdk045_run2_core_activity", "literal_1ksps_prefix", "total_power"): ("1.91084079", "ESTIMATE"),
            ("gpdk045_run2_core_activity", "literal_minus_active_wait_idle", "matched_total_delta"): ("0.00000087", "DERIVED"),
        }
        for key, value_status in expected.items():
            row = by_metric.get(key)
            if row is None or (row.get("value"), row.get("status")) != value_status:
                errors.append(f"run-2 PPA table mismatch for {key}: {row}")
        boundary_expectations = {
            ("gpdk045_run2_core", "timing", "max_transition_violating_nets"): "6 violating terminals worst slack -0.026 ns",
            ("gpdk045_run2_axi", "timing", "max_transition_violating_nets"): "469 violating terminals worst slack -0.476 ns",
            ("gpdk045_run2_common", "timing", "OCV_derate_assumption"): "not foundry-characterized AOCV or POCV",
            ("gpdk045_run2_core_activity", "accelerated_gap2", "total_power"): "not wall-time 1 kSPS decision energy or silicon power",
            ("gpdk045_run2_core_activity", "literal_1ksps_prefix", "total_power"): "no Snapshot or decision and not silicon power",
            ("gpdk045_run2_core_activity", "literal_minus_active_wait_idle", "matched_total_delta"): "not numeric annotation coverage pure clock power snapshot decision or energy per decision",
        }
        for key, token in boundary_expectations.items():
            row = by_metric.get(key)
            if row is None or token not in row.get("claim_boundary", ""):
                errors.append(f"run-2 PPA claim boundary mismatch for {key}: {row}")

    activity_path = ROOT / "verification/asic_gpdk45_run2/power/activity_power_summary.csv"
    if activity_path.exists():
        rows = load_csv_rows("verification/asic_gpdk45_run2/power/activity_power_summary.csv")
        required_fields = {
            "profile", "tag", "mode", "status", "internal_mw", "switching_mw",
            "leakage_mw", "total_mw", "sample_count", "window_cycles", "window_seconds",
            "stimulus_seed", "mapped_sequential_coverage", "release_unknowns",
            "initial_unknowns", "runtime_x_transitions", "xcelium_access", "delay_mode",
            "normalization_full_xz_mode", "activity_annotation_status",
            "unannotated_report_status", "claim_boundary",
        }
        actual_fields = set(rows[0]) if rows else set()
        if not required_fields.issubset(actual_fields):
            errors.append(f"run-2 activity summary schema missing: {sorted(required_fields - actual_fields)}")
        if len(rows) != 4 or len({row.get("mode") for row in rows}) != 4:
            errors.append(f"run-2 activity summary must contain four unique modes; found {len(rows)} rows")
        by_mode = {row.get("mode", ""): row for row in rows}
        expected_modes = {
            "accelerated_gap2": {
                "tag": "raw_aff_accelerated_access_seed11", "status": "PASS",
                "internal_mw": "1.52085678", "switching_mw": "0.50045621",
                "leakage_mw": "0.00404773", "total_mw": "2.02536072",
                "sample_count": "1800000", "window_cycles": "5401263", "window_seconds": "",
                "activity_annotation_status": "PASS",
            },
            "active_wait_idle": {
                "tag": "prefix100_idle_access_seed11", "status": "PASS",
                "internal_mw": "1.48928157", "switching_mw": "0.41750333",
                "leakage_mw": "0.00405502", "total_mw": "1.91083992",
                "sample_count": "0", "window_cycles": "10000000", "window_seconds": "0.1",
                "activity_annotation_status": "PASS",
            },
            "literal_1ksps_prefix": {
                "tag": "prefix100_literal1ksps_access_seed11", "status": "PASS",
                "internal_mw": "1.48928212", "switching_mw": "0.41750554",
                "leakage_mw": "0.00405312", "total_mw": "1.91084079",
                "sample_count": "100", "window_cycles": "10000000", "window_seconds": "0.1",
                "activity_annotation_status": "PASS",
            },
        }
        common = {
            "profile": "core", "stimulus_seed": "11",
            "mapped_sequential_coverage": "6045/6045", "release_unknowns": "0",
            "initial_unknowns": "0", "runtime_x_transitions": "0",
            "xcelium_access": "+rwc", "delay_mode": "zero",
            "normalization_full_xz_mode": "preserve",
        }
        for mode, expected_values in expected_modes.items():
            row = by_mode.get(mode)
            if row is None:
                errors.append(f"run-2 activity mode missing: {mode}")
                continue
            for field, expected_value in {**common, **expected_values}.items():
                if row.get(field) != expected_value:
                    errors.append(
                        f"run-2 activity mismatch {mode}.{field}: "
                        f"expected {expected_value!r}, found {row.get(field)!r}"
                    )
        delta = by_mode.get("literal_minus_active_wait_idle")
        if delta is None:
            errors.append("run-2 matched-window activity delta missing")
        else:
            for field, expected_value in {
                **common,
                "tag": "prefix100_literal1ksps_access_seed11_minus_prefix100_idle_access_seed11",
                "status": "DERIVED_MATCHED_WINDOW", "sample_count": "100",
                "window_cycles": "10000000", "window_seconds": "0.1",
                "activity_annotation_status": "PASS_BOTH",
            }.items():
                if delta.get(field) != expected_value:
                    errors.append(
                        f"run-2 activity mismatch literal_minus_active_wait_idle.{field}: "
                        f"expected {expected_value!r}, found {delta.get(field)!r}"
                    )
            try:
                delta_total = Decimal(delta.get("total_mw", ""))
            except InvalidOperation:
                errors.append(f"run-2 matched-window delta is not numeric: {delta.get('total_mw')!r}")
            else:
                if abs(delta_total - Decimal("0.00000087")) > Decimal("1e-15"):
                    errors.append(f"run-2 matched-window total delta mismatch: {delta_total}")
        if any(row.get("profile") != "core" for row in rows):
            errors.append("run-2 activity summary must remain core-only; AXI activity row found")

    activity_boundary = ROOT / "verification/asic_gpdk45_run2/power/activity_annotation_summary.txt"
    if activity_boundary.exists():
        text = activity_boundary.read_text(encoding="utf-8")
        for token in [
            "direct Xcelium mapped-gate -access +rwc, normalized SAIF, Innovus zero-delay",
            "seed 11 initialization with 6045/6045 coverage and release X 0",
            "preserved fully-X/Z entries; unannotated default is 0.0",
            "is not an annotation-coverage PASS",
            "not full-decision energy",
        ]:
            if token not in text:
                errors.append(f"run-2 activity boundary missing: {token}")

    run2_verification_path = ROOT / "tables/asic_gpdk45_run2_verification.csv"
    if run2_verification_path.exists():
        rows = load_csv_rows("tables/asic_gpdk45_run2_verification.csv")
        by_check = {(row["profile"], row["check"]): row for row in rows}
        expected = {
            ("run2_core", "scan_free_mapping"): ("scan_capable_cells_0", "PASS"),
            ("run2_core", "wrapper_RTL_canonical_digital"): ("36/36", "PASS"),
            ("run2_core", "wrapper_RTL_actual_raw_XMODEL"): ("4/4", "PASS"),
            ("run2_core", "mapped_to_postroute_LEC"): ("6178_points_diff0_abort0_unknown0", "PASS"),
            ("run2_axi", "mapped_to_postroute_LEC"): ("6287_points_diff0_abort0_unknown0", "PASS"),
            ("run2_pg", "exploratory_power_grid"): ("171_connectivity_715_geometry", "FAIL"),
            ("run2_gate", "unmodified_four_state_full_raw_case0"): ("output_X", "FAIL"),
            ("run2_gate", "XPR_mode"): ("license_unavailable", "NOT_RUN"),
            ("run2_gate", "forced_two_state_release10ns_mapped"): ("seeds_11_22_33_exact_PASS", "CONDITIONAL_PASS"),
            ("run2_gate", "forced_two_state_sequential_coverage"): ("6045/6045_releaseX0", "CONDITIONAL_PASS"),
            ("run2_sdf", "MAX_SDF_postroute_seed11"): ("6044/6044_exact_PASS", "CONDITIONAL_PASS"),
            ("run2_sdf", "SDF_annotation_port_alias"): ("88_SDFNCAP_warnings", "PARTIAL"),
        }
        for key, result_status in expected.items():
            row = by_check.get(key)
            if row is None or (row.get("result"), row.get("status")) != result_status:
                errors.append(f"run-2 verification table mismatch for {key}: {row}")
        sdf_row = by_check.get(("run2_sdf", "MAX_SDF_postroute_seed11"))
        if sdf_row is None or "timing checks disabled" not in sdf_row.get("claim_boundary", ""):
            errors.append(f"run-2 SDF timing-check boundary missing: {sdf_row}")

    claim_registry = ROOT / "project_registry/claim_registry.csv"
    if claim_registry.exists():
        claim_ids = {row["claim_id"] for row in load_csv_rows("project_registry/claim_registry.csv")}
        required_run2_claims = {f"CLM-{number:03d}" for number in range(29, 39)}
        if not required_run2_claims.issubset(claim_ids):
            errors.append(f"run-2 claim registry entries missing: {sorted(required_run2_claims - claim_ids)}")

    figures_index = (ROOT / "figures/FIGURE_INDEX.md").read_text(encoding="utf-8") if (ROOT / "figures/FIGURE_INDEX.md").exists() else ""
    figure_files = list((ROOT / "figures/final_submission").rglob("*.svg"))
    if len(figure_files) < 10:
        errors.append(f"too few final SVG figures: {len(figure_files)}")
    for p in figure_files:
        if p.name not in figures_index and p.stem not in figures_index:
            errors.append(f"final figure absent from index: {p.relative_to(ROOT)}")

    for rel in PUBLIC_TEXT:
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if "SNN-inspired" in text:
            errors.append(f"legacy SNN-inspired wording in public text: {rel}")
        for forbidden in [
            "actual raw XMODEL 36/36",
            "unmodified four-state gate PASS",
            "GPDK045 run-2 실측 전력",
            "exploratory PG 완료",
        ]:
            if forbidden in text:
                errors.append(f"forbidden run-2 wording in public text {rel}: {forbidden}")

    ok, output = run_checker("tools/check_clean_workspace.py")
    if not ok:
        errors.append("clean workspace checker failed:\n" + output.strip())
    ok, output = run_checker("tools/check_integrated_technical_report.py")
    if not ok:
        errors.append("technical report checker failed:\n" + output.strip())

    if errors:
        print("INTEGRATED_REPOSITORY: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("INTEGRATED_REPOSITORY: PASS")
    print(f"- {len(REQUIRED)} canonical artifacts present")
    print(f"- {len(figure_files)} indexed final SVG figures")
    print("- fixed metrics and evidence-scope boundaries verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
