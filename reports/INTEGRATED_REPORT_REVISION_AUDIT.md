# 통합 보고서 개정 감사

## 2026-07-24 본문 통합 개정

- `INTEGRATED_TECHNICAL_REPORT_KR.md`는 2026년 7월 23일 제출 기술내용을 중심으로 공개 보고서를 구성했다.
- 편집 방침을 설명하던 원문 보존 안내와 별도 부록을 제거했다.
- 개인정보, 서명, 신청 행정 정보와 권리보호 양식은 공개 저장소에서 제외했다.
- 사전 annotation 분석은 창작 과정, 선행연구는 알고리즘 비교, timing 병목 해결은 구현 결과, 재현성과 한계는 검증 및 목표 비교 절에 통합했다.
- 본문에서 인용한 여덟 문헌을 `[1]`부터 `[8]`까지 번호로 연결했다.

## 기준

- 대회 설계기술설명서의 공개 가능한 기술 내용
- MATLAB fixed commit `907f7e1f081a9d6a5703a32095d962143315a192`
- XMODEL fixed commit `4756a5086023547328ef44fd5fd87da3c250dc39`
- Digital fixed commit `c6b80de19cdcad5b7e43fe7835588b629d847f75`
- 최신 benchmark evidence `d44e67517650f1f95ca67b93c2788f41e99f1a5e`

## 주요 개정

1. 공개 클래스명을 NSR, CHF, ARR, AF로 통일했다. legacy model ID, RTL port와 raw artifact의 `AFF`는 재현성을 위해 보존했다.
2. `SNN-inspired`를 `SNN 기반`으로 교체하고 event, LIF firing과 membrane accumulation의 구현 근거를 연결했다.
3. 사전 annotation 분석은 feature 선택에 사용되지만 최종 RTL 추론 입력에는 사용되지 않음을 명시했다.
   - 30분 구간이 원천 label을 뒷받침하는 박동 및 리듬 증거를 충분히 포함하는지 annotation으로 점검한 데이터 구성 절차를 추가했다.
4. 30분은 현재 검증 조건, 24시간 이상 Holter는 설계 지향점으로 분리했다.
5. RDM-to-prediction critical path 관측, pipeline 분할, timing 재검증과 기능 정합의 개발 이력을 추가했다.
6. 최종 구현 9,719 LUT와 5,038 FF를 profiler build 9,759 LUT와 5,049 FF에서 분리했다.
7. benchmark를 36.0129 ms, 49.36배, 142.0 mW와 조건부 2.991 µW의 최신 근거로 갱신했다.
8. 36-case compact acceptance와 저장소가 보유한 4-case raw-dump 재실행 범위를 분리했다.

## 유지한 한계

- database–class confounding
- 실제 24시간 정확도, 처리시간과 전력 미검증
- 2026-07 개정 당시 physical AFE PCB, ADC silicon, ASIC/post-layout와 clinical validation 미수행; ASIC 범위는 아래 2026-08 개정에서 갱신
- FPGA 전력은 activity 기반 추정이며 2.991 µW는 완전 power-gating 조건의 산출값

문장별 근거는 `INTEGRATED_TECHNICAL_REPORT_EVIDENCE_MAP.csv`에 있다.

## 2026-08-20 GPDK045 core-only PPA 개정

