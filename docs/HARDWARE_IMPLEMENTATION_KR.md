# 하드웨어 구현, 가속 성능과 전력

## Pure RTL implementation

- Tool/device: Vivado 2020.2, Artix-7 XC7A100T
- Top: `snn_ecg_30min_final_top`
- Resources: 9,719 LUT, 5,038 FF, 0 BRAM, 0 DSP
- Post-route WNS: 8.184 ns

이 수치는 최종 고정 Pure RTL 구현 결과다. benchmark용 profiler가 추가된 build의 9,759 LUT와 5,049 FF는 cycle/power 분석 범위이며 최종 자원 수치와 혼합하지 않는다.

## GPDK045 core-only ASIC implementation

상위 경계는 `snn_ecg_asic_core_top`이며, 고정 분류 코어 `snn_ecg_30min_final_top`을 `PROFILE_EN=0`으로 인스턴스화해 profiler/debug 출력을 physical-design 경계에서 제외했다. 12-bit ADC 입력과 분류 결과·Final Membrane 출력은 유지했다. Xcelium에서 8 samples/snapshot·2 snapshots의 synthetic 16-sample reduced-parameter wrapper smoke를 cycle mismatch 0으로 PASS했고, 실제 코어 Conformal RTL-to-mapped LEC에서 13개 hierarchical module이 모두 PASS하여 diff 0, abort 0을 기록했다. Wrapper smoke는 default `60000 × 30` workload나 실제 ECG 36-case wrapper regression을 뜻하지 않는다.

| 항목 | 결과 | 범위·제약 |
|---|---:|---|
| Library | GPDK045 GSCLIB v4.7 | generic representative 45 nm; foundry sign-off PDK 아님 |
| Clock constraint | 100 MHz | 10 ns block-level SDC |
| Setup view | slow 1.08 V, 125 °C | setup library PVT |
| Hold view | fast 1.32 V, 0 °C | hold library PVT |
| RC technology | `gpdk045.tch` | setup/hold에 같은 QRC tech 사용; 별도 RC corner 특성화 아님 |
| Genus mapped result | 35,188 cells, 93,585.906 µm² | `syn_map` 기준; `syn_opt` license 미확보로 최적화 미실행 |
| Historical scan-capable mapping | `SDFFQX1` 995개, undefined scan 10.70% flops | scan chain 미정의; placement/timing QoR 영향 가능 |
| Genus mapped setup slack | +3.349 ns | pre-route mapped timing |
| Innovus post-route result | 35,663 instances, 95,321.556 µm² | core-only standard-cell area |
| Innovus DIE boundary | 421.000 × 418.190 µm | DEF 2,000 DBU/µm 변환; pad ring/package를 포함한 fabricated die area가 아님 |
| Extracted setup WNS | +2.980 ns | explicit slow setup report; clock slew 위반 86개 별도 존재 |
| Extracted hold WNS | −0.050 ns | fast hold view; hold 위반으로 full timing closure 아님 |
| CCOpt clock slew | 86 violations, target 0.060 ns, worst 0.062 ns | clock design-rule closure 미달성 |
| IQuantus extraction | status 0 | high-effort extraction 실행 상태 |

신호 배선은 완료되었지만 VDD/VSS는 배선하지 않았고 power grid·IR drop 분석을 수행하지 않았다. connectivity report의 2건은 미배선 PG 정보이며, Innovus internal route DRC 1건이 남아 있다. Library antenna 정보가 불완전해 internal antenna count 0도 signoff PASS가 아니다. Filler/decap/endcap/welltap, metal fill, foundry DRC/LVS deck, DFT, pad, package와 fabrication은 범위 밖이다. 따라서 이 결과는 **generic GPDK045 core-only exploratory post-route PPA**로만 해석한다.

## GPDK045 run-2 scan-free core and AXI block

Run-2는 run-1 historical baseline을 덮어쓰지 않고 scan-free core와 AXI-Lite/AXI-Stream 경계를 포함한 `snn_ecg_axi_asic_top`을 별도 profile로 구현했다. AXI profile은 `PROFILE_EN=0`이며 MicroBlaze, SmartConnect, BRAM, UART, board clock/reset, pad와 package를 포함하지 않는다.

