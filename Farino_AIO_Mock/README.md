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

## Mock 올인원 실행

저장소 루트에서 DB와 역할 권한을 먼저 적용합니다. 기존 DB는 migration을, 신규 DB는
기준 DDL을 사용합니다. `DB_ADMIN_DSN`은 DDL과 역할 변경 권한이 있는 운영용 접속
문자열이며 애플리케이션에 전달하지 않습니다.

기존 DB:

```bash
psql "$DB_ADMIN_DSN" -f DATA_STATION/DB/007_defect_report_delivery_migration.sql
psql "$DB_ADMIN_DSN" -v ON_ERROR_STOP=1 -f DATA_STATION/DB/008_vision_slot_results_migration.sql
psql "$DB_ADMIN_DSN" -v ON_ERROR_STOP=1 -f DATA_STATION/DB/009_unit_execution_completion_migration.sql
psql "$DB_ADMIN_DSN" -f DATA_STATION/DB/005_roles.sql
```

신규 Mock DB:

```bash
psql "$DB_ADMIN_DSN" -f DATA_STATION/DB/production_schema.sql
psql "$DB_ADMIN_DSN" -f DATA_STATION/DB/004_mock_seed.sql
psql "$DB_ADMIN_DSN" -f DATA_STATION/DB/005_roles.sql
```

DB 관리자는 접속 대상이 **Mock 전용 DB인지 먼저 확인**하고 환경을 지정합니다.
다음 명령은 접속한 DB에 적용되므로 Real DB에 실행하지 않습니다.

```bash
psql "$DB_ADMIN_DSN" <<'SQL'
SELECT format('ALTER DATABASE %I SET app.runtime_mode = %L', current_database(), 'mock') \gexec
SQL
```

MainServer·Sequencer는 `pg_db_role_setting`의 DB 전체 설정을 검사합니다.
세션 옵션으로 환경 식별값을 대신할 수 없으며, 미설정·불일치면 쓰기 전에 연결을 닫습니다.
애플리케이션 계정에는 DB 소유자·관리자 권한을 부여하지 않습니다.
Mock 계정의 Real DB 접근 및 실제 설비망 접근은 배포 관리자가 별도로 차단해야 합니다.

Mock의 손목→TCP 기본 보정은 현재 Unity의 단축된 그리퍼에 맞춘
FLU 기준 `(-0.115, 0, 254.364536) mm`, 회전 `(0, 0, 0)°`입니다.
URDF 원본의 공구 길이나 Real 현장 보정값과 혼용하지 않습니다.
PTP 접근은 현재 관절값으로 IK를 요청한 뒤 관절 목표로 계획하며,
현재 J5에서 90°를 초과해 벗어나는 궤적은 실행 전에 거절합니다.
이는 현재 조립의 손목 자세를 유지하는 Mock 정책이며 설비 안전 인증을 대신하지 않습니다.

Mock 올인원 launch는 자식 프로세스에 `ROS_DOMAIN_ID=42`를 지정합니다.
외부 ROS CLI도 `export ROS_DOMAIN_ID=42`를 사용합니다.
불량 보고 프로세스를 개별 실행할 때도 `export MAIN_SERVER_MODE=mock`을 지정합니다.
HTTP health 외 요청에는 `X-Runtime-Mode: mock` 헤더가 필요합니다.

공통 빌드와 실행:

```bash
cd ASSEMBLY_SEQUENCER
colcon build --symlink-install
source install/setup.bash
cd ../Farino_AIO_Mock
colcon build --symlink-install
source install/setup.bash
cd ..

ros2 launch mock_db_mvp launch_mock.launch.py
```

실행 전에 `PRODUCTION_DB_DSN`은 `production_writer`, `MAIN_SERVER_DB_DSN`은
`job_submitter` 권한을 상속한 배포 계정으로 export해야 합니다.
두 DSN은 서로 다른 비슈퍼유저 계정을 사용하고, 각 계정에는 해당 역할만 부여합니다.
두 역할 모두 production 테이블을 조회할 수 있지만 쓰기 권한은 분리됩니다.
계정에 반대 역할, 테이블 소유권 또는 별도 쓰기 권한을 부여하면 이 제한을 우회할 수 있습니다.

