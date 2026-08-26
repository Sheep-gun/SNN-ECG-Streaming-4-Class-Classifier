# ADC-디지털 E2E 하네스 실행 결과

- 상태: **PASS**
- 시뮬레이터: `xsim`
- 입력 manifest: `representative_xmodel4.csv`
- 검증 case: 4/4 PASS
- case당 입력: 1,800,000 samples
- 검사 경로: 같은 ADC code를 direct core와 AXI4-Stream wrapper에 동시 입력
- 판정: 두 경로의 class, 4개 membrane, AXI accepted/consumed가 모두 일치

이 결과는 입력 파일에 기록된 ADC code부터 디지털 RTL 출력까지의 검증이다. Virtuoso 회로가 실제로 생성한 CSV를 사용한 경우에만 아날로그 회로까지 포함한 ETE 증거가 된다.
