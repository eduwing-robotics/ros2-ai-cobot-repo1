# 통합 이관 기록

## 원본

- `/home/juchan-yoon/ros2-ai-cobot-repo1`
- `/home/juchan-yoon/FR5_AIR_DEMO_20260817`

원본은 수정하거나 삭제하지 않았다.

## 이관한 항목

`ros2-ai-cobot-repo1`에서 FAIRINO 벤더 소스, Vision ROS 패키지와 인터페이스,
D435/Hand-Eye 캘리브레이션 코드, 활성 JSON/CSV 보정 데이터, 기판·부품 검출 및
단계별 조립 코드를 가져왔다.

`FR5_AIR_DEMO_20260817`에서 `fr5_process_sequences` 패키지와 테스트,
provisional 공중 교시점, 제어 아키텍처 및 commissioning 문서를 가져왔다.

## 의도적으로 제외한 항목

- 모든 `build/`, `install/`, `log/`, `runtime/log/`
- `.git`, 캐시, `__pycache__`
- calibration `archive/`
- 캘리브레이션 원본 이미지 폴더와 디버그 이미지
- GoPro, S22, Unity endpoint 등 현재 Eye-in-Hand FR5 통합에 직접 필요하지 않은 구성

제외 항목은 원본 폴더에 그대로 남아 있다. 재캘리브레이션의 원본 이미지나 과거
실험 증거가 필요하면 원본에서 선택적으로 가져온다.

## 설계 결정

`FR5_robot_control`을 앞으로의 단일 개발 루트로 사용한다. 두 ROS 작업공간은
벤더 드라이버 격리를 위해 루트 내부에서만 `robot_ws`와 `ros2_ws`로 분리한다.
이는 두 프로젝트를 따로 운영하는 것이 아니라 한 프로젝트 안에서 vendor overlay와
application overlay를 분리하는 구조다.

