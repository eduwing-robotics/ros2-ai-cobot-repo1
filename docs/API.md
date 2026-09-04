# 공개 API 목록

이 문서는 현재 구현되어 외부 컴포넌트가 사용하는 API 문서의 목차입니다. endpoint, payload, 오류와 완료 의미는 제공 컴포넌트의 API 문서와 실행 코드가 함께 소유합니다.

| 제공자 | 공개 경계 | 소비자 | 상세 계약 |
|---|---|---|---|
| MainServer | HTTP `/api/v1/*` | UnityDT·외부 클라이언트 | `MAIN_SERVER/Main_serverAPI.md` |
| Assembly Sequencer (Mock) | ROS 2 service·topic | UnityDT·MainServer | `ASSEMBLY_SEQUENCER/API.md` |

Real 자동 조립용 Assembly Sequencer API는 아직 구현되어 있지 않으며 endpoint나 메시지 이름을 미리 예약하지 않습니다. 구현과 IDL이 추가되는 변경에서 이 목록과 제공 컴포넌트 API 문서를 함께 갱신합니다.

다음 항목은 public API 문서 대상이 아닙니다.

- 내부 클래스, queue와 worker 구조
- PostgreSQL 내부 호출과 SQL 함수
- 레시피 파일의 구현 세부사항
- 미구현 인터페이스와 미래 계획

계층 책임, 완료·실패와 production 데이터 의미는 [시스템 아키텍처](architecture/index.md)가 소유합니다.
