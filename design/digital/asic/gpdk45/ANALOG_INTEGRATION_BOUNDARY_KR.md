# 아날로그부 후속 통합 경계

현재 Cadence 결과는 디지털 분류 코어와 project-owned AXI digital wrapper만 다룬다. AFE·S/H·ADC의 transistor/layout 구현은 아날로그 팀 범위이며, Virtuoso·공식 mixed-signal PDK가 없는 현재 환경에서는 physical analog integration을 완료했다고 주장하지 않는다.

## 고정 digital handoff

- Sample rate: 1 kSPS
- Data: signed 12-bit two's-complement ECG code
- Functional acceptance: `sample_valid && sample_ready`
- Control: synchronous `rst`, one-cycle `start`
- Completion: one-cycle `final_valid`, 2-bit class와 네 32-bit Final Membrane
- Canonical workload: 60,000 samples/snapshot × 30 snapshots, accepted-sample 사이 `gap=2`

ASIC core-only top의 직접 경계는 `snn_ecg_asic_core_top`이다. AXI profile의 AXI-Lite는 host control/result, AXI-Stream은 digitized sample ingress를 나타내며 analog macro 자체를 포함하지 않는다.

## 아날로그 팀에서 받아야 할 자료

1. ADC code transfer와 signed-code 정의
2. `sample_valid` 생성 clock/domain, jitter와 latency 범위
3. output drive, input load, rise/fall, setup/hold 또는 asynchronous handoff 조건
4. AFE/ADC supply·ground·reference와 digital supply 사이 power-domain 정의
5. reset/start-up/settling 및 invalid-sample 표시 규약
6. behavioral XMODEL/Verilog-A와 대표 accepted-code dump
7. hard macro로 통합할 경우 timing Liberty, abstract LEF, GDS/CDL, antenna/ESD·DRC/LVS 근거

## 실제 chip 통합 전 필수 설계

- ADC clock이 digital core clock과 다르면 CDC synchronizer 또는 asynchronous FIFO
- pad/ESD, level shifter, isolation, analog/digital power separation
- clock/reset distribution과 reference/bias start-up sequence
- substrate/noise coupling, floorplan keep-out와 analog routing 제약
- full-chip PG/IR/EM, pad ring, package pinout
- mixed-signal co-simulation과 foundry DRC/LVS/ERC/antenna signoff

현재 GPDK045 결과에 위 항목의 면적·전력·timing을 합산하지 않는다. 나중에 아날로그 팀이 physical abstract와 timing/power boundary를 제공하면 digital block를 hard macro 주변의 full-chip floorplan에 배치하고 별도 full-chip PPA/signoff 범위로 확장한다.
