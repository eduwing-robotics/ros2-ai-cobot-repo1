# 통합 설치와 실행 경계

## PC별 구성

각 PC에서 저장소를 clone하고 담당 디렉터리로 이동합니다. 기존 문서의 `~/KSMC`, `/home/juchan-yoon/FR5_robot_control` 예시는 각각 이 저장소의 `vision-server`, `robot-server`로 치환합니다. 내부 workspace와 설정 경로는 그대로입니다. 기존 설치 폴더를 복사하지 말고 각 PC에서 다시 빌드합니다.

| PC | 작업 디렉터리 | 준비 |
|---|---|---|
| 관제 | `main-server` | PostgreSQL 스키마·계정, mode별 환경, Unity 프로젝트, Sequencer |
| 로봇 | `robot-server` | FR5 드라이버, D435, Hand–Eye/TCP·교시점, 트레이 모델, 공통 Endpoint |
| 비전 | `vision-server` | S22 연결, 컨베이어, GoPro, 학습 모델과 정상 기준 이미지 |

## 통합 Endpoint: 한 인스턴스만 실행

기준 구성에서는 로봇 스택의 `scripts/run_fairino_endpoint.sh`가 FR5 상태 서버와 Unity Endpoint를 실행합니다. Endpoint 소스의 기본 경로는 `../main-server/Ros2UnityEndopoint_PKG`입니다. 다른 경로는 `KSMC_UNITY_ENDPOINT_ROOT`, 로봇 경로는 `FR5_ROOT`로 명시할 수 있습니다.

관제 PC는 로봇 PC의 Endpoint IP/포트에 연결합니다. 이 구성에서 Real Sequencer를 실행할 때에는 중복 Endpoint를 끕니다.

```bash
cd main-server
ros2 launch launch/main_real.launch.py
# 별도 터미널, main-server 디렉터리에서
ros2 launch launch/assembly_real.launch.py start_endpoint:=false
```

관제 PC에서 Endpoint를 실행하는 다른 배치는 로봇 스택의 Endpoint 자동 시작과 함께 사용하지 않습니다. Mock 런치는 관제 영역의 기존 안내대로 별도로 사용합니다. Real domain은 5, Mock은 42입니다.

## 운전 전 준비 순서

1. 각 PC 의존성과 필요한 ROS 메시지를 빌드하고, 같은 Real domain·네트워크를 설정합니다.
2. 로봇 측 보정·모델과 비전 측 정상 기준·학습 가중치, DB 스키마·권한을 준비합니다.
3. 장비 담당자가 기존 실행 안내로 로봇, 카메라·컨베이어·검사 서비스를 준비합니다.
4. MainServer·Real Sequencer를 실행하고 Unity에서 연결·관측·장비 상태를 확인합니다.
5. 완료 이벤트와 검사 결과까지 연결되는 실기 시험은 작업자가 셀 상태를 확인한 뒤 수행합니다.

비전 서버 `--check`는 사전 확인, `--monitor-only`는 이동 요청 거절 모드입니다. `--execute --confirm-motion`은 기존 운영 절차의 명시적 운전 선택입니다. 통합 작업 중 이러한 장비 실행 명령은 수행하지 않았습니다.

## 역할 간 계약

- Sequencer ↔ 로봇: `/real/assembly/*` 실행 명령·상태·이벤트, 확정 슬롯과 완료 식별자.
- Sequencer ↔ 컨베이어: `/conveyor/*` 이동 요청, 요청에 해당하는 도착 상태.
- Sequencer ↔ 검사: `/vision/inspection/*` 요청·상태·결과·이미지.
- Unity ↔ 서버: 작업/진행/품질 이력 API 및 ROS-TCP 상태.

검사 인터페이스는 `main-server/ASSEMBLY_SEQUENCER/src/vision_interfaces`와 `vision-server/ros2_ws/src/vision_interfaces`의 공통 srv 정의를 동일하게 유지합니다. 로봇 영역은 조립용 메시지 구성이 다르므로 서로 덮어쓰지 않습니다.
