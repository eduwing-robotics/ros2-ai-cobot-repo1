# Unity FR5 그리퍼 TCP 위치 불일치 조사 보고서

- 작성일: 2026-09-02
- 조사 대상: `UnityDT/Assets/Scenes/SampleScene.unity`의 FR5 그리퍼 TCP와 실제 로봇/ROS Mock 기준의 위치 차이
- 조사 범위: 현재 Unity 런타임 계층, 프로젝트 URDF, FAIRINO 공식 URDF, PGEA 제조사 치수, 프로젝트 STL·OBJ 경계값, Real/Mock TCP 처리 경로와 Git 이력

## 1. 결론

FR5 팔 본체 URDF의 치수 오류보다는 **TCP 기준이 Unity Scene, Real Tool 설정, Mock ROS 사이에서 서로 다르게 남아 있는 것**이 핵심 원인이다.

1. 현재 Unity Scene의 TCP는 프로젝트에 설정된 Real Tool 1 값과 약 `0.42 mm` 이내로 일치한다. 따라서 현재 Scene의 TCP Transform 자체를 실제 Tool 1 대비 크게 잘못된 값으로 보기는 어렵다.
2. 물리적인 커스텀 핑거 외곽 끝은 현재 TCP보다 공구축 방향으로 약 `9.27 mm` 더 바깥에 있다. 현재 TCP는 18 mm 커스텀 핑거의 끝이 아니라 거의 중앙을 가리킨다. “그리퍼 끝”을 외곽 형상 끝으로 해석하면 이 차이가 보인다.
3. Mock ROS는 과거 Scene TCP 길이인 `274.073 mm`를 계속 사용한다. 현재 Scene의 `wrist3_link` 원점 기준 TCP 축방향 길이 `255.73 mm`보다 `18.343 mm` 길다. 현재 기본 Mock 실행 경로는 이 값을 별도로 덮어쓰지 않으므로, Mock 동작에서는 공구축 방향 위치 불일치가 실제로 발생한다.
4. Real shadowing은 컨트롤러에서 받은 Cartesian TCP로 Unity 모델을 정렬하지 않고 관절각 6개만 적용한다. 따라서 활성 Tool 번호, Tool 좌표 또는 로봇 베이스 설치 좌표가 다르면 그 오차가 Unity에서 자동으로 보정되지 않는다.

현재 자세에서는 공구축이 거의 월드 아래쪽을 향하므로, 위의 공구축 오프셋 차이가 화면에서 주로 상하 위치 차이로 나타난다.

## 2. 조사한 실행 경로

### Unity Scene

현재 공개 진입점은 `RobotMaster`이고, Inspector에 연결된 `TCP` Transform을 사용한다. 해당 Transform은 다음 계층에 있다.

```text
FR5
└─ Model
   └─ FR5 Imported (URDF Articulation)
      └─ j1/j2/j3/j4/j5/j6
         └─ gripper_adapter_joint
            └─ gripper_joint
               └─ TCP
```

Scene에 직렬화된 TCP 로컬 위치는 다음과 같다.

```text
Unity local position = (0.00232, 0.14673, -0.00201) m
```

