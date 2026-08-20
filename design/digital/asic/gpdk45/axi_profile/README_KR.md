# GPDK045 AXI 포함 비교 profile

이 디렉터리는 기존 core-only 결과와 별도로, 프로젝트가 작성한 AXI-Lite 제어·AXI-Stream 입력 경계를 포함한 디지털 가속기 block의 PPA를 측정하기 위한 독립 profile이다. 아직 이 디렉터리에는 Genus·Innovus PPA 결과가 없으며, 실제 실행 전에는 수치를 주장하지 않는다.

## 고정 구현 경계

- Physical top: `snn_ecg_axi_asic_top`
- AXI accelerator: `snn_ecg_axi_lite_stream_top`
- Canonical classifier: `snn_ecg_30min_final_top`
- Interface: 32-bit AXI-Lite, 12-bit address, 16-bit AXI-Stream input, `irq`
- Core: signed 12-bit ADC, `60000 samples/snapshot`, `30 snapshots/chunk`, `POST_DONE_TICKS=37`
- Feature switches: `PROFILE_EN=0`, `PROF_COUNTER_W=64`, `TLAST_CHECK_EN=1`

`PROFILE_EN=0`은 기존 core-only GPDK045 baseline과 AXI wrapper의 증분 비용을 비교하기 위한 선택이다. 따라서 FPGA full-replay에서 사용한 profiler-enabled build와 동일한 구성이라고 표현하지 않는다. 축소 파라미터는 smoke에서만 사용하며 PPA top은 반드시 위 canonical default로 elaborate한다.

## 포함하는 project-owned RTL

`scripts/rtl_files.tcl`은 다음 재귀 closure를 정의한다.

- canonical core compiled Verilog 15개와 include parameter header 1개
- `design/digital/rtl/common/reset_sync.v`
- `design/digital/rtl/axi/snn_ecg_axi_lite_stream_top.v`
- `rtl/snn_ecg_axi_asic_top.v`

총 compiled Verilog는 18개이며 `strict_recordwise_locked_params.vh`를 별도 hash dependency로 취급한다.

## 의도적으로 제외하는 범위

- `axi_lite_axis_sample_feeder.v`: 별도 host-side replay feeder이며 accelerator IP 경계가 아님
- MicroBlaze, MDM/debug, local memory와 BRAM controller
- AXI SmartConnect/interconnect, AXI INTC, UARTLite
- Clocking Wizard, Processor System Reset과 board clock/reset logic
- block design, packaged-IP metadata, XCI/DCP/bitstream와 모든 Xilinx generated product
- pad, DFT/scan, PG/IR, package, AFE·ADC physical implementation

따라서 이 결과는 AXI 인터페이스를 포함한 accelerator block이지 MicroBlaze SoC 또는 full chip 결과가 아니다.

## Xilinx 의존성 감사

이 closure에는 `BUFG`, `XPM`, `RAMB`, `DSP48`, `UNISIM` 같은 Xilinx primitive 또는 vendor module 인스턴스가 없다. 다음 합성 속성만 존재한다.

- `reset_sync.v`: `ASYNC_REG`
- `qrs_maf_neuron.v`: `ram_style="distributed"`
- `final_membrane_layer.v`: `keep`, `dont_touch`

속성을 지원하지 않는 Cadence tool은 이를 무시할 수 있으며 기능 RTL은 Verilog-2001로 유지된다. Cadence 실행에서는 무시된 속성 warning과 실제 unresolved module을 구분하고, unresolved/empty module이 0인지 별도로 확인한다.

## 제약과 비교 규칙

`constraints/axi_100mhz.sdc`는 core-only profile과 같은 100 MHz, setup/hold uncertainty 0.2/0.1 ns, I/O delay 1 ns, input/clock transition 0.1 ns, output load 0.020 pF를 사용한다. Active-low external reset은 3-stage synchronizer의 asynchronous reset 입력이므로 일반 data input delay에서 제외하고 false path로 둔다.

Core-only와 AXI 포함 수치를 비교하려면 같은 Liberty/LEF/QRC, optimization stage, floorplan policy와 activity 가정을 사용해야 한다. 차이는 AXI register channel, stream FIFO, status/error counters, IRQ와 TLAST 검사 로직을 포함하지만 MicroBlaze subsystem 비용은 포함하지 않는다.

## Smoke 범위

`sim/tb_snn_ecg_axi_asic_smoke.v`는 `8 samples/snapshot × 2 snapshots`의 synthetic 16-sample 실행에서 다음을 검사한다.

- ASIC wrapper와 동일 parameter의 원본 AXI top functional output cycle comparison
- AXI-Lite AW/W 동시·분리 handshake와 stalled read-data 안정성
- start-while-busy error 및 clear
- AXI-Stream backpressure, accepted/consumed count와 TLAST 검사
- sticky done/IRQ/result register와 clear
- `PROFILE_EN=0`에서 profile accepted count가 0인지 확인

이 smoke는 default `60000 × 30` 실제 ECG regression, 36-case 정확도, formal equivalence 또는 PPA 결과가 아니다.

## 로컬 정적·smoke 검증

2026-08-21에 Vivado Simulator 2020.2로 source 18개와 testbench를 compile·elaborate하고 reduced smoke를 실행했다.

- source file 존재·중복 검사: 19/19 file path 존재, duplicate module name 0
- Xilinx primitive/XPM instance 정적 검색: 0
- `xvlog` compile: PASS
- `xelab` static elaboration: PASS
- `xsim`: `AXI_ASIC_SMOKE_PASS samples=16`

Elaboration에는 locked core의 abandoned IPB stub 경계에 존재하는 기존 8-bit→4-bit port warning 4개가 남는다. 새 AXI wrapper에서 추가된 unresolved module 또는 compile error는 없었다. 이 로컬 결과 역시 canonical workload 검증으로 확대하지 않는다.

Cadence Xcelium 실행 예시는 repository root 기준이다.

```csh
xrun -64bit -sv -f design/digital/asic/gpdk45/axi_profile/scripts/xcelium_axi_smoke.f \
  -top tb_snn_ecg_axi_asic_smoke
```
