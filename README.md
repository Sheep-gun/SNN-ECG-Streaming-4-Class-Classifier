# 다중 시간 척도 SNN을 적용한 장시간 ECG 4-클래스 저전력 스트리밍 분류 가속기 IP

이 저장소는 AFE–ADC와 SNN 기반 RTL 분류 가속기 IP를 결합하여 장시간 ECG 기록을 **NSR, CHF, ARR, AF** 중 하나로 분류하는 통합 구조의 설계, 모델, RTL, Vivado project와 검증 근거를 한곳에 보존한다.

[통합 기술보고서](reports/INTEGRATED_TECHNICAL_REPORT_KR.md)는 제출 기술내용을 중심으로 사전 특징 분석, 선행연구, timing 병목 개선, 재현 근거와 claim 한계를 관련 절에 통합한 공개 기준 문서다.

> 현재 검증 입력은 공개 데이터베이스 조건에 맞춘 **30분**이다. 24시간 이상 Holter ECG는 설계 지향점이며, 실제 24시간 정확도, 처리시간과 전력은 아직 검증하지 않았다.

## 핵심 아이디어

사전 데이터 분석을 통해 네 범주의 구분에 유효한 PNN 기반 박동 간격 규칙성, RDM 기반 박동 간 변동성 및 DSCR 기반 파형 굴곡 등의 핵심 특징을 선정하고, 이를 스파이크 발생과 막전위 기반 증거 누적으로 표현하는 뉴로모픽 구조로 구현하였다. 연속 ECG 입력을 60초 길이의 Window로 나누고 각 구간의 특징을 Snapshot 뉴런층에서 요약하며, 여러 Window에 걸쳐 반복·지속되는 장기 경향을 최종 판정에 함께 반영한다.

이러한 계층형 뉴로모픽 구조를 통해 전체 원시 ECG를 저장하지 않고도 장·단기 특징을 지속적으로 갱신하는 다중 시간 척도 저전력 스트리밍 분류 가속기 IP를 구성하였다.

![다중 시간 척도 ECG 분류 구조](figures/final_submission/알고리즘%20구성%20및%20예상결과/알고리즘%20구조도.svg)

## 구현 범위

```text
공개 digitized ECG
  → PWL 전압 자극 재구성
  → MATLAB 공칭 설계
  → LTspice AFE, S/H, ADC
  → SystemVerilog XMODEL
  → 1 kSPS signed 12-bit stream
  → SNN Pure RTL
  ├→ AXI IP, MicroBlaze
  │ → Vivado implementation, Nexys A7-100T replay
  └→ core-only ASIC wrapper (PROFILE_EN=0)
    → Cadence Genus / Conformal / Innovus / IQuantus
```

- 아날로그 모델: HPF, 3-op-amp IA, Active Twin-T 60 Hz notch, 150 Hz LPF, buffer, S/H, 12-bit ADC
- 디지털 코어: Strong Event, QRS LIF, PNN, RDM, Ectopic Evidence, DSCR, RAM, QRS MAF, RBBB-like, Snapshot/Final Membrane
- 인터페이스: AXI-Lite control/result, AXI-Stream signed 12-bit input, done/IRQ, UART result
- Vivado project: Pure RTL hierarchy용 1개, MicroBlaze 구현·replay용 1개

## 최종 결과

