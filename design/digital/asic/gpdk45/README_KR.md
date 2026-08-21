# GPDK45 Core-only ASIC Flow

이 디렉터리는 검증된 Pure RTL 분류 코어를 Cadence GPDK045 demonstration library에서 합성·논리 등가성·배치배선·기생성분 추출·PPA 분석하기 위한 재현 스크립트를 보관한다.

## 구현 경계

- physical top: `snn_ecg_asic_core_top`
- canonical core: `snn_ecg_30min_final_top`
- `PROFILE_EN=0`, `PROF_COUNTER_W=64`
- 12-bit signed ECG input 고정
- MicroBlaze, AXI wrapper, FPGA IP, pad ring, DFT, SRAM macro, AFE·ADC는 제외
- class와 네 Final Membrane은 검증된 기능 출력이므로 유지

이 wrapper는 PPA용 block boundary다. 독립 chip top이나 package pinout이 아니다.

## 기준 제약

| 항목 | 값 |
|---|---:|
| clock | 100 MHz, 10.000 ns |
| clock source transition | 0.100 ns |
| setup uncertainty | 0.200 ns |
| hold uncertainty | 0.100 ns |
| input/output delay | 1.000 ns |
| input transition | 0.100 ns |
| output load | 0.020 pF |
| setup Liberty | slow, 1.08 V, 125 C |
| hold Liberty | fast, 1.32 V, 0 C |

`max_rc`와 `min_rc`는 동일한 `gpdk045.tch`와 unit scaling 1.0을 공유하고 온도만 125 °C/0 °C로 다르게 둔다. 독립적으로 특성화된 foundry RC corner가 아니다.

## 파일

- `rtl/snn_ecg_asic_core_top.v`: profile/debug-free physical wrapper
- `constraints/core_100mhz.sdc`: block-level timing/load assumptions
- `scripts/rtl_files.tcl`: canonical 15-source closure와 wrapper
- `scripts/run_genus.tcl`: Genus mapping, reports, netlist/SDC, LEC dofile
- `scripts/report_mapped_netlist.tcl`: 저장한 mapped netlist의 독립 readback report
- `scripts/mmmc.tcl`: slow setup/fast hold analysis views
- `scripts/run_innovus.tcl`: floorplan, placement, CTS, signal route, Quantus RC, PPA export
- `scripts/report_routed_checkpoint.tcl`: pre-extract routed checkpoint의 복구·재추출·report
- `scripts/export_layout.tcl`: post-extract checkpoint의 routed-core GIF export
- `sim/tb_asic_core_wrapper_smoke.v`: 원본 top과 wrapper의 functional output cycle comparison
- `tools/compute_adc_activity.py`: canonical ECG stream의 bit별 primary-input activity 계산

## 실행 환경 변수

```csh
setenv REPO_ROOT <repository-root>
setenv RUN_ROOT <temporary-run-directory>
setenv PDK_ROOT <GSCLIB045-root>
setenv GENUS_EFFORT medium
setenv RUN_SYN_OPT 0
setenv RUN_POSTROUTE_OPT 0
setenv RUN_TIMEDESIGN 0
```

| 변수 | 기본값 | 의미 |
|---|---:|---|
| `RUN_SYN_OPT` | `0` | Genus `syn_map` 뒤의 `syn_opt`를 선택적으로 실행 |
| `RUN_POSTROUTE_OPT` | `0` | Innovus post-route setup/hold 최적화를 제한적으로 시도 |
| `RUN_TIMEDESIGN` | `0` | `timeDesign` setup/hold 요약을 제한적으로 시도 |

기본 재현 경로는 Genus `syn_generic -> syn_map`까지만 실행한다. 실제 2026-08-20 실행 script는 `syn_map` 뒤 `syn_opt -logical`을 시도했지만 limited Genus license 오류로 중단됐고, 기준 netlist는 그 직전의 `fv_map`을 복구한 것이다. 현재 script는 이 실패를 반영해 `RUN_SYN_OPT=0`을 기본값으로 hardened했지만, hardened 전체 flow를 새로 실행한 결과로 표현하지 않는다.

Innovus 기본 경로는 route 뒤 IQuantus high-effort extraction을 수행하고 즉시 database·DEF·netlist checkpoint를 저장한 다음, `report_timing`, vectorless `report_power`, SDF와 corner별 SPEF를 내보낸다. `optDesign -postRoute`, `optDesign -postRoute -hold`, `timeDesign`은 기본 경로에 포함되지 않는다.

