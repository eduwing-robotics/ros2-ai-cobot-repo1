# 조립 레시피 규격 — 로봇이 소유하는 것

## 이 문서의 범위

조립 레시피 파일의 형식과 소유 경계를 정한다. 레시피는 **DB에 저장하지 않고 로봇 관리 PC에
파일로 두며 Git으로 버전을 관리한다.**

스키마는 [DB.md](./DB.md), 계층 구조는 [Architecture.md](./Architecture.md)를 참고한다.

## 왜 DB가 아니라 파일인가

`production.jobs.recipe_version`은 레시피 본문이 아니라 **식별자만** 저장한다. 이 참조가
성립하려면 레시피 버전이 덮어써지지 않고 추가만 되어야 한다.

| 요구 | DB | 파일 + Git |
|---|---|---|
| 버전 불변성 | `UPDATE` 한 줄로 깨짐 | commit이 구조적으로 보장 |
| "R1과 R2가 뭐가 다른가" | 행 비교 쿼리를 짜야 함 | `git diff` |
| 리뷰·승인 | 별도 워크플로 필요 | PR |
| 동시 쓰기·트랜잭션 | 지원 | 불필요 (티칭은 사람이 가끔) |

레시피는 데이터라기보다 **로봇 프로그램**이다. 코드는 Git에 둔다.

DB가 맞아지는 시점은 여러 사람이 웹 UI로 자주 편집하거나, 레시피를 가로질러 질의할 일
("파지 힘 4N 이상인 스텝 전부")이 생길 때다. 현재는 둘 다 아니다.

## 소유 경계

레시피 한 스텝에 들어가는 값의 출처는 둘뿐이다.

| 값 | 출처 | 성격 |
|---|---|---|
| `slot_code` | `production.product_slots` | **복사** (생성 시 동결) |
| `part_id` | `production.product_slots` | **복사** (생성 시 동결) |
| `order`, `tool`, `source`, `target`, `motion`, `verify` | 로봇 티칭 | 로봇 소유. DB에 없음 |

`production`은 **무엇이 어디에** 들어가는지만 안다. 슬롯의 3D Pose도, 파지 힘도, 접근
방향도 모른다. `DB.md`가 담지 않기로 선언한 항목이 곧 레시피 본문의 대부분이다.

### 참조가 아니라 복사다

`slot_code`와 `part_id`는 파일에 값으로 박아 넣는다. **실행 중에 DB를 다시 읽지 않는다.**

- 로봇이 DB 없이도 돈다
- 레시피가 진짜로 동결된다. 나중에 DB가 바뀌어도 "R2로 만든 완성품"의 의미가 변하지 않는다

복사본이 어긋날 위험은 `products.definition_locked_at`이 막는다. 첫 `jobs`가 생기면
`product_slots`가 잠기므로 원본이 변하지 않는다.

## 디렉터리 구조

```text
recipes/
├── SEMICON-QA-ASSEMBLY-2026.08/      ← product_code + product_version
│   ├── R1.yaml
│   └── R2.yaml                        ← 대책 적용본
├── SEMICON-QA-ASSEMBLY-2026.09/      ← 구조가 바뀌면 디렉터리가 생긴다
│   └── R1.yaml
└── robot/
    ├── tools.yaml                     ← 그리퍼 정의 (레시피 공통)
    └── frames.yaml                    ← 좌표계 · 캘리브레이션
```

디렉터리가 `product_version`, 파일이 `recipe_version`이다. 구조가 바뀌면 디렉터리가 생기고,
공정만 튜닝하면 파일이 늘어난다. 앞서 나눈 두 축이 파일 시스템에 그대로 드러난다.

### recipe_version 명명

```text
{product_code}-{product_version}-R{n}
예: SEMICON-QA-ASSEMBLY-2026.08-R2
```

**전역 고유여야 한다.** 레시피는 특정 제품 버전의 슬롯 구성에서 파생되므로 제품마다 따로
존재하는데, `R1` 같은 제품 내 일련번호를 쓰면 서로 다른 제품이 같은 값을 갖게 되고
`recipe_version`만으로 조인하는 쿼리가 조용히 틀린다.

`n`은 1부터 증가하며 재사용하지 않는다. 폐기한 레시피의 번호도 다시 쓰지 않는다.

## 파일 규격

### 최상위

