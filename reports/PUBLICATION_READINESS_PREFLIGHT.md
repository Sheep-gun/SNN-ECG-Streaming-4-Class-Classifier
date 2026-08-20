# Public repository preflight

## 포함

- 고정 AFE–ADC와 Digital RTL source
- Python과 Exact C++ equivalent model
- Pure RTL 및 MicroBlaze canonical Vivado project 각 1개
- 재현 script, compact acceptance, raw-dump audit와 final figures
- GPDK045 core-only wrapper·Cadence flow script와 sanitize된 mapping/LEC/post-route/PPA 근거
- claim, evidence, upstream commit와 unresolved registry

## 제외

- 참가신청서의 개인정보, 서명과 직인
- raw PhysioNet database
- temporary Vivado packaging, IP catalog와 cache project
- 중복 upstream checkout과 중간 screenshot
- GPDK045 Liberty·LEF·QRC·cell model·CDL·GDS, Cadence work database와 접속·license 정보

## 공개 claim boundary

30분 engineering validation, FPGA implementation, model-level AFE–RTL integration과 generic GPDK045 digital core-only exploratory post-route PPA까지 공개한다. ASIC 결과에는 hold WNS −0.050 ns, clock slew 위반 86개, undefined scan 10.70% flops, VDD/VSS 미배선, physical fill 미삽입과 internal route DRC 1건이 남아 있다. 24시간 성능, physical AFE/ADC, ASIC physical timing closure·scan-aware QoR·PG/IR·complete antenna/foundry DRC/LVS·pad/package/fabrication, workload/silicon power와 clinical validation은 완료 결과로 주장하지 않는다.

최종 검사는 다음 명령으로 수행한다.

```text
python tools/check_clean_workspace.py
python tools/check_integrated_technical_report.py
python tools/check_integrated_repository.py
git diff --check
```
