# UnityDT

HBM 조립체의 Unity 디지털 트윈, 운전 UI, Scenario와 Mock/Real robot backend를 포함합니다.

## 현재 기능

- FR5 관절·TCP·그리퍼 상태 표시
- RUN, INSPECT, MANUAL, QUALITY 페이지
- `RobotMaster`의 단일 Mock/Real backend 선택과 의존성 주입
- Mock 자동 조립 요청, feedback 기반 진행 표시와 메모리 스냅샷 복구
- 주입된 `IRobotControl` 기반 수동 조작

Real 자동 조립과 MainServer 조회 데이터의 UI 연결은 아직 완료되지 않았습니다.

## 문서

- [프로젝트 기능 목표](../overview.md)
- [작업 계획](../TODO.md)
- [현재 시스템 구조](Docs/Architecture.md)
- [Unity ↔ ROS2 API](Docs/API.md)
- [현재 UI](Docs/UI.md)
- [DB 핵심 설계](Docs/DB.md)
- [조립 레시피 규격](Docs/Recipe.md)