| 항목 | 결과 | 주장 범위 |
|---|---:|---|
| 잠금 최종 시험 | 29/36, 정확도 80.56%, Macro-F1 80.44% | 30분 public-dataset engineering result |
| 원천 record별 집계 | 16/19, 정확도 84.21% | 같은 final partition의 집계이며 별도 시험이 아님 |
| Pure RTL 구현 | 9,719 LUT, 5,038 FF, BRAM 0, DSP 0 | Artix-7 XC7A100T, Vivado 2020.2 |
| Pure RTL timing | WNS 8.184 ns | post-route timing closure |
| MicroBlaze 통합 | 12,494 LUT, 8,494 FF, 16 BRAM, 3 DSP, WNS 0.097 ns | 전체 시스템 자원 |
| FPGA 기능 정합 | class 36/36, Final Membrane 144/144 | XSim 대비 기능 등가성, 분류 정확도와 다름 |
| Exact C++ 대비 활성시간 | 1,777.6998 ms 대 36.0129 ms, 49.36배 | 단일 thread kernel 대 profiler counter 기반 FPGA core |
| 1 kSPS 연속 할당전력 | 142.0 mW | post-route activity 기반 추정, 보드 실측 아님 |
| 이상적 평균전력 | 2.991 µW | 30분마다 36.0129 ms 동작 후 완전 power-gating을 가정한 산출값 |
| GPDK045 Genus mapping | 35,188 cells, 93,585.906 µm² | GSCLIB v4.7, `syn_map` 기준; `syn_opt` 미실행 |
| GPDK045 논리 등가성 | 13 hierarchical modules PASS, diff 0, abort 0 | actual-core RTL↔mapped netlist Conformal LEC |
| GPDK045 core-only post-route | 35,663 instances, 95,321.556 µm², 421.000 × 418.190 µm | generic 45 nm exploratory block, pad/PG 제외 |
| GPDK045 post-route timing | setup WNS +2.980 ns, hold WNS −0.050 ns, clock slew 위반 86개 | 100 MHz explicit report; setup/hold·clock-rule closure 아님 |
| GPDK045 post-route power | 3.35554239 mW | setup-slow vectorless, default 0.10 activity; workload 전력·실측값 아님 |
| GPDK045 run-2 scan-free core | mapped 36,565 cells / 94,421.754 µm²; post-route 42,958 instances / 120,287.898 µm² | run-1을 대체하지 않는 functional profile; DFT insertion·scan QoR 아님 |
| Run-2 core timing | setup +2.469 ns; hold −0.008 ns, TNS −0.094 ns / 37 paths | slow-early 0.95·fast-late 1.05 engineering derate; hold·data-net transition closure 아님 |
| GPDK045 run-2 AXI block | mapped 37,293 cells / 96,548.994 µm²; post-route 43,901 instances / 123,650.100 µm² | AXI accelerator block; MicroBlaze SoC·pad·package 제외 |
| Run-2 AXI timing | setup +2.781 ns; hold −0.016 ns, TNS −0.518 ns / 107 paths | clock slew 0 @ 60 ps이지만 hold·data-net transition closure 아님 |
| Run-2 vectorless power | core 3.71626492 mW; AXI 3.69335598 mW | default PI/sequential activity 0.10 estimate; actual workload power 아님 |
| Run-2 core conditioned activity | accelerated gap2 2.02536072 mW; active-wait idle 1.91083992 mW; literal 1 kSPS 100-sample prefix 1.91084079 mW; matched delta 0.00000087 mW | seed11, mapped 6,045/6,045, `-access +rwc`, zero-delay normalized SAIF; prefix는 Snapshot/decision 아님; silicon power·energy/decision 아님; AXI는 vectorless only |
| Run-2 regression / LEC | core wrapper canonical RTL 36/36, actual raw XMODEL 4/4; core LEC 6,178, AXI LEC 6,287 points clean | AXI 36-case replay 주장이 아니며 raw XMODEL archive는 여전히 4/36; LEC는 timing/accuracy 검증이 아님 |
| Run-3 core hold/DRV closure | setup +2.470 ns; hold 0.000 ns, TNS 0 / 0 paths; data max-transition 0; clock slew 0; internal DRC 0 | 43,016 instances / 120,532.428 µm²; fixed engineering OCV 조건의 generic core block closure이며 foundry sign-off 아님 |
| Run-3 AXI hold closure | setup +2.435 ns; hold 0.000 ns, TNS 0 / 0 paths | hold는 닫혔지만 data max-transition 264 nets/1,387 terminals와 clock slew 263 pins가 남아 full physical closure 아님 |
| Run-4 AXI closure 개선 | setup +2.661 ns; hold 0.000 ns, TNS 0 / 0 paths; clock slew 0; internal DRC 0 | 43,956 instances / 123,906.258 µm²; data max-transition은 141 nets/1,149 terminals가 남아 full physical closure 아님; vectorless 3.71285384 mW |
| Run-5 AXI full closure | setup +2.703 ns; hold 0.000 ns, TNS 0 / 0 paths; data max-transition 0; clock slew 0; internal DRC 0 | 42,881 instances / 126,069.441 µm²; 50% floorplan의 area–closure tradeoff; vectorless 3.58433691 mW; foundry sign-off 아님 |
| Run-6 AXI hold guardband | setup +2.602 ns; hold +0.010 ns, TNS 0 / 0 paths; data max-transition 0; clock slew 0; internal DRC 0 | 기존 100 ps uncertainty 뒤 10 ps 잔여 slack; 44,602 instances / 131,487.003 µm²; vectorless 3.71636663 mW |

LTspice와 XMODEL의 동일 10초 ECG 비교에서는 MAE 0.6445 LSB, RMS 1.3020 LSB, 상관계수 0.999518, 지연 0표본을 기록했다. 이는 모델 간 정합이며 물리 AFE 또는 ADC 실측이 아니다.

## 평가 원칙

- 한 원천 ECG record에서 파생한 모든 30분 구간은 train, validation, final test 중 하나에만 속한다.
- 각 30분 구간은 원천 DB label과 가용한 beat/rhythm annotation을 대조하여 해당 클래스의 박동 및 리듬 증거가 충분히 포함되는지 점검했다. annotation은 데이터 구성과 품질 확인에만 사용하며 최종 RTL 입력에는 포함하지 않는다.
- 구조, 가중치와 임계값은 train/validation으로 결정한 뒤 고정했다.
- final test는 모델 선택에 사용하지 않았으며 설계 고정 후 한 번만 평가했다.
- 클래스는 서로 다른 공개 DB와 결합되어 있으므로 database–class confounding이 남는다.
- 공개 문서에서는 `AF`를 사용한다. 고정 model ID, RTL port와 과거 파일명의 `AFF`는 재현성을 위해 변경하지 않는다.

