# 아날로그–디지털 및 FPGA 통합 검증

## 검증 계층

1. MATLAB 공칭 전달함수와 LTspice AC sweep 비교
2. 동일 10초 PWL ECG에 대한 LTspice AFE/S/H/ADC와 XMODEL code 비교
3. Python과 RTL 최종 class/membrane 비교
4. Exact C++과 RTL의 정수 연산, module trace, sample state, Snapshot 경계 비교
5. XMODEL/AFE 생성 stream과 Pure RTL replay acceptance
6. AXI/IP XSim protocol 검증
7. MicroBlaze FPGA replay와 XSim 비교
8. GPDK045 run-2 wrapper RTL의 canonical digital 36-case와 actual raw XMODEL 4-case regression
9. Scan-free mapped netlist와 selected post-route netlist의 Conformal LEC
10. Unmodified four-state 및 강제 초기화 gate/MAX-SDF 진단

## 아날로그 모델 정합

LTspice 결과는 HPF 0.481174 Hz, IA gain 200.594 V/V, 60 Hz attenuation −83.557 dB, LPF 150.211 Hz와 clipping 0을 기록했다.

동일 10초, 10,000 samples의 LTspice–XMODEL 비교 결과는 mean error +0.0221 LSB, MAE 0.6445 LSB, RMS 1.3020 LSB, correlation 0.999518, lag 0 sample이다. ±1 LSB 91.19%, ±5 LSB 98.74%, ±10 LSB 99.89%, maximum 13 LSB였다.

## 디지털 기능 정합

- Python–RTL: class 36/36, Final Membrane 144/144
- Exact C++–RTL: integer operations 793,595/793,595, module microtrace 18/18, sample state 240,000/240,000, Snapshot boundary 1,080/1,080
- Full-top RTL: 36/36 cases, each 1,800,000 accepted samples, 30 Snapshots, one final decision

## 36-case compact acceptance evidence

`verification/xmodel_rtl_acceptance_36case/`는 AFE 생성 final-test chunk와 digital replay input의 SHA-256 36/36 동일성 및 canonical `sample_gap_cycles=2`에서 class 36/36, four membranes 144/144를 기록한다. 이는 과거 고정 통합 환경에서 생성한 compact CSV와 재현 harness를 보존한 것이다.

이 evidence는 label accuracy가 100%라는 뜻이 아니다. 고정 기준 출력 재현은 36/36이고 ground-truth label accuracy는 29/36이다.

## raw full-30분 XMODEL dump 재감사

`verification/xmodel_rtl_e2e/`는 실제 raw `accepted_*.mem`을 현재 저장소의 fixed RTL로 다시 replay한 별도 감사다. 4개 보존 파일은 각 1,800,000 samples, 30 Snapshots, one decision을 만들었고 직접 통합 결과와 class 4/4, membranes 16/16 bit-exact였다.

그러나 raw dump 32개가 현재 보존되지 않아 이 패키지만으로 36개 raw XMODEL dump replay를 완결할 수 없다. compact acceptance 36/36과 raw archive 4/36을 구분한다.

## AXI/IP와 FPGA

AXI-Lite control/result register, AXI-Stream backpressure, TLAST, done과 IRQ는 XSim testbench에서 확인했다. MicroBlaze 통합 FPGA에서 36개 final-test input을 replay한 결과 UART class 36/36과 four membranes 144/144가 XSim과 일치했다.

## GPDK045 run-2 digital ASIC 검증

Scan-free `snn_ecg_asic_core_top` wrapper RTL은 regenerated canonical digital cohort 36/36과 현재 보유한 actual raw XMODEL cohort 4/4에서 expected class와 four membranes가 exact하게 일치했다. Canonical 36-case는 raw XMODEL 36-case가 아니며 actual raw archive 범위는 계속 4/36이다. AXI-inclusive profile은 별도 16-sample RTL smoke만 수행했으므로 AXI block의 36-case replay를 주장하지 않는다.

Conformal mapped-to-postroute LEC는 core 6,178 compare point와 AXI-inclusive accelerator block 6,287 compare point에서 diff·abort·unknown 0으로 PASS했다. 이는 selected scan-free mapped/post-route netlist의 논리 등가성 근거이며 timing closure, 분류 정확도, reset-aware four-state gate simulation 또는 sign-off를 뜻하지 않는다.

Unmodified four-state full raw case0 gate run은 output X를 남겼고 XPR license는 사용할 수 없었다. Testbench-only forced two-state initialization의 mapped seeds 11/22/33은 6,045/6,045 sequential coverage와 release X 0에서 exact하게 일치했다. MAX-SDF postroute seed11 pilot은 6,044/6,044 coverage에서 일치했지만 timing check를 비활성화했고 88건의 `SDFNCAP` port-alias warning을 남겼다. 두 결과는 유한 seed의 조건부 initialization sensitivity이며 일반 GLS·reset/power-up·SDF timing regression 근거가 아니다.

같은 seed11-conditioned mapped-gate 경계에서 `-access +rwc`, zero-delay activity를 normalized SAIF로 분석했다. Accelerated full gap2 total은 2.02536072 mW, matched 0.1 s active-wait idle은 1.91083992 mW, literal 1 kSPS 100-sample prefix는 1.91084079 mW이고 literal-minus-idle total delta는 0.00000087 mW다. Fully-X/Z entry를 보존하고 unannotated default 0을 적용한 parse/annotation status PASS는 numeric annotation coverage PASS가 아니다. Prefix는 Snapshot/decision에 도달하지 않으며 이 결과는 silicon power나 energy/decision 검증이 아니다. AXI activity power는 수행하지 않았다.

## 해석 경계

- SHA-256 동일성은 byte-level input integrity다.
- bit-exact equivalence는 implementation fidelity다.
- label accuracy는 별도의 29/36이다.
- model-based AFE/XMODEL 결과는 physical analog measurement가 아니다.
- Post-route LEC PASS는 hold·data-transition closure 또는 foundry sign-off가 아니다.
- Forced initialization gate/MAX-SDF 결과는 unmodified four-state robustness가 아니다.
