# 웨어러블 저전력 IP 근거 보강 결과

## 결론

현재 결과는 **100 MHz Artix-7에서 기능 정합된 ECG 가속기**와 **generic GPDK045 digital core-only exploratory post-route** 근거를 뒷받침한다. 다만 ASIC hold·clock-slew closure, scan-aware QoR, power grid·physical fill, workload activity, sign-off·silicon 실측과 전체 wearable 부품 예산이 없으므로 “웨어러블용 저전력 반도체 IP”를 최종 입증한 단계는 아니다.

## 즉시 완료한 근거

| 항목 | 결과 | 분류 |
|---|---:|---|
| 실제 ECG burst top Total On-Chip Power 중앙값 | 0.1775 W | ESTIMATED |
| 실제 ECG burst 가속기 hierarchy dynamic 중앙값 | 0.0525 W | ESTIMATED |
| 실제 ECG burst 가속기+FPGA static 할당 전력 | 0.1495 W | ESTIMATED |
| literal 100 MHz/1 kS/s top Total On-Chip Power 중앙값 | 0.1660 W | ESTIMATED |
| literal 1 kS/s 가속기 hierarchy dynamic 중앙값 | 0.0450 W | ESTIMATED |
| literal 1 kS/s 가속기+FPGA static 할당 전력 | 0.1420 W | ESTIMATED |
| 36.0129 ms 기준 가속기 할당 energy/decision | 5.3839 mJ | DERIVED |
| 36.0129 ms 기준 가속기 dynamic energy/decision | 1.8907 mJ | DERIVED |
| 기존 CE + Vivado tool gating | 68.735% (2740 user + 727 tool / 5044) | ESTIMATED |
| power_opt burst top | 0.1775 W | ESTIMATED |
| power_opt 1 kS/s top | 0.1660 W | ESTIMATED |
| FPGA rail idle/active 차동 | 미측정 | NOT MEASURED |
| GPDK045 core-only post-route vectorless total | 3.35554239 mW | ESTIMATED; default activity 0.10 |
| GPDK045 extracted timing | setup WNS +2.980 ns, hold WNS −0.050 ns, clock slew 86건 | PARTIAL; physical timing closure 미달성 |
| Historical scan-capable mapping | `SDFFQX1` 995개, undefined scan 10.70% flops | PARTIAL; placement/timing QoR 한계 |
| Foundry target ASIC sign-off/silicon | PG/IR·DRC/LVS·fabrication 부재 | NOT AVAILABLE |

네 클래스에서 각각 실제 1,800,000샘플 burst SAIF와 실제 100샘플 literal 1 kS/s SAIF를 생성했다. 모든 burst 캡처는 잠긴 final prediction과 네 membrane 값을 통과했다. RTL SAIF의 routed-net 매칭률은 약 12%이며 나머지는 Vivado vectorless propagation이므로 confidence는 Medium이다. 따라서 이 결과는 기존 완전 vectorless 값보다 workload 관련성이 높지만 sign-off activity power는 아니다.

## Streaming과 preloaded burst 해석

- streaming은 100 MHz global clock가 계속 동작한다. 따라서 1 kS/s로 입력 활동이 낮아져도 FPGA static과 clock power가 남는다.
- 30분 레코드를 36.0129 ms에 burst 처리하고 나머지 시간을 clock-gate한다고 가정하면, power-gating이 없는 평균은 약 97.001 mW이며 대부분 FPGA static이다.
- accelerator dynamic만 duty-cycle한 항은 약 1.050 uW이다.
- static까지 완전히 제거하는 이상적 power-gating 상한은 약 2.991 uW지만 retention, isolation, wake energy, switch leakage가 모두 빠져 있어 제품 수치로 사용할 수 없다.

## Wearable 전체 예산

MAX30001의 85 uW ECG AFE는 외부 datasheet reference로만 포함했다. 실제 sample memory, MCU, BLE와 PMIC는 부품·전압·duty cycle이 정해지지 않아 빈 stage gate로 남겼다. 따라서 현재 전체 wearable subtotal이나 배터리 수명은 제시하지 않는다.

## 남은 필수 근거

1. GPDK045 hold·clock slew, scan-aware remapping, internal route DRC, VDD/VSS power routing과 PG/IR 해소
2. Filler/decap/tap/endcap·metal fill, complete antenna data와 실제 ECG workload VCD/SAIF를 결합한 parasitic/leakage/dynamic power
3. UPF/CPF 기반 retention·isolation·power-switch 및 wake overhead
4. 실제 선정 MCU/BLE/memory/PMIC workload와 전체 전력 예산
5. 외부 계측기와 ASIC silicon의 idle/stream/burst 실측

물리 보드와 ASIC silicon 전력은 측정하지 않았다. Vivado 및 GPDK045 power는 **ESTIMATED**이고, 전력과 latency의 곱은 명시한 조건에서만 **DERIVED**이다. GPDK045 vectorless power로는 판정당 에너지를 산출하지 않았다.
