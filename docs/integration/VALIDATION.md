# main 통합 검증 · 2026-09-15

## 확인 결과

| 항목 | 결과 | 범위 |
|---|---|---|
| 로봇 실행·비전·supervisor·조립 진행 | 1,021 passed / 1 skipped | fake 장비, synthetic 상태, isolated ROS context |
| Sequencer DB writer·Mock/Real 경계 | 92 passed | Mock 저장소·API 경계, 실 DB 아님 |
| 비전 컨베이어 ROS 로직 | 190 passed | fake 노드·도착/인터록/ROI/검사 규칙 |
| 카메라·오프라인 도구 | 88 passed | 카메라·외부 프로세스 mock |
| 하이브리드 검사 로직 | 344 passed / 2 skipped | 합성 데이터·로직 회귀, 현장 정확도 아님 |
| 검사 서비스 정의 | 3종 동일 | Main/비전 서버 공통 srv |
| 전체 Python 구문 | 683개 확인, 오류 0 | application import/실행 없음 |
| 비전 자체 syntax | Python 199 / shell 107, 오류 0 | 구문 확인 |

총 **1,735개 통과, 3개 생략**. 실패를 통과나 생략으로 숨기지 않고 환경 준비 후 재실행한 최종 결과입니다.

### 생략 항목

- 로봇 `test_whole_contract_roundtrip.py`: 과거 외부 `assembly_execution_client` 모듈에 의존하는 선택 테스트. 현재 Main 브랜치는 `RealBackend`를 사용하므로 이 파일은 자동 생략됨. 이 결과를 전체 장비간 E2E 검증으로 사용하지 않음.
- 검사 테스트 2개: Git에서 제외된 현장 촬영 회귀 이미지가 없어 자동 생략됨.

### 검증 환경

Ubuntu / Python 3.12 / ROS 2 Jazzy. `fairino_msgs`, 관제·검사용 `vision_interfaces`, 로봇 조립용 `vision_interfaces`를 각각 임시 경로에 빌드했습니다. 동명 vision 패키지는 서로 다른 프로세스 환경에서 검사했습니다.

로봇은 기존 로컬 `.venv-vision`과 SMD 가중치를 검증 폴더의 **Git 제외 링크**로 참조했습니다. 가중치는 이 테스트에서 추론하거나 수정하지 않았고 설치 조건 검증에 사용했습니다. 검사 테스트는 기존 Torch 환경을 사용했습니다. DB 테스트는 별도 테스트 환경의 `psycopg`와 mock 저장소를 사용했습니다. 생산 DB 접속·변경, 로봇·그리퍼·컨베이어 이동은 하지 않았습니다.

## 재현 방법

가벼운 소스/인터페이스 확인은 루트에서 실행합니다.

```bash
python3 scripts/check_integration.py
```

각 suite는 담당 디렉터리와 해당 PC의 빌드 환경에서 실행합니다. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`은 ROS launch-testing 플러그인이 선택 테스트의 skip을 전체 수집에 전파하는 것을 방지합니다.

```bash
# 로봇: 로봇용 fairino_msgs / vision_interfaces와 Python 의존성을 먼저 준비
cd robot-server
bash scripts/test_all.sh

# 관제: 관제용 ROS interfaces, psycopg 및 Python 의존성을 먼저 준비
cd main-server
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q ASSEMBLY_SEQUENCER/src/assembly_sequencer/test/test_db_writer.py

# 비전: 별도 터미널, 비전용 ROS interfaces를 source
cd vision-server
PYTHONPATH="$PWD/ros2_ws/src/vision_server${PYTHONPATH:+:$PYTHONPATH}" \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q ros2_ws/src/vision_server/test
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q camera2_scrcpy gopro_camera3 scripts/test_offline_checks.py scripts/test_remote_camera_view.py
# Torch/OpenCV/pytest를 갖춘 검사 환경에서
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q vision_assembly/hybrid_inspection
python3 scripts/run_offline_checks.py --syntax-only
```

위 `cd`는 각각 저장소 루트 기준입니다. 로봇과 관제/검사 overlay를 한 shell에 동시에 source하지 않습니다.

## 통합 시 변경한 부분

- 각 원본 브랜치를 `main-server`, `robot-server`, `vision-server` 아래로 이관하고 출처 SHA 기록.
- 로봇 supervisor/Endpoint 실행기의 개인 절대경로를 저장소 상대 기본값으로 변경. 기존 환경 변수 override는 유지.
- 실제 호출하는 Endpoint `run.sh`를 supervisor 사전 검사에서도 확인하도록 수정.
- supervisor 테스트 fixture를 동일 파일명으로 맞춤.
- GoPro 최신 발행 시각 필드에 맞춰 mock fixture 초기화. 카메라 runtime 변경 없음.
- 25 슬롯 구성 테스트는 추적되지 않는 실측 이미지 대신 임시 합성 기준 이미지를 사용. 실제 판정/보정값 변경 없음.
- robot offline runner의 pytest plugin 자동 수집 비활성화.
- 루트 문서, PC별 운영/Endpoint 중복 방지 안내, 소스 점검 도구 추가.

## 별도 확인이 필요한 범위

Unity 에디터 빌드, 실제 PostgreSQL 스키마 기반 integration suite, 실물 반복 조립·이송·촬영·검사 전체 E2E, 재배치한 경로에서 장비별 런처의 실기 동작은 수행하지 않았습니다. 모델·보정·현장 이미지·DB 계정은 기존 장비 설정을 사용해 운영자가 준비합니다.
