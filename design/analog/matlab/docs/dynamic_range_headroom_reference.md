> **이전 설계 자료** — 현재 3클래스 설계의 설명과 수치는 [2026 설계보고서](../../../../reports/INTEGRATED_TECHNICAL_REPORT_KR.md)를 기준으로 합니다. 이 문서는 당시의 코드·검증 이력을 보존합니다.

# Dynamic Range and ADC Headroom Reference

MATLAB nominal pre-validation을 통해 선택한 IA gain과 ADC range가 대표 ECG 입력에 대해 clipping 없이 충분한 headroom을 제공함을 확인하였다.
이 결과는 representative input 기준의 nominal ADC headroom reference이다.

| record_name | input_duration_s | sample_count | sampling_rate_Hz | afe_output_min_V | afe_output_max_V | adc_input_min_V | adc_input_max_V | adc_code_min | adc_code_max | adc_code_peak_to_peak | positive_rail_hit_count | negative_rail_hit_count | clipping_ratio_percent | positive_headroom_to_rail_V | negative_headroom_to_rail_V | minimum_headroom_to_rail_V | minimum_headroom_to_rail_LSB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NSR | 60 | 60000 | 1000 | -0.111193406382 | 0.385184380538 | -0.111193406382 | 0.385184380538 | 1909 | 2525 | 616 | 0 | 0 | 0 | 1.26481561946 | 1.53880659362 | 1.26481561946 | 1569.52120051 |
| CHF | 60 | 60000 | 1000 | -0.27871279025 | 0.557422001284 | -0.27871279025 | 0.557422001284 | 1701 | 2739 | 1038 | 0 | 0 | 0 | 1.09257799872 | 1.37128720975 | 1.09257799872 | 1355.78997113 |
| ARR | 60 | 60000 | 1000 | -0.630366559914 | 0.466399103006 | -0.630366559914 | 0.466399103006 | 1265 | 2626 | 1361 | 0 | 0 | 0 | 1.18360089699 | 1.01963344009 | 1.01963344009 | 1265.2724052 |
| AFF | 60 | 60000 | 1000 | -0.350374111024 | 0.326537714373 | -0.350374111024 | 0.326537714373 | 1612 | 2452 | 840 | 0 | 0 | 0 | 1.32346228563 | 1.29962588898 | 1.29962588898 | 1612.71758041 |