| 항목 | Run-2 scan-free core | Run-2 AXI-inclusive block |
|---|---:|---:|
| Mapped cells / area | 36,565 / 94,421.754 µm² | 37,293 / 96,548.994 µm² |
| Sequential cells | 6,045 | 6,244 |
| Mapped setup slack | +3.3509 ns | +3.3498 ns |
| Post-route instances / cell area | 42,958 / 120,287.898 µm² | 43,901 / 123,650.100 µm² |
| DIE boundary | 422.8 × 419.9 µm | 426.2 × 425.03 µm |
| DIE boundary area | 177,533.720 µm² | 181,147.786 µm² |
| Placement density | 82.775% | 83.215% |
| Setup WNS | +2.469 ns | +2.781 ns |
| Hold WNS / TNS / paths | −0.008 / −0.094 ns / 37 | −0.016 / −0.518 ns / 107 |
| Max-transition residual | 3 nets / 6 terminals, worst −0.026 ns | 73 nets / 469 terminals, worst −0.476 ns |
| Clock slew at 60 ps target | 0 violations | 0 violations |
| Innovus internal DRC | 0 | 0 |
| Vectorless total power | 3.71626492 mW | 3.69335598 mW |

양 profile은 slow early 0.95와 fast late 1.05의 fixed engineering derate와 CPPR을 사용했다. Slow/fast RC view 모두 같은 `gpdk045.tch`와 scale 1.0을 사용했으므로 이는 OCV assumption이지 foundry-characterized AOCV/POCV/LVF가 아니다. Clock slew와 internal DRC는 개선되었지만 hold와 data-net transition 위반이 남아 physical timing closure는 아니다.

`PROFILE_EN=0` core wrapper RTL은 regenerated canonical digital 36/36과 actual raw XMODEL 4/4에서 exact PASS했다. Raw XMODEL은 여전히 4/36만 보존하며 canonical 36과 혼합하지 않는다. Mapped-to-postroute LEC는 core 6,178 points와 AXI 6,287 points에서 diff, abort, unknown 0이었다.

Unmodified four-state full raw case0 gate run은 output X를 남겼고 XPR 기능 license는 사용할 수 없었다. Testbench-only forced digital two-state initialization을 reset window에 적용한 mapped seeds 11/22/33은 6,045/6,045 sequential coverage와 release X 0으로 full raw case0 exact PASS했다. MAX-SDF postroute seed11 pilot은 같은 강제 초기화와 6,044/6,044 coverage에서 exact PASS했지만 timing check를 비활성화했고 88건의 `SDFNCAP` port-alias warning을 남겼다. 이 결과는 유한 seed의 **testbench-conditioned initialization sensitivity**이며 unmodified GLS, reset/power-up robustness, 일반 SDF timing PASS 또는 signoff가 아니다.

Exploratory PG attempt은 geometry-only ring/stripe/filler 가정에서 171 connectivity와 715 geometry violation으로 실패했다. 선택한 core/AXI checkpoint는 signal-only이며 VDD/VSS가 unrouted이다. Top PG pad/source, foundry current-density rule, IR/EM이 없으므로 PG 구현으로 표현하지 않는다.

## MicroBlaze 통합 시스템

- 12,494 LUT, 8,494 FF, 16 BRAM, 3 DSP
- setup WNS 0.097 ns
- Nexys A7-100T
- 구성: MicroBlaze, Local Memory, AXI interconnect, Sample Feeder, SNN accelerator, AXI INTC, UARTLite

통합 시스템의 BRAM과 DSP는 processor, memory와 peripheral 자원이며 Pure RTL 분류기 자원이 아니다.

## timing bottleneck와 pipeline 최적화

초기 병목은 `class_score_neurons`의 `rdm_level_spike → pred_class` 경로였다. 약 90 logic levels와 52 CARRY4를 포함한 누산·비교·WTA 경로를 관측한 뒤 clock requirement를 완화하지 않고 구조적으로 분할했다.

주요 변경은 C24 readout과 class WTA 분리, `*_next` counter capture, event/gate/score delta 등록, RDM·RAM exact lookup, Snapshot update–adjust–commit 분리, RBBB gate 정렬, QRS MAF timestamp FIFO, PNN center 등록, Final Membrane pairwise WTA, ARR commit과 flush 정렬이다.