올인원 실행은 대책서를 기본 로컬 모드로 생성합니다. 기본 저장 위치는
`MAIN_SERVER/reports/defects`이며 SMTP 설정 없이 동작합니다.
`DEFECT_REPORT_OUTPUT_DIR`을 변경하면 MainServer와 생성기에 같은 경로를 전달해야 합니다.
두 프로세스는 문서 파일을 읽을 수 있는 같은 운영 계정으로 실행합니다.

이메일은 기본 비활성입니다. 이후 명시적으로 활성화할 때 아래 변수를 launch 프로세스에 전달합니다.
SMTP 비밀번호 파일은 배포 secret으로 만들고 소유자 읽기만 허용하며 저장소에 두지 않습니다.

| 변수 | 필수/기본값 | 의미 |
|---|---|---|
| `DEFECT_MAIL_ENABLED` | `false` | 기본 로컬 생성, `true`일 때 이메일 모드로 실행 |
| `DEFECT_REPORT_OUTPUT_DIR` | `MAIN_SERVER/reports/defects` | 생성기·MainServer 공통 문서 보관 경로 |
| `DEFECT_MAIL_HOST` | 활성 시 필수 | SMTP 서버 |
| `DEFECT_MAIL_SECURITY` | `ssl` | `ssl` 또는 `starttls` |
| `DEFECT_MAIL_PORT` | SSL `465`, STARTTLS `587` | SMTP 포트 |
| `DEFECT_MAIL_FROM` | 활성 시 필수 | 발신 주소 |
| `DEFECT_MAIL_TO` | 활성 시 필수 | 쉼표로 구분한 수신 주소 |
| `DEFECT_MAIL_ALLOWED_DOMAINS` | 활성 시 필수 | 수신 허용 도메인 목록 |
| `DEFECT_MAIL_USERNAME` | 선택 | SMTP 인증 사용자 |
| `DEFECT_MAIL_SECRET_FILE` | 인증 시 필수 | 권한 `0600`인 비밀번호 파일 |
| `DEFECT_IMAGE_ROOT` | `UnityDT/Assets/StreamingAssets` | 검사 JSON·이미지 허용 루트. Vision 저장 호출 시 명시 필수 |
| `DEFECT_IMAGE_MAX_BYTES` | `10485760` | 문서에 포함할 이미지 상한 |
| `DEFECT_MAIL_MAX_ATTACHMENT_BYTES` | `10485760` | XLSX 첨부 상한 |
| `DEFECT_MAIL_TIMEOUT_SECONDS` | `10` | SMTP timeout |
| `DEFECT_MAIL_POLL_SECONDS` | `2` | 대기 DB poll 간격 |
| `DEFECT_MAIL_MAX_ATTEMPTS` | `10` | 최종 실패 전 전송 시도 횟수 |

활성 예시는 실제 비밀값을 환경 변수에 노출하지 않습니다.

```bash
export DEFECT_MAIL_ENABLED=true
export DEFECT_MAIL_HOST=smtp.example.com
export DEFECT_MAIL_FROM=quality@example.com
export DEFECT_MAIL_TO=owner@example.com
export DEFECT_MAIL_ALLOWED_DOMAINS=example.com
export DEFECT_MAIL_USERNAME=quality@example.com
export DEFECT_MAIL_SECRET_FILE=/run/secrets/defect_smtp_password

ros2 launch mock_db_mvp launch_mock.launch.py
```

확정 불량 한 건 또는 전체를 로컬 생성하는 기존 진입점:

```bash
# MAIN_SERVER_MODE와 MAIN_SERVER_DB_DSN은 대상 DB에 맞게 설정한 상태
python3 MAIN_SERVER/generate_defect_reports.py --unit-defect-id 42
python3 MAIN_SERVER/generate_defect_reports.py --once
```

`--watch`는 2초 간격으로 확인하며 이미 존재하는 파일은 건너뜁니다.
`--mode email`을 명시할 때만 기존 SMTP 설정을 읽고 발송합니다.
로컬 생성 실패는 로그로 남고 watch에서 재시도합니다. 단일 실행 실패는 비정상 종료합니다.

