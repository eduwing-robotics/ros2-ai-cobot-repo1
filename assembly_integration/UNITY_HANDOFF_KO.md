# Unity 조립 진행상태 연동 안내

## 전달 파일

- `AssemblyProgressSynchronizer.cs`: ROS 2 조립상태 토픽을 수신하는 Unity 컴포넌트
- `assembly_recipe.yaml`: 25개 부품의 조립 순서와 `part_id`, `slot_code` 정의
- `assembly_progress_sample.json`: Unity에서 수신하게 될 메시지 예시

## 연결 정보

- ROS-TCP Endpoint IP: 로봇 PC의 LAN IP
- ROS-TCP Endpoint 포트: `10000`
- ROS 버전: ROS 2
- 구독 토픽: `/assembly/progress`
- 메시지 타입: `std_msgs/msg/String`
- String 내부 데이터: JSON
- JSON 스키마: `fr5.assembly.progress/v1`

## Unity 설정

1. Unity 프로젝트에 ROS-TCP Connector와 Newtonsoft JSON 패키지가 있어야 한다.
2. `AssemblyProgressSynchronizer.cs`를 `Assets/Scripts`에 복사한다.
3. 씬에서 조립 전체 시간 동안 유지되는 빈 GameObject를 만든다.
4. 해당 GameObject에 `AssemblyProgressSynchronizer`를 추가한다.
5. Unity의 Robotics/ROS Settings에서 ROS 2, 로봇 PC IP, 포트 `10000`을 설정한다.
6. UI 또는 부품 표시 스크립트에서 `ProgressChanged` 이벤트를 구독한다.

## Unity에서 사용할 값

- `CycleId`: 현재 생산 사이클 ID
- `CompletedCount`: 조립 완료 개수
- `TotalCount`: 전체 개수, 현재 25
- `NextSlotCode`: 다음 조립 슬롯 코드
- `AssembledSlots`: DB에 완료로 저장된 슬롯 코드 집합

`AssembledSlots`에 슬롯이 추가되었을 때 해당 패키지판 부품을 조립 완료 상태로 표시한다.
카메라 기반 트레이 부품 표시는 기존 `/vision/tray/unity_state`와
`TrayVisionSynchronizer.cs`를 그대로 사용한다.

## 권장 슬롯 표시 규칙

- 아직 조립되지 않은 슬롯: 빈 슬롯 또는 반투명 부품
- `NextSlotCode`와 같은 슬롯: 노란색 강조
- `AssembledSlots`에 포함된 슬롯: 실제 부품 표시 또는 초록색 완료 표시
- `cycle_status == COMPLETE`: 전체 조립 완료 UI 표시

## 메시지 처리 규칙

- `schema`가 `fr5.assembly.progress/v1`이고 `valid`가 `true`인 메시지만 처리한다.
- `sequence`가 이전 메시지보다 클 때만 화면을 갱신한다.
- `assembled` 배열은 DB에서 확정된 완료 상태이므로 Unity가 자체적으로 완료를 추측하지 않는다.
- 동일 단계 완료 메시지가 다시 와도 `slot_code` 기준으로 한 번만 표시한다.
- Unity는 로봇 명령을 보내지 않고 진행상태만 표시한다.

## 부품 ID와 개수

| part_id | 의미 | 개수 | 슬롯 |
|---|---|---:|---|
| HBM | HBM | 8 | HBM-01 ~ HBM-08 |
| PM | Power Module | 4 | PM-01 ~ PM-04 |
| GPU | GPU | 1 | GPU-01 |
| HBM | HBM | 8 | HBM-01 ~ HBM-08 |
| PM | Power Module | 4 | PM-01 ~ PM-04 |
| VRM | VRM | 5 | VRM-01 ~ VRM-05 |
| IND | Inductor | 2 | IND-01 ~ IND-02 |
| CAP | SMD Capacitor | 5 | CAP-01 ~ CAP-05 |

ROS PC에서 Endpoint와 Unity를 연결한 후 다음 토픽을 확인한다.

```bash
ros2 topic echo /assembly/progress std_msgs/msg/String
```

테스트 사이클 생성 예시:

```bash
source scripts/ksmc_env.sh
python3 assembly_integration/assembly_progress.py start --cycle-id unity-test-001
python3 assembly_integration/assembly_progress.py complete-step \
  --cycle-id unity-test-001 --order 1 --source-instance 1
```

두 번째 명령 후 Unity에는 `CompletedCount=1`, `NextSlotCode=HBM-01`,
`AssembledSlots`에 `GPU-01`이 표시되어야 한다.

## 현재 제한사항

현재 패키지판에서 물리 좌표가 등록된 것은 CAP 5개 슬롯이다. HBM, PM,
GPU, IND, VRM의 총 20개 슬롯은 위치·각도·배치 높이 교시 전이므로 실제
25단계 자동조립은 차단되어 있다. 이 제한은 Unity 화면 연동 테스트에는
영향이 없다.
