# MainServer · 생산 데이터 창구와 불량대책서 생성

> 작업자 화면과 외부 클라이언트가 생산 정보를 조회하고 새 작업을 등록하는 **HTTP API 서버**입니다. 검사에서 확정된 불량은 **불량대책서(엑셀)** 로 자동 생성합니다.

## 역할

은행 창구에 비유할 수 있습니다. 요청을 검증해 장부(데이터베이스)에 기록하고 조회해 주지만, 금고(설비)를 직접 열지는 않습니다.

- 제품·부품·재고·작업·검사 결과를 조회합니다.
- 새 생산 작업(Job)을 등록하고, 아직 시작 전인 작업은 취소합니다.
- 검사 이미지와 슬롯별 불량률을 제공합니다.
- 확정 불량마다 불량대책서 XLSX를 생성하고 내려받게 합니다.

작업이 시작된 이후의 상태 변경, 조립 순서, 설비 제어는 Assembly Sequencer가 담당합니다.

## 주요 기능

| 기능 | API |
|---|---|
| 서버·DB 상태 | `GET /api/v1/health` |
| 제품과 필요 부품·재고 | `GET /api/v1/products`, `/products/{id}`, `/products/{id}/requirements`, `/parts/{id}` |
| 작업 등록 | `POST /api/v1/assemblies` |
| 작업·시도 조회 | `GET /api/v1/jobs`, `/jobs/{id}`, `/jobs/{id}/units` |
| 대기 작업 취소 | `DELETE /api/v1/jobs/{id}` |
| 검사 이미지 | `GET /api/v1/units/{id}/inspection/image` |
| 품질 통계·대책서 | `GET /api/v1/products/{id}/quality/slot-rates`, `/quality/defect-reports`, `/defect-reports/{id}/file` |
| 현재 조립 상태 | `GET /api/v1/assemblies/current` (Sequencer에 ROS 2로 조회) |

전체 요청·응답 형식은 [MainServer HTTP API](Main_serverAPI.md)를 참고하세요.

## 불량대책서 자동 생성

검사에서 불량 한 건이 확정되면, 그 불량 전용 대책서 한 장이 곧바로 발행됩니다. **시스템은 사실을 채우고, 사람은 판단만 씁니다.**

<p align="center">
  <img src="templates/images/defect-report-sample.png" width="560" alt="불량대책서 표준양식 작성 예시">
</p>

*최신 표준양식으로 발행한 QA-D21-GPU-CRACK 작성 예시(종결본). 흰 칸은 시스템이 자동으로 채우고, 노란 칸은 담당자가 작성합니다.*

1. Sequencer가 검사 FAIL을 확정하는 같은 DB 트랜잭션에서 발행 대기를 함께 기록합니다.
2. 생성기(`generate_defect_reports.py --watch`)가 2초마다 새 대기 건을 확인합니다.
3. DB 기록 · 부품 데이터시트 · 검사 증거 이미지를 표준양식에 채워 XLSX를 만듭니다.
4. 작업자는 Unity 품질 화면에서 문서를 내려받아 노란 칸을 작성합니다.

| 구분 | 내용 |
|---|---|
| 발행 단위 | 불량 1건 = 문서 1장. Job이 끝나기를 기다리지 않고 확정 즉시 발행 |
| 파일 | `QA-D{불량 ID}-{부품}-{불량 유형}.xlsx` · 대책서(A4 세로) + 대체품(A4 가로) 시트 |
| 시스템 자동 입력 | 문서번호, Job·Unit·슬롯·불량 ID, 검사·발행 시각, 부품·제조사, 불량 유형, 증거 이미지와 SHA-256 |
| 담당자 작성 | 주관 담당·회신 기한, 납품 Lot/PO, 판정 근거, 초동조치, 발생·유출 원인, 재발방지, 효과 확인, 종결 |
| 하지 않는 것 | 원인 자동 추정, 담당자가 작성한 내용을 DB에 역기록 |
| 무결성 | 이미지는 보관 루트 기준 경로·형식(JPEG/PNG)·크기를 검사한 뒤 원자적으로 확정하고, 기존 파일은 덮어쓰지 않음 |
| 전송 | 기본은 로컬 생성. email 모드에서만 발송하며, 실패 시 같은 Message-ID로 재시도하고 수신 도메인 허용 목록을 적용 |

![대체품 후보 시트](templates/images/defect-alternatives.png)

*같은 문서의 대체품 시트. 부품 데이터시트에서 같은 범주 부품의 정격·공급사·단가를 자동으로 붙입니다. 추천 순위가 아니며, 호환성 검증과 변경 승인을 거친 뒤에만 적용합니다.*

작업자가 작성한 내용을 지키기 위해 **이미 생성된 파일은 덮어쓰지 않습니다.** 필드별 입력 주체는 [불량대책서 필드 계약](templates/불량대책서_필드매핑.md)을 따릅니다.

## 설계에서 신경 쓴 점

1. **같은 요청은 한 번만 등록**
   호출자가 만든 작업 ID(UUID)로 등록합니다. 네트워크 문제로 같은 요청이 두 번 와도 기존 작업을 돌려주고, 내용이 다르면 거절합니다.
2. **등록 ≠ 실행**
   작업 등록 성공은 생산 시작을 뜻하지 않습니다. 실제 시작은 Sequencer가 설비 준비를 확인한 뒤 결정합니다.
