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

요청 수락은 완료가 아닙니다. Unity는 backend가 실제 완료를 반환한 뒤에만 성공을 표시하고 실패와 timeout을 사용자에게 전달합니다.

## 문서

- [Unity UI 책임](Docs/UI.md)
- [HMI 설계 원칙](Docs/ui-design.md)
- [전체 시스템 아키텍처](../docs/architecture/index.md)
- [계층 간 통합 계약](../docs/API.md)
