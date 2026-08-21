# Ros2UnityEndopoint_PKG

UnityDT와 로봇 작업 공간 사이의 연결을 담당하는 패키지입니다.

## 현재 구현된 기능

- Unity와 로봇 작업 공간의 기본 연결
- Mock 조립 시나리오 실행에 필요한 연결 경로
- 로컬 실행 안내 스크립트

## TODO

- Mock과 실제 작업 환경의 연결 반복 검증
- 연결 실패 상황의 확인 절차 정리

## 폴더 구조

```text
Ros2UnityEndopoint_PKG/
├── src/       연결 패키지 원본
├── run.sh     실행 스크립트
└── install.sh 설치 스크립트
```

## 세부 문서

- [실행 안내](실행방법.md)
- [패키지 안내](src/ROS-TCP-Endpoint/README.md)
