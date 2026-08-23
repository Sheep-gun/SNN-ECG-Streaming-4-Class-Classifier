# Cadence native visual exports

이 폴더는 AI 생성·재구성·후처리 그림이 아니라 Cadence Innovus가 실제 checkpoint에서 `dumpToGIF`로 직접 출력한 화면만 보존한다. 최종 기준은 GPDK045 run-6 AXI block이며, 배치·CTS·일반 신호 배선이 완료된 `snn_ecg_axi_asic_top` checkpoint다.

## Run-6 native view

| 파일 | Innovus 표시 상태 | 해석 |
|---|---|---|
| `01_full_placement_routing.gif` | instances + all signal nets | 최종 배치·배선 전체 화면 |
| `02_placement_only.gif` | nets hidden, instances visible | 최종 standard-cell placement |
| `03_routing_only.gif` | instances hidden, nets visible | 최종 signal routing |
| `04_full_with_pins.gif` | instances + nets + pin objects | pin을 포함한 전체 physical view |
| `05_clock_nets_selected.gif` | 114 clock nets selected | 실제 CTS clock-net 선택 화면 |
| `06_qrs_maf_placement_selected.gif` | 9,261 `qrs_maf` leaf instances selected | transition 병목이 있던 영역의 실제 배치 선택 화면 |
| `07_metal1_only.gif` | Metal1 only | local routing layer |
| `08_metal2_3.gif` | Metal2–Metal3 only | lower routing layers |
| `09_metal4_6.gif` | Metal4–Metal6 only | middle routing layers |
| `10_metal7_11.gif` | Metal7–Metal11 only | upper/global routing layers |

`06_qrs_maf_placement_selected.gif`은 `fit -selected`가 해당 Innovus build에서 status 1을 반환해 full-chip fit 상태로 저장됐다. 선택 자체는 status 0이며 cyan highlight가 `qrs_maf` leaf placement다. 모든 dump와 layer-visibility 명령의 실제 반환 상태는 `provenance/`에 있다.

`03_routing_only.gif`과 `04_full_with_pins.gif`은 이 full-chip zoom에서 pixel byte가 동일하다. Pin/instance visibility 명령은 status 0이지만 dense routing이 해당 객체를 완전히 가려 최종 raster에 차이가 생기지 않은 것이다. 두 파일은 command provenance를 보존하기 위해 그대로 둔다.

## Historical native GIF

다음 기존 파일도 모두 각 run의 Innovus checkpoint에서 직접 출력한 native GIF다.

- `verification/asic_gpdk45_core/figures/routed_core.gif`
- `verification/asic_gpdk45_run2/figures/core_routed.gif`
- `verification/asic_gpdk45_run2/figures/axi_routed.gif`
- `verification/asic_gpdk45_hold_closure/figures/core_holdclosed.gif`
- `verification/asic_gpdk45_hold_closure/figures/axi_holdclosed.gif`
- `verification/asic_gpdk45_axi_closure_run4/figures/axi_run4_final.gif`
- `verification/asic_gpdk45_axi_full_closure_run5/figures/axi_util50_full_closed.gif`
- `verification/asic_gpdk45_axi_hold_guardband_run6/figures/axi_holdguard10_final.gif`

## Genus와 Innovus 원본 report

Genus AXI `area_generic`, `area_mapped`, `gates_mapped`, `qor_mapped`, `timing_generic`, `timing_mapped`, vectorless power report와 run-6 Innovus area·timing·power·clock-tree·DRC·connectivity·LEC report는 Git 밖의 local delivery 폴더에 원본 그대로 보존한다. Report에는 실행환경 절대경로가 있어 공개 Git에는 넣지 않았다.

## 재현

- `design/digital/asic/gpdk45/scripts/export_innovus_native_visual_suite.tcl`
- `design/digital/asic/gpdk45/scripts/export_innovus_metal_visual_suite.tcl`

두 script는 checkpoint를 변경하지 않고 layer visibility와 selection만 바꿔 GIF를 출력한다. 이미지 픽셀을 Python·ImageMagick·AI 도구로 가공하지 않았다.
