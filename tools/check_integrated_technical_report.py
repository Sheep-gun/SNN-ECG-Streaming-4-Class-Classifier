#!/usr/bin/env python3
"""Fail-closed checks for the public integrated technical report."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/INTEGRATED_TECHNICAL_REPORT_KR.md"
EVIDENCE = ROOT / "reports/INTEGRATED_TECHNICAL_REPORT_EVIDENCE_MAP.csv"
CLAIMS = ROOT / "project_registry/claim_registry.csv"

REQUIRED_HEADINGS = [
    "# I. 설계작품 요약서",
    "# II. 설계결과물 설명서",
    "## 1. 설계 개요",
    "## 2. 설계기술 설명서",
    "### 2.1 설계 목표",
    "### 2.2 알고리즘 구성 및 결과(예상)",
    "### 2.3 설계회로 구성",
    "### 2.4 설계회로 검증",
    "### 2.5 설계회로 구현 결과",
    "#### RTL timing 병목 분석과 파이프라인 최적화",
    "### 2.6 목표 대비 결과 비교",
    "# III. 제품 및 기술요약",
    "# 참고문헌",
]
REQUIRED_TEXT = [
    "80.56%", "80.44%", "9,719", "5,038", "8.184 ns",
    "12,494", "8,494", "0.097 ns", "36.0129 ms", "49.36",
    "142.0 mW", "2.991 µW", "database–class confounding", "30분", "24시간",
    "35,188", "93,585.906 µm²", "35,663", "95,321.556 µm²",
    "421.000 × 418.190 µm", "+2.980 ns", "−0.050 ns", "3.35554239 mW",
    "default PI/sequential activity 0.10", "VDD/VSS unrouted", "internal route DRC 1",
    "clock slew 위반 86개", "`SDFFQX1` 995개", "undefined scan 10.70% flops",
    "antenna data incomplete",
    "36,565", "94,421.754 µm²", "42,958", "120,287.898 µm²",
    "422.8 × 419.9 µm", "+2.469 ns", "−0.008 ns", "−0.094 ns", "37 paths",
    "37,293", "96,548.994 µm²", "43,901", "123,650.100 µm²",
    "426.2 × 425.03 µm", "+2.781 ns", "−0.016 ns", "−0.518 ns", "107 paths",
    "slow early 0.95", "fast late 1.05", "3.71626492 mW", "3.69335598 mW",
    "1.52085678", "0.50045621", "0.00404773", "2.02536072 mW",
    "1.48928157", "0.41750333", "0.00405502", "1.91083992 mW",
    "1.48928212", "0.41750554", "0.00405312", "1.91084079 mW",
    "0.00000087 mW", "`-access +rwc`", "zero delay", "normalized SAIF parse PASS",
    "fully-X/Z preserved", "unannotated default 0", "numeric annotation coverage PASS",
    "Snapshot/decision", "energy/decision", "AXI activity 없음",
    "canonical 36/36", "actual raw XMODEL 4/4", "core LEC 6,178", "AXI LEC 6,287",
    "AXI 36-case replay를 뜻하지 않는다",
    "unmodified four-state output X", "6,045/6,045", "6,044/6,044",
    "SDF timing checks disabled", "`SDFNCAP` 88 warnings",
    "171 connectivity", "715 geometry violations",
    "43,016", "120,532.428 µm²", "setup +2.470 ns", "hold 0.000 ns",
    "data max-transition 0", "3.72167787 mW",
    "44,062", "124,717.482 µm²", "setup +2.435 ns",
    "264 nets/1,387 terminals", "clock slew 263 pins", "3.79286409 mW",
    "43,956", "123,906.258 µm²", "setup +2.661 ns",
    "141 nets/1,149 terminals", "clock slew 0", "3.71285384 mW",
    "953,367.865 µm", "346,666",
    "42,881", "126,069.441 µm²", "481.2 × 478.04 µm", "65.274%",
    "setup +2.703 ns", "data max-transition 0", "3.58433691 mW",
    "812,624.320 µm", "313,004", "230,032.848 µm²",
    "실제 full-30분 raw XMODEL accepted dump는 4/36개",
    "c6b80de19cdcad5b7e43fe7835588b629d847f75",
    "c7c75cfebf7add12bfcc32bb59d5edf38ac6e5aa",
    "5e2e5d0a46be47d8086b8642e055066079bfa4e6",
]
REQUIRED_VERBATIM_EXCERPTS = [
    "대표적인 ECG 검사인 Holter 검사가 24~48시간 이상 심전도를 기록하는 것도 간헐적으로 나타나는 이상을 포착하기 위해서이다.",
    "이에 본 작품은 분류에 필요한 사건, 리듬 및 파형 증거만 순차적으로 누적하는 SNN 기반 저전력 스트리밍 구조를 채택하였다.",
    "따라서 30분은 하드웨어의 처리 한계가 아니라 공개 데이터셋을 공정하게 비교하기 위한 표준 평가 단위이다.",
    "각 30분 구간은 원천 DB label과 가용한 beat/rhythm annotation을 대조하여 해당 클래스의 박동 및 리듬 증거가 충분히 포함되는지 확인하고 라벨 대표성을 점검하였다.",
    "분류 구조의 가중치와 임계값은 학습 및 검증 데이터로 결정하고 RTL로 구현한 뒤 최종 시험 전에 고정하였다.",
    "Run-3 post-route ECO에서는 같은 slow-early 0.95·fast-late 1.05 engineering derate와 100 ps hold uncertainty를 유지하면서 core hold·data-transition·clock-slew·internal-DRC를 0 violation으로 닫았다.",
    "Run-5 AXI는 floorplan utilization을 0.50으로 낮춰 setup·hold·data-transition·clock-slew·internal-DRC를 모두 닫고 LEC를 유지했다.",
    "원시 ECG 전체를 저장하지 않고, 표본이 입력될 때마다 사건을 검출하고 뉴런의 증거 누적값을 순차적으로 갱신하는 스트리밍 구조이다.",
    "현재 표본과 직전 표본의 차이인 ΔECG를 구하고, 그 절댓값이 구간 초기의 입력 변화에 맞춰 자동 설정된 문턱값을 넘으면 부호에 따라 상승 또는 하강 Strong Event를 발생시킨다.",
    "Pure RTL은 AXI IP로 패키징하였다.",
    "분류 성능은 학습/검증 데이터와 원천 record가 겹치지 않고 모델 선택에도 사용되지 않은 fully held-out 최종 시험 데이터로, 설계 고정 후 최초 한 번만 평가하였다.",
    "장시간 처리와 저전력 목표도 30분 입력과 조건부 추정에 근거하므로 유지한다.",
    "Forced gate/SDF와 activity 결과의 기존 조건부 경계도 유지한다.",
]
FORBIDDEN = [
    "SNN-inspired", "본 연구는 세계 최초", "동일한 연구가 없음을 확인",
    "실측 소비전력 2.991", "FPGA 소비전력은 2.991", "임상적으로 검증",
    "ASIC full timing closure를 달성", "GPDK045 실측 전력", "foundry sign-off를 완료",
    "AFE–ADC와 Pure RTL을 직접 연결한 36개 XMODEL End-to-End",
    "End-to-End full replay에서는 30분 입력 36개 모두",
    "actual raw XMODEL 36/36", "unmodified four-state gate PASS",
    "AXI run-2 RTL 36/36",
    "GPDK045 run-2 실측 전력", "exploratory PG 완료",
    "Run-2 physical timing closure를 달성", "foundry-characterized AOCV/POCV를 적용",
    "ACTIVITY_RESULT_" + "PENDING_LOCAL_RUN", "2.02536072 mW는 silicon 실측 전력",
    "0.00000087 mW는 energy/decision", "AXI activity power 2.02536072 mW",
]


def main() -> int:
    errors: list[str] = []
    text = REPORT.read_text(encoding="utf-8")
    for item in REQUIRED_HEADINGS:
        if item not in text:
            errors.append(f"missing heading: {item}")
    for item in REQUIRED_TEXT:
        if item not in text:
            errors.append(f"missing required statement/token: {item}")
    for item in REQUIRED_VERBATIM_EXCERPTS:
        if item not in text:
            errors.append(f"missing submission verbatim excerpt: {item}")
    for item in FORBIDDEN:
        if item in text:
            errors.append(f"forbidden wording: {item}")
    if "원문 보존 안내" in text or "보고서 외 추가 기술기록" in text:
        errors.append("editorial preservation notice or detached supplemental section remains")
    body = text.split("# 참고문헌", maxsplit=1)[0]
    for number in range(1, 9):
        if f"[{number}]" not in body:
            errors.append(f"reference [{number}] is not cited in the report body")
    if "이는 세계 최초이거나 동일 연구가 없다는 단정은 아니다" not in text:
        errors.append("missing explicit novelty limitation")

    with CLAIMS.open(encoding="utf-8", newline="") as handle:
        claim_ids = {row["claim_id"] for row in csv.DictReader(handle)}
    with EVIDENCE.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        errors.append("evidence map is empty")
    for row in rows:
        if row["claim_id"] not in claim_ids:
            errors.append(f"unknown claim id in evidence map: {row['claim_id']}")
        if not (ROOT / row["evidence_path"]).exists():
            errors.append(f"missing evidence path: {row['evidence_path']}")

    ref_count = sum(1 for line in text.splitlines() if line[:1].isdigit() and ". " in line[:4])
    if ref_count < 8:
        errors.append(f"expected at least 8 numbered references; found {ref_count}")

    if errors:
        print("INTEGRATED_REPORT: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("INTEGRATED_REPORT: PASS")
    print(f"- {len(rows)} evidence-map rows resolved")
    print(f"- {ref_count} numbered references")
    return 0


if __name__ == "__main__":
    sys.exit(main())
