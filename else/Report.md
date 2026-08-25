# Assembly 조립 좌표 도달 실패 조사 보고서

- 조사일: 2026-08-17
- 조사 기준 Unity 커밋: `d9fd4ff`
- 대상 씬: `UnityDT/Assets/Scenes/SampleScene.unity`
- 범위: 코드·Unity 라이브 Transform·URDF/SRDF·MoveIt 설정·plan-only 비교
- 제외: 실제 FAIRINO의 Base/Tool 보정값 실측, 생산 코드 수정

## 1. 결론

현재 조립 좌표는 로봇의 절대 작업영역 밖이라고 보기 어렵다. 동일 자세에서 최종 하강 목표를 MoveIt PTP로 계획하면 `j3 >= 0 deg` 조건에서도 성공한다.

가장 강한 원인은 다음 두 요소의 조합이다.

1. `AssemblySlot.Target`이 사용자가 보는 부품 중심과 다른 Transform 피벗을 사용한다.
   - 첫 슬롯 피벗: `(0.513300, -0.129580, 0.080890)` m
   - 첫 슬롯 렌더 중심: `(0.489300, -0.121684, 0.056890)` m
   - 차이: `(-24.000, +7.896, -24.001)` mm
   - 현재 코드는 렌더 중심이나 별도 조립점을 사용하지 않고 이 피벗을 그대로 TCP 목표로 사용한다.

2. 원래 요구한 `j3 >= 0 deg` 안전 제한이 현재 Mock 실행 설정에서는 `-162 deg`로 완화돼 있다.
   - 잘못된 슬롯 피벗으로 만든 접근점은 `j3 >= 0 deg`에서 거부된다.
   - 같은 접근점을 `j3 >= -162 deg`로 완화하면 계획이 성공한다.
   - 따라서 완화된 설정은 원인을 해결하지 않고 음수 j3의 다른 IK 분기를 허용해, 관찰된 팔 뒤집힘으로 이어질 수 있다.

슬롯 피벗을 보이는 메시 중심으로만 바꾼 비교 계획에서는 접근점과 하강점이 모두 `j3 >= 0 deg`에서 성공했다. 다만 렌더 중심이 실제 조립 TCP 위치라는 보장은 없으므로, 최종 해결은 메시 중심 자동 사용이 아니라 명시적으로 교시한 조립 TCP Transform을 `AssemblySlot.Target`에 지정하는 것이다.

## 2. 실제 명령 흐름

현재 호출 순서는 다음과 같다.

1. `Scenario`가 `AssemblyReady`로 이동한다.
2. `PlaceAsync(slotId)`가 `AssemblySlot.Target`을 찾는다.
3. `placement.position = slot.position`을 사용한다.
4. 현재 TCP 높이를 유지하고 슬롯 XZ만 적용한 `approach`를 만든다.
5. 접근점까지 PTP, 슬롯까지 수직 LIN으로 이동한다.
6. 그리퍼를 연 뒤 부품을 `slot.position`, `slot.rotation`으로 강제 스냅한다.

근거:

- `Scenario.cs:23-30`
- `mockAsyncPlay.cs:55-68`
- `MockRobotControl.cs:117-128`

즉 실패한 `mockAsyncPlay.cs:62`의 목표는 최종 슬롯 좌표가 아니라 다음 상부 접근점이다.

```text
approach.x = slot.position.x
approach.y = AssemblyReady 완료 후 현재 TCP 높이
approach.z = slot.position.z
```

## 3. Unity 좌표 조사

### 3.1 활성 로봇 기준

플레이 모드에서 실제 주입된 활성 객체는 다음과 같았다.

```text
RobotMaster       FR5                       active
MockRobotMaster   FR5/MockMaster            active
MockRobotControl  FR5/MockMaster            active
robotBase         FR5 Imported (URDF Articulation)
robotBase world   position=(0,0,0), rotation=(0,0,0), scale=(1,1,1)
```

`FR5_Save`에도 RobotMaster가 있지만 비활성 상태였다. 현재 실행에서 잘못된 두 번째 로봇이 명령을 받은 증거는 없다.

### 3.2 좌표축 변환

현재 위치 변환은 Unity RUF에서 ROS FLU로 다음처럼 적용된다.

