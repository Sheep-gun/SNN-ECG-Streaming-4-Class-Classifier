# 보고서와 근거 연결

보고서 문장별 claim과 artifact는 `reports/INTEGRATED_TECHNICAL_REPORT_EVIDENCE_MAP.csv`에서 관리한다. 수치의 canonical source는 `project_registry/global_metrics.yaml`, 주장 범위는 `project_registry/claim_registry.csv`, 미완료 항목은 `project_registry/unresolved_artifacts.csv`를 따른다.

Figure의 출처와 용도는 `figures/FIGURE_INDEX.md`, upstream commit은 `project_registry/upstream_commits.yaml`에 기록한다. GPDK045 run-1 historical PPA와 run-2 scan-free core·AXI PPA/verification은 각각 `tables/asic_gpdk45_ppa.csv`, `tables/asic_gpdk45_run2_ppa.csv`, `tables/asic_gpdk45_run2_verification.csv`에서 구분한다. Run-2 core conditioned activity의 primary public summary는 `verification/asic_gpdk45_run2/power/activity_power_summary.csv`이며 AXI activity 결과로 확대하지 않는다.
