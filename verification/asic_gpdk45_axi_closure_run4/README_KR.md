# GPDK045 AXI closure run-4

Run-3에서 hold는 닫혔지만 data max-transition 264 nets / 1,387 terminals와 clock slew 263 pins가 남았던 AXI-inclusive accelerator block을 다시 보정한 후속 증거다. Run-2 checkpoint를 별도로 복원해 Cadence hold threshold의 lower-bound 의미를 바로잡고, 목표 0 ns의 소규모 DLY-cell ECO를 반복한 뒤 마지막 반올림 경로에 DLY1X1 한 개를 추가했다.

| 항목 | Run-3 AXI | Run-4 AXI selected |
|---|---:|---:|
| Instances / cell area | 44,062 / 124,717.482 µm² | 43,956 / 123,906.258 µm² |
| Placement density | 83.934% | 83.388% |
| Routed wire / vias | 1,054,817.085 µm / 373,512 | 953,367.865 µm / 346,666 |
| Setup WNS | +2.435 ns | +2.661 ns |
| Hold WNS / TNS / paths | 0.000 / 0.000 ns / 0 | 0.000 / 0.000 ns / 0 |
| Data max-transition | 264 nets / 1,387 terminals, worst −1.813 ns | 141 nets / 1,149 terminals, worst −0.821 ns |
| Clock slew @ 60 ps | 263 pins, worst 0.064 ns | 0 pins, worst 0.059 ns |
| Internal route DRC | 0 | 0 |
| Vectorless total power | 3.79286409 mW | 3.71285384 mW |
| Mapped→postroute LEC | 6,287 points clean | 6,287 points clean |

Run-4는 run-3보다 106 instances와 811.224 µm²를 줄였고, routed wire는 약 9.62%, via는 약 7.19%, vectorless total power는 약 2.11% 감소했다. Hold, clock slew와 internal route DRC는 0 violation이고 논리 등가성도 유지했다. 다만 data max-transition 141 nets / 1,149 terminals가 남으므로 AXI full physical closure라고 부르지 않는다.

자동 hold target을 +0.020 ns로 올린 후보는 2,127 cells를 추가해 기각했다. Pre-CTS 119-endpoint rebuild와 driver-downsize, post-route DRV 재복구도 각각 hold/DRV/DRC를 악화시켜 선택하지 않았다. 선택 결과는 run-2 대비 55 cells만 추가한 경로다. 실패 후보는 [experiment_summary.csv](results/experiment_summary.csv)에 분리했다.

모든 수치는 같은 100 MHz SDC, 100 ps hold uncertainty, slow-early 0.95와 fast-late 1.05 fixed engineering OCV, CPPR, SI-on, IQuantus high-effort 조건이다. GPDK045는 generic demonstration library이고 두 RC view는 같은 `gpdk045.tch`와 scale 1.0을 사용한다. 따라서 foundry AOCV/POCV/LVF 또는 sign-off 결과가 아니다.

이 block은 padless signal-route 범위이며 VDD/VSS, PG/IR/EM, filler/tap/endcap/metal fill, complete antenna rule, foundry DRC/LVS, DFT, pad/package와 fabrication을 포함하지 않는다. 전력은 default PI/sequential activity 0.10의 vectorless estimate이며 workload 또는 실리콘 실측값이 아니다.

Public package에는 sanitize한 CSV/JSON과 routed GIF만 포함한다. Innovus DB, netlist, DEF, SDF, SPEF와 원본 로그는 Git 밖의 local private archive에 보존했고 SHA-256은 `479c4c3528935934ac73290656b2b0196220d66c38493e8a41fa87ba1685e117`이다. 원격 작업 폴더는 회수·검증 후 삭제했다.
