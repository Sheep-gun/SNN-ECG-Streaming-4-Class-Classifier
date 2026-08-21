# 한계와 claim 경계

## 검증 완료

- strict source-record-wise locked 30분 final test
- 29/36 accuracy 80.56%, Macro-F1 80.44%
- MATLAB, LTspice와 XMODEL model-level AFE/ADC 정합
- Python, Exact C++, RTL/XSim 기능 정합
- Pure RTL and MicroBlaze post-route timing closure
- MicroBlaze FPGA replay class 36/36, membranes 144/144
- profiler counter 기반 FPGA core active time와 activity-based power estimate
- GPDK045 core-only wrapper reduced-parameter synthetic 16-sample Xcelium smoke PASS; default workload·36-case wrapper regression 아님
- GPDK045 Genus `syn_map`, actual-core Conformal LEC 13-module PASS, Innovus signal post-route와 IQuantus extraction
- 100 MHz explicit extracted setup WNS +2.980 ns; hold WNS −0.050 ns와 clock slew 위반 86개가 남아 physical timing closure는 미달성
- Run-2 scan-free core/AXI mapping, core wrapper canonical RTL 36/36·actual raw XMODEL 4/4, post-route LEC core 6,178·AXI 6,287 points diff/abort/unknown 0; AXI 36-case replay 주장은 아님
- Run-2 core setup +2.469 ns·AXI setup +2.781 ns; clock slew 0 @ 60 ps와 internal DRC 0
- Run-3 core setup +2.470 ns, hold WNS/TNS/path 0, data max-transition 0, clock slew 0, internal DRC 0; mapped-to-postroute LEC 6,178 points clean
- Run-3 AXI setup +2.435 ns와 hold WNS/TNS/path 0; mapped-to-postroute LEC 6,287 points clean
- Run-4 AXI setup +2.661 ns, hold WNS/TNS/path 0, clock slew 0, internal DRC 0; mapped-to-postroute LEC 6,287 points clean
- Run-5 AXI setup +2.703 ns, hold WNS/TNS/path 0, data max-transition 0, clock slew 0, internal DRC 0; mapped-to-postroute LEC 6,287 points clean
- Run-2 core seed11-conditioned activity windows: accelerated gap2 2.02536072 mW, active-wait idle 1.91083992 mW, literal 1 kSPS 100-sample prefix 1.91084079 mW, matched total delta 0.00000087 mW

## 조건부 또는 미완료

- 24시간 이상 Holter: 설계 지향점이며 실제 accuracy/time/power 미검증
- XMODEL raw full-30분 archive: 4/36만 현재 저장소에 보존
- 2.991 µW: 완전 power-gating을 가정한 산출값
- GPDK045 power 3.35554239 mW: default 0.10 activity의 vectorless post-route estimate, workload 전력·실측값 아님
- VDD/VSS 배선, power grid, IR drop, DFT, pad, package: 미수행
- Innovus internal route DRC 1건, hold WNS −0.050 ns: 미해소
- Historical `SDFFQX1` 995개와 undefined scan 10.70% flops: placement/timing QoR 한계
- Clock slew 86건, incomplete antenna data, physical-only cell·metal fill 미삽입: 미해소
- foundry DRC/LVS sign-off, fabricated silicon: 미수행
- Run-2 core hold −0.008 ns/TNS −0.094 ns/37 paths과 AXI hold −0.016 ns/TNS −0.518 ns/107 paths: historical baseline이며 run-3에서 0으로 보정
- Run-3 AXI data max-transition 264 nets/1,387 terminals와 clock slew 263 pins: historical 결과
- Run-4 AXI data max-transition 141 nets/1,149 terminals, worst −0.821 ns: 개선됐지만 미해소; AXI full physical closure 아님
- Run-5는 50% floorplan과 230,032.848 µm² die area를 사용한 area–closure tradeoff; block-level engineering closure이지 foundry sign-off 아님
- Slow-early 0.95·fast-late 1.05 derate: fixed engineering assumption이며 foundry AOCV/POCV/LVF 아님
- Exploratory PG: 171 connectivity/715 geometry violation으로 실패; selected core/AXI checkpoint는 signal-only·VDD/VSS unrouted이며 PG/IR/EM 구현 아님
- Unmodified four-state gate run: X; forced two-state seed와 timing check를 끈 single-seed MAX-SDF pilot은 conditional sampled sensitivity로만 해석
- Run-2 activity: mapped gate 6,045/6,045, `-access +rwc`, zero-delay normalized SAIF의 seed-conditioned estimate; fully-X/Z 보존·unannotated default 0; parse PASS는 numeric annotation coverage PASS 아님
- Run-2 prefix activity: Snapshot/decision 미도달; matched delta는 silicon power·energy/decision 아님; AXI는 vectorless only
- physical AFE PCB, ADC silicon: 미수행
- clinical validation와 medical-device certification: 미수행
- database–class confounding: 해소되지 않음

