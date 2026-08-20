# GPDK045 디지털 코어 PPA 검증

이 디렉터리는 `snn_ecg_asic_core_top`을 Cadence 흐름으로 합성·등가성 검증·배치배선·RC 추출한 2026-08-20 실행의 공개 가능한 증거를 정리한다. 사용 라이브러리는 generic 교육용 GPDK045 GSCLIB v4.7이며, 결과 범위는 표준셀 디지털 코어에 한정된다.

## 결론

| 항목 | 결과 |
|---|---:|
| RTL dependency hash | compiled Verilog 16개 + parameter header 1개, 로컬과 실행본 17/17 일치 |
| Xcelium wrapper smoke | PASS, cycle mismatch 0 |
| Genus unresolved/empty module | 0 / 0 |
| Conformal RTL→`fv_map` | 13/13 equivalent, NEQ 0, abort 0 |
| Genus mapped cell / cell area | 35,188 / 93,585.906 µm² |
| Innovus post-route instance / cell area | 35,663 / 95,321.556 µm² |
| Placement density | 66.20% |
| Extracted setup WNS at 100 MHz | +2.980 ns; clock slew violation 86개 별도 존재 |
| Extracted hold WNS | **-0.050 ns** |
| Vectorless post-route total power | 3.35554239 mW |
| Signal-route internal DRC | **1 Metal1 spacing violation** |

explicit data-path setup report의 WNS는 양수지만 clock slew 위반 86개, hold 위반과 내부 route-rule 위반이 남아 있으므로 이 결과를 **setup/hold physical closure**, **DRC clean**, **signoff**라고 부르지 않는다.

## 구현 범위와 조건

- Top: `snn_ecg_asic_core_top`
- 내부 canonical top: `snn_ecg_30min_final_top`
- 고정 구성: 12-bit ADC, `PROFILE_EN=0`, `PROF_COUNTER_W=64`, `60000 samples/snapshot`, `30 snapshots/chunk`, `POST_DONE_TICKS=37`
- Clock: 10 ns, 100 MHz
- SDC 가정: setup/hold uncertainty 0.2/0.1 ns, input/output delay 1 ns, input transition 0.1 ns, output load 0.020 pF(20 fF)
- Historical clock-source transition: 명시하지 않음; CCOpt root slew 약 0.004 ns. 현재 SDC의 0.100 ns 명시는 post-run hardening이며 기존 PPA에 적용된 조건이 아니다.
- Setup view: `slow_vdd1v2_basicCells.lib`, 1.08 V, 125 °C
- Hold view: `fast_vdd1v2_basicCells.lib`, 1.32 V, 0 °C
- 두 view 모두 동일한 `gpdk045.tch`와 단위 RC scale을 사용한다. 독립적으로 특성화된 RCmax/RCmin signoff corner가 아니다.
- GSCLIB timing constraint table은 tool demonstration용 2×2 특성화이며 silicon 정확도 권장 7×7 table이 아니다.
- Genus 결과는 limited license에서 완료한 `syn_map` 기준선이다. `syn_opt`는 라이선스가 없어 실행하지 않았다. 이 historical mapped netlist에는 `SDFFQX1` 995개가 functional logic으로 사용됐고 scan chain은 정의되지 않아, Innovus가 10.70% flop의 placement/timing QoR 영향 가능성을 보고했다.
- Innovus 결과는 core-only signal routing이다. PG ring/stripe/sroute, IR-drop, DFT insertion, pad ring, package는 범위 밖이다.

## 논리 검증 경계

Xcelium smoke는 축소 파라미터(`8 samples/snapshot`, `2 snapshots`)와 synthetic 16-sample stream에서 wrapper의 `PROFILE_EN=0` 인스턴스와 원본 top의 `PROFILE_EN=1` 인스턴스를 cycle-by-cycle 비교했다. `sample_ready`, `busy`, `final_valid`, class, 네 final membrane이 모두 일치했다.

