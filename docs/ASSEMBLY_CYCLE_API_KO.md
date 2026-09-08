# 검증된 전체 조립 사이클 API — 2026-09-08

Unity에서 내부 실기 실행기를 그대로 호출하고 진행 상태를 받는 ROS 2 API다.
`/real/robot/command`의 개별 Pick/Place와 별도이며, 새 경로 계산기를 만들지 않는다.
기존 ROS-TCP-Endpoint를 통해 사용한다. HTTP URL이 아니다.


## 공통 실행 진입점 — 최신

이제 터미널 런처도 API 클라이언트다. Unity/터미널 모두 같은 API 기록과 상태를 사용한다.
API 연결이 없으면 실패하며 직접 로봇 실행으로 우회하지 않는다.

```bash
./run_fr5_cycle.sh --status                 # API 상태 조회, 이동 없음
./run_fr5_cycle.sh --check                  # API를 통한 장치 점검, 이동 없음
./run_fr5_cycle.sh --execute                # 준비 확인 후 전체25개
./run_fr5_cycle.sh --execute --part HBM     # HBM8개만 새 촬영부터 시험
./run_fr5_cycle.sh --execute --part PM      # 파워모듈4개만 시험
./run_fr5_cycle.sh --execute --part SMD     # SMD5개만 근접촬영 후 시험
./run_fr5_cycle.sh --stop                   # 현재 API 작업 중단 요청
```

`--part`는 GPU/HBM/PM/VRM/IND/SMD의 해당 종류 전체를 의미한다. 대상 슬롯은 비우고,
해당 종류 부품은 모두 트레이에 준비해야 한다. 다른 부품은 옮기지 않는다.
부품 시험도 새 기판·트레이 관측/필요한VRM정밀측정·SMD근접측정/IK/파지검사/배치/복귀사진을 사용한다.
과거 runtime/ 시험스크립트·저장계획은 이력이며 앞으로 실행 진입점으로 사용하지 않는다.
내부 실행기 `scripts/run_assembly_cycle_worker.sh`는 API가 호출한다. 공개 런처를
내부에서 다시 호출하지 않으므로 API 재귀호출이 없다.

기본/--dry-run은 API 상태 조회이며 로봇에 접속하지 않는 오프라인 계획 검사가 아니다.
--execute는 종전과 같이 현장 준비를 확인한 명시적 실행 요청이다.
CLI Ctrl+C는 해당 job/operation 중단을 API에 요청하고 결과를 기다린다.
통신 두절/시간초과는 물리 작업 취소가 아니므로 새 ID로 자동 재실행하지 않는다.

API `assembly.start`의 선택 필드 `profile` 기본값은 full, 허용값은 위6종류와 full이다.
`assembly.check`는 profile=full만 허용하고 scene-ready 없이도 무동작 점검만 수행한다.
완료상태 check_completed/check_failed는 장치점검 결과이며 조립완료가 아니다.
Unity `StartAssembly(true, "HBM")`으로 같은 그룹 시험을 요청할 수 있다.

## 제공 레시피 검토

최신 참고 YAML: `assembly_integration/config/sequencer_recipe.current.yaml`.
원본 `sequencer_recipe.example.yaml`은 이전 예제로 보존했다.
새 파일은 사용자 제공 순서 HBM8→PM4→GPU1→CAP5→IND2→VRM5와
Home→Pick→Home→AssemblyReady→Place 흐름을 유지하고 그리퍼 값을 갱신했다.
이 참고 YAML 자체를 무인 실기 준비 완료로 간주하면 안 된다.

| 부품 | 진입 개도 | 파지 개도 | 해제 개도 | 제공 YAML에서 수정 |
|---|---:|---:|---:|---|
| HBM | 25 | 18 | 25 | 진입값 명시 |
| PM | 30 | 25 | 30 | 파지26→25 |
| GPU | 70 | 65 | 70 | 진입값 명시 |
| CAP(SMD) | 18 | 12 | 17 | 파지5→12, 해제8→17 |
| IND | 21 | 14 | 20 | 파지16→14 |
| VRM | 30 | 24 | 28 | 파지32→24, 해제34→28 |

