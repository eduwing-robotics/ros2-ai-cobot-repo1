# MAIN_SERVER

제품·부품·재고·작업·검사 결과를 조회하고 조립 요청을 ROS2 bridge로 전달하는 HTTP 서버입니다.

## 현재 기능

- 제품, 슬롯·부품 구성과 생산 가능 수량 조회
- 요청 수량 기준 재고·부족분 조회
- Job, Unit, 검사와 불량 슬롯 조회
- 제품별 슬롯 불량률 조회
- 조립 시작 요청과 현재/최근 조립 스냅샷 조회
- production 불량과 XLSX 데이터시트를 결합한 불량대책서 파일 생성
- `MAIN_SERVER_MODE=mock|real` 실행 설정 검증

조립 route는 ROS2 `/unity/assembly/start` 서비스를 호출하므로 ROS2와 Farino
workspace가 source된 환경이 필요합니다. DB 조회는 읽기 전용 DSN을
사용합니다. Mock에서는 MainServer를 따로 실행하지 않고
[Farino_AIO Mock 올인원 실행](../Farino_AIO/README.md#mock-올인원-실행)을
사용합니다.

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

부품·대체품·검사항목은
`data/semiconductor_assembly_quality_datasheet_2026-08-18.xlsx`를 직접 읽습니다.
DB에는 `production` 6개 테이블 외의 업무 스키마를 두지 않습니다.

## 문서

- [HTTP API 계약](Main_serverAPI.md)
- [프로젝트 기능 목표](../overview.md)
- [작업 계획](../TODO.md)
- [현재 시스템 구조](../UnityDT/Docs/Architecture.md)
- [DB 핵심 설계](../UnityDT/Docs/DB.md)
