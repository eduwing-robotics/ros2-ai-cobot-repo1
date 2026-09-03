# Farino_AIO_Mock

FR5의 MoveIt 구성, 하드웨어 연동과 Mock 실행 backend를 포함하는 ROS 2 workspace입니다.

## 역할과 책임

- FR5 모델, 메시지와 MoveIt 실행 구성
- Real 로봇 상태와 저수준 명령 경계
- Mock 로봇 동작과 검사 backend
- 의미 단위 설비 동작의 입력 검증과 실제 완료·실패 반환
- 통합 Mock 실행에 필요한 설비 프로세스 구성

HTTP 요청 수신, Job 선택, 조립 업무 순서와 production DB 갱신은 소유하지 않습니다.

## Mock과 Real

Mock과 Real은 상위 계층에 같은 업무 의미를 제공해야 합니다. 구현 차이는 좌표 출처, 장비 통신과 완료 감지 안에 숨깁니다.

Mock 성공도 시뮬레이션 요청 수락이 아니라 동작과 검사 완료를 뜻합니다. Real에서 지원하지 않는 기능은 임시 성공을 반환하지 않고 명시적으로 실패합니다.

## 안전 경계

backend는 timeout, 통신 실패와 로봇 fault를 호출자에게 전달합니다. 물리 E-Stop은 하드와이어드 안전회로가 수행하고 소프트웨어는 안전 상태 수신, 신규 명령 차단과 실패 전달을 담당합니다.

## 문서

- [시스템 아키텍처](../docs/architecture/index.md)
- [계층 간 통합 계약](../docs/API.md)
- [Assembly Sequencer](../ASSEMBLY_SEQUENCER/README.md)
