# 조립 시작 자동 활성화 및 복구

실제 실행 런처는 Unity Start와 로컬 --execute의 공통 경로다. 그리퍼가 비활성이면 ActGripper(1,1)을 한 번 전송하고, 활성 상태와 유효 피드백을 1초간 확인한 후 진행한다. --check는 읽기 전용이다.

startup_safety.json은 조립 동작 시작 전임과 활성화 결과 불명 여부를 영속 기록한다. 활성화 전 intent를 기록하고 검증 성공 후에만 결과 불명을 해제한다. workflow/lease 진입 전에 동작 시작 장벽을 기록한다.

실행 프로세스가 종료되고 launcher/step 잠금을 얻을 수 있으며, 해당 실행의 동작 전 기록이 있고, 활성화 결과 불명·lease·cycle 기록·부품 완료·attachment·robot event가 없는 경우에만 자동 복구를 검토한다. 현재 로봇의 정지·건강·AUTO·Tool1/User0와 개별 API의 비활성·비보유·비복구 상태도 확인한다. 조건이 안 맞으면 recovery_required를 유지한다.

안전한 실패는 failed_before_motion / EXECUTION_FAILED로 남고 auto_recovery에 이유와 증거를 기록한다. 새 Start는 새 execution_id 및 유효한 scene_confirmation으로 전송한다. 같은 ID는 기존 결과를 반환하며 자동으로 조립을 재실행하지 않는다. Python 진단 클라이언트는 failed_before_motion을 종료 상태로 처리한다.

과거 실행에는 startup_safety.json 증거가 없으므로 이 변경만으로 자동 해제하지 않는다. 기존 실패 로그와 현장 상태를 별도로 확인해야 한다. 서버 Python 소스 변경은 설치/서버 재시작 후 적용되며, 실행 런처 스크립트는 다음 호출부터 적용된다.
