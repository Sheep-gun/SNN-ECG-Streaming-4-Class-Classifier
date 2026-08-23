# 최종 Figure index

최종 제출 보고서에 사용한 Figure만 `figures/final_submission/`에 보존한다. SVG/EMF 쌍은 동일 그림의 편집용 vector와 한글 호환 export다.

| Figure | 내용 | 파일 |
|---|---|---|
| 1 | 연구·개발 workflow | `창작과정/창작과정 블록도_가로형.svg` |
| 2 | 다중 시간 척도 SNN 알고리즘 | `알고리즘 구성 및 예상결과/알고리즘 구조도.svg` |
| 3 | AFE–ADC signal/non-ideal flow | `설계회로 구성/아날로그 회로 구조도.svg` |
| 4 | LTspice AFE/S/H/ADC 전체 회로 | `설계회로 구성/full schematic by LTspice.svg` |
| 5 | Pure RTL hierarchy | `설계회로 구성/디지털 RTL 계층 구조도_한글호환.svg` |
| 6 | Vivado IP Integrator 기반 통합 구조 | `설계회로 구성/디지털 IP 패키징 통합 구조도_한글호환.svg` |
| 7 | 아날로그 검증 흐름 | `설계회로 검증/아날로그 검증/아날로그 검증 흐름.svg` |
| 8a | MATLAB–LTspice overall AFE response | `설계회로 검증/아날로그 검증/LTspice vs Matlab/Overall AFE Frequency Response Comparison.svg` |
| 8b | MATLAB–LTspice 60 Hz notch response | `설계회로 검증/아날로그 검증/LTspice vs Matlab/60 HZ Active Twin-T Notch Response Comparison.svg` |
| 9 | LTspice–XMODEL 10 s waveform overlay | `설계회로 검증/아날로그 검증/xmodel vs LTspice/adc_waveform_full.png` |
| 10 | 디지털 검증 흐름 | `설계회로 검증/디지털 검증/디지털 검증 흐름.svg` |
| 11 | AFE–ADC XMODEL–RTL integration | `설계회로 검증/AXI,IP 및 mixed 검증/VAL-03_analog_digital_integration_flow.svg` |
| 12 | XMODEL AFE–ADC stage waveform | `설계회로 구현결과/Xmodel 구현 결과.svg` |
| 13 | FPGA implementation/placement | `설계회로 구현결과/FPGA 구현ㆍ배치 결과.svg` |
| 14 | GPDK045 core-only signal placement/routing | `설계회로 구현결과/GPDK045 코어 배치배선 결과.gif` |
| 15 | GPDK045 run-6 AXI standard-cell placement | `설계회로 구현결과/GPDK045 AXI 표준셀 배치 결과.gif` |
| 16 | GPDK045 run-6 AXI placement/signal routing | `설계회로 구현결과/GPDK045 AXI 최종 배치배선 결과.gif` |
| 17 | GPDK045 run-6 AXI CTS clock-net selection | `설계회로 구현결과/GPDK045 AXI Clock Net 선택 결과.gif` |
| 18 | GPDK045 run-6 qrs_maf leaf-placement selection | `설계회로 구현결과/GPDK045 AXI QRS-MAF 배치 선택 결과.gif` |

Figure 13은 ASIC layout이 아니라 Vivado post-route FPGA placement를 바탕으로 정리한 publication figure다. Figure 14는 generic GPDK045 historical core의 일반 신호 배선 화면이다. Figure 15–18은 최종 run-6 AXI checkpoint에서 Innovus가 직접 출력한 placement·routing·clock-net·qrs_maf selection 화면이다. 모든 GPDK045 Figure는 signal-only block이며 PG·pad·foundry-signoff layout이 아니다. Figure 5는 원본 RTL hierarchy에 근거한 reader-facing vector 정리이며 synthesized leaf-cell netlist가 아니다.

## 보조 Cadence native view

보고서 Figure 번호와 별개로 최종 run-6 AXI checkpoint의 placement-only, routing-only, clock-net selection, `qrs_maf` selection과 Metal1–Metal11 layer-group 화면을 `verification/cadence_native_visuals/`에 보존한다. 이 GIF는 모두 Innovus `dumpToGIF` 직접 출력이며 재도식화·AI 생성·이미지 후처리를 하지 않았다.