검증은 메일 서버 없이 다음 self-check로 수행합니다. 실제 SMTP 전송은 승인된 테스트
수신 주소로 별도 확인합니다.

```bash
python3 MAIN_SERVER/generate_defect_reports.py --self-check
```

## 안전 경계

backend는 timeout, 통신 실패와 로봇 fault를 호출자에게 전달합니다. 물리 E-Stop은 하드와이어드 안전회로가 수행하고 소프트웨어는 안전 상태 수신, 신규 명령 차단과 실패 전달을 담당합니다.

## 문서

- [시스템 아키텍처](../docs/architecture/index.md)
- [공개 API 목록](../docs/API.md)
- [Assembly Sequencer](../ASSEMBLY_SEQUENCER/README.md)

## Real 실행 환경과 명령 계약

Real 통신 프로세스와 외부 ROS CLI는 `ROS_DOMAIN_ID=5`를 사용합니다.
`real_robot.launch.py`는 자식 프로세스에 5를 지정하며 command server는 다른 도메인에서
SDK 연결 전에 종료합니다. MainServer는 `MAIN_SERVER_MODE=real`과 관리자 설정
`app.runtime_mode=real`인 전용 DB를 사용합니다. 위 SQL은 확인한 Real DB에 한해서
환경 값을 `real`로 지정하여 사용합니다.

공통 Sequencer 실행 파일은 `sequencer_node`입니다. 기존 Mock 올인원 launch는
`ASSEMBLY_SEQUENCER_MODE=mock`을 지정합니다. Real launch는 `start_sequencer:=true`를
명시할 때만 `ASSEMBLY_SEQUENCER_MODE=real`로 Sequencer와 ROS TCP endpoint를 추가합니다.
기본값은 `false`이며 `start_endpoint:=false`로 이미 실행 중인 endpoint를 재사용할 수 있습니다.
Real Sequencer도 `PRODUCTION_DB_DSN`을 요구하고 관리자 설정이 Real인 DB만 사용합니다.
`recipe` 인자의 기본값은 설치된 공통 `assembly-r1.yaml`입니다.
이 선택은 기존 Real MoveIt 실행에 프로세스를 추가하는 옵션이며 전체 스택 실행기를 새로 만들지 않습니다.
현재 Real 실행 준비는 항상 미완료로 판정되므로 이 옵션으로 로봇 자동조립이 활성화되지는 않습니다.

`/fairino_remote_command_service`의 `cmd_str`는 실제 LF를 포함한 `real\n` 접두사 뒤에
기존 `Function(arguments)`를 전달합니다. 누락·다른 접두사는 `MODE_MISMATCH`를 반환하고
SDK를 호출하지 않습니다. 읽기 전용 `GetRuntimeMode()`는 접두사 없이 `real`을 반환합니다.
외부 호출자도 갱신해야 하며 접두사는 인증·설비망 접근 통제를 대체하지 않습니다.

Mock 수동 명령은 Unity가 상태 service의 모드를 확인한 뒤 발행합니다.
Mock 실행기는 arm·gripper trajectory 전송 전에 활성 FakeSystem 구성을 확인합니다.
동일 도메인에 별도 controller manager나 동일 이름의 실행 서버를 중복 배치하지 않습니다.
검증 실패·timeout은 자동 명령 재시도 없이 로그와 호출자 오류로 전달합니다.


검사 자료를 공유할 때 Sequencer와 MainServer·대책서 worker의 `DEFECT_IMAGE_ROOT`는
동일한 파일을 가리키는 보관 루트여야 합니다. 서로 다른 PC에서는 공유 마운트를 사용합니다.
배포 시 보관 루트를 먼저 만들고 두 계정이 공유하는 그룹과 디렉터리 setgid를 설정합니다.
Sequencer는 파일을 `0640`으로 저장하므로 조회 계정에는 그룹 읽기와 경로 탐색 권한이 필요합니다.
기존 Mock 샘플을 유지하려면 같은 루트에서 `InspectionSamples`도 읽을 수 있어야 합니다.