```yaml
recipe_version: SEMICON-QA-ASSEMBLY-2026.08-R2
product_code: SEMICON-QA-ASSEMBLY
product_version: "2026.08"

derived_from:
  product_id: 1001
  product_slot_ids: [5001, 5002, 5003, 5004, 5005, 5006]
  generated_at: 2026-08-19T08:40:00+09:00
  generated_by: recipe-gen 0.3.1

defaults:
  speed: 60          # mm/s
  blend: 5           # mm
  timeout_ms: 8000

steps: [ ... ]
```

| 필드 | 타입 | 필수 | 뜻 |
|---|---|---|---|
| `recipe_version` | string | O | 전역 고유. 파일명과 일치해야 한다 |
| `product_code` · `product_version` | string | O | `products` 의 값과 일치 |
| `derived_from.product_id` | int | O | 생성 시점의 제품 |
| `derived_from.product_slot_ids` | int[] | O | 생성 시 읽은 슬롯 PK 목록. 검증용 |
| `derived_from.generated_at` | timestamp | O | 생성 시각 |
| `defaults` | object | — | 스텝에서 생략된 값의 기본값 |
| `steps` | array | O | 조립 스텝. 배열 순서가 아니라 `order` 가 실행 순서 |

### steps[]

```yaml
steps:
  - order: 1
    slot_code: C01                 # production.product_slots 에서 복사
    part_id: C-001                 # production.product_slots 에서 복사
    tool: vacuum_small             # robot/tools.yaml 키

    source:                        # 부품을 집는 곳
      frame: tray_A
      index: 3                     # 트레이 셀 번호 (선택)
      pose: {x: 312.4, y: -88.0, z: 45.2, rx: 180.0, ry: 0.0, rz: 0.0}

    target:                        # 놓는 곳
      frame: board
      pose: {x: 120.0, y: 64.5, z: 12.8, rx: 180.0, ry: 0.0, rz: 90.0}

    motion:
      approach: {dz: 20.0, speed: 60, blend: 5}
      insert:   {dz: -8.0, speed: 5, force_n: 4.0, force_axis: z}
      retract:  {dz: 30.0, speed: 80}

    verify:                        # 스텝 직후 확인 (선택)
      camera: cam_top
      roi: [420, 260, 180, 140]
      timeout_ms: 1500
```

| 필드 | 타입 | 필수 | 뜻 |
|---|---|---|---|
| `order` | int | O | 1부터. 중복 불가. 실행 순서 |
| `slot_code` | string | O | DB 복사. 검사 결과 보고 시 그대로 사용 |
| `part_id` | string | O | DB 복사. 재고 차감 대상 식별 |
| `tool` | string | O | `robot/tools.yaml` 의 키 |
| `source.frame` · `target.frame` | string | O | `robot/frames.yaml` 의 키 |
| `source.pose` · `target.pose` | object | O | 해당 frame 기준 상대 Pose |
| `source.index` | int | — | 트레이 셀 번호 |
| `motion.approach` | object | O | 접근. `dz` 만큼 위에서 진입 |
| `motion.insert` | object | O | 삽입. `force_n` 도달 시 정지 |
| `motion.retract` | object | O | 후퇴 |
| `verify` | object | — | 없으면 스텝 직후 검사를 하지 않는다 |

**단위 규약**

| 항목 | 단위 |
|---|---|
| 거리 (`x`, `y`, `z`, `dz`, `blend`) | mm |
| 회전 (`rx`, `ry`, `rz`) | deg |
| 속도 (`speed`) | mm/s |
| 힘 (`force_n`) | N |
| 시간 (`timeout_ms`) | ms |

Pose는 항상 **해당 `frame` 기준 상대값**이다. 로봇 베이스 절대좌표를 직접 쓰지 않는다.
지그를 옮기면 `frames.yaml` 한 곳만 고치면 되기 때문이다.

## robot/tools.yaml

```yaml
tools:
  vacuum_small:
    type: vacuum
    tcp_offset: {x: 0.0, y: 0.0, z: 92.5, rx: 0.0, ry: 0.0, rz: 0.0}
    payload_kg: 0.15
    grip:    {vacuum_kpa: -60, settle_ms: 200}
    release: {blow_kpa: 10, duration_ms: 120}

  gripper_2f:
    type: parallel
    tcp_offset: {x: 0.0, y: 0.0, z: 118.0, rx: 0.0, ry: 0.0, rz: 0.0}
    payload_kg: 0.8
    grip:    {width_mm: 12.0, force_n: 20}
    release: {width_mm: 30.0}
```

레시피마다 반복하지 않고 여기 한 번만 정의한다. 그리퍼를 교체하면 이 파일만 고친다.

