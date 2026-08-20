# 실제 실행 script snapshot

이 폴더는 2026-08-20 원격 실행에서 사용한 project-owned wrapper, SDC, testbench와 Tcl의 byte-exact snapshot이다. 각 hash는 [`../executed_flow_sha256.csv`](../executed_flow_sha256.csv)에 기록한다. PDK·Cadence DB·접속정보는 포함하지 않는다.

이 snapshot은 성공 경로만 정리한 재현 script가 아니라 **실제로 실행된 상태**를 보존한다.

- `run_genus.tcl`은 `syn_map`을 완료한 뒤 `syn_opt -logical`에서 limited Genus license 오류로 중단됐다. PPA netlist는 Genus가 생성한 `fv_map.v.gz`를 복구한 것이며, private recovered mapped netlist와 byte-identical함을 hash로 확인했다.
- 실제 Conformal 실행은 자동 생성된 RTL→`fv_map` dofile 한 단계다. 13/13 hierarchical module이 equivalent였고 NEQ/abort는 0이었다.
- `run_innovus.tcl`은 placement·CTS·signal route와 IQuantus high extraction까지 진행한 뒤 Non-OCV 분석 구성에서 post-route optimization이 중단됐다.
- `report_routed_checkpoint.tcl`로 pre-extract routed checkpoint를 복구해 IQuantus high extraction을 다시 수행했다. `timeDesign`은 같은 Non-OCV 제한으로 실패했지만, 명시적 setup/hold `report_timing`, area, vectorless power, SDF와 두 SPEF export는 완료됐다.
- Historical SDF는 high-performance export의 SDF-808 경고가 있었고 back-annotation GLS를 실행하지 않았다. 현재 script는 future export에 `-recompute_delay_calc`를 추가했지만 아직 재실행하지 않았다.
- `export_layout.tcl`은 최종 공개 GIF를 생성한 성공본이다.

현재 [`../../../design/digital/asic/gpdk45/`](../../../design/digital/asic/gpdk45/) script와 SDC는 위 실패를 반영해 `syn_opt`, post-route optimization과 `timeDesign`을 opt-in으로 만들고, 실패 시 routed baseline을 재추출하며 clock transition을 명시하도록 개선했다. 따라서 현재 파일과 이 historical snapshot의 hash가 다른 것은 의도적이며, 개선본 full-flow는 아직 재실행하지 않았다.
