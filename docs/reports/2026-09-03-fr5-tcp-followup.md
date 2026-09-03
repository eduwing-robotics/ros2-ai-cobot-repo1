# FR5 그리퍼 TCP 위치 불일치 추가 조사 보고서

- 작성일: 2026-09-02
- 추가 기준: 사용자 지정 기준본 `Trash/Farino_AIO_leg`
- 기준본 보존 상태: 로컬 격리 자료로 Git에는 포함되지 않으며, 이 보고서는 비교 결과와 해시만 보존한다.
- 비교 대상: 기준본, 현재 `Farino_AIO_Mock`, Unity URDF와 현재 Scene TCP
- 선행 보고서: [2026-09-02 선행 보고서](2026-09-02-fr5-tcp-investigation.md)

## 1. 추가 조사 결론

`Trash/Farino_AIO_leg`를 기준본으로 추가 비교한 결과, 0902 보고서의 핵심 판단은 유지되며 다음과 같이 더 구체화된다.

1. **상하 위치 차이는 FR5 팔 또는 그리퍼의 축방향 URDF 변경 때문에 발생한 것이 아니다.** 기준본, 현재 ROS URDF와 Unity URDF의 `wrist3_link → 플랜지 99 mm`, 어댑터 `10 mm`, 핑거 시작 `138 mm`, 핑거 길이 `18 mm`가 모두 같다.
2. **Unity URDF는 기준본의 실측 좌우 배치를 유지하고 있다.** 오히려 현재 `Farino_AIO_Mock` ROS URDF가 기준본의 비대칭 좌우 위치를 대칭값으로 변경했다. 이 차이는 좌우 중심에 영향을 주지만 공구축/상하 오차의 원인은 아니다.
3. **기준본에는 TCP link/Transform이나 수치형 Tool offset이 없다.** 따라서 기준본은 현재 Scene TCP `146.73 mm` 또는 Mock의 `274.073 mm`를 직접 정답으로 지정하지 않는다.
4. **기준본에는 `mock_sim.py` 자체가 없다.** 현재 Mock 기본값 `274.073 mm`는 기준본에서 계승된 정격값이 아니라 이후 Mock 통합 과정에서 추가된 값이다.
5. 기준본과 현재 ROS의 FR5 및 PGEA 메시 파일은 바이트 단위로 동일하다. 형상 파일 교체로 인한 상하 오차도 확인되지 않았다.
6. 기준본의 실물 상태 전달 코드에는 TCP와 플랜지 위치를 별도로 저장할 필드가 있지만, CNDE 수신 경로에서 두 필드에 동일한 `tcp_pos`를 기록한다. 따라서 이 경로의 상태 메시지만으로는 실제 `TCP - flange` 오프셋을 독립적으로 계산할 수 없다.

따라서 현재 증상은 다음 두 기준 불일치로 해석하는 것이 가장 타당하다.

- 물리적 커스텀 핑거 외곽 끝과 현재 Scene TCP 사이: 약 `9.27 mm`
- 현재 Scene TCP와 Mock의 오래된 Tool offset 사이: 축방향 `18.343 mm`

## 2. 기준본의 성격과 적용 범위

기준본 README는 이 폴더를 FAIRINO Chapter 11~14 통합 워크스페이스로 설명하며, 실물 Digital Twin 실행 경로로 `real_robot.launch.py`를 사용한다.

관련 파일: `Trash/Farino_AIO_leg/README.md` (로컬 기준본 경로)

다만 기준본의 FR5 URDF에는 FAIRINO 순정 팔 모델뿐 아니라 다음 프로젝트별 항목이 이미 추가되어 있다.

- DH-Robotics PGEA-100-40 그리퍼
- 실물의 10 mm 어댑터 플레이트
- PGEA STL 축 변환과 X축 반전
- 실측 jaw face 위치
- 18 mm 커스텀 핑거를 나타내는 box link

따라서 이 폴더는 제조사 순정 배포본 그 자체라기보다, **사용자가 지정한 프로젝트 실물 기준본**으로 해석했다. 제조사 순정 FR5 관절 체인과의 대조는 FAIRINO 공식 ROS2 URDF로 별도 확인했다.

