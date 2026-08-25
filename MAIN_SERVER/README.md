# MAIN_SERVER

제품·부품·재고·작업·검사 결과를 조회하고 조립 요청을 ROS2 bridge로 전달하는 HTTP 서버입니다.

## 현재 기능

- 제품, 슬롯·부품 구성과 생산 가능 수량 조회
- 요청 수량 기준 재고·부족분 조회
- Job, Unit, 검사와 불량 슬롯 조회
- 제품별 슬롯 불량률 조회
- 조립 시작 요청과 현재/최근 조립 스냅샷 조회
- `MAIN_SERVER_MODE=mock|real` 실행 설정 검증

조립 route는 ROS2 `/unity/assembly/start` 서비스를 호출하므로 ROS2와 Farino workspace가 source된 환경이 필요합니다. DB 조회는 읽기 전용 DSN을 사용합니다.

```bash
MAIN_SERVER_MODE=mock \
MAIN_SERVER_DB_DSN='dbname=main_unity_mock_test' \
python3 MAIN_SERVER/server.py
```

## 문서

- [HTTP API 계약](Main_serverAPI.md)
- [프로젝트 기능 목표](../overview.md)
- [작업 계획](../TODO.md)
- [현재 시스템 구조](../UnityDT/Docs/Architecture.md)
- [DB 핵심 설계](../UnityDT/Docs/DB.md)
