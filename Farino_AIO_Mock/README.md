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
psql "$DB_ADMIN_DSN" -f DATA_STATION/DB/005_roles.sql
```

신규 Mock DB:

```bash
psql "$DB_ADMIN_DSN" -f DATA_STATION/DB/production_schema.sql
psql "$DB_ADMIN_DSN" -f DATA_STATION/DB/004_mock_seed.sql
psql "$DB_ADMIN_DSN" -f DATA_STATION/DB/005_roles.sql
```

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

대책서 이메일은 기본 비활성입니다. 활성화할 때 아래 변수를 launch 프로세스에 전달합니다.
SMTP 비밀번호 파일은 배포 secret으로 만들고 소유자 읽기만 허용하며 저장소에 두지 않습니다.

| 변수 | 필수/기본값 | 의미 |
|---|---|---|
| `DEFECT_MAIL_ENABLED` | `false` | `true`일 때 전송 worker 시작 |
| `DEFECT_MAIL_HOST` | 활성 시 필수 | SMTP 서버 |
| `DEFECT_MAIL_SECURITY` | `ssl` | `ssl` 또는 `starttls` |
| `DEFECT_MAIL_PORT` | SSL `465`, STARTTLS `587` | SMTP 포트 |
| `DEFECT_MAIL_FROM` | 활성 시 필수 | 발신 주소 |
| `DEFECT_MAIL_TO` | 활성 시 필수 | 쉼표로 구분한 수신 주소 |
| `DEFECT_MAIL_ALLOWED_DOMAINS` | 활성 시 필수 | 수신 허용 도메인 목록 |
| `DEFECT_MAIL_USERNAME` | 선택 | SMTP 인증 사용자 |
| `DEFECT_MAIL_SECRET_FILE` | 인증 시 필수 | 권한 `0600`인 비밀번호 파일 |
| `DEFECT_IMAGE_ROOT` | `UnityDT/Assets/StreamingAssets` | 검사 이미지 허용 루트 |
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

검증은 메일 서버 없이 다음 self-check로 수행합니다. 실제 SMTP 전송은 승인된 테스트
수신 주소로 별도 확인합니다.

```bash
python3 MAIN_SERVER/generate_defect_reports.py --self-check
```

## 안전 경계

backend는 timeout, 통신 실패와 로봇 fault를 호출자에게 전달합니다. 물리 E-Stop은 하드와이어드 안전회로가 수행하고 소프트웨어는 안전 상태 수신, 신규 명령 차단과 실패 전달을 담당합니다.

## 문서

- [시스템 아키텍처](../docs/architecture/index.md)
- [계층 간 통합 계약](../docs/API.md)
- [Assembly Sequencer](../ASSEMBLY_SEQUENCER/README.md)
