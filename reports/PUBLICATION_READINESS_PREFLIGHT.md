# Public repository preflight

## 포함

- 고정 AFE–ADC와 Digital RTL source
- Python과 Exact C++ equivalent model
- Pure RTL 및 MicroBlaze canonical Vivado project 각 1개
- 재현 script, compact acceptance, raw-dump audit와 final figures
- GPDK045 run-1 historical core baseline과 run-2 scan-free core·AXI-inclusive accelerator의 sanitize된 mapping/LEC/post-route/PPA·regression·실패/조건부 실험 근거
- claim, evidence, upstream commit와 unresolved registry

## 제외

- 참가신청서의 개인정보, 서명과 직인
- raw PhysioNet database
- temporary Vivado packaging, IP catalog와 cache project
- 중복 upstream checkout과 중간 screenshot
- GPDK045 Liberty·LEF·QRC·cell model·CDL·GDS, Cadence work database와 접속·license 정보

## 공개 claim boundary

30분 engineering validation, FPGA implementation, model-level AFE–RTL integration과 generic GPDK045 run-1 historical core baseline 및 run-2 scan-free core·AXI-inclusive accelerator의 exploratory post-route PPA까지 공개한다. Run-2 core/AXI는 setup WNS +2.469/+2.781 ns, clock-tree slew 위반 0 @ 60 ps와 internal DRC 0을 기록했지만 hold WNS −0.008/−0.016 ns와 data-net max-transition 위반이 남아 있다. Fixed global engineering derate, vectorless power, failed PG attempt, forced-initialization gate 및 timing check를 끈 single-seed MAX-SDF sensitivity는 각각 foundry variation model, workload/silicon power, 구현된 PG/IR, 일반 GLS·reset/power-up·SDF timing proof로 확대하지 않는다. Core seed11-conditioned activity windows는 mapped 6,045/6,045, `-access +rwc`, zero delay의 normalized SAIF estimate이며 parse PASS가 numeric coverage PASS를 뜻하지 않는다. Prefix는 Snapshot/decision에 도달하지 않고 matched delta는 energy/decision이 아니며 AXI는 vectorless only다. 24시간 성능, physical AFE/ADC, ASIC physical timing closure·성공한 PG/IR·physical fill·complete antenna/foundry DRC/LVS·DFT·pad/package/fabrication, reset-aware decision activity·silicon power와 clinical validation은 완료 결과로 주장하지 않는다.

최종 검사는 다음 명령으로 수행한다.

```text
python tools/check_clean_workspace.py
python tools/check_integrated_technical_report.py
python tools/check_integrated_repository.py
git diff --check
```
