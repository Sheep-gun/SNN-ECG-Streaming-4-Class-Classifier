# 검증과 구현 증거

| 하위 경로 | 내용 |
|---|---|
| `xmodel_rtl_acceptance_36case/` | 과거 고정 환경의 compact 36-case input/output acceptance |
| `xmodel_rtl_e2e/` | 실제 보유 XMODEL ADC 입력의 Pure RTL replay와 출처 |
| `fpga_implementation/` | Vivado 배치·배선, 자원, timing 원본 |
| `asic_gpdk45_core/` | Generic GPDK045 core-only mapping·LEC·signal post-route·PPA 증거 |
| `asic_gpdk45_run2/` | Scan-free core·AXI PPA, RTL36/raw4, post-route LEC, conditional gate/SDF, failed PG, core seed11-conditioned activity-window 증거 |
| `asic_gpdk45_hold_closure/` | Run-3 core hold/DRV closure와 AXI hold-closure tradeoff 증거 |
| `asic_gpdk45_axi_closure_run4/` | Run-4 AXI hold·clock·DRC closure 개선과 residual data-transition 증거 |
| `integration_evidence/` | 통합 전후 상태와 의도적 제외 자료 |
| `timing_optimization/` | critical path 관측과 pipeline 최적화 이력 |

실제 full-30분 XMODEL ADC dump는 4개만 보존되어 있으며, 나머지 32개가 존재하는 것처럼 해석하지 않는다.