`RUN_POSTROUTE_OPT=1`이면 setup/hold 최적화를 시도하고 결과를 `postroute_optimization_status.txt`에 남긴다. 하나라도 실패하면 routed baseline을 복원하고 high-effort RC를 다시 추출한 뒤 그 baseline을 보고한다. `RUN_TIMEDESIGN=1`의 성공·실패는 `time_design_status.txt`에 별도로 기록되며 baseline 산출물 생성을 막지 않는다.

## 실행 순서

Xcelium file list는 repository-relative이므로 smoke는 repository root에서 실행한다. Genus는 자동 `fv/` evidence 위치를 고정하기 위해 별도 work directory에서 실행한다.

```csh
mkdir -p "$RUN_ROOT/work/genus" "$RUN_ROOT/work/innovus" "$RUN_ROOT/logs"

cd "$REPO_ROOT"
xrun -64bit -sv -f design/digital/asic/gpdk45/scripts/xcelium_wrapper_smoke.f >! "$RUN_ROOT/logs/xrun_wrapper_smoke.console.log"

cd "$RUN_ROOT/work/genus"
genus -no_gui -files "$REPO_ROOT/design/digital/asic/gpdk45/scripts/run_genus.tcl" >! "$RUN_ROOT/logs/genus_core.console.log"
```

Xcelium은 exit 0, `ASIC_CORE_SMOKE_PASS`, mismatch/FAIL 0을 확인한다. Genus는 `check_design_unresolved.rpt`의 unresolved/empty 0, mapped report와 netlist 생성을 확인한다.

## Conformal 재현과 판정

Genus working directory에서 자동 생성된 RTL→`fv_map` dofile과 output directory의 `fv_map`→저장 netlist dofile을 순서대로 실행한다.

```csh
lec -XL -nogui -dofile "$RUN_ROOT/work/genus/fv/snn_ecg_asic_core_top/rtl_to_fv_map.do" >! "$RUN_ROOT/logs/lec_rtl_to_fv_map.console.log"
lec -XL -nogui -dofile "$RUN_ROOT/outputs/genus/fv_map_to_final_netlist.do" >! "$RUN_ROOT/logs/lec_fv_map_to_final.console.log"
```

각 단계는 process status 0, comparison PASS, non-equivalent 0, aborted 0을 모두 확인해야 한다. 실제 기준 실행은 첫 RTL→`fv_map` 단계에서 13/13 hierarchical PASS였다. 이후 저장한 mapped Verilog가 decompressed `fv_map.v.gz`와 byte-identical함을 확인했지만, 두 번째 dofile을 별도로 실행한 결과나 Innovus post-route netlist LEC로 확대하지 않는다.

```csh
cd "$RUN_ROOT/work/innovus"
innovus -no_gui -files "$REPO_ROOT/design/digital/asic/gpdk45/scripts/run_innovus.tcl" >! "$RUN_ROOT/logs/innovus_core.console.log"
```

Innovus는 extraction status 0, explicit setup/hold report, connectivity, area, power status와 SDF/SPEF export를 각각 확인한다. `RUN_POSTROUTE_OPT=0`, `RUN_TIMEDESIGN=0`이 현재 기본 재현 경로다. Historical byte-exact 실행 파일과 실패 경계는 `verification/asic_gpdk45_core/executed_snapshot/`에 별도로 보존한다.

PDK 원본과 원격 접속 정보는 저장소에 포함하지 않는다. 실행 로그는 로컬로 회수해 식별정보를 제거한 뒤 `verification/asic_gpdk45_core/`에 보존한다.

## 결과 해석 경계

### 실제 기준선과 제한된 실행 범위

