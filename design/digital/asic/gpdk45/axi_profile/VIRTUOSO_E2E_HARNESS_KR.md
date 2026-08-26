# Virtuoso ADC → 디지털 E2E 하네스

이 하네스는 팀원의 Virtuoso/Spectre AFE·ADC 결과를 파일로 넘겨받아, 같은 12-bit ADC code stream을 다음 두 디지털 경로에 동시에 입력한다.

1. `snn_ecg_asic_core_top`: classifier direct-core 경로
2. `snn_ecg_axi_asic_top`: 실제 ASIC PPA 경계인 AXI-Lite control + AXI-Stream data 경로

두 경로의 최종 class와 NSR/CHF/ARR/AFF membrane을 bit-exact 비교하고, AXI가 1,800,000 samples를 전부 accepted/consumed했는지도 확인한다. expected class·membrane과 다른 결과, `X/Z`, sample 수 오류, TLAST 오류, AXI error, timeout은 모두 실패다.

## 팀원에게 받을 파일

Virtuoso 결과는 다음 CSV 형식이 가장 좋다.

```csv
time_sec,adc_code
0.000,2048
0.001,2051
0.002,2046
```

- `time_sec`: strictly increasing, 정확히 1 kSPS이며 1 ns 이내의 period 오차
- `adc_code`: 12-bit ADC integer code `0..4095`
- encoding: 기본 계약은 offset-binary
- 길이: 한 30분 case당 정확히 1,800,000 samples
- analog 측에서 volts를 임의로 재정규화하지 말고, 실제 ADC quantizer가 낸 code를 전달

offset-binary 입력은 디지털 signed code로 넘기기 전에 MSB를 한 번 반전한다.

```text
signed_bits[11:0] = {~adc_code[11], adc_code[10:0]}
```

이미 signed two's-complement 12-bit hex `.mem`인 파일도 기존 회귀 fixture용으로 받을 수 있다. 다만 `.mem`에는 timestamp가 없으므로 1 kSPS cadence를 증명하지 못한다. 실제 analog handoff acceptance에는 timestamp가 있는 CSV를 사용한다.

## 1. 입력만 검사·정규화

```powershell
python -B tools/verification/prepare_virtuoso_adc_dump.py `
  --input C:\handoff\AFF.csv `
  --output C:\handoff\AFF_signed12.mem `
  --metadata C:\handoff\AFF_signed12.json `
  --format csv `
  --encoding offset_binary `
  --sample-rate-hz 1000 `
  --expected-samples 1800000 `
  --require-cadence
```

변환기는 입력 SHA-256, 정규화 출력 SHA-256, sample count, signed min/max와 cadence 오차를 JSON에 기록한다. 출력 파일은 canonical signed two's-complement 12-bit hex이며 한 줄에 한 sample이다.

## 2. manifest 작성

`manifests/representative_xmodel4.csv`를 복사해 case별 입력 경로와 encoding을 바꾼다. expected class와 네 membrane은 동일 ECG 원본을 사용한 승인된 XMODEL/direct-core 기준값이어야 한다. 결과를 먼저 본 뒤 expected를 고쳐 쓰면 검증이 아니므로 허용하지 않는다.

필수 열은 다음과 같다.

```text
case_id,case_name,expected_class,sample_count,
expected_mem_nsr,expected_mem_chf,expected_mem_arr,expected_mem_aff,
input_path,input_format,input_encoding
```

## 3. 로컬 XSim 실행

```powershell
python -B tools/verification/run_virtuoso_adc_e2e.py `
  --manifest C:\handoff\virtuoso_cases.csv `
  --simulator xsim `
  --result-dir verification\virtuoso_adc_e2e\results\virtuoso_signoff
```

실행기는 입력을 다시 검증·정규화한 뒤 한 번 compile/elaborate하고 모든 case를 순차 replay한다. PASS marker가 없거나 CSV의 한 case라도 실패하면 process도 실패한다. 결과 폴더에는 사용자명·host·절대경로를 제거한 summary, result, provenance, simulator log만 남긴다. 1,800,000-sample dump 복사본과 simulator work database는 임시 디렉터리에서 삭제된다.

## 4. Cadence Xcelium 실행

서버의 임시 작업 폴더에 repository와 analog dump를 복사한 다음 다음과 같이 실행할 수 있다.

```csh
source ~/control_digi.cshrc
cd <temporary-repository-copy>
python3 -B tools/verification/run_virtuoso_adc_e2e.py \
  --manifest <virtuoso-manifest.csv> \
  --simulator xrun \
  --xrun /home/tools/cadence/XCELIUMMAIN2309/tools/bin/64bit/xrun \
  --result-dir <temporary-result-directory>
```

Xcelium 설치·file-list 호환성만 빠르게 교차 확인할 때는 `--case-id 9`처럼 manifest의 한 case를 선택할 수 있다. 최종 analog acceptance에는 옵션을 빼고 전달받은 모든 case를 실행한다.

서버에 Python 3이 없으면 testbench의 `+MANIFEST`, `+RESULT` plusarg 진입점을 직접 사용한다. 다음 예시는 대표 1개만 교차 확인하는 명령이며, 최종 acceptance에는 4-case 또는 실제 Virtuoso manifest를 지정한다.

```csh
cd <temporary-repository-copy>
/home/tools/cadence/XCELIUMMAIN2309/tools/bin/64bit/xrun -64bit -sv \
  -f design/digital/asic/gpdk45/axi_profile/scripts/xcelium_virtuoso_e2e_rtl.f \
  -top tb_snn_ecg_axi_virtuoso_e2e \
  +MANIFEST=design/digital/asic/gpdk45/axi_profile/manifests/representative_xmodel_case9.sim_manifest \
  +RESULT=<temporary-result.csv>
```

`-sv`는 testbench의 fail-closed `$fatal` 처리를 위해 필수다. 이 옵션이 없으면 Xcelium이 `.v`를 IEEE 1364-2001로 해석해 elaboration에서 중단한다.

결과 폴더만 로컬로 회수한 뒤 서버의 temporary repository, analog dump와 Xcelium work database를 지운다. 접속 host/account/password와 원격 절대경로는 manifest, script, report 또는 Git에 넣지 않는다.

## 5. post-route GLS 재사용 경계

testbench는 `AXI_SDF_FILE` macro가 정의되면 `dut`에 SDF를 annotate할 수 있게 작성되어 있다. Run-6 post-route netlist, 정확히 대응하는 SDF, GSCLIB045 Verilog cell model로 AXI RTL top을 대체하면 같은 input/result checker를 GLS에도 재사용할 수 있다. 그러나 현재 대표 실행은 RTL simulation이며, post-route SDF back-annotation 결과로 확대해 표현하지 않는다.

## 검증 범위

이 하네스가 증명하는 것은 다음과 같다.

- 전달된 ADC code가 정해진 signed contract로 변환됨
- 해당 code stream에 대한 direct-core와 AXI wrapper의 디지털 결과가 같음
- manifest의 사전 고정 expected class·membrane과 bit-exact 일치함
- AXI protocol 경계가 전체 30분 sample을 빠뜨리지 않음

Virtuoso transistor simulation으로 만든 CSV를 넣어야만 AFE·ADC 회로 출력까지 이어진 ETE 증거가 된다. 기존 XMODEL `.mem`으로 통과한 결과는 하네스와 디지털 경로 검증이지, 팀원의 실제 analog 회로 검증은 아니다. mixed-signal transistor-level co-simulation, package/parasitic, PVT/Monte Carlo, DRC/LVS 또는 silicon 측정도 별도 범위다.