- 기준 URDF: `Trash/Farino_AIO_leg/.../fairino5_v6.urdf` (로컬 기준본 경로)
- [FAIRINO 공식 FR5 URDF](https://github.com/FAIR-INNOVATION/frcobot_ros2/blob/main/fairino_description/urdf/fairino5_v6.urdf)

## 3. 메시 파일 동일성 확인

SHA-256을 비교한 결과 기준본과 현재 `Farino_AIO_Mock`의 FR5 팔 메시 7개가 모두 동일했다.

| 메시 | 기준본과 현재 ROS 비교 |
|---|---|
| `base_link.STL` | 동일 |
| `shoulder_link.STL` | 동일 |
| `upperarm_link.STL` | 동일 |
| `forearm_link.STL` | 동일 |
| `wrist1_link.STL` | 동일 |
| `wrist2_link.STL` | 동일 |
| `wrist3_link.STL` | 동일 |

PGEA 메시도 기준본, 현재 ROS와 Unity에 있는 세 파일의 SHA-256이 모두 아래 값으로 동일했다.

```text
3a7286260c9ab5d00c60a8cbef6b18a5c990b6b1595ed64fc76631f224d0e36e
```

- 기준본: `pgea_100_40.stl` (로컬 기준본 경로)
- 현재 ROS: [`pgea_100_40.stl`](../../Farino_AIO_Mock/src/fairino_description/meshes/gripper/pgea_100_40.stl)
- Unity: [`pgea_100_40.stl`](../../UnityDT/Assets/URDF/Sources/FR5/meshes/gripper/pgea_100_40.stl)

이 결과는 로봇 또는 그리퍼 메시 파일 버전 차이가 현재 위치 증상의 원인이 아님을 확인한다.

## 4. URDF 좌표 상세 비교

### 축방향 좌표

공구축 방향 좌표는 기준본, 현재 ROS와 Unity에서 모두 같다.

| 항목 | 기준본 | 현재 ROS | Unity | 판정 |
|---|---:|---:|---:|---|
| `gripper_adapter_joint` Z | `0.099 m` | `0.099 m` | `0.099 m` | 동일 |
| `gripper_joint` Z | `0.010 m` | `0.010 m` | `0.010 m` | 동일 |
| `finger_right_joint` Z | `0.138 m` | `0.138 m` | `0.138 m` | 동일 |
| `finger_left_joint` Z | `0.138 m` | `0.138 m` | `0.138 m` | 동일 |
| finger box Z 크기 | `0.018 m` | `0.018 m` | `0.018 m` | 동일 |

주요 위치:

- 기준본 어댑터: `fairino5_v6.urdf` (로컬 기준본 경로)
- 현재 ROS 어댑터: [`fairino5_v6.urdf`](../../Farino_AIO_Mock/src/fairino_description/urdf/fairino5_v6.urdf#L496)
- Unity 어댑터: [`fairino5_v6.urdf`](../../UnityDT/Assets/URDF/Sources/FR5/urdf/fairino5_v6.urdf#L473)

따라서 기준본과 현재 파일 사이의 URDF 변경으로 그리퍼 끝이 위나 아래로 이동하지 않는다.

### 좌우 좌표

전체 URDF diff에서 실질적으로 변경된 형상 좌표는 다음 세 곳이었다.

| 항목 | 기준본 | 현재 ROS | Unity |
|---|---:|---:|---:|
| PGEA visual/collision X | `+2.8 mm` | `0 mm` | `+2.8 mm` |
| 오른쪽 finger joint X | `+31.1 mm` | `+28.4 mm` | `+31.1 mm` |
| 왼쪽 finger joint X | `-26.0 mm` | `-28.4 mm` | `-26.0 mm` |

기준본 주석은 `+31.1/-26.0 mm`를 실제 jaw face의 비대칭 측정 위치로 설명한다. 현재 ROS URDF는 이를 `±28.4 mm` 대칭값으로 바꿨지만 Unity URDF는 기준본 값을 유지한다.

따라서 0902 보고서에서 확인한 Unity/ROS 좌우 차이는 다음과 같이 판정할 수 있다.

- 기준본과 Unity: 일치
- 기준본과 현재 ROS: 불일치
- 영향 방향: 주로 그리퍼 좌우 중심
- 현재 상하/TCP 축방향 증상과의 관계: 직접 원인 아님

## 5. MoveIt 체인 비교

기준본과 현재 ROS의 다음 파일은 SHA-256까지 동일했다.

- `fairino5_v6_robot.srdf` (로컬 기준본 경로)
- `fairino5_v6_robot.urdf.xacro` (로컬 기준본 경로)

MoveIt arm chain의 tip은 두 버전 모두 `wrist3_link`이다.

```xml
<chain base_link="base_link" tip_link="wrist3_link"/>
```

별도의 `tcp_link` 또는 `tool_link`는 정의하지 않는다. 따라서 MoveIt에 TCP 목표를 보낼 때는 외부 코드가 `TCP → wrist3_link` 변환을 완결해야 한다.

`kinematics.yaml`에는 다음 차이가 있다.

- 기준본 solver timeout: `0.005 s`
- 현재 solver timeout: `0.1 s`
- 현재 파일에 attempts와 j1 weight 설정 추가

이 변경은 IK 탐색 시간과 해 선택에 영향을 줄 수 있지만, 같은 관절각에서 계산되는 기구학적 TCP 위치나 고정적인 `9~18 mm` 축방향 오차를 만들지는 않는다.

## 6. 기준본이 정의하는 물리적 끝

기준본 URDF가 정의한 축방향 형상은 다음과 같다.

```text
wrist3_link 원점 → 플랜지         99 mm
플랜지 → 그리퍼 장착면 어댑터     10 mm
그리퍼 장착면 → 기본 jaw 위치     138 mm
커스텀 finger box 길이             18 mm
```

따라서 커스텀 핑거 외곽 끝은 다음 위치다.

```text
wrist3_link 기준 = 99 + 10 + 138 + 18 = 265 mm
플랜지 기준      =      10 + 138 + 18 = 166 mm
```

PGEA-100-40의 `138 mm` 전체 길이는 프로젝트 STL 경계값 및 브레이크형 모델의 제조사 도면과도 일치한다.

[DH-Robotics PGEA 공식 카탈로그](https://en.dh-robotics.com/wp-content/uploads/2025/06/DH_PGEAPGIA-catalog_V255.pdf)

## 7. 기준본과 현재 TCP의 관계

기준본 URDF에는 이름이 `TCP`, `tcp_link` 또는 `tool_link`인 요소가 없다. 즉, 기준본은 물리 형상 끝 `166 mm`는 계산할 수 있게 하지만 실제 로봇 작업점이 반드시 그 끝이어야 한다고 규정하지 않는다.

현재 Unity Scene의 TCP는 다음과 같다.

```text
Scene local = (2.32, 146.73, -2.01) mm in Unity axes
플랜지 기준 ROS = (-2.01, -2.32, 156.73) mm
wrist3_link 기준 축방향 = 99 + 10 + 146.73 = 255.73 mm
```

관련 위치: [`SampleScene.unity`](../../UnityDT/Assets/Scenes/SampleScene.unity#L1954)

프로젝트 Real Tool 1 설정은 플랜지 기준 `(-2, -2, 157) mm`이므로 현재 Scene과 약 `0.42 mm` 이내로 일치한다.

관련 위치: [`RealRobotGhostControl.cs`](../../UnityDT/Assets/src/Runtime/Robot/Real/RealRobotGhostControl.cs#L127)

반면 기준본 형상의 외곽 끝은 플랜지 기준 `166 mm`이므로 현재 TCP는 외곽 끝보다 `9.27 mm` 안쪽이다.

```text
166 - 156.73 = 9.27 mm
```

기준본 추가 확인으로 확정할 수 있는 내용은 다음과 같다.

- `9.27 mm` 차이는 URDF 버전 차이가 아니라 “물리 외곽 끝”과 “현재 Tool 1 작업점”의 의미 차이다.
- 기준본만으로는 Tool 1을 외곽 끝으로 옮겨야 한다고 결론 내릴 수 없다.
- 실제 컨트롤러 Tool 1이 `(-2, -2, 157)`인지 직접 조회해야 현재 Scene TCP의 실물 일치 여부가 최종 확정된다.

## 8. Mock offset의 출처 재판정

기준본에는 `mock_sim.py`, `/unity/tcp_target` 처리 또는 `DEFAULT_TOOL_OFFSET`이 존재하지 않는다. 현재 패키지의 CMake에 다음 설치 항목이 나중에 추가되었다.

```cmake
install(PROGRAMS ../../notebooks/mock_sim.py DESTINATION lib/${PROJECT_NAME})
```

관련 위치: [`CMakeLists.txt`](../../Farino_AIO_Mock/src/fairino5_v6_moveit2_config/CMakeLists.txt#L12)

현재 Mock 기본값은 다음과 같다.

```text
DEFAULT_TOOL_OFFSET = (0, 0, 274.073, 0, 0, 0)
```

관련 위치: [`mock_sim.py`](../../Farino_AIO_Mock/notebooks/mock_sim.py#L45)

이 값은 기준본 URDF의 물리 외곽 끝 `265 mm`와도 다르고, 현재 Scene TCP `255.73 mm`와도 다르다.

```text
Mock - 기준본 외곽 끝 = 274.073 - 265.000 = 9.073 mm
Mock - 현재 Scene TCP = 274.073 - 255.730 = 18.343 mm
```

`274.073 mm`는 과거 Unity Scene TCP의 다음 합과 정확히 일치한다.

```text
99 + 10 + 165.073 = 274.073 mm
```

따라서 이 값은 기준본이 보증한 정격 TCP가 아니라, 과거 Scene에서 사용하던 작업점을 Mock 코드에 복제한 값으로 판정된다. 현재 정식 Mock launch는 `--tool-offset`을 전달하지 않으므로 이 기본값을 그대로 사용한다.

관련 위치: [`mock.launch.py`](../../ASSEMBLY_SEQUENCER/src/assembly_sequencer/launch/mock.launch.py#L18)

## 9. 실물 상태 데이터에서 확인된 제한

기준본 FAIRINO SDK 구조체는 도구 현재 위치와 플랜지 현재 위치를 별도 필드로 정의한다.

- `tl_cur_pos[6]`: 도구 현재 위치
- `flange_cur_pos[6]`: 말단 플랜지 현재 위치

관련 위치: `robot_types.h` (로컬 기준본 경로)

그러나 CNDE UDP 수신 경로는 다음처럼 동일한 `rt_state.tcp_pos`를 두 필드에 복사한다.

```cpp
shm_shared_data.tcp_cur_pos[i] = rt_state.tcp_pos[i];
shm_shared_data.flange_cur_pos[i] = rt_state.tcp_pos[i];
```

관련 위치: `CNDE_thread.cpp` (로컬 기준본 경로)

현재 `Farino_AIO_Mock`에도 같은 코드가 유지되어 있다. 이 상태에서는 `RobotNonrtState`의 TCP와 flange 값을 빼서 실제 Tool offset을 검증하면 항상 잘못된 결과를 얻는다.

기준본에는 Tool 번호로 실제 컨트롤러 설정을 조회하는 `GetToolCoordWithID` 공개 진입점이 있다.

관련 위치: `command_server.cpp` (로컬 기준본 경로)

따라서 실물 최종 검증에는 상태 메시지의 flange 필드가 아니라 `GetToolCoordWithID(1)`의 직접 응답을 사용해야 한다. 조사 당시 실제 로봇 연결이 없어 이 호출은 수행하지 않았다.

## 10. 최종 원인 판정

### Unity 형상 끝을 실제 금속 끝과 비교한 경우

기준본과 Unity URDF 형상은 일치한다. 현재 TCP가 커스텀 핑거 외곽 끝이 아니라 Tool 1 작업점에 배치되어 있으므로 약 `9.27 mm` 차이가 난다.

### Mock 이동 결과를 Unity 또는 실물 목표와 비교한 경우

Mock이 기준본에 없는 과거 오프셋 `274.073 mm`를 사용하므로 현재 Scene TCP보다 축방향으로 `18.343 mm` 차이가 난다. 현재 자세처럼 공구축이 아래쪽을 향하면 화면에서는 주로 높이 오차로 나타난다.

### Real shadowing 결과를 실물과 비교한 경우

기준본과 현재 Scene의 팔/그리퍼 축방향 URDF는 일치한다. 현재 Scene TCP도 프로젝트 Real Tool 1 설정과 일치한다. 따라서 남는 확인 대상은 다음 두 가지다.

1. 실제 컨트롤러의 활성 Tool 번호와 `GetToolCoordWithID(1)` 결과
2. Unity `FR5` Base Transform과 실물 로봇 베이스 설치 좌표

Real shadowing은 관절값만 Unity Articulation에 적용하고 실제 Cartesian TCP나 flange 좌표로 모델을 보정하지 않기 때문에, 이 두 값이 다르면 그대로 화면 오차가 된다.

## 11. 검증 및 변경 범위

수행한 검증:

- 기준본과 현재 ROS FR5 URDF 전체 diff
- 기준본, 현재 ROS와 Unity의 관련 URDF 좌표 비교
- FR5 팔 메시 7개 및 PGEA 메시 SHA-256 비교
- SRDF와 URDF Xacro SHA-256 비교
- KDL kinematics 설정 diff
- 기준본 Real launch와 현재 Real launch 비교
- 기준본/현재 FAIRINO message 및 hardware 경로 비교
- `GetToolCoordWithID` 공개 진입점과 TCP/flange 상태 전달 경로 확인
- 현재 Unity Scene TCP 및 Mock offset과 기준본 형상 수치 재계산

검증 결과:

- 축방향 URDF와 메시: 기준본과 현재 파일 사이 차이 없음
- 좌우 URDF: Unity가 기준본과 일치하고 현재 ROS가 대칭값으로 변경됨
- Real launch, SRDF, URDF Xacro와 메시 계약: 기준본과 현재 동일
- Mock tool offset: 기준본에 존재하지 않으며 현재 Scene과 불일치
- 실제 컨트롤러 Tool 1: 연결 부재로 미검증

변경 내용:

- Scene, URDF, C#, Python, ROS 설정은 수정하지 않았다.
- 본 추가 조사 보고서만 생성했다.