```text
ROS x = Unity z
ROS y = -Unity x
ROS z = Unity y
```

활성 `robotBase`가 원점·무회전이므로 현재 씬에서는 `InverseTransformPoint`에 의한 위치 오염이나 Local/World 혼용이 주원인은 아니다. 또한 `mockAsyncPlay`는 `slot.localPosition`이 아니라 월드 좌표인 `slot.position`을 사용한다.

MotherBoard의 scale이 `(0.01, 0.01, 0.01)`이라 슬롯 localPosition 값이 크게 보이지만, Unity가 계산한 `Transform.position`은 정상적인 월드 m 단위다. 이 문제를 고치기 위해 localPosition을 직접 사용하면 오히려 잘못된다.

### 3.3 슬롯 피벗과 화면상 중심

첫 두 슬롯의 실측값은 다음과 같다.

| 슬롯 | Target 피벗 (Unity world m) | Renderer 중심 (Unity world m) | 중심 - 피벗 |
|---|---|---|---|
| `1` | `(0.513300, -0.129580, 0.080890)` | `(0.489300, -0.121684, 0.056890)` | `(-24.000, +7.896, -24.001)` mm |
| `2` | `(0.513300, -0.129580, 0.128530)` | `(0.489300, -0.121684, 0.104530)` | `(-24.000, +7.896, -24.001)` mm |

첫 슬롯의 X 값이 MotherBoard 부모 X 값과 동일해 부모 중심으로 이동하는 것처럼 보이지만, 코드는 부모 좌표를 읽지 않는다. 슬롯 오브젝트 자체의 피벗이 부모 X 근처에 있고 메시가 그 피벗에서 24 mm 떨어져 있는 상태다.

반면 공급 부품 `Sk_hynix`는 피벗과 렌더 중심 차이가 약 `0.006 mm` 이하였다. 따라서 같은 모델 타입이라도 공급 부품은 피벗이 정상이고, MotherBoard 아래의 슬롯용 오브젝트만 메시/피벗 관계가 다르다.

### 3.4 TCP와 wrist3 오프셋

플레이 상태에서 측정한 값은 다음과 같다.

```text
wrist3 -> TCP 거리: 0.274073 m
wrist3 로컬 오프셋: (0, 0.274073, 0) Unity
상대 회전: identity
```

Unity는 원하는 TCP Pose에서 이 오프셋을 제거해 ROS의 `wrist3_link` 목표를 만든다. 현재 첫 슬롯에 대해 실제 변환되는 목표는 다음과 같다.

| 구간 | Unity TCP 목표 (m) | ROS wrist3 목표 (m) |
|---|---|---|
| AssemblyReady | `(0.465300, 0.035000, 0.001600)` | `(0.001601, -0.465299, 0.309074)` |
| 현재 슬롯 피벗 접근 | `(0.513300, 0.035000, 0.080890)` | `(0.080891, -0.513299, 0.309074)` |
| 현재 슬롯 피벗 하강 | `(0.513300, -0.129580, 0.080890)` | `(0.080891, -0.513299, 0.144494)` |
| 렌더 중심 접근 비교 | `(0.489300, 0.035000, 0.056890)` | `(0.056891, -0.489299, 0.309074)` |
| 렌더 중심 하강 비교 | `(0.489300, -0.121684, 0.056890)` | `(0.056891, -0.489299, 0.152390)` |

현재 강제 자세는 ROS RPY `(180, 0, 0)`이며 Unity wrist 회전으로는 `(0, 0, 180)`으로 관찰됐다.

## 4. URDF/SRDF 및 MoveIt 조사

### 4.1 관절 범위

`fairino5_v6.urdf`의 주요 범위는 다음과 같다.

| 관절 | URDF 범위 |
|---|---|
| j1 | 약 `-175 ~ +175 deg` |
| j2 | 약 `-265 ~ +85 deg` |
| j3 | 약 `-162 ~ +162 deg` |
| j4 | 약 `-265 ~ +85 deg` |
| j5 | 약 `-175 ~ +175 deg` |
| j6 | 약 `-175 ~ +175 deg` |

URDF 자체는 j3 음수를 허용한다. `j3 >= 0 deg`는 URDF 기구 한계가 아니라 Mock에 추가한 운용·안전 정책이다.