3. **취소와 시작이 동시에 일어나도 안전**
   대기 작업 취소와 Sequencer의 작업 시작이 겹치면 데이터베이스에서 하나만 성공합니다.
4. **환경 혼동 차단**
   모든 요청에 `X-Runtime-Mode`(mock/real) 헤더를 요구하고, 서버·DB 모드와 다르면 DB 작업 전에 거절합니다.
5. **가벼운 런타임**
   서버는 Python 표준 라이브러리 HTTP 서버로 동작하고, 엑셀 데이터시트도 추가 라이브러리 없이 읽습니다.

## 기술 스택

| 분야 | 사용 기술 |
|---|---|
| 서버 | Python 3 `http.server` (ThreadingHTTPServer) |
| 데이터 | PostgreSQL (`psycopg` 3) |
| 문서 | XLSX (표준 양식 템플릿 + 데이터시트) |
| 연동 | ROS 2 `rclpy` (조립 상태 조회) |
| 테스트 | unittest 기반 API 통합 테스트 |

## 폴더 구조

```text
MAIN_SERVER/
├── server.py                    # HTTP API 진입점
├── queries.py                   # 생산 조회와 작업 등록
├── assembly_gateway.py          # Sequencer 상태 조회 (ROS 2)
├── datasheet.py                 # 부품 데이터시트 XLSX 읽기
├── generate_defect_reports.py   # 불량대책서 생성기
├── data/                        # 부품 데이터시트
├── templates/                   # 대책서 표준 양식, 필드 매핑, 양식 생성 도구
├── Main_serverAPI.md            # HTTP API 계약
└── test_server.py
```

## 실행

[최상단 실행 절차](../README.md#실행)의 `main_mock` / `main_real` 런치가 HTTP 서버와 대책서 생성기를 함께 시작합니다.

```bash
# 메일 서버 없이 대책서 생성기 자체 점검
python3 MAIN_SERVER/generate_defect_reports.py --self-check
```

## 관련 문서

- [MainServer HTTP API](Main_serverAPI.md)
- [불량대책서 필드 계약](templates/불량대책서_필드매핑.md)
- [시스템 아키텍처](../docs/architecture/index.md)
- [production 데이터 설계](../DATA_STATION/DB/README.md)

---

## 구현 상세

<details>
<summary>경계와 책임</summary>

- 외부 입력과 업무 식별자 검증
- 제품, 재고, Job, Unit과 품질 결과 조회
- 호출자가 만든 UUID `job_id`로 `PENDING` Job 등록
- 아직 claim되지 않은 `PENDING` Job 요청 철회
- 확정된 생산·검사 사실을 이용한 품질 문서 생성과 전송 상태 관리

MainServer는 요청 철회에 한해 DB의 제한된 원자 연산으로 `PENDING` Job을 `CANCELLED`로 전이합니다. claim 이후 Job·Unit 상태 전이, 조립 순서, 좌표 해석과 설비 제어는 소유하지 않습니다.

`production.jobs`가 영속 생산 요청의 유일한 진입점입니다. 같은 `job_id`와 같은 내용의 재요청은 기존 Job을 반환하고 다른 내용은 거절합니다.

Job 등록 성공은 실행 시작이나 완료가 아닙니다. MainServer 조회 실패도 실행 중인 설비나 저장된 production 상태를 변경하지 않습니다.

대기 취소는 Sequencer와 설비를 호출하지 않습니다. 취소와 claim이 경합하면 DB에서 하나만 성공하며, MainServer 계정에는 Job의 일반 UPDATE 권한을 부여하지 않습니다.

품질 문서는 확정된 불량 사실로 생성하며 작업자 회신을 보호하기 위해 기존 파일을 덮어쓰지 않습니다. 문서 전송 실패는 확정된 Unit과 검사 결과를 바꾸지 않습니다.

</details>

<details>
<summary>검사 자료 보관 조회</summary>

MainServer는 `DEFECT_IMAGE_ROOT`의 Unit별 `result.json`을 DB UID와 대조하고
검사 조회 응답에 슬롯·findings를 제공합니다. PNG는 같은 보관 루트의 파일을
크기·SHA256 검증 후 HTTP로 제공합니다. SQL에는 파일 본문을 저장하지 않습니다.
대책서 생성기는 동일 자료를 읽고 확정 불량의 UID·이미지를 검증합니다.
자료 누락·불일치는 생산 판정이나 파일을 수정하지 않고 조회·생성 실패로 전달합니다.

</details>

<details>
<summary>로컬 대책서</summary>

기존 `generate_defect_reports.py`는 기본 `local` 모드로 확정 불량 XLSX를 생성합니다.
같은 문서가 있으면 보존하며 로컬 생성은 발송 대기 기록을 claim하거나 SENT로 바꾸지 않습니다.
품질 화면은 MainServer에서 제품·슬롯별 문서 준비 여부를 조회하고 XLSX를 내려받습니다.
Unity 다운로드는 `Application.persistentDataPath/DefectReports`에 저장하며 기존 파일을 덮어쓰지 않습니다.
이메일 전송은 생성기의 명시적 `email` 모드에서만 수행합니다.
이메일 설정 변수는 [Farino_AIO_Mock 운영 참고](../Farino_AIO_Mock/README.md#운영-참고)에 정리되어 있습니다.

</details>
