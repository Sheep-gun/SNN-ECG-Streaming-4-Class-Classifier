# 웨어러블 저전력 IP 근거 보강 결과

## 결론

현재 결과는 **100 MHz Artix-7에서 기능 정합된 ECG 가속기**, **generic GPDK045 run-1 historical core baseline**, **run-2 scan-free core와 AXI-inclusive accelerator block의 exploratory post-route**, **run-3 core closure**, **run-4 AXI hold·clock·DRC closure 개선**, **run-2 core의 seed11-conditioned activity window** 근거를 뒷받침한다. 다만 AXI data-net transition residual, 성공한 power grid·physical fill, unconditioned reset-aware Snapshot/decision activity, sign-off·silicon 실측과 전체 wearable 부품 예산이 없으므로 “웨어러블용 저전력 반도체 IP”를 최종 입증한 단계는 아니다.

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
| GPDK045 run-1 core post-route vectorless total | 3.35554239 mW | ESTIMATED; default activity 0.10 |
| GPDK045 run-1 extracted timing | setup WNS +2.980 ns, hold WNS −0.050 ns, clock slew 86건 | PARTIAL; historical baseline, physical timing closure 미달성 |
| GPDK045 run-1 historical scan-capable mapping | `SDFFQX1` 995개, undefined scan 10.70% flops | PARTIAL; placement/timing QoR 한계 |
| GPDK045 run-2 scan-free core post-route vectorless total | 3.71626492 mW | ESTIMATED; default PI/sequential activity 0.10, workload power 아님 |
| GPDK045 run-2 AXI block post-route vectorless total | 3.69335598 mW | ESTIMATED; default PI/sequential activity 0.10, workload power 아님 |
| GPDK045 run-2 core extracted timing | setup WNS +2.469 ns, hold WNS −0.008 ns, hold TNS −0.094 ns/37 paths | PARTIAL; data-net max-transition 3 nets도 잔존 |
| GPDK045 run-2 AXI extracted timing | setup WNS +2.781 ns, hold WNS −0.016 ns, hold TNS −0.518 ns/107 paths | PARTIAL; data-net max-transition 73 nets도 잔존 |
| GPDK045 run-2 clock/internal checks | core/AXI clock slew 0 @ 60 ps, internal DRC 0 | PARTIAL; data-net transition·foundry DRC sign-off를 뜻하지 않음 |
| GPDK045 run-3 core closure / vectorless | hold·data transition·clock slew·internal DRC 0, total 3.72167787 mW | PARTIAL; generic signal-route block, workload power·foundry sign-off 아님 |
| GPDK045 run-4 AXI closure / vectorless | setup +2.661 ns, hold 0 path, clock slew 0, internal DRC 0, total 3.71285384 mW | PARTIAL; data transition 141 nets/1,149 terminals 잔존 |
| GPDK045 run-2 core accelerated gap2 activity | internal 1.52085678, switching 0.50045621, leakage 0.00404773, total 2.02536072 mW | ESTIMATED; seed11-conditioned zero-delay full-record accelerated window |
| GPDK045 run-2 core active-wait idle | internal 1.48928157, switching 0.41750333, leakage 0.00405502, total 1.91083992 mW | ESTIMATED; matched 0.1 s, pure clock power 아님 |
| GPDK045 run-2 core literal 1 kSPS prefix | internal 1.48928212, switching 0.41750554, leakage 0.00405312, total 1.91084079 mW | ESTIMATED; 100 samples, Snapshot/decision 미도달 |
| GPDK045 run-2 matched literal-minus-idle delta | 0.00000087 mW total | DERIVED; short-prefix delta, energy/decision 아님 |
| Foundry target ASIC sign-off/silicon | PG/IR·DRC/LVS·fabrication 부재 | NOT AVAILABLE |

네 클래스에서 각각 실제 1,800,000샘플 burst SAIF와 실제 100샘플 literal 1 kS/s SAIF를 생성했다. 모든 burst 캡처는 잠긴 final prediction과 네 membrane 값을 통과했다. RTL SAIF의 routed-net 매칭률은 약 12%이며 나머지는 Vivado vectorless propagation이므로 confidence는 Medium이다. 따라서 이 결과는 기존 완전 vectorless 값보다 workload 관련성이 높지만 sign-off activity power는 아니다.

GPDK045 activity 표의 수치는 FPGA SAIF와 별개다. Seed11-conditioned mapped gate 6,045/6,045를 `-access +rwc`, zero delay로 실행하고 normalized SAIF를 사용했다. Parse/annotation status는 PASS이며 fully-X/Z entry를 보존하고 unannotated default 0을 사용했지만, numeric annotation coverage PASS를 주장하지 않는다. Accelerated gap2는 wall-time 1 kSPS가 아니고 prefix는 Snapshot/decision에 도달하지 않으며, AXI activity power는 없다.

## Streaming과 preloaded burst 해석

- streaming은 100 MHz global clock가 계속 동작한다. 따라서 1 kS/s로 입력 활동이 낮아져도 FPGA static과 clock power가 남는다.
- 30분 레코드를 36.0129 ms에 burst 처리하고 나머지 시간을 clock-gate한다고 가정하면, power-gating이 없는 평균은 약 97.001 mW이며 대부분 FPGA static이다.
- accelerator dynamic만 duty-cycle한 항은 약 1.050 uW이다.
- static까지 완전히 제거하는 이상적 power-gating 상한은 약 2.991 uW지만 retention, isolation, wake energy, switch leakage가 모두 빠져 있어 제품 수치로 사용할 수 없다.

## Wearable 전체 예산

MAX30001의 85 uW ECG AFE는 외부 datasheet reference로만 포함했다. 실제 sample memory, MCU, BLE와 PMIC는 부품·전압·duty cycle이 정해지지 않아 빈 stage gate로 남겼다. 따라서 현재 전체 wearable subtotal이나 배터리 수명은 제시하지 않는다.

## 남은 필수 근거

1. GPDK045 AXI data-net max-transition, VDD/VSS power routing과 PG/IR 해소
2. Filler/decap/tap/endcap·metal fill, complete antenna data와 quantified annotation coverage를 갖춘 unconditioned reset-aware Snapshot/decision VCD/SAIF power
3. UPF/CPF 기반 retention·isolation·power-switch 및 wake overhead
4. 실제 선정 MCU/BLE/memory/PMIC workload와 전체 전력 예산
5. 외부 계측기와 ASIC silicon의 idle/stream/burst 실측

물리 보드와 ASIC silicon 전력은 측정하지 않았다. Vivado 및 GPDK045 power는 **ESTIMATED**이고, 전력과 latency의 곱은 명시한 조건에서만 **DERIVED**이다. Run-1/run-2/run-3/run-4 vectorless power와 run-2 conditioned activity windows로 ASIC 판정당 에너지를 산출하지 않았다. Matched 0.00000087 mW delta도 energy/decision이 아니며 AXI는 vectorless only다.
