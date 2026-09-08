# UnityDT

HBM 조립체의 작업자 화면과 디지털 트윈을 소유하는 Unity 프로젝트입니다.

## 역할과 책임

- Scene과 Asset, 작업자 UI와 3D 상태 표현
- Scenario의 상위 업무 흐름
- `RobotMaster`에서 Mock/Real backend 선택과 계약 주입
- 자동 조립의 진행·완료·실패 표현
- 주입된 수동 제어 계약을 통한 작업자 조작

생산 DB 쓰기, Job·Unit 상태 전이, ROS 전송 중계와 설비의 실제 완료 판정은 소유하지 않습니다.

## 설계 경계

Scenario는 주입된 자동 조립 계약만 사용합니다. UI와 Scenario는 구체 Mock/Real 구현을 참조하거나 캐스팅하지 않습니다.

자동 조립과 수동 조작은 별도 계약입니다. 자동 흐름은 수동 명령을 조합해 만들지 않으며, 수동 UI는 생산 Job 상태를 변경하지 않습니다.

`IRobotScenarioControl.IsRunning`은 호출자 timeout 이후에도 추적 중인 작업을 표시합니다. Mock 완료 대기에서는 확인된 일시정지 시간을 제외하고, timeout 이후에도 종료 피드백을 받을 때까지 작업 ID와 재개 경로를 유지합니다.

요청 수락은 완료가 아닙니다. Unity는 backend가 실제 완료를 반환한 뒤에만 성공을 표시하고 실패와 timeout을 사용자에게 전달합니다.

## 조립체 씬 객체

`ItemManager`가 프리팹 슬롯·공급 위치와 현재 Job의 기판 인스턴스를 소유합니다.
Real에서는 Play 중 유효하고 안정된 기판 관측으로 Job 없이도 PCB와 25개 슬롯을 표시합니다.
`BeginUnit(jobId, unitId)`는 관측 PCB가 있으면 같은 객체를 Unit에 연결하고, 없을 때만 생성합니다.
관측만으로 Job·Unit ID를 만들거나 실행 상태를 바꾸지 않습니다.
`CompleteUnit(jobId, unitId)`는 기판과 장착 부품을 현재 위치에 보존합니다.
다른 Job의 첫 Unit을 생성할 때 이전 완료품을 정리하며, 적재 위치 이동은 수행하지 않습니다.
보존 범위는 현재 Unity 실행 세션이며 앱 재시작 후 과거 완료품 전체 복원은 제공하지 않습니다.

기판 관측이 불안정하거나 끊기면 마지막 정상 배치를 유지하며 UI에 수신·반영 경과 시간을 표시합니다.
관측에는 PCB 개체 ID가 없으므로 Unit 완료 후에는 완료품을 보존하고 다음 Unit 확인까지
관측 PCB를 새로 만들지 않습니다. 새 프레임만으로 새 PCB라고 판단하지 않습니다.
Real 관측 수신기를 비활성화하면 Unit에 연결되지 않은 관측 객체만 정리합니다.
카메라 패널은 트레이 부품 검출, PCB 인식, 컨베이어 정지선, 조립 인식 영상을 사용합니다.

Scene의 `ItemManager`에는 기존 motherboard 프리팹, `TransSpots/BoardSpawnPoint`,
`Items`, `Items/CompletedBoards`를 연결합니다. 슬롯은 프리팹 내부 Transform을,
공급 위치는 `Items/SupplyPoints`의 고정 Transform을 참조합니다.
Mock은 Unit별 공급 부품을 새로 생성하므로 완료품의 장착 부품을 회수하지 않습니다.

Mock 피드백의 `unit_id`로 투입·완료를 연결합니다. Real의 `BeginUnit`·`CompleteUnit`도
동일한 ItemManager를 사용합니다. Real 자동조립은 공통 ROS service에 요청하고
`runtime_mode=real`과 일치하는 Job 상태·DB 저장 완료를 확인합니다.
현재 Real 설비 실행은 미연결이므로 Sequencer의 `NOT_READY`를 호출자에게 전달합니다.
요청 수락이나 통신 연결만으로 성공을 반환하지 않습니다.

## 문서

- [Unity UI 책임](Docs/UI.md)
- [HMI 설계 원칙](Docs/ui-design.md)
- [전체 시스템 아키텍처](../docs/architecture/index.md)
- [공개 API 목록](../docs/API.md)
