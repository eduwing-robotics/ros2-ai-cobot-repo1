# 현재 Unity UI

이 문서는 현재 UI 파일과 데이터 경계만 설명한다.

## 페이지

| 페이지 | 현재 상태 |
|---|---|
| RUN | 로봇 상태, 조립 진행과 Scenario 시작 경로가 있다. |
| REQUEST | UXML과 binder가 있으나 MainServer 작업 API 연결은 완료되지 않았다. |
| INSPECT | 카메라·검사 레이아웃이 있으나 실제 Unit·불량 조회 연결은 완료되지 않았다. |
| MANUAL | 로봇 상태를 표시한다. APPLY·그리퍼 실동작과 `IRobotControl` 명령 경로는 아직 연결되지 않았다. |
| QUALITY | 레이아웃과 빈 상태가 있으나 실제 품질 조회 연결은 완료되지 않았다. |
| SETUP | 라우터 항목만 있고 UXML은 없어 비활성이다. |

`FR5PageRouter`는 활성 페이지의 `UIDocument`만 켠다. 공통 셸과 색·타이포 규칙은 `FR5Shell.uxml`과 `FR5Theme.uss`에 있다.

## 데이터 경계

- `UIMaster`가 `RobotMaster`, 공통 상태, 조립 진행과 Scene 참조를 UI binder에 제공한다.
- UI와 Scenario는 Mock/Real 구현 클래스를 직접 참조하거나 캐스팅하지 않는다.
- 실시간 로봇·조립 상태는 ROS/공통 runtime 상태에서 읽는다.
- 제품·재고·Job·검사·품질 데이터는 MainServer API 연결 전까지 `FR5EmptyState`로 미연결임을 표시한다.
- UI는 DB에 직접 접속하지 않는다.

## 구현 파일

- `Assets/UI/FR5Run.uxml`, `FR5RunBinder.cs`
- `Assets/UI/FR5Request.uxml`, `FR5RequestBinder.cs`
- `Assets/UI/FR5Inspect.uxml`, `FR5InspectBinder.cs`
- `Assets/UI/FR5Manual.uxml`, `FR5ManualBinder.cs`, `ManualJointPanel.cs`
- `Assets/UI/FR5Quality.uxml`, `FR5QualityBinder.cs`
- `Assets/UI/FR5PageRouter.cs`, `UIMaster.cs`, `FR5EmptyState.cs`