## robot/frames.yaml

```yaml
frames:
  base:   {parent: null, pose: {x: 0, y: 0, z: 0, rx: 0, ry: 0, rz: 0}}
  board:  {parent: base, pose: {x: 480.0, y: 0.0,    z: 120.0, rx: 0, ry: 0, rz: 0}}
  tray_A: {parent: base, pose: {x: 250.0, y: -320.0, z: 95.0,  rx: 0, ry: 0, rz: 0}}

calibration:
  updated_at: 2026-08-18T14:20:00+09:00
  method: 3-point touch
  operator: ...
```

**캘리브레이션이 바뀌어도 `recipe_version`은 올리지 않는다.** 좌표계 보정은 레시피 내용의
변경이 아니라 같은 레시피를 물리 환경에 다시 맞추는 일이기 때문이다. 대신 `updated_at`을
갱신해 언제 맞췄는지 남긴다.

## 검증

### 로드 시 (셀 제어 노드)

Job Order를 받고 레시피를 읽은 직후 확인한다. 하나라도 실패하면 **작업을 시작하지 않는다.**

1. `recipe_version` 이 Job Order의 값과 일치하는가
2. `recipe_version` 이 파일명·디렉터리와 일치하는가
3. `order` 가 1부터 연속이고 중복이 없는가
4. 모든 `tool` 이 `tools.yaml` 에 있는가
5. 모든 `frame` 이 `frames.yaml` 에 있는가
6. `steps` 개수와 `derived_from.product_slot_ids` 개수가 같은가

어떤 레시피로 만들었는지 확정할 수 없는 완성품은 만들지 않는다.

### 생성 시 (레시피 생성기)

DB의 슬롯 구성과 대조한다.

```sql
SELECT product_slot_id, slot_code, part_id
FROM production.product_slots
WHERE product_id = :product_id
ORDER BY product_slot_id;
```

- `product_slot_ids` 집합이 일치하는가
- 각 `slot_code` → `part_id` 대응이 일치하는가

이 대조를 생성기 마지막 단계에서 자동으로 돌린다.

## 불변성

**커밋된 레시피 파일은 수정하지 않는다.** 바꿔야 하면 새 `recipe_version`을 만든다.

`production.jobs.recipe_version`이 과거 작업이 어떤 조건으로 실행되었는지를 가리키는데,
파일을 고치면 그 참조가 가리키는 내용이 소급해서 바뀐다. 불량 대책의 효과 검증이 성립하지
않게 된다.

| 바뀌는 것 | 대응 |
|---|---|
| 슬롯 구성·부품 (구조) | 새 `product_version` → 새 디렉터리 → 레시피 재생성 |
| 순서·Pose·힘·속도 (방법) | 새 `recipe_version` → 새 파일 |
| 좌표계 보정 | `frames.yaml` 갱신. 버전 그대로 |
| 그리퍼 교체 | `tools.yaml` 갱신. 영향 범위를 확인하고 필요하면 새 레시피 |

## 티칭에서 배포까지

```text
① 펜던트로 포즈 티칭   → 컨트롤러 내부 레지스터에 임시 저장
② 익스포트            → 레지스터를 읽어 YAML 로 덤프
③ 검증               → 생성 시 검증 (위) 통과 확인
④ 리뷰 · 커밋         → R3.yaml 로 Git 에 고정
⑤ 배포               → 셀 제어 노드가 파일을 로드
```

컨트롤러 내부 저장소는 **작업대이지 원본이 아니다.** 초기화하면 사라지고, 컨트롤러가 두
대가 되면 어느 쪽이 맞는지 알 수 없다. 원본은 항상 Git에 있다.

## 데이터시트와 혼동하지 않는다

`semiconductor_assembly_quality_datasheet_*.xlsx` 는 레시피와 **무관하다.**

| 파일 | 담는 것 | 쓰는 곳 |
|---|---|---|
| 레시피 YAML | 슬롯·부품·순서·Pose·힘 | 셀 제어 노드 (실행) |
| 데이터시트 xlsx | 제조사·대체품·가격·출처·검사 항목 | 대책서 발행 백엔드 (`part_catalog`) |

데이터시트에는 슬롯이 몇 개인지, 어떤 순서인지, 어디에 놓는지가 한 줄도 없다. 이것으로는
제어 큐를 만들 수 없다. 로봇 관리 PC에 두지 않는다. 두면 로봇이 조달 데이터에 결합된다.