현재 `mock_sim.py`와 `mock_sim_with_unity.launch.py` 기본값, 실제 실행 프로세스 모두 `--min-j3-deg -162`였다. 따라서 현재 상태에서는 이 운용 정책이 사실상 꺼져 있다.

관련 위치:

- `fairino5_v6.urdf:226-252`
- `mock_sim.py:274-293`, `mock_sim.py:496`
- `mock_sim_with_unity.launch.py:66`

### 4.2 계획 기준 링크

SRDF의 로봇 계획 체인은 `base_link -> wrist3_link`이고, Mock 노드 기본 tip도 `wrist3_link`다.

- `fairino5_v6_robot.srdf:12-24`
- `mock_sim.py:491-492`

URDF에는 그리퍼 어댑터와 그리퍼, 손가락 링크는 있지만 별도 `tcp_link`가 없다.

```text
wrist3_link
  -> 0.099 m fixed adapter
  -> 0.010 m fixed gripper mount
  -> gripper/finger geometry
```

Unity의 TCP는 wrist3에서 `274.073 mm` 떨어져 있다. URDF 형상으로 계산한 손가락 외곽은 대략 `265 mm` 부근이므로 약 `9 mm` 차이가 있지만, 이는 TCP를 손가락 끝보다 바깥에 둔 의도일 수도 있다. 실제 Tool Center 보정값과 대조하기 전에는 결함으로 단정할 수 없다.

현재 구조는 Unity의 라이브 Transform에서 TCP 오프셋을 역산해 `wrist3_link` 목표로 보내므로 작동할 수는 있다. 다만 Unity TCP와 ROS Tool 프레임 사이에 명시적 공통 계약이 없어 씬 계층이나 TCP 위치가 바뀌면 두 모델이 조용히 달라질 위험이 있다.

관련 위치:

- `MockRobotControl.cs:242-270`
- `fairino5_v6.urdf:462-560`

### 4.3 계획 조건

Mock PTP는 다음 조건을 사용한다.

- Pilz `PTP`
- 계획 시도 1회
- 위치 허용 영역 반지름 1 mm
- 축별 자세 허용오차 0.01 rad
- 계획 후 전체 궤적의 j3 최솟값 검사

LIN은 다음 조건을 모두 만족해야 한다.

- Cartesian fraction 100%
- step 5 mm
- 관절 jump threshold 0.35 rad
- self/world collision 회피 활성

따라서 이전의 `MoveL path is only 7.8% complete`는 단순 목표점 도달 여부가 아니라 직선 경로 전체의 IK 연속성, 관절 jump 또는 충돌 조건 실패를 뜻한다.

현재 실행 중인 launch에는 `Twin_Visual.py`가 포함되지 않았고 활성 프로세스도 없었다. 따라서 Unity의 MotherBoard가 MoveIt planning scene 장애물로 자동 등록된 상태는 아니다. 현재 PTP의 j3 거부를 PCB 충돌 탓으로 볼 수 없으며, 반대로 실제 보드 충돌을 Mock이 검사한다고도 볼 수 없다.

## 5. MoveIt plan-only 비교

실행 없이 현재 MoveIt에 정확한 `wrist3_link` Pose를 넣어 비교했다. 시작 관절은 다음과 같았다.

```text
[-8.277, -65.102, 100.077, -124.975, -90.000, 81.723] deg
```

| 목표 | j3 하한 | 결과 |
|---|---:|---|
| AssemblyReady | `0 deg` | 성공, 36 points / 3.50 s |
| 현재 슬롯 피벗 접근 | `0 deg` | 실패: j3가 0도 아래로 이동 |
| 현재 슬롯 피벗 접근 | `-162 deg` | 성공, 49 points / 4.76 s |
| 현재 슬롯 피벗 하강점 PTP 비교 | `0 deg` | 성공, 51 points / 4.95 s |
| 렌더 중심 접근 비교 | `0 deg` | 성공, 38 points / 3.64 s |
| 렌더 중심 하강점 PTP 비교 | `0 deg` | 성공, 38 points / 3.64 s |

이 비교는 각 목표를 같은 시작 상태에서 독립적으로 계획한 결과이며 전체 Scenario를 순차 실행한 결과는 아니다. 다만 실제 Scenario에서도 `AssemblyReady` 다음 `PlaceAsync`의 접근 PTP에서 동일한 `j3 would move below 0.0 deg` 오류가 이미 발생했다.