개발 순서는 **critical path 관측 → pipeline 분할 → timing 재검증 → Python/RTL 및 FPGA 기능 등가성 확인**이었다. 상세 commit과 RTL 근거는 `verification/timing_optimization/RTL_TIMING_OPTIMIZATION_HISTORY_KR.md`에 있다.

최적화 전 약 17.5k LUT는 historical OOC hotspot 수치다. 최종 9,719 LUT와 보고 범위가 달라 직접 감소율로 비교하지 않는다.

## 처리시간 benchmark

| 구현 | 범위 | 시간 |
|---|---|---:|
| Exact C++ | preloaded 1,800,000 samples, single thread kernel | 1,777.6998 ms median |
| FPGA core | profile total − input wait, 100 MHz | 36.0129 ms |
| 비율 | C++ / FPGA active time | 49.36배 |

FPGA 활성시간은 3,601,290 cycles이며 36개 board case와 XSim에서 동일했다. UART-paced transaction 시간은 입력 전송 대기가 포함되므로 accelerator speedup에 사용하지 않는다.

## 전력과 에너지

| 조건 | 결과 | 근거 |
|---|---:|---|
| 1 kSPS continuous clocked allocation | 142.0 mW | post-route real-ECG activity estimate |
| 100 MHz burst allocation | 149.5 mW | activity estimate |
| 30분 판정 active energy | 5.3839 mJ | 149.5 mW × 36.0129 ms |
| ideal power-gated average | 2.991 µW | 5.3839 mJ / 1,800 s |

2.991 µW는 현재 FPGA 소비전력이나 ASIC 실측값이 아니다. off leakage, retention, isolation, wake-up, power switch와 data buffering 비용을 0으로 둔 이상적 조건이다. 보드 전체 전력은 측정하지 않았다. 산출 원본과 한계는 `models/digital_equivalence/results/`와 `models/digital_equivalence/reports/POWER_ENERGY_METHODOLOGY.md`에 있다.

GPDK045 post-route vectorless power는 setup-slow 1.08 V view에서 internal 2.42385086 mW, switching 0.92844734 mW, leakage 0.00324419 mW, total 3.35554239 mW이다. PI/sequential default activity 0.10을 사용했고 모든 instance에 activity가 할당되었지만, 실제 ECG workload VCD/SAIF를 사용한 전력은 아니다. PG 배선·IR drop·power-gating이 제외되었으므로 실리콘 전력, 판정당 에너지 또는 wearable 평균전력으로 전환하지 않는다.

Run-2 core 3.71626492 mW와 AXI 3.69335598 mW는 PI/sequential default activity 0.10의 vectorless 추정치다. AXI에는 activity-based power 결과가 없다.

Run-2 core의 seed11-conditioned activity 분석은 다음과 같다.

| Activity window | Internal | Switching | Leakage | Total |
|---|---:|---:|---:|---:|
| Accelerated raw full gap2 | 1.52085678 mW | 0.50045621 mW | 0.00404773 mW | 2.02536072 mW |
| Active-wait idle, matched 0.1 s | 1.48928157 mW | 0.41750333 mW | 0.00405502 mW | 1.91083992 mW |
| Literal 1 kSPS, 100-sample 0.1 s prefix | 1.48928212 mW | 0.41750554 mW | 0.00405312 mW | 1.91084079 mW |

Literal prefix와 active-wait idle의 matched total delta는 0.00000087 mW다. 모든 window는 testbench-conditioned mapped gate 6,045/6,045, `-access +rwc`, zero delay에서 생성한 normalized SAIF를 사용했다. Parse/annotation status는 PASS이고 fully-X/Z entry를 보존했으며 unannotated default는 0이지만, numeric annotation coverage PASS를 뜻하지 않는다. Accelerated gap2는 wall-time 1 kSPS가 아니고 두 prefix는 Snapshot이나 decision에 도달하지 않는다. Active-wait idle은 pure clock power가 아니며 matched delta도 silicon power 또는 energy per decision으로 해석하지 않는다.

## 구현하지 않은 범위

GPDK045 run-2는 scan-free mapping, clock-slew 0와 internal DRC 0까지 개선했지만 core/AXI hold·data-net transition closure, 성공한 VDD/VSS PG/IR/EM, physical-only cell·metal fill, complete antenna data, foundry DRC/LVS, DFT, pad, package와 fabricated silicon은 완료하지 않았다. physical AFE PCB, ADC silicon과 clinical validation도 미수행이다.