높이·방향·속도·힘은 내부 `part_gripper_recipes.json`과 성공 방향표가 원본이다.
SMD force1, PM2 배치C180, PM −0.5mm/HBM −1.0mm/CAP1 −1.7mm/CAP2~5 −2.4mm를
전체 사이클이 그대로 사용한다. YAML에 TCP나 경험적 보정값 사본을 추가하지 않는다.

| 흐름 | 현재 지원 범위 |
|---|---|
| conveyor.move_to | 외부 Sequencer handler 필요. 이 조립 API가 컨베이어를 제어하지 않음 |
| vision.resolve_targets | 기존 비전 API/어댑터 있음. 전체 사이클은 자체 새 촬영·보정·근접SMD 측정을 사용 |
| robot.move_joint / pick / place | 기존 개별 API 있음. 임시 준비점, 목표 freshness, 경로·파지검사 차이 때문에 YAML 전체 실기 검증은 미완료 |
| assembly.start | 이번에 내부 전체25개 런처와 연결. 새 촬영·전체IK·파지검사·저속하강·해제·후퇴 재사용 |
| inspection.run | 외부 handler 필요. 동작완료를 검사PASS로 처리하지 않음 |
| robot.transfer assembled_pcb | 기존 계약/단계 구현은 있으나 실제 PCB pickup/drop 교정·파지검증 미완료 |

`item_ready`와 `assembly_ready`는 Home 복사본이다. 실기 교시가 끝났다는 뜻이 아니다.
완성 PCB 개도0/100 역시 검증된 PCB 파지값으로 인정하지 않는다.

## 실제 전체 사이클 순서

검증된 런처의 순서: GPU1→HBM8→PM4→VRM5→IND2→SMD5.
PlaceCamera/TrayHome 새 촬영, VRM 정밀 측정, 일반20개 계획/IK/실행,
SMDView 근접촬영, SMD5 계획/IK/실행을 따른다.
사용자 YAML 순서로 재정렬하거나 부품 사이에 Home 이동을 추가하지 않는다.
컨베이어·검사·PCB 이송은 호출자가 전후로 수행하는 별도 공정이다.

## 토픽과 상태 조회

| 용도 | 이름 | ROS 형식 |
|---|---|---|
| 시작/점검/중단 요청 | `/real/assembly/command` | std_msgs/String JSON |
| 요청 결과/진행 | `/real/assembly/event` | std_msgs/String JSON |
| 재접속용 현재 상태 | `/real/assembly/state` | std_msgs/String JSON, 2Hz, transient-local |
| 실제 로봇 피드백 | `/real/assembly/robot_state` | std_msgs/String JSON, 10Hz |
| 현재 상태 조회 | `/real/assembly/status` | std_srvs/Trigger, message JSON |

먼저 상태에서 현재 `recipe_revision`, `hardware_execution_enabled`를 읽는다.
화면의 명시적 시작 동작에서만 아래 요청을 전송한다. 로봇이 빈 그리퍼이고,
기판이 비어 있으며, 트레이25개·지그·작업영역 준비가 끝났을 때만
`confirm_scene_ready=true`로 보낸다. 이는 카메라의 자동 안전 판정을 뜻하지 않는다.

```json
{
  "schema": "fr5.assembly_cycle/v1",
  "action": "assembly.start",
  "job_id": "11111111-1111-4111-8111-111111111111",
  "operation_id": "22222222-2222-4222-8222-222222222222",
  "recipe_revision": "20260908_integrated_pm02_heights_udp_camera_return",
  "confirm_scene_ready": true
}
```

시작마다 새 UUID를 사용한다. 같은 operation_id와 같은 내용의 재전송은 저장된 상태만
반환하며 두 번 실행하지 않는다. 같은 ID로 내용을 바꾸면 request_rejected다.
임의 TCP/파일경로/실행명령 필드는 거부한다. 시작 직전 레시피 revision도 다시 검사한다.
실행폴더는 `runtime/assembly_cycles/<operation_id>`이며 기존 폴더를 재사용하지 않는다.