- 합성 기준선: slow 1.2 V 계열 Liberty를 사용한 `syn_map` 출력, `syn_opt` 미실행
- 물리 기준선: floorplan, placement, CTS, signal routing, high-effort post-route RC extraction
- timing evidence: `setup_slow`와 `hold_fast` view의 명시적 `report_timing`
- power evidence: 기본 switching activity를 사용한 post-route vectorless 추정치
- 라이선스/분석 한계: Genus `syn_opt`는 limited license 오류로 미실행이다. Innovus post-route setup/hold optimization과 `timeDesign`은 라이선스 오류가 아니라 Non-OCV MMMC 분석 구성에서 요구 조건을 충족하지 못해 완료되지 않았다. 이는 RTL 기능 실패가 아니며, 해당 단계를 완료한 것으로 주장하지 않는다.
- hold report는 위반 상태를 관찰하는 자료일 뿐 hold closure 증거가 아니다.
- historical mapped netlist에는 scan-capable `SDFFQX1` 995개가 functional logic으로 사용됐고 scan chain은 정의되지 않았다. Innovus는 10.70% flop의 undefined scan chain이 placement/timing QoR에 영향을 줄 수 있다고 보고했다. 현재 Genus script는 `S*DFF*` family를 avoid하도록 개선했지만 재실행 전까지 기존 PPA의 한계로 남긴다.
- CCOpt에는 clock slew violation 86개가 남아 있다. setup WNS가 양수여도 clock-tree design-rule closure를 뜻하지 않는다.

이 기준선에는 PG ring/stripe/sroute, IR-drop/EM, scan insertion·ATPG 같은 DFT, filler/decap/endcap/welltap, metal fill, foundry DRC/LVS, signoff STA, pad·package가 없다. `verifyConnectivity -type regular`은 signal net만 검사하며 VDD/VSS physical connectivity를 검증하지 않는다. Library antenna 정보도 불완전해 internal antenna count 0을 signoff PASS로 사용하지 않는다.

허용되는 표현:

> Cadence GPDK045 demonstration library에서 SNN 디지털 코어를 `syn_map`하고 core-only placement·CTS·signal routing·high-effort RC extraction을 수행했으며, 명시한 slow/fast view에서 post-route timing과 vectorless power를 평가하였다.

금지되는 표현:

- 공식 foundry 45 nm PDK 또는 tape-out/sign-off 완료
- full-chip, pad ring, package, PG/IR-drop 완료
- AXI full physical closure 또는 foundry sign-off hold closure 완료
- DFT, scan insertion 또는 ATPG 완료
- foundry DRC/LVS 완료
- signoff STA 또는 signoff RC extraction 완료
- archived SDF의 post-route back-annotation GLS 완료
- 실제 ASIC 또는 실리콘 실측 전력
- AFE·ADC를 포함한 칩 면적·전력

실제 2026-08-20 실행 SDC에는 clock source transition이 명시되지 않아 CCOpt root slew가 약 0.004 ns의 tool-default/derived 값이었다. 현재 SDC의 0.100 ns 가정과 scan-cell avoid는 후속 재현을 위한 post-run hardening이며, 기존 PPA를 이 개선 제약으로 재실행한 것으로 주장하지 않는다. Checkpoint는 RCDB를 보존하지 않으므로 restore 뒤 high-effort extraction을 다시 수행해야 한다.

GSCLIB045 문서는 이 공정을 generic representative 45 nm CMOS이자 tool demonstration용으로 규정한다. Timing constraint table도 silicon 정확도에 권장되는 7×7이 아니라 demonstration용 2×2 특성화다. 결과는 구현 가능성 연구 자료이며 실제 silicon 성능 보증이 아니다.

## Run-3 hold-closure 재현 자산

- `tools/extract_violating_hold_endpoints.py`: Innovus hold report에서 unique violated endpoint를 fail-closed로 추출한다.
- `scripts/manual_hold_endpoint_eco.tcl`: endpoint별 DLY ECO와 global 또는 targeted `ecoRoute`, 재추출·timing·DRC·checkpoint 생성을 수행한다.
- `scripts/hold_resize_only.tcl`: 새 인스턴스 없이 cell resizing만 시도한 비교 실험이다. AXI hold를 닫지 못해 최종 후보로 채택하지 않았다.
- `scripts/export_hold_closed_candidate.tcl`: 선택 checkpoint를 독립 복원해 IQuantus high-effort RC, setup/hold, vectorless power, DRC, SDF/SPEF와 netlist를 최종 export한다.
- `scripts/run_postroute_lec.do`: mapped netlist와 최종 postroute netlist를 비교한다.

Run-3 core는 setup +2.470 ns, hold WNS/TNS/path 0, data max-transition 0, clock slew 0와 internal DRC 0을 기록했다. AXI는 setup +2.435 ns와 hold WNS/TNS/path 0이지만 data max-transition 264 nets/1,387 terminals와 clock slew 263 pins가 남았다. 상세 수치와 claim boundary는 `verification/asic_gpdk45_hold_closure/`에 있다.
