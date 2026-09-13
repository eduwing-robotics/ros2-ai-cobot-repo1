# Unity 부품 대응과 Pick/Place callback 수정

## 확인된 원인

실행 49de7115-da42-4061-8cac-8e3828f555e5의 HBM-05, PM-01, PM-03은 지속 트레이 ID가 없었다. 기존 어댑터는 null을 그대로 허용했고 이벤트 생성기는 같은 null을 여러 소스가 공유한다고 판단하여 attachment_binding_valid=false로 전송했다.

## 적용 계약

- Vision은 등록 ID, 관측 ID, 부품 타입, 원본 instance_index 조합으로 관측 범위에서 유일한 observation:SHA256 ID를 만든다. 기존 유일한 추적 ID는 유지한다. 중복 인덱스·겹친 관측 셀·유효하지 않은 원본 좌표는 ID를 부여하지 않는다.
- 표시 토픽 /vision/tray/unity_state의 id와 source_id는 같다. 각 부품에 tray_registration_id, source_observation_id, source_identity_scope도 포함한다. getTraySnapshot은 해당 부품 메타데이터를 보존한다.
- 세트 선택 이전의 원본 인덱스는 calibration_instance_index로 보존한다. source_index는 기존 레시피 계약의 부품 타입별 실행 인덱스이며 의미를 바꾸지 않는다. Unity는 source_id로 결합하고 원본 calibration 인덱스가 필요하면 calibration_instance_index를 사용한다. 두 인덱스가 항상 같다고 가정하지 않는다.
- 실행 어댑터는 모든 parts/slots에 대해 ID/관측/타입별 인덱스/슬롯 대응의 유일성과 Pick·Place 일치를 검사한다. ID만 없는 경우 유효한 원본 관측 키로 동일한 observation ID를 생성한다. 관측 키까지 누락된 과거 계획은 추정하지 않고 거부한다.
- source_bindings_sha256은 전체 대응을 고정한다. 실행기는 첫 Pick부터 같은 계획의 대응 변경을 차단하며 Place는 완료된 Pick의 보관된 계획을 사용한다. 완료된 비-SMD 단계 이후 별도 SMD 계획을 추가하는 기존 절차는 유지한다.
- callback의 source_id, source_index, tray_registration_id, source_observation_id는 해당 실행 부품에 대해 동일하게 유지한다. calibration_instance_index/source_identity_scope도 전달한다. /real/robot/status의 준비된 parts 대응에도 원본 인덱스를 노출한다.
- 유효한 대응은 attachment_binding_valid=true이다. 이 값은 실제 파지 증명이 아니다. 현재 그리퍼 피드백과 트레이 빈 셀 검사는 physical_holding_verified=true를 증명하지 못하므로 false를 유지한다. 완료 메시지가 식별자나 파지 증명을 덮어쓸 수 없다.
- 대응이 누락·중복·불일치하거나 고정 후 변경되면 INVALID_REQUEST로 거부하고 팔/그리퍼 동작을 시작하지 않는다. 거부 callback은 유효한 부품 대응이 없으므로 attachment_binding_valid=false일 수 있다. move_joint처럼 부품과 무관한 callback에도 부품 ID를 꾸며 넣지 않는다.

## 검증

전체 테스트 1,020개 통과(53.40초), Python 198개 및 셸 구문 검사 통과. 25개 부품 각각의 Pick·Place와 25개 연속 조립/50개 요청 시뮬레이션에서 callback 식별자를 검증했다. 누락/중복/불일치/실행 중 변경 시 동작 전에 거부되는 테스트도 포함한다.

runtime/source_binding_fix_20260913/recorded_validation.json은 마지막 실제 기록을 오프라인 검증한 결과다. 원본 관측과 정확히 일치하는 기록에서 calibration 인덱스를 확인하고 복사본에 보완했다. 20개 대응이 유효하며 HBM-05, PM-01, PM-03의 누락 ID 3개를 관측 범위 ID로 해결했다. 원본 실행 기록은 수정하지 않았고 재생 명령이나 타깃을 발행하지 않았다.

조립 launcher/step 잠금과 실제 정지를 확인한 뒤 API와 Vision을 재시작하여 적용했다. 로봇/그리퍼/복구 명령은 보내지 않았다. 현재 로봇 위치의 라이브 관측 결과는 runtime/source_binding_fix_20260913/live_validation.json에 기록한다. 실제 Unity에서 부품이 그리퍼에 붙고 놓이는 화면과 물리 전체 조립은 후속 실기 검증 대상이다.

추가 확인: 현재 SMD 촬영 위치에서는 전체 트레이 라이브 토픽이 valid=false/부품 0개이므로 실제 50개 라이브 ID 검증은 수행하지 못했다. 위 식별자 검증 근거는 오프라인 실제 기록과 시뮬레이션이다. 관측 자체가 ambiguous/invalid로 판정된 경우에는 어댑터의 ID 생성으로 우회할 수 없도록 추가 차단했다.