중단은 현재 job/operation을 지정한다.

```json
{"schema":"fr5.assembly_cycle/v1","action":"assembly.stop","job_id":"11111111-1111-4111-8111-111111111111","operation_id":"22222222-2222-4222-8222-222222222222"}
```

런처에 SIGINT를 전달하고, 런처가 실행 중인 작업의 기존 중단·StopMotion 처리를 수행한다.
`stop_requested`는 정지 완료가 아니다. 오류/중단 뒤 `recovery_required`는 현장상태와
실행기 중단 로그 확인이 필요함을 뜻한다. 자동 resume/regrasp/restart 기능은 없다.
기존 `/real/robot/pause`는 개별 operation용이며 전체 사이클에는 위 중단 API를 사용한다.

## Unity 동기화

`unity_integration/Assets/Scripts/AssemblyCycleClient.cs`를 지속되는 씬 오브젝트에 연결한다.
Start 버튼에서 `StartAssembly(true)`, Stop 버튼에서 `RequestStop()`을 호출한다.
컴포넌트를 켜거나 연결이 복구됐다고 시작 명령을 자동 발행하지 않는다.
`StateChanged`의 step/completed_slots/last_verified_waypoint로 단계와 부품별 동작완료를 표시한다.
`MeasuredRobotState`의 joints_deg(J1~J6, degree), tcp_mm_deg(XYZABC),
gripper_position, state_fresh를 기존 실제 로봇 모델 수신기에 연결한다.
`state_fresh=false` 또는 수신 중단일 때 실제 로봇 표시를 stale로 표시하고 움직임을 추정하지 않는다.
`AssemblyMeasuredRobotSynchronizer.cs`를 실제 로봇 표시 모델에 붙이고 client/J1~J6를 할당하면 관절 피드백을 drive target에 반영한다. 기존 실제 모델 드라이브 작성 컴포넌트와 동시에 사용하지 않는다. StateFresh로 수신 중단을 표시한다.
모델별 축 부호/영점은 기존 보정값을 유지한다. 이것은 실제 피드백이며 Ghost 목표가 아니다.
이 어댑터는 내부 사이클의 새 Ghost 궤적이나 접촉 시뮬레이션을 제공하지 않는다.

terminal `motion_complete_awaiting_physical_verification`은 25개 동작완료 증거가 있을 때만 반환한다.
`physical_placement_verified`는 false이며 부품 정밀안착이나 검사PASS를 의미하지 않는다.
기존 AssemblyProgressSynchronizer의 물리조립확정 이벤트로 무조건 변환하지 않는다.
`request_rejected`는 요청 거절일 뿐 기존 작업의 완료나 실패를 덮어쓰지 않는다.
네트워크 타임아웃 때 새 operation_id로 재시작하지 말고 상태를 먼저 확인한다.

## 운영 및 검증 한계

기존 `scripts/run_real_robot_api.sh`가 새 API도 함께 서비스한다.
KSMC_ROOT가 유효한 프로젝트를 가리킬 때 연결되며 기존 하드웨어 활성화 값을 유지한다.
개별 API와 CLI 전체 사이클은 같은 launcher.lock을 사용한다.
잠금 실패 요청은 소유 중인 로봇에 StopMotion을 보내지 않는다.
진행중/미해결 실행 기록을 발견하면 API 재시작 후 재실행을 차단한다.
운영 서버는 server.lock으로 한 인스턴스만 허용한다. 관리자가 복구기록을 검토하기 전
recovery_required 기록을 삭제하거나 시각을 바꿔 재실행하지 않는다.

자동검사는 모의 프로세스만 사용한다. 실제 전체 사이클 API 호출과 Unity Editor 컴파일·
씬 연결은 별도 실기/외부 환경 검증이 필요하다. 수동정위치 사진 보정은 여전히 미완료다.