- `snn_ecg_asic_core_top`, `PROFILE_EN=0`의 generic GPDK045 flow 근거를 추가했다.
- 실제 raw XMODEL 재실행 4/36과 과거 36-case compact acceptance를 분리해, 36개 raw dump 직접 재실행처럼 읽히던 표현을 바로잡았다.
- Xcelium wrapper smoke, actual-core Conformal 13-module PASS, Genus `syn_map`, Innovus signal post-route와 IQuantus extraction을 구분해 기록했다.
- mapped 35,188 cells/93,585.906 µm²와 post-route 35,663 instances/95,321.556 µm²를 보고했다.
- setup WNS +2.980 ns와 hold WNS −0.050 ns를 함께 제시해 full timing closure가 아님을 명시했다.
- clock slew 위반 86개, `SDFFQX1` 995개와 undefined scan 10.70% flops의 QoR 한계를 추가했다.
- Incomplete antenna data, physical-only cell·metal fill 미삽입과 historical clock-source transition 미지정을 공개했다.
- 3.35554239 mW를 default activity 0.10의 vectorless estimate로 제한하고 FPGA 추정치·이상적 power-gating 산출값·실측 전력과 구분했다.
- VDD/VSS 미배선, internal route DRC 1, PG/IR, foundry DRC/LVS, DFT, pad/package와 fabrication 미수행을 claim 경계로 남겼다.

## 2026-08-21 GPDK045 run-2 정적 결과 개정

- Run-1 historical core baseline을 보존하고 run-2 scan-free core와 AXI-inclusive accelerator block을 별도 profile로 추가했다.
- Core는 mapped 36,565 cells/94,421.754 µm², post-route 42,958 instances/120,287.898 µm²이고 AXI block은 mapped 37,293 cells/96,548.994 µm², post-route 43,901 instances/123,650.100 µm²로 기록했다.
- 100 MHz에서 core/AXI setup WNS +2.469/+2.781 ns, hold WNS −0.008/−0.016 ns와 data-net max-transition residual을 함께 공개해 physical timing closure로 표현하지 않았다.
- Slow-early 0.95와 fast-late 1.05의 fixed global engineering derate는 foundry-characterized AOCV/POCV/LVF가 아님을 명시했다.
- Core/AXI post-route vectorless 3.71626492/3.69335598 mW를 default activity 기반 추정치로 제한했다.
- Canonical digital RTL 36/36과 actual raw XMODEL 4/4를 분리했으며 raw XMODEL archive 범위는 4/36으로 유지했다.
- Mapped-to-postroute LEC는 core 6,178/AXI 6,287 compare point에서 diff·abort·unknown 0이지만 timing·accuracy·four-state GLS·sign-off와 구분했다.
- Run-3 core는 stated engineering OCV에서 hold·data-transition·clock-slew·internal-DRC를 닫았고, run-4 AXI는 hold·clock-slew·internal-DRC를 닫으면서 run-3보다 PPA를 개선했지만 data-transition 141 nets/1,149 terminals를 residual로 유지했다.
- Run-5 AXI는 50% floorplan에서 setup·hold·data-transition·clock-slew·internal-DRC를 모두 닫고 LEC 6,287점 clean을 유지했으며, 더 큰 die를 area–closure tradeoff로 공개했다.
- Run-6 AXI는 100 ps hold uncertainty 뒤에 추가 10 ps slack을 확보하고 다른 closure·LEC를 유지했으며, guardband의 면적·배선·전력 비용을 공개했다.
- Exploratory PG attempt는 171 connectivity·715 geometry violation으로 실패했으며 PG/IR/EM 구현 근거가 아님을 남겼다.
- Unmodified four-state gate output X와 XPR license 부재를 보존하고, forced mapped seeds 11/22/33 및 timing check를 끈 single-seed MAX-SDF 결과를 testbench-conditioned sampled sensitivity로 제한했다.
- Core seed11-conditioned activity 분석을 accelerated gap2 2.02536072 mW, active-wait idle 1.91083992 mW, literal 1 kSPS 100-sample prefix 1.91084079 mW, matched total delta 0.00000087 mW로 추가했다.
- Mapped gate 6,045/6,045, `-access +rwc`, zero delay, normalized SAIF parse PASS, fully-X/Z preserve와 unannotated default 0을 방법 경계로 기록했다.
- Parse/annotation PASS는 numeric annotation coverage PASS가 아니며 prefix는 Snapshot/decision에 도달하지 않고 matched delta는 silicon power·energy/decision이 아님을 명시했다. AXI power는 vectorless only로 유지했다.