관련 위치: [`SampleScene.unity`](../../UnityDT/Assets/Scenes/SampleScene.unity#L1954)

Unity URDF Importer의 좌표 변환은 다음 계약을 사용한다.

```text
Unity(x, y, z) = ROS(-y, z, x)
```

관련 위치: [`Ros2UnityCoordinate.cs`](../../UnityDT/Assets/URDF_Importer/Ros2UnityCoordinate.cs#L7)

### Real shadowing

`RealStatusSubscriber`는 실제 상태 메시지에서 관절각과 Cartesian TCP를 모두 읽지만, `RealShadowing.ApplyState()`는 `JointDegrees`만 Unity Articulation에 적용한다.

- 상태 수신: [`RealStatusSubscriber.cs`](../../UnityDT/Assets/src/Runtime/Robot/Real/RealStatusSubscriber.cs#L110)
- 모델 반영: [`RealShadowing.cs`](../../UnityDT/Assets/src/Runtime/Robot/Real/RealShadowing.cs#L48)

따라서 실제 컨트롤러 Cartesian TCP는 UI/상태 데이터로는 존재하지만 Unity 로봇 형상을 보정하는 기준으로 사용되지 않는다.

### Mock 실행

정식 Mock launch는 `mock_sim.py`를 실행하지만 `--tool-offset` 인자를 전달하지 않는다.

- Launch: [`mock.launch.py`](../../ASSEMBLY_SEQUENCER/src/assembly_sequencer/launch/mock.launch.py#L18)
- 기본 오프셋: [`mock_sim.py`](../../Farino_AIO_Mock/notebooks/mock_sim.py#L45)

따라서 아래 기본값이 그대로 사용된다.

```text
DEFAULT_TOOL_OFFSET = (0.0, 0.0, 274.073, 0.0, 0.0, 0.0)
```

## 3. URDF와 형상 치수 대조

### FR5 팔과 플랜지

프로젝트의 `j1`~`j6` 관절 체인은 FAIRINO 공식 FR5 ROS2 URDF와 일치했다. 공식 URDF도 `j6`의 자식으로 `wrist3_link`를 사용하며, 조사 범위에서 팔 본체의 축방향 치수가 달라진 증거는 없었다.

- 프로젝트 URDF: [`fairino5_v6.urdf`](../../UnityDT/Assets/URDF/Sources/FR5/urdf/fairino5_v6.urdf#L473)
- [FAIRINO 공식 FR5 URDF](https://github.com/FAIR-INNOVATION/frcobot_ros2/blob/main/fairino_description/urdf/fairino5_v6.urdf)

프로젝트의 `wrist3_link.STL` 경계값을 확인한 결과 로컬 Z 범위가 약 `53.2~99.0 mm`였고, 플랜지 면은 `wrist3_link` 원점에서 약 `99 mm` 떨어져 있다. 그래서 프로젝트 URDF의 다음 배치는 형상과 일치한다.

```text
wrist3_link origin → flange = 99 mm
gripper adapter thickness     = 10 mm
```

### PGEA-100-40와 커스텀 핑거

DH-Robotics 공식 카탈로그는 브레이크가 있는 PGEA-100-40의 전체 길이를 `138 mm`로 명시한다. 프로젝트의 `pgea_100_40.stl` 경계값도 장축 방향으로 정확히 `138 mm`였다.

- [DH-Robotics PGEA 공식 카탈로그](https://en.dh-robotics.com/wp-content/uploads/2025/06/DH_PGEAPGIA-catalog_V255.pdf)
- 프로젝트 STL: [`pgea_100_40.stl`](../../UnityDT/Assets/URDF/Sources/FR5/meshes/gripper/pgea_100_40.stl)

프로젝트 URDF의 커스텀 핑거는 그리퍼 장착면에서 `138 mm` 위치에 시작하며 길이가 `18 mm`이다.

```text
커스텀 핑거 시작 = 138 mm
커스텀 핑거 길이 = 18 mm
외곽 끝          = 156 mm
```

관련 형상: [`Gripper pgea10041_endtip.obj`](../../UnityDT/Assets/Objs/Gripper%20pgea10041_endtip.obj)

## 4. TCP 수치 계산

### 현재 Unity TCP

현재 Scene TCP를 ROS 축 기준으로 변환하면 그리퍼 장착면 기준 위치는 다음과 같다.

```text
(-2.01, -2.32, 146.73) mm
```

여기에 10 mm 어댑터를 포함하면 플랜지 기준 위치는 다음과 같다.

```text
Scene TCP, flange-relative = (-2.01, -2.32, 156.73) mm
```

`wrist3_link` 원점 기준 축방향 거리는 다음과 같다.

```text
99 + 10 + 146.73 = 255.73 mm
```

### 프로젝트 Real Tool 1

Real Ghost 경로에 직렬화된 Tool 1 위치는 다음과 같다.

```text
Real Tool 1, flange-relative = (-2, -2, 157) mm
```

관련 위치: [`RealRobotGhostControl.cs`](../../UnityDT/Assets/src/Runtime/Robot/Real/RealRobotGhostControl.cs#L127)

Scene TCP와 Real Tool 1의 차이는 다음과 같다.

```text
Δ = (-0.01, -0.32, -0.27) mm
|Δ| ≈ 0.42 mm
```

현재 Scene TCP는 프로젝트 Real Tool 1 설정과 사실상 같은 지점이다. 다만 이것은 프로젝트에 저장된 Tool 1과의 비교이며, 조사 당시 실제 컨트롤러가 동일한 Tool 1을 활성화했는지는 연결이 없어 직접 확인하지 못했다.

### 물리적 핑거 외곽 끝

커스텀 핑거 외곽 끝은 플랜지 기준으로 다음 위치에 있다.

```text
adapter 10 + gripper/custom tip 156 = 166 mm
```

현재 TCP는 `156.73 mm`이므로 물리적 외곽 끝보다 `9.27 mm` 안쪽에 있다.

```text
166 - 156.73 = 9.27 mm
```

즉, 현재 TCP의 의미는 “커스텀 핑거 외곽 끝”보다 “커스텀 핑거 중앙 부근의 작업점”에 가깝다.

## 5. 확정된 Mock 오프셋 불일치

현재 Mock 기본값은 `wrist3_link → TCP = 274.073 mm`이다. 이 값은 과거 Scene 계층의 다음 합과 정확히 일치한다.

```text
99 + 10 + 165.073 = 274.073 mm
```

Git 이력에서 Scene TCP 로컬 축방향 값은 `165.073 mm`에서 `146.73 mm`로 변경되었지만, Mock 기본값은 갱신되지 않았다.

```text
과거 Mock/Scene = 274.073 mm
현재 Scene      = 255.730 mm
축방향 차이     = 18.343 mm
```

현재 Scene에는 약 `-2.01 mm`, `-2.32 mm`의 횡방향 보정도 있지만 Mock 기본값은 두 값을 모두 0으로 둔다. 따라서 Mock에는 주된 축방향 오차 외에도 작은 횡방향 오차가 남는다.

이 값은 Unity가 보내는 TCP 목표를 `wrist3_link` 목표로 변환할 때 사용된다. 그러므로 Mock 계획 결과와 Unity Scene의 TCP 표시가 동일한 관절 자세에서도 일치하지 않을 수 있다.

## 6. 원인별 식별 기준

관측되는 차이의 크기와 방향으로 원인을 구분할 수 있다.

| 관측 특성 | 가능성이 높은 원인 |
|---|---|
| 공구축 방향 약 `9.3 mm` | TCP와 커스텀 핑거 외곽 끝의 기준 차이 |
| 공구축 방향 약 `18.3 mm` | Mock의 오래된 `274.073 mm` 오프셋 |
| 그리퍼 자세를 바꾸면 오차 방향도 함께 회전 | Tool/TCP 오프셋 문제 |
| 그리퍼 자세와 무관하게 월드 Z 차이가 일정 | Unity 로봇 Base Transform 또는 실제 설치 높이 정렬 문제 |
| Real에서만 발생 | 컨트롤러 활성 Tool 번호·Tool 좌표 또는 Base 정렬 확인 필요 |

Unity URDF와 ROS URDF 사이에는 핑거 좌우 위치가 Unity `+31.1/-26.0 mm`, ROS `±28.4 mm`로 다른 부분이 있다. 이는 수 mm의 좌우 중심 차이를 만들 수 있지만 현재 조사 대상인 공구축/상하 위치 차이의 주원인은 아니다.

## 7. 검증 상태와 제한

수행한 확인:

- Unity Editor의 현재 Scene, Play Mode 상태와 실제 FR5 계층 확인
- `TCP`, `gripper_adapter_joint`, `gripper_joint`의 직렬화 값과 런타임 Transform 확인
- 런타임 커스텀 핑거 MeshRenderer bounds와 TCP 월드 위치 비교
- Unity/ROS URDF의 관절 및 그리퍼 고정 조인트 비교
- `wrist3_link.STL`, `pgea_100_40.stl`, 커스텀 핑거 OBJ 경계값 측정
- FAIRINO 공식 URDF 및 DH-Robotics 공식 PGEA 치수와 교차 확인
- Real 상태 수신부터 shadowing까지의 호출 경로 확인
- Unity Mock 명령부터 `mock_sim.py` Tool 보정까지의 호출 경로 확인
- Git 이력에서 과거/현재 TCP 값 변경 확인

실행하지 못한 확인:

- 조사 당시 Unity UI는 실제 ROS/로봇 연결이 없는 상태여서 실제 컨트롤러의 활성 Tool 1 값과 동일 자세의 Cartesian 좌표를 직접 대조하지 못했다.
- 열린 Play Mode에서는 `RealMaster`가 활성 상태였지만 저장된 Scene 변경 내용은 `MockMaster` 활성 상태였다. 재시작 전후 실행 모드가 달라 동일 조건 재현이 되지 않았다.
- 현재 `Farino_AIO_Mock/install/.../mock_sim.py` 심볼릭 링크가 존재하지 않는 `Farino_AIO` 경로를 가리키고, 최상단 README도 동일한 이전 경로를 source하도록 되어 있어 현재 작업공간에서 공식 명령 그대로 End-to-End Mock 실행을 재현할 수 없었다.

## 8. 변경 여부

이 조사는 원인 확인 요청 범위로 수행했으며 Scene, URDF, Runtime 코드와 ROS 코드는 수정하지 않았다. 진단 결과를 기록하기 위해 본 보고서만 추가했다.
