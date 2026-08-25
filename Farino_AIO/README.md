# Farino_AIO

FR5 MoveIt 구성, Mock 조립 노드와 선택적 PostgreSQL bridge를 포함하는 ROS2 workspace입니다.

## 현재 기능

- MoveIt 기반 Mock 수동 이동과 고정 레시피 Pick·Place
- `/unity/assembly/start` 서비스와 `/unity/assembly/feedback` 토픽
- 실행 중 중복 조립·수동 명령 차단
- `mock_db_mvp` bridge를 통한 Job·Unit·재고·검사 기록
- Mock 검사 PASS/FAIL 확률과 seed 설정

## 문서

- [프로젝트 기능 목표](../overview.md)
- [작업 계획](../TODO.md)
- [Unity ↔ ROS2 API](../UnityDT/Docs/API.md)
- [현재 시스템 구조](../UnityDT/Docs/Architecture.md)
- [DB 핵심 설계](../UnityDT/Docs/DB.md)
