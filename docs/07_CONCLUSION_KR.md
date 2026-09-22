# 결론 및 제언 · 참고문헌

[설계보고서 PDF](../reports/ECG_Design_Report_2026.pdf)

<!-- report:p13:id113 -->
### 6) 결론 및 제언

<!-- report:p13:id114 -->
웨어러블 ECG 연구는 기기 안에서 이상을 판단해 저장과 전송 부담을 줄이는 방향으로 발전하고 있다. Bauer 등은 이벤트 기반 뉴로모픽 이상 검출[[4]](../reports/INTEGRATED_TECHNICAL_REPORT_KR.md#ref-4), Chu 등은 스파이크 구동 SNN[[5]](../reports/INTEGRATED_TECHNICAL_REPORT_KR.md#ref-5), Bhanushali 등은 ADC와 분류 회로의 칩 통합[[6]](../reports/INTEGRATED_TECHNICAL_REPORT_KR.md#ref-6), Busia 등은 저전력 마이크로컨트롤러 기반 Transformer[[7]](../reports/INTEGRATED_TECHNICAL_REPORT_KR.md#ref-7)로 기기 내 분석의 가능성을 제시하였다.

<!-- report:p13:id115 -->
본 작품은 이러한 흐름에서 Holter 방식의 장시간 관찰에서 반복되는 특징을 제한된 저장 공간에 남기는 데 초점을 맞추었다. AFE–ADC 입력에서 검출한 박동과 파형 특징을 Snapshot으로 요약하고 Final 막전위에 누적해, 전체 원시 파형을 보관하지 않고 장기 리듬을 판단하도록 하였다.

<!-- report:p13:id116 -->
전용 ASIC에서는 이 처리 방식에 맞춰 연산 경로를 재사용하고 저장 폭과 클록 공급 시점을 정하였다. 뉴로모픽 특징 추출, 계층적 증거 누적과 이벤트 기반 클록 게이팅을 하나의 장시간 분석 구조로 연결한 점이 본 작품의 기여이다.

<!-- report:p13:id117 -->
최종 시험 96건에서 정확도 94.79%와 macro-F1 94.78%를 기록하고, AXI 및 배선 지연 반영 검증에서도 계산 결과의 일치를 확인하였다. 평균 전력은 아날로그부 약 0.256 mW, 대표 30분 입력을 처리한 디지털부 약 1.366 mW로 추정되어 장시간 ECG 분석용 IP의 구현 기반을 마련하였다.

<!-- report:p13:id118 -->
현재 모델의 장시간 적용 가능성을 살피기 위해 24시간 ECG 9건을 예비 평가하였다. NSR 우세 3건은 NSR 2건과 OTHER 1건으로, AF 우세 3건은 모두 AF로 예측되었다. OTHER 혼합 3건은 NSR, AF, OTHER로 각각 1건씩 예측되어, 혼합 리듬 기록의 판정 기준과 누적 방식에 대한 추가 검토가 필요하다.

<!-- report:p13:id119 -->
이를 바탕으로 더 많은 환자의 24시간 이상 ECG 데이터를 확보하고, 본 구조의 분류 가중치와 누적 방식을 장시간 입력에 맞춰 재튜닝한 뒤 독립된 기록에서 성능을 검증하고자 한다. 구간별 판정 시각과 이상이 의심되는 원시 파형을 선택적으로 보존하고, 실제 착용 환경에서 짧은 이상과 움직임 잡음에 대한 검증을 보완하여 의료진의 판독을 돕는 저전력 ECG 패치용 IP로 발전시키고자 한다.

<!-- report:p13:id120 -->
### 7) 참고문헌

<!-- report:p13:id121 -->
<a id="ref-1"></a>

[1] M. Zihlmann et al., “Convolutional Recurrent Neural Networks for Electrocardiogram Classification,” CinC, vol. 44, pp. 1–4, 2017. DOI: 10.22489/CinC.2017.070-060.

<!-- report:p13:id122 -->
<a id="ref-2"></a>

[2] G. D. Clifford et al., “AF Classification from a Short Single Lead ECG Recording: The PhysioNet/Computing in Cardiology Challenge 2017,” CinC, 2017. DOI: 10.22489/CinC.2017.065-469.

<!-- report:p13:id123 -->
<a id="ref-3"></a>

[3] PhysioNet, Long-Term AF Database v1.0.0. DOI: 10.13026/C2QG6Q.

<!-- report:p13:id124 -->
<a id="ref-4"></a>

[4] F. C. Bauer et al., “Real-Time Ultra-Low Power ECG Anomaly Detection Using an Event-Driven Neuromorphic Processor,” IEEE TBCAS, 2019. DOI: 10.1109/TBCAS.2019.2953001.

<!-- report:p13:id125 -->
<a id="ref-5"></a>

[5] H. Chu et al., “A Neuromorphic Processing System With Spike-Driven SNN Processor for Wearable ECG Classification,” IEEE TBCAS, vol. 16, no. 4, pp. 511–523, 2022. DOI: 10.1109/TBCAS.2022.3189364.

<!-- report:p13:id126 -->
<a id="ref-6"></a>

[6] S. P. Bhanushali et al., “Fully Integrated Mixed-Signal Classifier for Cardiovascular Health Monitoring,” IEEE BioCAS, 2023. DOI: 10.1109/BioCAS58349.2023.10388918.

<!-- report:p13:id127 -->
<a id="ref-7"></a>

[7] P. Busia et al., “A Noisy Beat is Worth 16 Words: a Tiny Transformer for Low-Power Arrhythmia Classification on Microcontrollers,” 2024. arXiv:2402.10748v1.
