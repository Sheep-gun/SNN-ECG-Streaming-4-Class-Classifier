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

## 금지되는 표현

- “24시간 정확도와 실시간 동작을 검증했다.”
- “FPGA 또는 ASIC의 실측 전력이 2.991 µW다.”
- “36/36 기능 정합이므로 정확도 100%다.”
- “물리 AFE, ADC silicon 또는 fabricated SoC를 검증했다.”
- “ASIC full timing closure, power-grid 구현 또는 sign-off를 완료했다.”
- “Clock-tree design rule과 scan-aware placement QoR까지 닫혔다.”
- “GPDK045 3.35554239 mW는 실제 ECG workload 또는 실리콘 실측 전력이다.”
- “Foundry 45 nm PDK로 tape-out 가능성을 sign-off했다.”
- “임상 진단이 가능하거나 상용 wearable보다 우수하다.”
- “세계 최초” 또는 “동일 연구가 없다.”

## 제한된 최초성 표현

“검토한 대표 선행연구 범위에서는 NSR·CHF·ARR·AF 기록 분류, Snapshot별 질환 증거의 명시적 상태화, 장시간 증거 누적, RTL/IP/FPGA 구현과 MATLAB–XMODEL–RTL 추적성을 함께 적용한 사례를 확인하지 못하였다.”

이는 체계적 문헌고찰이나 세계 최초 주장으로 확대하지 않는다.
