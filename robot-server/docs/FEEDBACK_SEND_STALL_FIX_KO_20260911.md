# 2026-09-11 피드백 송신 대기 수정

## 원인과 근거

16:54 PlaceCamera 이동 중 ROBOT_TIMEOUT으로 중단된 실행은 37f4778f-e35a-4e8b-a79a-fb606d107876이다. 실패 당시 네이티브 추적은 없으므로 아래 정지 상태 재현을 당시의 유일 원인으로 단정하지 않는다.

- 로봇 TCP 20005 수신 패킷 최대 간격 10.335ms, 같은 측정의 ROS 수신 최대 공백 469.834ms.
- 드라이버 rcl_publish 함수에서 최대 338ms 소요 관측. Fast DDS RTPSWriter::send_nts 내부 잠금 대기 확인.
- UDP sendto가 원격 DDS 주소(192.168.11.4, 10.77.5.1, 10.77.5.2 등)로 송신할 때 최대 약 300ms 대기하는 추적 확인. 목적지 장비가 고장났다는 의미는 아니다.
- 드라이버 UDP 전환만으로는 공백이 남았다(최대 333.447ms, 250ms 초과 3회).
- 드라이버 비차단 송신 적용 후 발행 1,794회 중 최대 2.517ms, 250ms 초과 0회.
- API도 UDP 송신 최대 341.047ms 대기가 확인돼 동일 프로필을 적용했다.
- 드라이버만 수정한 중간 65초 검사에서는 352.847ms 공백 1회가 남았다. 이 결과는 verification.json에 보존했다. 최종 결과와 혼동하지 않는다.

## 최종 변경

- config/fairino_fastdds.xml: UDPv4 사용자 전송, non_blocking_send=true, useBuiltinTransports=false.
- scripts/run_fairino_endpoint.sh: 드라이버 자식에만 FASTRTPS_DEFAULT_PROFILES_FILE 지정. Unity endpoint 환경 유지.
- scripts/run_real_robot_api.sh: API에도 동일 프로필 지정. 자식 worker가 환경을 상속한다.
- 프로필 경로 재정의: KSMC_FAIRINO_DDS_PROFILE / KSMC_REAL_API_DDS_PROFILE.
- 프로필이 전송을 결정하므로 기존 KSMC_REAL_API_TRANSPORT만으로 프로필을 덮어쓰지 않는다.
- 250ms 신선도 검사, Reliable QoS, 좌표, 경로, 실행 복구 기준은 변경하지 않았다.

송신 버퍼 포화 시 패킷이 유실될 수 있지만 송신 호출이 버퍼 대기로 로컬 피드백 처리를 붙잡지 않도록 하는 설정이다. 원격 수신 무손실을 보장하지 않는다. 동작 의미는 [Fast DDS 2.14 UDPTransportDescriptor 공식 문서](https://fast-dds.docs.eprosima.com/en/2.x/fastdds/api_reference/transport/udp_transport/udp_transport_descriptor.html)를 참고한다.

## 배포 및 최종 검증

로봇 정지와 활성 조립 worker 부재를 확인한 뒤 드라이버/endpoint와 API를 순차 재시작했다. 전체 스택 RUNNING, Unity TCP 10000 연결 유지, 두 프로세스 실제 환경에 프로필 적용 확인.

- 최종 65.00초, 6,075개 피드백, 최대 수신 공백 139.590ms, 250ms 초과 0회.
- 진단기 자체 루프 최대 공백 15.240ms.
- API 상태 조회 6회 모두 state_fresh=true, robot_motion_done=1, active_operation=null.
- 런처 기존 테스트 13개 통과, Bash 문법 및 diff 공백 검사 통과.
- 상세 증거: runtime/feedback_fix_20260911/final_verification.json, publish_after.txt, api_send_before.txt, process_environment.json, udp_send.txt.

## 남은 현장 상태

로봇은 정지, abnormal_stop=1이며 기존 실패의 recovery_required=true를 보존했다. 현장 정리 확인, recover_assembly.sh의 복구 성공 확인 후 새 실행 ID로 시작해야 한다. 이 작업은 이동, 그리퍼 동작, ResetAllError, 새 조립 시작을 보내지 않았다. 전체 실제 생산 사이클에서의 검증은 아직 하지 않았다.
