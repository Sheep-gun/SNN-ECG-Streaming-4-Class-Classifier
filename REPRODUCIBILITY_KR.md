# 재현 안내

## 고정 환경

- Digital fixed source: `c6b80de19cdcad5b7e43fe7835588b629d847f75`
- Timing pipeline history: `c7c75cfebf7add12bfcc32bb59d5edf38ac6e5aa`, `5e2e5d0a46be47d8086b8642e055066079bfa4e6`
- MATLAB fixed source: `907f7e1f081a9d6a5703a32095d962143315a192`
- XMODEL fixed source: `4756a5086023547328ef44fd5fd87da3c250dc39`
- Vivado: 2020.2
- FPGA: Artix-7 XC7A100T-CSG324-1
- ASIC exploratory flow: Cadence Xcelium 23.09, Genus/Innovus 23.14, Conformal 24.1, GPDK045 GSCLIB v4.7
- Stream: 1 kSPS signed 12-bit two's complement

## 1. 데이터 준비

```powershell
python tools/fetch_physionet_datasets.py
python tools/verify_physionet_datasets.py
python tools/data/generate_locked_digital_36case.py
```

PhysioNet raw data와 generated input은 Git 외부 workspace path에 생성한다. checksum과 record 목록은 `datasets/dataset_manifest.yaml`을 따른다.

## 2. Python과 Exact C++

Python equivalence:

```powershell
python models/digital_equivalence/tools/check_python_equivalence.py
```

Exact C++:

```powershell
cmake -S models/digital_equivalence/exact_cpp -B build/exact_cpp
cmake --build build/exact_cpp --config Release
python models/digital_equivalence/exact_cpp/tools/run_cpp_equivalence.py
```

Exact C++ 결과를 benchmark로 사용하기 전 fixed-width, module trace, sample state, Snapshot과 final equivalence gate를 모두 통과해야 한다.

## 3. Pure RTL Vivado

```powershell
vivado -mode batch -source tools/vivado/generate_readable_rtl_elaborated_schematic.tcl
```

GUI project:
`vivado/pure_rtl/project/SNN_ECG_PURE_RTL_VISUALIZATION.xpr`

## 4. MicroBlaze Vivado

GUI project:
`vivado/microblaze/SNN_ECG_MB_FULL_REPLAY.xpr`

Project IP repository path가 이동한 경우 `design/digital/ip_repo/`를 지정하고 IP Catalog refresh 후 Block Design을 validate한다.

## 5. raw XMODEL output replay

```powershell
python tools/verification/run_xmodel_adc_pure_rtl_replay.py
```

현재 저장소는 raw full-30분 XMODEL accepted file 4개만 보존한다. 32개를 재생성하지 않으면 이 단계는 4-case audit로 완료되며 36-case raw replay PASS를 선언하지 않는다.

## 6. GPDK045 core-only ASIC flow

Wrapper, 100 MHz SDC와 tool script는 `design/digital/asic/gpdk45/`에 있다. GPDK045 library와 Cadence tool은 외부 licensed dependency이며 저장소에 포함하지 않는다. 실행은 `snn_ecg_asic_core_top`, `PROFILE_EN=0`, 100 MHz, slow 1.08 V/125 °C setup과 fast 1.32 V/0 °C hold view를 사용한다. 두 view에 같은 `gpdk045.tch`를 사용했으므로 독립적으로 특성화된 max/min RC corner로 해석하지 않는다.

새 실행은 외부 임시 workspace에서 수행하고 필요한 결과를 local에 회수해 SHA-256을 확인한 뒤 원격 work directory와 process를 삭제한다. 공개 결과와 제약은 `verification/asic_gpdk45_core/README_KR.md`와 `tables/asic_gpdk45_ppa.csv`를 따른다. 실제 실행 파일은 `verification/asic_gpdk45_core/executed_snapshot/`, post-run hardened flow는 `design/digital/asic/gpdk45/`로 구분한다. 접속 정보, 라이선스 서버와 절대경로는 Git에 기록하지 않는다.

Run-2는 run-1을 덮어쓰지 않고 `verification/asic_gpdk45_run2/`에 별도 보존한다. Scan-free core와 `snn_ecg_axi_asic_top` AXI block은 같은 100 MHz·Liberty·LEF·QRC 기준을 사용하고, slow early 0.95와 fast late 1.05의 fixed engineering derate를 OCV assumption으로 적용했다. 이는 foundry-characterized AOCV/POCV/LVF가 아니다.

Run-2 functional authority는 `manifests/canonical_digital_36.manifest`의 regenerated digital 36-case와 `manifests/raw_xmodel_4.manifest`의 actual XMODEL 4-case를 구분한다. Post-route LEC는 mapped→post-route 논리 등가성이며 timing 또는 분류 정확도 근거가 아니다. Forced two-state gate 결과와 timing check를 끈 single-seed MAX-SDF pilot은 unmodified four-state GLS PASS가 아닌 sampled initialization-sensitivity 실험으로만 사용한다. Exploratory PG attempt는 실패 근거로 보존하며 PG·IR·EM 구현을 주장하지 않는다.

Core activity power는 `verification/asic_gpdk45_run2/power/activity_power_summary.csv`와 `activity_annotation_summary.txt`를 authority로 사용한다. 모든 window는 seed11-conditioned mapped gate 6,045/6,045, `-access +rwc`, zero delay이며, normalized SAIF parse에서 fully-X/Z entry를 보존하고 unannotated default 0을 사용했다. Parse/annotation status PASS는 numeric annotation coverage PASS가 아니다. Accelerated gap2 full-record, active-wait idle와 100-sample literal 1 kSPS prefix는 서로 다른 cadence이므로 혼합하지 않으며, prefix는 Snapshot/decision에 도달하지 않는다. Matched delta는 energy/decision이 아니고 AXI에는 activity-based result가 없다.

Run-3 hold closure는 `extract_violating_hold_endpoints.py`, `manual_hold_endpoint_eco.tcl`, `hold_resize_only.tcl`, `export_hold_closed_candidate.tcl`과 `run_postroute_lec.do`로 재현한다. Run-2 checkpoint와 PDK를 새 private work root에 복원하고 OCV·hold uncertainty를 유지한 채 endpoint ECO와 재추출을 수행한다. Core는 hold·data-transition·clock-slew·internal-DRC closure, AXI는 hold closure만 달성했다. Public 결과는 `verification/asic_gpdk45_hold_closure/`, raw DB/netlist/DEF/SDF/SPEF는 Git 밖의 checksum archive에 보존한다.

## 7. repository 검사

```powershell
python tools/check_clean_workspace.py
python tools/check_integrated_technical_report.py
python tools/check_integrated_repository.py
git diff --check
```

검사기는 핵심 파일, 수치, 두 Vivado project, claim/evidence mapping, private path와 절대경로 누출을 fail-closed로 검사한다.
