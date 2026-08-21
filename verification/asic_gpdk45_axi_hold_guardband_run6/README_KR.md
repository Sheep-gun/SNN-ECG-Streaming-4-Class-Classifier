# GPDK045 AXI hold-guardband run-6

Run-5 AXI의 hold WNS 0.000 ns를 보강한 후속 증거다. 기존 100 ps hold uncertainty와 fixed engineering OCV를 유지한 채 positive hold target을 단계적으로 10·12·15 ps로 올리고, 각 hold ECO 후 재발한 data-transition을 별도 DRV pass로 복구했다.

| 항목 | Run-5 AXI | Run-6 AXI selected |
|---|---:|---:|
| Instances / cell area | 42,881 / 126,069.441 µm² | 44,602 / 131,487.003 µm² |
| Die / density | 481.2 × 478.04 µm / 65.274% | 481.2 × 478.04 µm / 68.079% |
| Routed wire / vias | 812,624.320 µm / 313,004 | 933,258.465 µm / 331,718 |
| Setup WNS | +2.703 ns | +2.602 ns |
| Hold WNS / TNS / paths | 0.000 / 0.000 ns / 0 | +0.010 / 0.000 ns / 0 |
| Data max-transition | 0 | 0 |
| Clock slew @ 60 ps | 0 pins, worst 0.056 ns | 0 pins, worst 0.057 ns |
| Internal route DRC | 0 | 0 |
| Vectorless total power | 3.58433691 mW | 3.71636663 mW |
| Mapped→postroute LEC | 6,287 points clean | 6,287 points clean |

Run-6는 기존 100 ps uncertainty 뒤에 추가 hold guardband 10 ps를 남긴다. Run-5 대비 1,721 instances, standard-cell area 약 4.30%, routed wire 약 14.85%, vias 약 5.98%, vectorless power 약 3.68%가 증가했다. Setup slack은 2.602 ns로 충분하고 transition·clock·DRC·LEC는 유지됐다. Hold robustness를 얻기 위해 면적·배선·전력을 지불한 명시적 tradeoff다.

첫 10 ps target은 1,059 hold cells를 추가했지만 최종 margin은 6 ps였고 transition 6 nets가 재발했다. DRV 복구 후 12 ps target으로 216 cells를 추가해 7 ps를 확보했다. 두 번째 DRV 복구 후 15 ps target으로 439 cells를 추가해 최종 10 ps를 확보했고, 마지막 DRV pass에서 transition을 다시 0으로 닫았다. 상세 단계는 [guardband_progress.csv](results/guardband_progress.csv)에 보존한다.

모든 수치는 동일한 100 MHz SDC, 100 ps hold uncertainty, slow-early 0.95와 fast-late 1.05 fixed engineering OCV, CPPR, SI-on, IQuantus high-effort 조건이다. 따라서 총 hold 방어 여유를 “110 ps의 foundry 보증”으로 해석하면 안 된다. 100 ps는 engineering uncertainty이고 10 ps는 해당 generic view에서의 잔여 slack이다.

이 block은 padless signal-route 범위이며 VDD/VSS, PG/IR/EM, filler/tap/endcap/metal fill, complete antenna rule, foundry DRC/LVS, DFT, pad/package와 fabrication을 포함하지 않는다. 전력은 default PI/sequential activity 0.10의 vectorless estimate이며 workload 또는 실리콘 실측값이 아니다.

Public package에는 sanitize한 CSV/JSON과 routed GIF만 포함한다. Innovus DB, netlist, DEF, SDF, SPEF와 원본 로그는 Git 밖의 local private archive에 보존했고 SHA-256은 `0a39b2e2d8123c6d0bad78aab259360298a6c8529f92c91bbe5bbfd40277424a`다. 원격 작업 폴더는 회수·검증 후 삭제했다.
