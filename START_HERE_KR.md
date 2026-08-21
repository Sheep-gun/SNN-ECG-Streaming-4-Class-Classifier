# 빠른 시작

## 1. 프로젝트 이해

1. [README.md](README.md)
2. [통합 기술보고서](reports/INTEGRATED_TECHNICAL_REPORT_KR.md) — 제출 기술내용과 근거 기반 보충 설명을 관련 절에 통합한 기준 문서
3. [한계와 claim 경계](docs/LIMITATIONS_AND_CLAIM_BOUNDARY_KR.md)

## 2. 파일 위치

| 찾는 항목 | 위치 |
|---|---|
| 사전 feature·annotation 분석 | `analysis/feature_selection/`, `docs/FEATURE_SELECTION_AND_ANNOTATION_KR.md` |
| 데이터 version, split, checksum | `datasets/` |
| MATLAB | `design/analog/matlab/` |
| LTspice | `design/analog/ltspice/` |
| XMODEL | `design/analog/xmodel/` |
| Pure RTL | `design/digital/rtl/` |
| AXI IP와 testbench | `design/digital/ip_repo/`, `design/digital/sim/` |
| Python 모델 | `models/digital_equivalence/tools/` |
| Exact C++ 모델 | `models/digital_equivalence/exact_cpp/` |
| Pure RTL Vivado project | `vivado/pure_rtl/project/SNN_ECG_PURE_RTL_VISUALIZATION.xpr` |
| MicroBlaze Vivado project | `vivado/microblaze/SNN_ECG_MB_FULL_REPLAY.xpr` |
| GPDK045 core-only flow | `design/digital/asic/gpdk45/` |
| GPDK045 PPA 결과와 한계 | `verification/asic_gpdk45_core/`, `tables/asic_gpdk45_ppa.csv` |
| GPDK045 run-2 core·AXI·regression·LEC·conditioned activity | `verification/asic_gpdk45_run2/`, `tables/asic_gpdk45_run2_ppa.csv`, `tables/asic_gpdk45_run2_verification.csv` |
| GPDK045 run-3 hold closure | `verification/asic_gpdk45_hold_closure/`, `tables/asic_gpdk45_hold_closure.csv` |
| GPDK045 run-4 AXI closure 개선 | `verification/asic_gpdk45_axi_closure_run4/`, `tables/asic_gpdk45_axi_closure_run4.csv` |
| GPDK045 run-5 AXI full closure | `verification/asic_gpdk45_axi_full_closure_run5/`, `tables/asic_gpdk45_axi_full_closure_run5.csv` |
| GPDK045 run-6 AXI hold guardband | `verification/asic_gpdk45_axi_hold_guardband_run6/`, `tables/asic_gpdk45_axi_hold_guardband_run6.csv` |
| timing pipeline 이력 | `verification/timing_optimization/` |
| compact 36-case 통합 acceptance | `verification/xmodel_rtl_acceptance_36case/` |
| raw XMODEL replay audit | `verification/xmodel_rtl_e2e/` |
| FPGA report와 checkpoint | `verification/fpga_implementation/` |
| 최종 Figure | `figures/final_submission/` |
| claims와 commits | `project_registry/` |
| 검사 도구 | `tools/check_*.py` |

## 3. 재현 순서

[REPRODUCIBILITY_KR.md](REPRODUCIBILITY_KR.md)의 환경과 명령을 따른다. 대용량 PhysioNet 원본과 36-case generated input은 Git 외부에 둔다.

## 4. 두 XMODEL 근거를 혼동하지 말 것

- `xmodel_rtl_acceptance_36case`: compact 36-case acceptance, PASS
- `xmodel_rtl_e2e`: raw full-30분 accepted dump archive audit, 4 present / 32 missing

## 5. 용어

공개 클래스명은 `AF`다. 고정 model ID, RTL port나 legacy artifact 안의 `AFF`는 hash와 재현성 때문에 변경하지 않는다.