해석:

- 최종 조립 영역 자체는 URDF/MoveIt상 도달 가능하다.
- 현재 슬롯 피벗으로 만든 상부 접근점이 `j3 >= 0 deg` 정책과 충돌한다.
- 피벗의 24 mm XZ 오차를 제거한 비교 접근점은 같은 정책에서 계획된다.
- `-162 deg`로 완화하면 잘못된 접근점도 계획되므로 팔 뒤집힘을 허용할 수 있다.

## 6. 원인 및 의심 사항 우선순위

### P0 — 확인됨: 슬롯 Target 피벗이 실제 조립 위치와 다름

영향:

- 로봇은 화면에 보이는 슬롯 중심이 아니라 X/Z 각각 24 mm 벗어난 지점을 향한다.
- 이 차이만으로 `j3 >= 0 deg`에서 접근 계획 결과가 실패에서 성공으로 바뀌었다.
- 배치 후 강제 스냅 때문에 로봇이 실제로 어느 점에 도달했는지 시각적으로 가려질 수 있다.

최소 해결:

- 렌더러 중심을 런타임에 자동 계산하지 않는다.
- 실제 그리퍼 TCP가 도달해야 하는 위치·회전을 나타내는 명시적 Transform을 씬에서 교시한다.
- 각 `AssemblySlot.Target`이 기존 메시 오브젝트 피벗이 아니라 그 Transform을 참조하게 한다.
- 첫 슬롯의 렌더 중심 값은 진단 비교값일 뿐, 실제 삽입 높이와 접촉점을 확인한 최종 교시값으로 그대로 간주하지 않는다.

### P0 — 확인됨: j3 안전 제한이 현재 완화돼 있음

영향:

- `j3 >= 0 deg`라면 거부될 궤적이 실행된다.
- 플래너가 음수 j3의 다른 IK 분기를 선택해 팔이 뒤집히는 동작을 할 수 있다.

최소 해결:

- 목표 좌표를 교정한 뒤 Mock 실행값을 다시 `--min-j3-deg 0`으로 고정한다.
- 단순히 제한을 `-162`로 낮추는 방식은 해결책으로 사용하지 않는다.
- 교정된 모든 필수 목표가 여전히 0도 제한에서 실패할 때만 Base/Tool 보정과 실제 로봇 관절 자세를 먼저 대조한다.

### P1 — 확인됨: 이동 자세와 최종 스냅 자세가 다름

현재 배치 이동은 `item.rotation`을 사용하지만, 해제 후 스냅은 `slot.rotation`을 사용한다.

```text
현재 held item rotation: (0, 0, 0) Unity
첫 slot rotation:        (0, 270, 0) Unity
```

또한 저수준 변환은 입력 회전의 Unity Y만 ROS yaw로 사용하고 roll/pitch는 `(180, 0)`으로 강제한다. 결과적으로 로봇은 item 기준 yaw로 이동한 뒤 부품만 slot 회전으로 순간 변경한다.

영향:

- 실제 그리퍼 자세와 조립 완료 자세가 일치하지 않는다.
- Mock 스냅이 잘못된 접근 자세를 숨긴다.
- slot 회전을 실제 이동에 적용하면 IK 결과도 달라질 수 있다.

최소 해결:

- 배치에 사용할 TCP Pose와 최종 부품 Pose의 관계를 하나로 정한다.
- slot 회전이 실제 요구 자세라면 이동 목표와 스냅이 같은 기준을 사용하도록 맞춘 뒤 plan-only를 다시 수행한다.

### P1 — 의심: 명시적 ROS TCP 프레임 부재

현재 ROS는 `wrist3_link`를 계획하고 Unity가 274.073 mm TCP 오프셋을 매번 역산한다. 활성 씬에서는 값이 일관됐지만 실제 로봇 Tool Center와 동일하다는 검증은 없다.

최소 확인:

- 동일 관절 자세에서 Unity `wrist3 -> TCP`, ROS TF, 실제 FAIRINO Tool 좌표를 비교한다.
- 위치와 회전이 일치하면 현재 변환을 유지할 수 있다.
- 씬과 ROS가 계속 따로 보정돼 불일치가 반복될 때만 URDF의 고정 `tcp_link` 도입과 MoveIt tip 변경을 검토한다. 이는 URDF/SRDF/API 계약 변경이므로 별도 승인 대상이다.

