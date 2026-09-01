# MAIN_SERVER

제품·부품·재고·작업·검사 결과를 조회하고 조립 요청을 PostgreSQL의 영속
제어 큐에 저장하는 HTTP 서버입니다.

## 역할과 책임

- 역할: UnityDT와 생산 데이터·조립 요청 사이의 HTTP 경계
- 책임: 요청 검증, 생산 데이터 조회, `control.assembly_requests` 기록, 불량대책서 생성
- 책임 아님: 생산 테이블 갱신, 조립 순서 제어, 로봇 직접 제어

## 현재 기능

- 제품, 슬롯·부품 구성과 생산 가능 수량 조회
- 요청 수량 기준 재고·부족분 조회
- Job, Unit, 검사와 불량 슬롯 조회
- 제품별 슬롯 불량률 조회
- 조립 시작 요청의 `control.assembly_requests` 저장과 현재/최근 조립 스냅샷 조회
- production 불량과 XLSX 데이터시트를 결합한 불량대책서 파일 생성
- `MAIN_SERVER_MODE=mock|real` 실행 설정 검증

`POST /api/v1/assemblies`는 ROS2를 호출하지 않고 요청을 PostgreSQL에 저장한다.
따라서 제품 조회와 조립 요청에는 DB 연결만 필요하다. 같은 DSN으로
`production`은 조회하고 `control.assembly_requests`는 읽고 쓸 수 있어야 한다.

`GET /api/v1/assemblies/current`만 AssemblySequencer의 ROS2 status service를
호출하므로 이 route를 사용할 프로세스에는 ROS2와 `Farino_AIO_Mock` workspace가
source돼야 한다. Mock 전체 실행은 [Farino_AIO_Mock](../Farino_AIO_Mock/README.md#mock-올인원-실행)을 따른다.

## 불량대책서 생성

`generate_defect_reports.py`는 완료된 Job의 FAIL 기록을 읽고, Job·부품·불량유형별
대책서를 `reports/defects/QA-J{job_id}-{part_id}-{defect_type}.xlsx`로 생성합니다.
같은 파일이 있으면 담당자 회신을 보호하기 위해 덮어쓰지 않습니다.

```bash
cd /home/codlab/Main_Unity
MAIN_SERVER_DB_DSN='dbname=main_unity_mock_test' \
  python3 MAIN_SERVER/generate_defect_reports.py
```

자동 발행은 운영 계정의 crontab에서 같은 명령을 1분마다 호출합니다.

```cron
* * * * * cd /home/codlab/Main_Unity && /usr/bin/flock -n /tmp/main-unity-defect-reports.lock /usr/bin/env MAIN_SERVER_DB_DSN='dbname=main_unity_mock_test' /usr/bin/python3 MAIN_SERVER/generate_defect_reports.py >> MAIN_SERVER/reports/defects/generator.log 2>&1
```

부품·단가·검사항목은
`data/semiconductor_assembly_quality_datasheet_2026-08-18.xlsx`를 직접 읽습니다.
DB 업무 데이터는 `production` 7개 테이블과 `control.assembly_requests`에만 둡니다.

XLSX 접근은 [datasheet.py](datasheet.py) 한 곳에 모여 있고, HTTP API와 대책서
생성기가 같이 씁니다. 파일 mtime이 바뀌면 다시 읽으므로 시트를 고쳐도 서버를
재시작하지 않아도 됩니다. 조회 키는 `production.parts.part_category`이고,
데이터시트의 `부품 타입`과 같은 값이어야 합니다.

운영 원본은 지정된 부품·품질 데이터 담당자만 수정하고, 다른 담당자가 필수값·단가·
검사 기준을 검토한 커밋만 배포합니다. 운영 중인 파일을 직접 덮어쓰지 않고 승인된
파일을 교체합니다. 로더는 필수 문자열, 양수 단가, `YYYY-MM-DD` 확인일,
`(부품 타입, MPN)` 중복, Components/Checklist 카테고리 일치를 검사합니다.
DB 선택 MPN이 없으면 최저가로 대체하지 않고 오류를 반환하며, 불량대책서에는 원본
파일명과 SHA-256을 함께 기록합니다.

## 문서

- [HTTP API 계약](Main_serverAPI.md)
- [현재 시스템 구조](../UnityDT/Docs/Architecture.md)
- [DB 핵심 설계](../UnityDT/Docs/DB.md)
