# Virtuoso ADC → Digital E2E 검증

이 디렉터리는 아날로그 팀의 실제 ADC code dump를 디지털 ASIC core/AXI RTL에 연결하는 재현 하네스와 실행 증거를 모은다.

- 사용법·계약: `design/digital/asic/gpdk45/axi_profile/VIRTUOSO_E2E_HARNESS_KR.md`
- 입력 정규화기: `tools/verification/prepare_virtuoso_adc_dump.py`
- 실행기: `tools/verification/run_virtuoso_adc_e2e.py`
- RTL/Xcelium file list: `design/digital/asic/gpdk45/axi_profile/scripts/xcelium_virtuoso_e2e_rtl.f`
- 대표 manifest: `design/digital/asic/gpdk45/axi_profile/manifests/representative_xmodel4.csv`
- 결과: `results/`

`representative_xmodel4` 결과는 저장소에 이미 있던 실제 XMODEL accepted dump 4개로 하네스와 digital core/AXI 경로를 검증한 것이다. 팀원의 Virtuoso transistor-level ADC 결과는 아직 별도 handoff로 받아 같은 실행기에 넣어야 한다. 두 결과를 혼합해 표현하지 않는다.

## 현재 실행 결과

2026-08-26 Vivado Simulator 2020.2에서 대표 XMODEL 4개를 각각 1,800,000 samples, gap 2로 replay했다.

| case | expected | AXI | direct core | final membrane NSR/CHF/ARR/AFF | accepted/consumed |
|---|---:|---:|---:|---:|---:|
| AFF_afdb_06995_chunk01 | 3 | 3 | 3 | 0/0/0/30 | 1,800,000/1,800,000 |
| ARR_mitdb_102_chunk00 | 2 | 2 | 2 | 0/3/27/0 | 1,800,000/1,800,000 |
| CHF_chfdb_chf06_chunk06 | 1 | 1 | 1 | 0/33/0/7 | 1,800,000/1,800,000 |
| NSR_nsrdb_16272_chunk03 | 0 | 0 | 0 | 17/0/6/7 | 1,800,000/1,800,000 |

결과 파일:

- `results/representative_xmodel4/results.csv`
- `results/representative_xmodel4/input_provenance.csv`
- `results/representative_xmodel4/summary.json`
- `results/representative_xmodel4/simulation.log`

Cadence Xcelium 23.09에서도 `results/xcelium23_case9_crosscheck/`의 AFF case 9를 교차 실행해 1/1 PASS했다. 이는 Xcelium file-list·testbench 호환성 확인이며, 전체 기능 기준은 위 XSim 4-case 결과다.

네 입력은 canonical signed `.mem`이라 sample 수·encoding·SHA-256은 검증했지만 timestamp cadence는 검사할 수 없다. 실제 Virtuoso CSV 실행에서는 변환기가 `time_sec`의 1 ms 간격까지 확인한다.

Elaboration에는 기존 locked core의 abandoned feature stub 경계에 있는 8-bit→4-bit port-width warning 4개와 사용하지 않는 `strong_event` port warning 1개가 남는다. 새 하네스·AXI 경계의 compile/elaboration error, runtime FAIL, timeout 또는 sample mismatch는 없다.
