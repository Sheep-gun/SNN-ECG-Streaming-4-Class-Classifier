# GPDK045 AXI full-closure run-5

Run-4 AXI block에 남아 있던 data max-transition 141 nets / 1,149 terminals를 해결한 후속 물리 구현 증거다. Run-4 transition report의 141 nets 중 140개가 `qrs_maf` 내부에 집중됐고, 주로 약한 NAND/NOR driver의 falling slew 문제였다. 외부 AXI constraint를 완화하지 않고 floorplan utilization을 0.65에서 0.50으로 낮춰 buffer와 큰 driver를 배치할 공간을 확보했다.

| 항목 | Run-4 AXI | Run-5 AXI selected |
|---|---:|---:|
| Instances / cell area | 43,956 / 123,906.258 µm² | 42,881 / 126,069.441 µm² |
| Die / density | 426.2 × 425.03 µm / 83.388% | 481.2 × 478.04 µm / 65.274% |
| Routed wire / vias | 953,367.865 µm / 346,666 | 812,624.320 µm / 313,004 |
| Setup WNS | +2.661 ns | +2.703 ns |
| Hold WNS / TNS / paths | 0.000 / 0.000 ns / 0 | 0.000 / 0.000 ns / 0 |
| Data max-transition | 141 nets / 1,149 terminals, worst −0.821 ns | 0 nets / 0 terminals |
| Clock slew @ 60 ps | 0 pins, worst 0.059 ns | 0 pins, worst 0.056 ns |
| Internal route DRC | 0 | 0 |
| Vectorless total power | 3.71285384 mW | 3.58433691 mW |
| Mapped→postroute LEC | 6,287 points clean | 6,287 points clean |

Run-5는 stated engineering checks에서 setup·hold·data transition·clock slew·internal route DRC를 동시에 닫았다. Run-4보다 standard-cell area는 약 1.75%, die area는 약 26.99% 증가했지만 routed wire는 약 14.76%, via는 약 9.71%, vectorless power는 약 3.46% 감소했다. 더 큰 die를 사용해 routing과 driver 배치 공간을 확보한 명시적 area–closure tradeoff다.

50% floorplan의 최초 post-route 기준은 transition 19 nets / 97 terminals와 hold −0.013 ns / 93 paths였다. 첫 closure pass에서 transition을 0으로 만들고 hold를 1 path까지 줄였으며, 두 번째 pass에서 hold도 0으로 닫았다. 세 번째 pass와 독립 final export에서 동일한 0-violation 상태를 재확인했다. 상세 단계는 [closure_progress.csv](results/closure_progress.csv)에 기록했다.

모든 수치는 동일한 100 MHz SDC, 100 ps hold uncertainty, slow-early 0.95와 fast-late 1.05 fixed engineering OCV, CPPR, SI-on, IQuantus high-effort 조건이다. GPDK045는 generic demonstration library이고 두 RC view는 같은 `gpdk045.tch`와 scale 1.0을 사용한다. 따라서 이 결과의 “full closure”는 명시한 block-level engineering checks에 한정되며 foundry AOCV/POCV/LVF 또는 sign-off를 뜻하지 않는다.

이 block은 padless signal-route 범위이며 VDD/VSS, PG/IR/EM, filler/tap/endcap/metal fill, complete antenna rule, foundry DRC/LVS, DFT, pad/package와 fabrication을 포함하지 않는다. 전력은 default PI/sequential activity 0.10의 vectorless estimate이며 workload 또는 실리콘 실측값이 아니다.

Public package에는 sanitize한 CSV/JSON과 routed GIF만 포함한다. Innovus DB, netlist, DEF, SDF, SPEF와 원본 로그는 Git 밖의 local private archive에 보존했고 SHA-256은 `8f43165b9fa79c38e8b389587cd360af9f2583ccb6d96424fcf466e365db3ee4`다. 원격 작업 폴더는 회수·검증 후 삭제했다.
