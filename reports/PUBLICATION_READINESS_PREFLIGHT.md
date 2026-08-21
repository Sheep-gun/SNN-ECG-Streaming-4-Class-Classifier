# Public repository preflight

## 포함

- 고정 AFE–ADC와 Digital RTL source
- Python과 Exact C++ equivalent model
- Pure RTL 및 MicroBlaze canonical Vivado project 각 1개
- 재현 script, compact acceptance, raw-dump audit와 final figures
- GPDK045 run-1 historical baseline, run-2 scan-free core·AXI, run-3 core closure, run-4 AXI 개선과 run-5 AXI full-closure의 sanitize된 mapping/LEC/post-route/PPA·regression·실패/조건부 실험 근거
- claim, evidence, upstream commit와 unresolved registry

## 제외

- 참가신청서의 개인정보, 서명과 직인
- raw PhysioNet database
- temporary Vivado packaging, IP catalog와 cache project
- 중복 upstream checkout과 중간 screenshot
- GPDK045 Liberty·LEF·QRC·cell model·CDL·GDS, Cadence work database와 접속·license 정보

## 공개 claim boundary

30분 engineering validation, FPGA implementation, model-level AFE–RTL integration과 generic GPDK045 run-5까지 공개한다. Run-3 core와 run-5 AXI는 stated engineering assumptions에서 setup·hold·data-transition·clock-slew·internal-DRC 0을 기록했다. Run-5 AXI는 50% floorplan과 더 큰 die를 사용한 area–closure tradeoff다. Fixed global engineering derate, vectorless power, failed PG attempt와 forced gate/SDF sensitivity는 각각 foundry variation model, workload/silicon power, 구현된 PG/IR 또는 일반 GLS proof로 확대하지 않는다. 24시간 성능, physical AFE/ADC, successful PG/IR, physical fill, complete antenna/foundry DRC/LVS, DFT, pad/package/fabrication, reset-aware decision activity, silicon power와 clinical validation은 완료 결과로 주장하지 않는다.

최종 검사는 다음 명령으로 수행한다.

```text
python tools/check_clean_workspace.py
python tools/check_integrated_technical_report.py
python tools/check_integrated_repository.py
git diff --check
```
