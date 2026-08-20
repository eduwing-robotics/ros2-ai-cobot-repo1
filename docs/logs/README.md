# KSMC 프로젝트 기록 체계

앞으로 작업 기록은 기술 영역별로 분리한다.

- `camera.md`: D435, 스마트폰, GoPro, 영상 토픽, 해상도, FPS, 인식 품질
- `robot.md`: FR5, TCP, Tool, Flange, 이동 명령, 속도, 안전
- `calibration.md`: Hand-Eye, ChArUco, intrinsic/extrinsic, 검증 오차
- `vision.md`: 카메라 역할, 객체 검출, YOLO, 수량·위치·방향·외관 검사
- `system_integration.md`: 컨베이어, 다중 카메라, 조립 공정, 검사, UI/로그
- `portfolio_evidence.md`: 포트폴리오에 사용할 문제·해결·성과·수치·산출물
- `presentation_notes.md`: 발표 자료의 스토리, 핵심 그림, 데모, 수치, 주의점

기존 전체 작업 기록은 삭제하지 않고
`FR5_EyeInHand_캘리브레이션_작업기록.md`에 보존한다. 새 작업부터는 관련
영역 파일에 우선 기록하고, 여러 영역에 걸친 중요한 결정만 전체 기록에도
요약한다. 같은 내용을 반복해서 적지 않고 서로 링크한다.

각 기록은 가능하면 다음 항목을 포함한다.

```text
날짜 / 작업 목적 / 기존 문제 / 원인 / 변경 내용 / 검증 방법 / 결과 수치
안전상 주의 / 변경 파일 / 다음 작업
```