### P1 — 조건부 결함: 베이스 회전이 있을 때 자세 변환 누락

`MockRobotControl`은 위치에는 `robotBase.InverseTransformPoint`를 적용하지만 회전은 월드 `wristTarget.rotation`을 바로 FLU로 변환한다.

현재 활성 base가 무회전이라 이번 실패에는 영향이 없다. 그러나 로봇 베이스가 회전된 씬에서는 위치는 base-local, 회전은 world 기준이 되어 Pose 프레임이 섞인다.

최소 해결은 그 상황을 지원해야 할 때 wrist 회전에도 base 역회전을 적용하는 것이다.

### P2 — 의심: 직선 경로 제약과 planning scene 차이

- LIN은 100% 완주만 허용해 작은 IK 단절도 전체 명령 실패가 된다.
- Unity 보드는 현재 planning scene에 없으므로 Mock 충돌 결과가 실제 환경과 같지 않다.
- 슬롯 TCP를 교정한 뒤에도 LIN만 실패하면 fraction이 끊기는 정확한 waypoint의 관절값과 self-collision pair를 조사해야 한다.

### P2 — 낮은 우선순위: URDF 오타

`fairino5_v6.urdf:354`의 wrist2 collision origin 태그가 `<origin>`이 아니라 `<origins>`다. 값이 `xyz=0, rpy=0`이라 현재 형상 위치에는 실질 영향이 없을 가능성이 높고, MoveIt도 기동하므로 이번 원인으로 보기는 어렵다. 그래도 URDF 정합성 검사 시 수정 대상이다.

### 별도 데이터 문제

현재 `AssemblySlots`는 26칸이지만 Target이 있는 것은 8개, Slot ID가 있는 것은 처음 2개뿐이다. 나머지는 빈 ID 또는 null Target이다. ItemGroup도 첫 `Sk_hynix` 공급 부품 1개 외에는 대부분 null이다. 좌표 문제를 해결해도 Scenario 전체 반복은 이후 데이터 검증에서 별도로 실패한다.

## 7. 권장 해결 순서

1. Mock의 j3 하한을 다시 `0 deg`로 복구해 팔 뒤집힘 궤적을 차단한다.
2. 첫 슬롯부터 실제 조립 TCP Pose를 나타내는 명시적 Transform을 교시하고 `AssemblySlot.Target`에 지정한다.
3. 슬롯 피벗, 목표 TCP, ROS `wrist3_link` 변환값을 한 번에 기록해 mm/m 및 RUF/FLU 변환을 확인한다.
4. 교정된 접근점과 하강점을 `j3 >= 0 deg` plan-only로 검증한다.
5. `item.rotation`과 `slot.rotation` 중 실제 이동 자세 기준을 확정하고 이동/스냅을 동일 기준으로 맞춘다.
6. 여전히 실제 로봇과 Mock이 다르면 동일 관절 자세에서 Base 및 wrist3-to-TCP 보정값을 대조한다.
7. 좌표와 TCP가 일치한 뒤에도 LIN만 실패할 경우 Cartesian jump/self-collision을 조사한다.

가장 작은 유효 수정 범위는 우선 씬의 `AssemblySlot.Target` 교정과 `min_j3_deg=0` 복구다. 새 인터페이스나 새 공개 함수는 이 문제 해결에 필요하지 않다.

## 8. 검증 상태와 한계

- Unity 플레이 상태의 활성 의존성, 슬롯 Transform, 렌더 bounds, TCP/wrist3 변환을 라이브로 확인했다.
- MoveIt plan-only 비교는 로봇을 실행하지 않고 수행했다.
- 조사 후 Unity Play Mode는 종료했다.
- 이번 작업에서는 생산 C#, 씬, URDF, Python을 수정하지 않았다.
- 실제 FAIRINO Base/Tool 보정값과 실물 조립점은 제공되지 않아 비교하지 못했다.
- Renderer 중심은 문제를 드러내는 비교 기준일 뿐, 최종 조립 TCP 교시값은 실물 기준으로 확정해야 한다.
