# Literal-1-kSPS short-prefix activity experiment

이 실험은 기존 `gap=2` full-record xReplay와 목적이 다르다.

- `gap=2` full record: 1,800,000 samples를 약 5.4 M clock에 처리하는 accelerated-throughput activity
- literal 1 kSPS prefix: 100 MHz에서 sample당 100,000 clocks, 즉 1 processing clock과 99,999 intervening clocks

기본 prefix는 기존 FPGA activity 방법과 같은 raw ECG 100 samples다. 측정 창은 정확히 10,000,000 clocks, 0.1 s이며 60,000-sample snapshot이나 30-minute decision에 도달하지 않는다.

이는 기록 시작의 짧은 initial prefix이므로 steady-state ECG, QRS-event 분포 또는 클래스 대표 활동이라고 주장하지 않는다. 최소 추가 실험은 raw case 한 개의 matched pair이며, 여러 클래스에 대한 반복은 별도 확장 실험이다. 99,999 intervening clocks에는 sample 직후의 내부 처리/hold cycle도 포함되므로 모두 완전 무활동 clock이라고 부르지 않는다.

이 설계의 기존 기능 golden은 `sample_gap_cycles=2` cadence에 고정돼 있다. Literal-1-kSPS schedule은 always-clocked activity를 관측하기 위한 별도 실험이며, canonical class/membrane expected output을 대체하거나 같은 기능 궤적이라고 가정하지 않는다.

## Matched windows

같은 초기화·start·warmup 뒤 동일한 0.1 s 길이로 두 SHM을 만든다.

1. `MODE=0`: core가 실행 중이지만 입력을 기다리는 active-wait idle
2. `MODE=1`: 같은 core 상태에서 raw sample을 100,000 clocks마다 하나씩 수락

`MODE=0` 전력은 순수 clock-tree 전력만이 아니라 leakage, 항상 켜진 100 MHz clock과 active-wait 상태의 내부 활동을 포함한다. `MODE=1 - MODE=0` 차이는 동일 조건에서 sample input 전송과 sample-triggered state update가 추가한 증분 추정치다. Clock network와 non-clock idle logic을 더 세분하려면 power report의 clock/hierarchy category를 별도로 사용한다.

Literal mode에서는 `sample_valid=0`인 intervening clocks 동안 `adc_data`를 마지막 수락 sample에 유지한다. 매 sample 뒤 0으로 되돌리는 인위적 input toggle을 만들지 않는다.

두 mode에서 total/internal/switching/leakage를 각각 보존한다. Leakage를 임의로 제거하거나 음수 차이를 0으로 바꾸지 않는다. 증분 에너지/sample을 계산한다면 matched-window 평균 전력 차이를 1,000 samples/s로 나눈 조건부 값으로만 표시한다.

## 생성과 실행

Prefix 생성 예:

```text
python design/digital/asic/gpdk45/tools/build_literal_1ksps_prefix.py \
  --input-mem <raw-1.8M.mem> --output-dir <run>/power_prefix \
  --samples 100 --case-id <id> --class-label <label>
```

두 Xcelium 실행은 `scripts/xcelium_power_prefix.f`를 사용하고 각각 다음 plusarg를 준다.

```text
+MODE=0 +PREFIX_SAMPLES=100 +CYCLES_PER_SAMPLE=100000 +DUMP_SYNC=1
+MODE=1 +MEM=<prefix100.mem> +PREFIX_SAMPLES=100 +CYCLES_PER_SAMPLE=100000 +DUMP_SYNC=1
```

`scripts/xcelium_dump_power_prefix_shm.tcl`은 testbench의 두 `$stop` 사이, 즉 matched measurement window만 SHM으로 저장한다. 두 SHM은 별도 tag로 Joules xReplay하고 같은 mapped netlist/checkpoint에서 power report를 생성한다.

Xcelium에서 직접 SAIF를 만들 때는 반드시 elaboration에 `-access +rwc`를 주고, raw SAIF를 Innovus에 바로 넣지 않는다. 빈 `DESIGN`, testbench wrapper와 Xcelium의 escaped multidimensional signal name을 다음처럼 정규화한 출력만 `ACTIVITY_FILE`로 사용한다.

```text
python design/digital/asic/gpdk45/tools/normalize_xcelium_saif_for_innovus.py \
  --input-saif <xcelium-raw.saif> --output-saif <innovus.saif> \
  --top snn_ecg_asic_core_top \
  --tb-instance tb_snn_ecg_asic_power_prefix \
  --dut-instance snn_ecg_asic_core_top
```

Full-record harness에는 `--tb-instance tb_snn_ecg_asic_core_manifest`를 사용한다. 변환기는 구조·크기·이름을 검사한 뒤 같은 디렉터리에서 원자적으로 게시하며, raw/normalized SAIF는 저장소에 커밋하지 않는다.

기본값은 fully-X/Z signal entry도 그대로 보존한다. 이번 공개 power run도 이 preserve mode로 실행했고 unannotated default activity는 0.0이었다. Fully-X/Z entry만 제거하는 별도 진단이 필요할 때에만 `--drop-full-xz`를 명시하며, reset release까지의 partial startup `TX`는 제거하거나 0으로 바꾸지 않는다. 변환기 자체 검사는 다음으로 실행한다.

```text
python design/digital/asic/gpdk45/tools/normalize_xcelium_saif_for_innovus.py --self-test
```

## Claim boundary

이 결과는 always-clocked active-wait baseline과 100-sample raw prefix의 literal-1-kSPS 증분 활동을 보여줄 뿐이다. 다음을 주장하지 않는다.

- 60-second snapshot workload power
- 30-minute final-decision average power 또는 energy/decision
- full-record class/membrane equivalence
- clock gating, power gating 또는 silicon measured power