이 smoke는 wrapper 연결과 해당 시험 궤적의 profiling 비간섭만 확인한다. default `60000 × 30` workload, 실제 ECG 36-case wrapper regression, 분류 정확도 또는 formal equivalence의 대체 근거가 아니다. 구현 논리 등가성 근거는 별도로 실행한 Conformal RTL-to-`fv_map` 13/13 PASS다.

## PPA 해석

- 면적: post-route standard-cell area는 95,321.556 µm²이고 floorplan DIEAREA는 421.000 × 418.190 µm다. DEF의 842000 × 836380 좌표를 `UNITS DISTANCE MICRONS 2000`에 따라 변환한 값이다. 이는 pad가 없는 block floorplan이며 실제 chip die 면적이 아니다.
- 성능: RC 추출 후 explicit setup report WNS는 +2.980 ns, hold WNS는 -0.050 ns다. CCOpt에는 target 0.060 ns 대비 worst 0.062 ns의 clock slew 위반 86개도 남았다. 따라서 100 MHz data-path setup WNS는 양수지만 setup/hold 및 clock design-rule closure는 달성하지 못했다.
- 전력: setup slow view 1.08 V에서 internal 2.42385086 mW, switching 0.92844734 mW, leakage 0.00324419 mW, total 3.35554239 mW다. primary input와 sequential activity를 각각 0.10으로 둔 vectorless 추정이며 ECG workload 기반 SAIF/VCD 전력이나 실측 전력이 아니다.
- 배선: 총 wire length 449,894 µm, via 259,424개다. Innovus 내부 검사에서 Metal1 spacing 위반 1건이 남았고 foundry DRC/LVS deck은 실행하지 않았다. Filler/decap/endcap/welltap과 metal fill도 삽입하지 않았다. Library antenna 정보가 불완전하므로 internal antenna count 0은 signoff PASS가 아니다.

## 증거와 보존

- [`run_manifest.json`](run_manifest.json): 실행 조건, 도구 버전, 결과와 한계
- [`executed_flow_sha256.csv`](executed_flow_sha256.csv), [`executed_snapshot/`](executed_snapshot/): byte-exact 실제 실행 파일과 current hardened flow의 경계
- [`results/ppa_summary.csv`](results/ppa_summary.csv): PPA 수치
- [`results/equivalence_summary.csv`](results/equivalence_summary.csv): simulation/LEC 경계
- [`results/netlist_identity.csv`](results/netlist_identity.csv): private recovered `fv_map`과 Innovus 입력 mapped netlist의 byte identity hash
- [`results/physical_checks.csv`](results/physical_checks.csv): route·timing·signoff 상태
- [`rtl_source_sha256.csv`](rtl_source_sha256.csv): 실제 실행 compiled Verilog 16개와 include parameter header 1개의 SHA-256
- [`pdk_file_sha256.csv`](pdk_file_sha256.csv): 사용 PDK 파일 식별 hash만 공개
- [`figures/routed_core.gif`](figures/routed_core.gif): Innovus routed signal-core 화면
- [`CHECKSUMS.txt`](CHECKSUMS.txt): 공개 evidence package SHA-256

PDK 원본, Cadence DB와 sanitize하지 않은 raw 로그는 Git에 넣지 않았다. 전체 raw archive는 로컬 비공개 보관소로 회수해 SHA-256을 확인했으며, 원격 전용 작업 디렉터리와 잔여 Cadence 프로세스는 회수 후 삭제했다.

## 주장 금지

- 공식 foundry PDK 또는 tape-out 완료
- full-chip/pad/package 구현 완료
- foundry DRC/LVS, antenna, ERC signoff 완료
- hold closure 또는 DRC-clean 완료
- clock-tree slew closure 또는 scan-aware placement QoR 완료
- 실제 ECG workload 전력, 실측 전력 또는 silicon 성능
- AFE·ADC를 포함한 면적·전력
- FPGA와 GPDK045 사이의 공정 정규화 없는 직접 우열 비교
