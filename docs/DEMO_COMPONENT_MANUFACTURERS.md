# 시연용 부품 제조사 정보

3D 프린팅 모형에 지정한 시연용 정보이며 영상에서 제조사를 식별한 결과가 아니다.

| part_id | manufacturer |
|---|---|
| GPU | NVIDIA |
| HBM | SK hynix |
| PM | Texas Instruments |
| VRM | Infineon Technologies |
| IND | TDK |
| CAP | Samsung Electro-Mechanics (삼성전기) |

신규 결과 JSON의 `result.slots[]`, `result.findings[]`에 `manufacturer`,
`manufacturer_basis`가 추가된다. basis는 `DEMO_ASSIGNED_NOT_IMAGE_INFERRED`이다.
기존 판정·불량 코드·ID·PNG 엔드포인트는 변경하지 않는다. 엄격한 JSON 스키마를
쓰는 수신자는 추가 필드를 허용해야 한다. DB 직접 쓰기나 대책서 생성은 수행하지 않는다.

기존 PM 품번 TPSM84424MOLR은 호환성을 위해 보존하되
`product_code_basis=LEGACY_DEMO_REFERENCE_NOT_VERIFIED_PHYSICAL_PART`로 표시한다.
다른 부품의 품번은 새로 만들어 넣지 않는다.

실행 중인 API는 exporter 모듈을 메모리에 유지할 수 있으므로 요청이 없는 때 재시작한 후
새 inspection_id로 확인해야 한다. 이전 검사 자료는 수정하지 않는다.
