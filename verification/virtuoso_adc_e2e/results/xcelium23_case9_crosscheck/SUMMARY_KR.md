# Xcelium 23.09 교차 실행

- 상태: **PASS**
- source commit: `0972651d6a04a754a325512b60175ca528492a13`
- simulator: Xcelium `23.09-s013`
- 범위: 대표 AFF case 9 한 개, 1,800,000 samples
- 결과: expected/AXI/direct-core class `3/3/3`
- membrane NSR/CHF/ARR/AFF: expected/AXI/direct-core 모두 `0/0/0/30`
- AXI accepted/consumed: `1,800,000/1,800,000`
- process status: 0, `VIRTUOSO_AXI_E2E_PASS`

이 실행은 Xcelium에서 RTL file list, plusarg manifest 진입점과 core/AXI 동시 replay가 동작하는지 교차 확인한 것이다. 4-case 전체 기능 근거는 `../representative_xmodel4/`의 XSim 4/4 결과이며, 실제 Virtuoso transistor-level ADC CSV 검증은 아직 아니다.

서버에는 Python 3이 없어 Python 자동 실행기 대신 testbench의 `+MANIFEST`/`+RESULT` 진입점을 사용했다. 최초 `-sv` 누락 명령은 `$fatal`을 Verilog-2001에서 인식하지 못해 elaboration 실패했고 증거에서 제외했다. 최종 실행은 `-sv`를 명시해 PASS했으며 재현 문서와 Python Xrun runner에도 이 옵션을 고정했다.

원본 console log와 result CSV는 로컬 private archive로 회수하고 SHA-256을 확인했다. Git에는 식별정보를 제거한 excerpt와 결과만 보존했으며, 임시 repository·입력·Xcelium work database·결과를 포함한 원격 작업 폴더는 회수 후 삭제되어 `REMOTE_CLEANUP_PASS`를 확인했다.
