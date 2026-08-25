# HBM 조립체 디지털 트윈

FR5, Unity 디지털 트윈, ROS2/MoveIt, MainServer와 PostgreSQL을 연결해 HBM 조립체의 Mock 조립과 생산·검사 기록을 다루는 작업 공간입니다.

기능 목표와 현재 범위는 [프로젝트 개요](overview.md) 한 문서에서 관리하고, 미구현 작업은 [TODO](TODO.md)에서 관리합니다.

## 구성

- `UnityDT/` — Unity 작업 화면, 조립 Scenario와 Mock/Real backend 선택
- `MAIN_SERVER/` — 제품·재고·작업 조회와 조립 실행 HTTP API
- `Farino_AIO/` — FR5 MoveIt, Mock 조립 노드와 DB bridge
- `Ros2UnityEndopoint_PKG/` — Unity와 ROS2 연결 패키지
- `DATA_STATION/DB/` — PostgreSQL 스키마, 기준정보와 권한 SQL

## 기준 문서

- [프로젝트 기능 목표와 현재 상태](overview.md)
- [작업 계획](TODO.md)
- [현재 시스템 구조](UnityDT/Docs/Architecture.md)
- [Unity ↔ ROS2 API](UnityDT/Docs/API.md)
- [MainServer HTTP API](MAIN_SERVER/Main_serverAPI.md)
- [production 핵심 DB 설계](UnityDT/Docs/DB.md)
- [3개 스키마 통합 설계](UnityDT/Docs/DB3.md)
- [조립 레시피 규격](UnityDT/Docs/Recipe.md)
