# GPDK045 hold-closure run-3

Run-2의 음수 hold WNS를 같은 100 MHz SDC, 100 ps hold uncertainty, slow-early 0.95·fast-late 1.05 engineering OCV와 CPPR 조건에서 보정한 후속 물리 ECO 증거다. Run-2 산출물은 변경하지 않고 별도 checkpoint에서 DLY-cell endpoint ECO, targeted `ecoRoute`, IQuantus high-effort extraction과 DRV recovery를 수행했다.

| 항목 | Core | AXI-inclusive block |
|---|---:|---:|
| Instances / cell area | 43,016 / 120,532.428 µm² | 44,062 / 124,717.482 µm² |
| Setup WNS | +2.470 ns | +2.435 ns |
| Hold WNS / TNS / paths | 0.000 / 0.000 ns / 0 | 0.000 / 0.000 ns / 0 |
| Data max-transition | 0 | 264 nets / 1,387 terminals, worst −1.813 ns |
| Clock slew @ 60 ps | 0 | 263 pins, worst 0.064 ns |
| Internal route DRC | 0 | 0 |
| Vectorless total power | 3.72167787 mW | 3.79286409 mW |
| Mapped→postroute LEC | 6,178 points clean | 6,287 points clean |

Core는 hold·data-transition·clock-slew·internal-DRC 기준을 모두 0 violation으로 닫았다. AXI block은 hold closure에는 성공했지만 data-transition과 clock-slew가 악화되어 full physical closure 또는 run-2 AXI QoR의 무조건적 대체 결과로 채택하지 않는다.

두 결과 모두 padless signal-route block이며 VDD/VSS, PG/IR/EM, filler/tap/endcap/metal fill, complete antenna rule, foundry DRC/LVS, DFT, pad/package와 fabrication은 포함하지 않는다. OCV도 fixed engineering assumption이지 foundry AOCV/POCV/LVF가 아니다. 전력은 default PI/sequential activity 0.10의 vectorless estimate이며 workload나 실리콘 실측값이 아니다.

Public package는 report에서 파싱·요약한 CSV/JSON과 routed GIF만 포함한다. Self-contained Innovus DB, netlist, DEF, SDF, SPEF와 원본 로그는 Git 밖의 private archive에 보존했으며 archive SHA-256은 `d04bf1d702bc8a7770d07ec2cbb509fbe7169ba118a02a133600899c010695b5`다.