## 허용되는 표현

- “30분 public-dataset 조건에서 4-class 분류를 검증했다.”
- “24시간 이상 Holter ECG를 위한 streaming 확장을 지향한다.”
- “Pure RTL 구현에서 BRAM 0, DSP 0을 기록했다.”
- “FPGA 결과는 XSim 기준과 36/36 기능 정합했다.”
- “이상적 완전 power-gating 조건에서 2.991 µW로 산출된다.”
- “Generic GPDK045 GSCLIB v4.7에서 digital core-only exploratory post-route PPA를 수행했다.”
- “100 MHz explicit setup WNS는 +2.980 ns지만 hold WNS −0.050 ns와 clock slew 위반 86개가 남아 physical timing closure는 아니다.”
- “3.35554239 mW는 default 0.10 activity의 vectorless post-route 추정치다.”
- “Run-2 scan-free core와 AXI block에서 setup WNS는 양수였지만 hold·data-net transition closure는 미달성이다.”
- “Run-3 core는 stated engineering OCV에서 hold·data-transition·clock-slew·internal-DRC를 0 violation으로 닫았다.”
- “Run-3 AXI block은 hold를 닫았지만 data-transition과 clock-slew가 남아 full physical closure는 아니다.”
- “Run-4 AXI block은 hold·clock-slew·internal-DRC를 닫았지만 data-transition 141 nets/1,149 terminals가 남아 full physical closure는 아니다.”
- “Run-5 AXI block은 stated engineering checks에서 setup·hold·data-transition·clock-slew·internal-DRC를 닫았지만 PG·fill·foundry sign-off는 포함하지 않는다.”
- “Canonical digital 36/36과 actual raw XMODEL 4/4를 별도 cohort로 재현했다.”
- “Forced two-state gate 결과와 timing check를 끈 single-seed MAX-SDF pilot은 조건부 초기화 민감도 실험이다.”
- “Run-2 core의 seed11-conditioned activity 분석에서 accelerated gap2 total은 2.02536072 mW였다.”
- “Literal 1 kSPS 100-sample prefix와 active-wait idle의 matched total delta는 0.00000087 mW이며 energy/decision이 아니다.”

## 금지되는 표현

- “24시간 정확도와 실시간 동작을 검증했다.”
- “FPGA 또는 ASIC의 실측 전력이 2.991 µW다.”
- “36/36 기능 정합이므로 정확도 100%다.”
- “물리 AFE, ADC silicon 또는 fabricated SoC를 검증했다.”
- “ASIC full timing closure, power-grid 구현 또는 sign-off를 완료했다.”
- “Clock-tree design rule과 scan-aware placement QoR까지 닫혔다.”
- “GPDK045 3.35554239 mW는 실제 ECG workload 또는 실리콘 실측 전력이다.”
- “Foundry 45 nm PDK로 tape-out 가능성을 sign-off했다.”
- “Slow-early 0.95·fast-late 1.05 engineering derate는 foundry-characterized AOCV/POCV signoff model이다.”
- “Exploratory PG를 구현하고 IR/EM을 검증했다.”
- “Forced two-state seed PASS는 unmodified GLS, power-up 또는 reset robustness 증명이다.”
- “Raw XMODEL 36-case를 재실행했다.”
- “2.02536072 mW는 unmodified workload, AXI 또는 silicon 실측 전력이다.”
- “Normalized SAIF parse PASS가 numeric annotation coverage PASS를 뜻한다.”
- “100-sample prefix 결과로 Snapshot·decision 전력 또는 energy/decision을 검증했다.”
- “임상 진단이 가능하거나 상용 wearable보다 우수하다.”
- “세계 최초” 또는 “동일 연구가 없다.”

## 제한된 최초성 표현

“검토한 대표 선행연구 범위에서는 NSR·CHF·ARR·AF 기록 분류, Snapshot별 질환 증거의 명시적 상태화, 장시간 증거 누적, RTL/IP/FPGA 구현과 MATLAB–XMODEL–RTL 추적성을 함께 적용한 사례를 확인하지 못하였다.”

이는 체계적 문헌고찰이나 세계 최초 주장으로 확대하지 않는다.
