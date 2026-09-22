# 구현과 재현 안내

[설계보고서 전문](reports/INTEGRATED_TECHNICAL_REPORT_KR.md) · [데이터셋 구성 및 학습](docs/04_DATASET_AND_TRAINING_KR.md) · [검증 결과](docs/05_VERIFICATION_AND_RESULTS_KR.md)

## 구현 파일

| 항목 | 경로 |
| --- | --- |
| AXI를 포함한 3클래스 RTL | [`design/digital/rtl/rhythm3_duration_v3/`](design/digital/rtl/rhythm3_duration_v3/) |
| RTL 최상위 모듈 | `rhythm3_axi_event_cf_1v8` |
| RTL 소스 목록 | [`sources.f`](design/digital/rtl/rhythm3_duration_v3/sources.f) |
| 고정된 분류 모델 | [`frozen_model.json`](models/rhythm3_duration/results_v3/frozen_model.json) |
| 모델 해시 | [`freeze_receipt.json`](models/rhythm3_duration/results_v3/freeze_receipt.json) |
| 모델 학습·정수 계산 | [`train_hierarchy.py`](models/rhythm3_duration/train_hierarchy.py) |
| Snapshot/Final RTL 생성 | [`generate_readout.py`](models/rhythm3_duration/generate_readout.py) |
| C++ 특징 추출 | [`extract_snapshots.cpp`](models/rhythm3_duration/extract_snapshots.cpp), [`exact_cpp`](models/digital_equivalence/exact_cpp/)의 특징 추출 구현 |
| 특징 누적값 → 분류 RTL 대조 | [`verify_readout.py`](models/rhythm3_duration/verify_readout.py) |
| ADC → 코어 / AXI 대조 | [`verify_core.py`](models/rhythm3_duration/verify_core.py), `--axi`로 AXI 경로 선택 |
| 라벨과 기록 분할 | [`datasets/rhythm3_duration_v3/`](datasets/rhythm3_duration_v3/) |
| 고정 모델의 최종 시험 결과 | [`test_result.json`](models/rhythm3_duration/results_v3/test_result.json) |
| 보고서 그림 | [`figures/report_2026/`](figures/report_2026/), SVG |

## 공개 파일 확인

저장소 루트에서 Python 3로 실행한다. 고정 모델과 RTL 소스 목록, 문서 링크 및 그림 파일을 확인한다.

```sh
python tools/check_report_publication.py
```

NumPy가 설치된 Python에서 고정 모델의 readout을 생성할 수 있다. 출력 경로는 존재하지 않는 새 폴더로 지정한다.

```sh
python models/rhythm3_duration/generate_readout.py \
  --model models/rhythm3_duration/results_v3/frozen_model.json \
  --out tmp/rhythm3_readout
```

생성된 `rhythm3_snapshot_final_readout.sv`는 공개 RTL과 동일해야 한다. PowerShell에서는 위 명령을 한 줄로 입력한다.

## RTL 기능 시뮬레이션

검증 스크립트는 Windows Vivado 2020.2의 `C:/Xilinx/Vivado/2020.2/bin`을 사용한다. `sources.f`의 경로는 해당 파일이 있는 디렉터리를 기준으로 해석한다. 기능 시뮬레이션에는 `MEMBRANE_FUNCTIONAL_MODEL`을 정의하고 [`TLATNTSCAX4_functional.v`](verification/low_power_gals_research/models/TLATNTSCAX4_functional.v)를 추가한다. 이 모델은 기능 검증용이며 물리 셀이나 전력 모델이 아니다.

`verify_readout.py`와 `verify_core.py`에는 `--repo`, `--dataset`, `--work`, `--model`, `--rtl`, `--out` 경로가 필요하다. `--work`에는 외부 ADC 코드, 특징 CSV와 해시 영수증이 있어야 한다. 원시 ECG, 대용량 ADC 코드와 전체 시뮬레이션 로그는 이 저장소에 포함하지 않았다. 따라서 공개 파일만으로 전체 96건 검증이나 배치배선 전력 분석이 즉시 재실행되는 것은 아니다.

클래스 번호는 NSR=0, AF=1, OTHER=2이다. 결과 포트 `final_mem_aff`는 AF, `final_mem_arr`는 OTHER에 연결되며, `final_mem_chf`는 0으로 고정된 예약 슬롯이다.

물리 구현에는 별도의 GPDK045/Cadence 환경과 프로젝트용 A18 셀 view가 필요하다. `physical_icg_binding.sv`는 외부 `a18_icg_probe`의 연결만 정의한다. PDK와 도구 라이선스, 전체 셀 라이브러리 및 배치배선 데이터베이스는 배포하지 않는다.

원시 데이터의 출처와 이용 조건은 [데이터 라이선스](datasets/DATASET_LICENSES.md)를 따른다.
