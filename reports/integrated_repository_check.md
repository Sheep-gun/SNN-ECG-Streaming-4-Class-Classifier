# 통합 저장소 검사

## 결과: PASS

- 기존 run-1·run-2 필수 설계·검증 artifact, run-3 core closure, run-4 AXI improvement와 run-5 AXI full-closure public evidence package를 확인하고 repository artifact manifest와 package checksum을 재검증
- 최종 제출용 SVG 13개와 GPDK045 routed-core GIF를 Figure index에 연결
- 분류 성능, FPGA 자원·timing, XMODEL–RTL·FPGA 정합과 GPDK045 mapping·LEC·PPA 근거 확인
- 30분 검증, 24시간 지향점, model-based analog와 조건부 전력 claim 경계 확인
- 실제 XMODEL ADC dump 4/36과 compact 36-case acceptance evidence를 명확히 구분
- GPDK045 run-1 historical baseline과 run-2 scan-free core·AXI block을 구분
- Run-2 explicit setup WNS와 residual hold·data-net transition을 함께 기록하고 physical timing closure·sign-off와 구분
- Run-3 core hold/DRV closure와 AXI hold closure를 확인하고 AXI transition·clock-slew residual을 full closure와 구분
- Run-4 AXI hold·clock·DRC closure와 PPA 개선을 확인하고 residual data-transition을 full closure와 구분
- Run-5 AXI setup·hold·data-transition·clock·DRC 0 violation을 확인하고 generic block closure를 foundry sign-off와 구분
- Run-2 canonical digital 36/36과 actual raw XMODEL 4/4, core/AXI post-route LEC를 별도 범위로 기록
- Failed PG attempt과 testbench-conditioned gate/SDF sensitivity를 구현 완료나 일반 GLS로 확대하지 않음
- Core conditioned activity 세 window와 matched delta를 검증하고 Snapshot/decision·numeric coverage·silicon·energy/decision 경계를 유지; AXI vectorless only

최종 repository artifact manifest와 run-2/run-3/run-4/run-5 evidence-package checksum을 재생성·검증했으며, 통합 기술보고서와 저장소 fail-closed 검사를 통과했다.