자세한 내용은 [통합 기술보고서](reports/INTEGRATED_TECHNICAL_REPORT_KR.md), [claim registry](project_registry/claim_registry.csv), [evidence map](reports/INTEGRATED_TECHNICAL_REPORT_EVIDENCE_MAP.csv)에서 확인할 수 있다.

## 저장소 안내

| 목적 | 경로 |
|---|---|
| 빠른 파일 찾기 | [START_HERE_KR.md](START_HERE_KR.md) |
| 데이터와 평가 | [docs/DATASET_AND_EVALUATION_KR.md](docs/DATASET_AND_EVALUATION_KR.md) |
| 사전 분석과 annotation | [docs/FEATURE_SELECTION_AND_ANNOTATION_KR.md](docs/FEATURE_SELECTION_AND_ANNOTATION_KR.md) |
| SNN/RTL 구조 | [docs/DIGITAL_ARCHITECTURE_KR.md](docs/DIGITAL_ARCHITECTURE_KR.md) |
| timing 병목 개선 | [verification/timing_optimization/RTL_TIMING_OPTIMIZATION_HISTORY_KR.md](verification/timing_optimization/RTL_TIMING_OPTIMIZATION_HISTORY_KR.md) |
| 하드웨어와 전력 | [docs/HARDWARE_IMPLEMENTATION_KR.md](docs/HARDWARE_IMPLEMENTATION_KR.md) |
| GPDK045 core-only flow | [design/digital/asic/gpdk45/](design/digital/asic/gpdk45/) |
| GPDK045 PPA 근거 | [verification/asic_gpdk45_core/README_KR.md](verification/asic_gpdk45_core/README_KR.md) |
| GPDK045 run-2 static evidence | [verification/asic_gpdk45_run2/README_KR.md](verification/asic_gpdk45_run2/README_KR.md) |
| GPDK045 run-3 hold closure | [verification/asic_gpdk45_hold_closure/README_KR.md](verification/asic_gpdk45_hold_closure/README_KR.md) |
| GPDK045 run-4 AXI closure 개선 | [verification/asic_gpdk45_axi_closure_run4/README_KR.md](verification/asic_gpdk45_axi_closure_run4/README_KR.md) |
| GPDK045 run-5 AXI full closure | [verification/asic_gpdk45_axi_full_closure_run5/README_KR.md](verification/asic_gpdk45_axi_full_closure_run5/README_KR.md) |
| GPDK045 run-6 AXI hold guardband | [verification/asic_gpdk45_axi_hold_guardband_run6/README_KR.md](verification/asic_gpdk45_axi_hold_guardband_run6/README_KR.md) |
| 통합 검증 | [docs/INTEGRATION_VERIFICATION_KR.md](docs/INTEGRATION_VERIFICATION_KR.md) |
| 최종 Figure | [figures/FIGURE_INDEX.md](figures/FIGURE_INDEX.md) |
| 재현 명령 | [REPRODUCIBILITY_KR.md](REPRODUCIBILITY_KR.md) |

## 중요한 검증 범위 구분

`verification/xmodel_rtl_acceptance_36case/`는 과거 고정 AFE 생성 36개 chunk와 digital replay 입력의 SHA-256 동일성, canonical cadence에서 class 36/36 및 membrane 144/144를 기록한 **compact acceptance evidence**다.

`verification/xmodel_rtl_e2e/`는 실제 full-30분 raw XMODEL accepted dump를 저장소 단독으로 다시 replay한 감사 자료다. 현재 raw dump는 4개만 보존되어 4개는 bit-exact PASS이고 나머지 32개는 재생성 환경이 필요하다. 두 근거의 범위를 혼합하지 않는다.

## 한계

Run-1 GPDK045 결과는 generic demonstration library의 historical core-only baseline이며 scan-capable cell·clock slew·hold·DRC 한계를 보존한다. Run-2는 scan-free core와 AXI-inclusive block으로 확장했지만 hold와 data-transition residual이 남았다. Run-3 core는 같은 constraint·OCV assumption에서 hold·data-transition·clock-slew·internal-DRC를 모두 0 violation으로 닫았다. Run-6 AXI는 50% floorplan에서 setup +2.602 ns, hold +0.010 ns, data max-transition 0, clock slew 0, internal DRC 0과 LEC 6,287점 clean을 달성했다. 기존 100 ps engineering uncertainty 뒤에 10 ps residual slack을 추가로 남겼지만, die area 230,032.848 µm²와 1,721-instance guardband cost를 지불했다. Slow-early 0.95와 fast-late 1.05는 foundry AOCV/POCV/LVF가 아닌 fixed engineering assumption이다. Exploratory PG는 실패했고 선택한 checkpoint는 signal-only이며 VDD/VSS가 unrouted이므로 PG/IR/EM 근거가 아니다. Run-3 core 3.72167787 mW와 run-6 AXI 3.71636663 mW는 workload 또는 실측값이 아니다. 물리 AFE PCB, ADC silicon, physical fill, foundry DRC/LVS, pad/package/fabrication, 실리콘 전력, 임상 검증과 실제 24시간 입력 검증은 수행하지 않았다.
