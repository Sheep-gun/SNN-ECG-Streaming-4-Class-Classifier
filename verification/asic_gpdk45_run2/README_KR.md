# GPDK045 run-2 parser staging

이 디렉터리는 raw run tree의 명시된 report/result만 fail-closed 방식으로 파싱한 public-builder 입력이다.
수치는 run_manifest.json과 각 CSV/TXT에 있으며 raw netlist, PDK, DEF/SDF/SPEF, SAIF/SHM은 포함하지 않는다.

core_candidate=snn_ecg_asic_core_top_iter1
axi_candidate=snn_ecg_axi_asic_top_cts50_drv2
canonical_regression_status=PASS
raw4_regression_status=PASS
core_lec_status=PASS
axi_lec_status=PASS
pg_status=FAILED

경계: short gate/SDF pilot는 full regression이 아니며 literal prefix power는 snapshot/decision power가 아니다.
