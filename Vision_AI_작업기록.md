# Vision/AI 작업 기록

Latest grouped record: [Unity request path deployment of provisional decisions](docs/logs/vision.md#2026-09-11-unity-request-path-deployment-of-provisional-decisions). Detailed entries are maintained there only; historical entries below are preserved.

## 2026-09-05 정상 복귀 확인 및 사용자 충격 전후 재촬영 묶음

- VRM 경계 학습 데이터 준비 완료(build_vrm_fixed_crop_dataset.py). 기존COMPLETE S22 24장/7scene/주부품120개를 기판 전체 정합 후 고정slot1.5x 정수crop으로 분리. ECC inverse sampling에 맞춰 정답polygon은 inverse(affine)×sourceH 적용, 원본SHA/라벨SHA/정합행렬/원점 보관, 부품별 재중심·회전/CLAHE 없음. 장면분리 train5scene20장100crop,val1scene2장10crop,test1scene2장10crop; 동일 원본 중복 거부.8crop에 이웃VRM 일부가 들어와 v2에는 잘린 이웃 정답8개도 보존(총128instance). v1은 DO_NOT_TRAIN 표시, 실제 학습 없음. 변환/분할/이웃클리핑 테스트3개 통과, v2 미리보기 직접 확인. 최종 vision_assembly/segmentation/vrm_fixed_boundary_dataset_v2. 정상만 있으므로 빈칸/불량 성능 검증 불가, 물리 부품 재사용에 따른 독립성 한계 유지. 실행 모델·카메라·로봇/컨베이어 명령 변경 없음.

- 네 변 공동 후보 실험(probe_vrm_joint_rectangle.py):각 변 최대4개 후보 조합/사각형 일치도/경쟁 사각형/raw-CLAHE 교점 비교. 기존9장45슬롯 원본SHA 확인 후 replay, 후보10/45로 기존18/45 대비 가용성 개선 없음. 정확도 검증 아니며 미적용. 기존+신규 합성 테스트11개 통과. 이어 S22 기존 세그 라벨 점검:COMPLETE24장/7scene,VRM120polygon,모두normal metadata. 3scene15polygon 원본/라벨 crop 직접 확인, 경계 보조 학습 재사용 후보 존재. 이 source에는 empty/회전 정답 마스크가 없어 정상 라벨만으로 해당 조건 검증 불가. 원본 라벨 수정/학습/실제 명령 없음. 결과 vrm_joint_rectangle_20260905.json 및 vrm_boundary_label_inventory/{inventory.json,preview.jpg}. 다음 경계 학습 검토는 이 S22 정답을 재사용하되 기존 고정슬롯/독립presence/외관 융합 계약 유지.

- vrm_line_pose_evidence.py 추가:4변 교점으로 중심/각도 산출, 경쟁선·변 각도 불일치·뒤집힌 사각형·raw/CLAHE 교점 불일치 시 좌표를 제공하지 않음.3°/4px는 실험 선 일치도 검사값이지 조립 허용 오차가 아니다. 저장9장45슬롯 중18개만 측정 후보 가능,27개 보류. 고정 정상143632 기준은VRM4만 통과해 다른 슬롯 상대 이동량은 제공하지 않음. 이전 회전144513VRM1의 raw 기울기 후보도 전체 raw/CLAHE 기하 일치 검증에는 실패: 부분적인 시각 개선을 검출 성공으로 해석하지 않음. 결과 vrm_line_pose_evidence_20260905.json. 중심·회전 합성정답/경쟁선/교차변/기울기불일치 테스트5개 통과. 실제 모델/임계값 변경, 새 촬영, 로봇·컨베이어 명령 없음. 이 경계 방식은 아직 실사용 좌표 공급자로 부적합.

- 경계 후보 개선 실험 추가:probe_vrm_robust_edges.py는9단면×최대3피크에서 결정적 직선 합의 탐색, 경쟁선/raw-CLAHE 불일치 시 불확실 표시.9장×5슬롯 저장 사진 실행 및 두 비교 이미지 직접 검토. 명시 회전144513 VRM1에서 이전 outline1.21°와 달리 현재 raw 변 기울기 크기4.76~6.77°로 기울어진 외곽을 따라가는 후보 관찰.144017 VRM5는8.67~10.84°,150517 VRM3는4.51~6.07°이나 경쟁선도 남음. 수평/수직 변은 기울기 부호 정의가 다르며 이 값은 교정된 부품 회전각이 아님.150807 위치불량은 기울기0~2.39°로 각도만으로 해결불가. 실행 판정 미적용/모든 status UNKNOWN. 단면 이상치·동등 경쟁선·무경계 입력 보존 테스트3개 통과. 결과 vrm_robust_edges_190202 및 vrm_robust_edges_pose_regression; 촬영/학습/실제 명령 없음.

- 경계 개선 실험:probe_vrm_boundary_consensus.py로4장×5슬롯에서7개 단면의 signed edge 및 raw/CLAHE 일치도를 비교. 부품/소켓 경계 후보 혼재 가능성을 드러내며 원본과 overlay 직접 확인. VRM2의185803 단면 산포14px→190202 3px, raw/CLAHE 중앙 경계 차1px→0px이나 다른 표본 산포는 최대63px. 원본/CLAHE 일치만으로 부품 경계가 맞다고 보장할 수 없고 높이·실측 여유도 아님. 진단 도구만 추가, 자동 판정에 미적용. 합성 직사각형 위치/원본 보존 및 무경계 강도 검증 테스트2개 수행. 결과 vrm_boundary_consensus_190202. 실제 카메라/모터 명령 없음.

- 오류 요인별 보관 결과 교차검증 추가(audit_vrm_failure_tracks.py). scene ID/slot으로 연결하고 현재 정답 및 존재하는 원본 SHA 일치 확인. 기존22장 replay 중 정상77개에서 geometry9오경고, 명시 회전/위치 오류5개 중 geometry4개 경고, 이동/턱걸림 배치7개 중4개 경고, POSITION_SEATING_ERROR1개는 누락. 분류 미지정 오류2개도 geometry누락. appearance는 이15개 모두 경고하나 오류 원인을 구분한 것은 아니며 이후 정상2오경고/과거VRM5누락을 포함하지 않는 별도 표본이다. 따라서 외관 점수로 턱걸림 확정 또는 outline 각도로 위치 정상 확정 불가. 결과 vrm_failure_tracks_20260905.json, 실행 모델/임계값 변경·새 촬영·실제 명령 없음.

- 동결 모델 저장 점수 분리성 진단 추가(audit_vrm_score_separation.py). 학습 split 제외, 최신 개별 재검사 report는 모델/원본 SHA 확인 후 병합. 수집된 정상86/오류19 슬롯에서 기존0.5는 정상 안착2건 경고(VRM2 공정 위치 우려와 별도), 오류1건 누락(VRM5 과거194959=0.262353). 정상 최대0.880559가 오류 최소0.262353보다 높아 공통 임계값 하나로 모두 분리 불가. 슬롯별로는 해당 저장 표본이 분리되지만 같은 개발자료로 임계값을 정하면 과적합이므로 선정/적용하지 않음. vrm_score_separation_20260905.json 보관. 위치 변화 원인 분석과 점수 분리성은 별개이며 안전 여유 측정은 아님. 재학습/촬영/실제 명령 없음.

- 저장 사진 추가 비교:185803 기준184100 VRM2 표면 매칭 dx=0,dy=0.5px,190202는 dx=-2,dy=5.5px(상관0.657,각도 검색0°). 사용자 왼쪽 이동 관찰과 영상상 수평 변화 방향은 일치하지만 아래 방향 변화도 있어 점수0.880559→0.008598을 왼쪽 이동만의 효과로 단정하지 않는다. 비교 이미지 직접 확인, 결과 runtime/inspection/vrm_motion_before_after_bump_190202. 이는 정합 영상의 국소 질감 이동 추정이며 슬롯 벽/부품 실측 간격이나 그리퍼 여유가 아니다. 허용거리/실행 판정 변경 없이 진단만 수행.

- 후속 확인:190202에서 VRM2가 살짝 왼쪽으로 이동했다고 사용자 확인.184100/185803의 우측벽 밀착은 턱걸림은 아니지만 PM 옆 그리퍼 간섭 우려 때문에 위치 오류로 취급하자는 요청을 별도 process_position_review에 기록. 기존 정상 안착 정답은 유지하고 공정 위치 오류와 분리한다. 실제 간섭/허용거리 미측정이므로 ADVISORY_ONLY/UNKNOWN, 학습 제외. 기존 오경고 수치는 안착 판별 평가이며 공정 안전 검증이 아니다. 메타데이터만 변경, 재촬영·학습·실행 임계값 변경·로봇/컨베이어 명령 없음.

- 사용자가185803은 VRM3/5 정상 복귀,VRM2는 기존 정상 우측벽 밀착 상태 그대로라고 명시 확인. VRM2/3/5만 정상 검증 라벨 추가, 다른 슬롯 미확인. 동결 점수는2=0.880559(오경고),3=0.136908,5=0.036510.
- 이후 사용자가 살짝 충격을 준 뒤 재촬영 요청:190202 flashOFF/4000×3000/69mm,overview 복구 확인. 같은 모델/같은0.5 기준에서1=0.026417,2=0.008598,3=0.022593,4=0.003533,5=0.000608로 모두 무경고. 정합0.979752. 사진 crop 비교 직접 확인. 충격 후 실제 정답은 미확인이므로 전체PASS나 충격 전 부품이 불량이었다는 결론을 내리지 않는다.
- vrm_recheck_185803/190202 및 vrm_recheck_crops_190202에 원본해시/예측/비교 보관. 두 장면 reserved manifest 추가(190202 labels/expected_pose는 빈 객체). 이전 정답을 점수에 맞춰 변경하지 않음. 학습/임계값/실제 모델 변경 또는 로봇·컨베이어 명령 없음. 정상 허용위치에 따른VRM2 오경고 문제는 유지하며 촬영/정답확인/비교를 묶어 기록.

## 2026-09-05 기판 고정 무늬·부품 표면 이동 분리 진단

- audit_vrm_board_motion.py로181938 대비183451/184100의 부품 제외 기판 특징 LK 왕복추적과 VRM 내부표면 추적을 분리. 정합 전 기판 특징 변위90백분위5.78/5.09px가 정합 후1.44/1.48px로 감소했고, 정합 후 전체 중앙값은[-0.314,-0.098]/[-0.365,-0.063]px(각246점). 전체 기판 정합이9px씩 밀린다는 설명은 지지되지 않는다.
- 독립적인 표면 LK도 VRM2 dx9.27px, VRM3 dx9.21~9.54/dy3.62~3.67px로 앞선 template 측정과 비슷했다. 초기 전체영상250점에서 VRM2/3 주변점을 고르면0개였으나, 지역별 별도 특징 추출로 VRM2 주변 고정 무늬17/16점을 확보했다(중앙값dx-0.592/-0.754px,90백분위1.09/1.31px). 따라서 초기0개는 무늬 부재가 아닌 전역 특징점 선택 편향이 섞인 결과였다. VRM3는 별도 추출에도0/2개로 부족하다. VRM2는 기판 주변 정렬과 표면 변화가 다르지만 실제 이동·높이·시점 원인까지 확정하지 않는다. 사용자 미이동 진술과 다른 슬롯 정답 미확인을 유지한다.
- 출력 vrm_board_motion_181938, vrm_board_and_surface_motion_181938, vrm_local_board_motion_181938/audit.json. 진단 마스크·왕복1px·거리40px는 측정점 선별용이며 실제 판정 규칙 아님. 촬영·학습·모델/기준 변경·로봇·컨베이어 명령 없음. 부품별 이동보정이나 전체9px 보정을 적용하지 않았음. 지역 샘플링 보완을 포함해 같은 진단 묶음에 기록.

## 2026-09-05 VRM5 정상→턱걸림→미세 턱걸림 검증 묶음 — 물리 정답 정정

- 원본181938은 정상,183451은 턱걸림,184100은 사용자가 의도적으로 아주 살짝 걸쳐 둔 불량이라고 명시했다. 이전 정상 복귀 추정 및 오경고 주장은 철회한다. manifest와 comparison.json의184100 VRM5만 FAIL로 정정했으며 이는 모델 점수가 아니라 사용자 물리 설명에 따른다.
- 동결4×4 VRM5 점수0.028589→0.987525→0.623486: 이 정상/불량/미세불량 세 장면에서는 경고 유무가 정답과 일치. 마지막 정합0.978892; 높이 독립 측정은 없음. 실제 정상복귀 시험은 아직 수행된 것으로 간주하지 않는다. 과거194959 누락은 여전히 별도 제한.
- 사용자는 다른 부품을 움직이지 않았다고 확인했다. 이를 정상 정답과 혼동하지 않고 다른 슬롯은 미확인 유지. 저장 사진 표면 매칭에서181938 대비183451/184100 VRM2는dx9/dy-0.5px, VRM3는dx10/dy3.5 및dx9/dy2.5px로 영상상 변화가 측정됐다. 이는 물리 이동이나 카메라 원인 확정이 아닌 진단값이다. 밝기/시점/정합/특징 매칭 오차를 분리해야 하며 슬롯별 자동 정합으로 결함을 지우지 않는다.
- 비교 이미지 vrm23_unchanged_review/review.png 직접 확인, 매칭 결과 vrm_unchanged_motion_181938/motion.json 보관. 이 정정·비교에서는 촬영/재학습/임계값/실제 모델 변경 또는 로봇·컨베이어 명령 없음. 두 앞선 촬영은 flashOFF/4000×3000/69mm, overview 복구 완료. 검증용 데이터 유지하며 기록을 묶어 정정.

## 2026-09-05 VRM5 비교 촬영·동결 검증 묶음 — 사용자 설명에 따른 정답 정정

- 사용자 요청으로181938 S22 flash OFF 촬영(4000×3000,69mm equivalent); overview 복구 확인. 동일256×256 VRM5 crop으로 과거194959와 비교했다. 이후 사용자가 명확히 설명: 현재181938은 벽에 최대한 붙였지만 걸치지 않은 정상이고, 불량 확인은 과거194959에 대한 말이었다. 기존 기록의 현재 불량/추가 누락 주장은 assistant의 지시대상 오해이므로 철회한다.
- 동결4×4 모델SHA f27f5fc842dade6e48c1accb39243391b3e1b8289ea0d3d13a857e864a398002 결과는 변경하지 않았다: 정합0.976093, VRM5 score0.028589, 무경고는 정상 정답과 일치한다. 자동 최종PASS가 아닌UNKNOWN/ADVISORY_ONLY 유지. 다른4슬롯은 미확인으로 집계하지 않는다.
- 원본SHA b080de57756a4614d7905b5257123c4c97f0a879fe8b19b68ae2961ac410be2c를 유지하고 manifest 및 comparison.json의 현재 VRM5만 PRESENT/PASS(normal)로 정정. 과거194959는 불량/누락 상태 유지. 검증 전용으로 정상학습에도 자동 편입하지 않음. 사진·추론점수·모델·임계값 변경 및 로봇·컨베이어 명령 없음. 이 사진을 근거로 한 추가 누락 주장을 철회하며 과거 누락 문제와 분리한다.

## 2026-09-05 비선형 분류기 오프라인 대안 검증

- 기존 원본 RGB 기반 동결B0 layer5+final 4×4 특징에 SVC RBF(C1,gamma=scale,class_weight=balanced)를 별도 적용. 기존106 train만 fit하고 validation/holdout 라벨은 학습·임계값 선택에 사용하지 않았다. 출력 sigmoid(decision margin)은 확률이 아님을 metadata에 명시했다.
- 결과 train105/106, validation10/10, 과거holdout4/5, 현재session91/92. 과거194959 VRM5 누락은 계속되고 현재150517 VRM3까지 새로 누락(score0.4861). 따라서 기존4×4 logistic 후보보다 개선되지 않아 채택하지 않았다. 새 후보는 별도candidate.joblib로 보존하고review.json에NOT_PROMOTED 명시. 현재 추론·bridge·임계값 변경 없음.
- evaluator에 실험 옵션과 기존NPZ/joblib 덮어쓰기 방지 추가, 문법 검증 통과. 저장 위치vrm_multiscale_rbf_offline_20260905. 촬영·로봇·컨베이어 명령 없음. 특징 공간/분류기만 바꾸는 두 대안 모두 미해결로, 시험 자료 성능에 맞춘 임계값 완화는 하지 않는다. 관련 구현·실행·판정을 묶어 기록.

## 2026-09-05 VRM5 누락 특징 분석 및 공간 분해능 후보 검증 묶음

- audit_vrm_holdout_features.py로 해시 확인된 학습106크롭과 분리된194959 VRM5 holdout의 동결 특징을 비교했다. 가장 가까운 정상 cosine0.84546, 불량0.80333. 기존 logit-1.03377/score0.262353을 4×4 특징 셀 기여 합+절편으로 재현했다. 특징 셀은 수용영역이 겹치므로 픽셀 결함 위치/원인으로 단정하지 않는다. 원본 3장 비교표를 직접 확인했고, 누락 crop은 정상 학습 crop과 유사하지만 물리 불량 정답은 유지했다.
- 기존 학습106건만으로 7×7 공간 특징 별도 후보를 fit(C1/진단0.5 유지). 기존4×4, active model, 데이터 라벨/분할은 불변. 결과 train106/106, validation10/10, 과거holdout4/5로 누락 해결 못함. 현재92슬롯도91/92로 낮아져150517 VRM3 불량을 새로 놓침(score0.4275). 후보를 채택하거나 bridge로 export하지 않았다.
- 산출물 vrm05_holdout_feature_audit/{audit.json,neighbors.png}, vrm_multiscale7_seating_offline_20260905/{candidate.npz,evaluation.json}. 분석 및 학습/예측 스크립트3개 문법 검증 통과. 재학습은 별도 오프라인 후보만이며 no runtime promotion/threshold change/capture/robot/conveyor commands. 기록은 특징 분석과 후보 비교를 묶어서 작성. 남은 과거 누락은 미해결이며, 반복 평가 데이터에서 성능 개선·완성을 주장하지 않는다.

## 2026-09-05 저장 데이터 일괄 검증: 위치 기준 대안·착좌 모델·과거 누락

- 촬영 없이22개 저장 장면을 기판 전용 정합 후 GPU YOLO로 일괄 재생했다. evaluate_vrm_fixed_pose.py는 과거 검증 정상151315/151404/151508의 raw centroid 중앙값만 고정 기준으로 만들고, 예약 검증 장면에 맞춰 기준이나0.70mm/3도 진단 한계를 변경하지 않았다. 초기12장 후 구형 manifest에 해시 필드가 없어 중단됐고, 재개 시 이미 생성한 이미지 해시와 검출 결과를 검증·재사용했다. 최종22장 모두 기존 manifest 또는 당시 report의 원본 해시 일치를 확인했다.
- 부품 수 독립 고정 centroid 대안은 정상77슬롯 중9오경고, 불량15슬롯 중8검출/7누락이었다. 실제 현업 적용 또는 현재 기준 교체 불가. 특히 턱걸림은 중심/평면각만으로 판단할 수 없었다. 22장 중 명시적 PRESENT+PASS/FAIL만92개 위치 평가에 포함했고, 미지정 슬롯은 임의 정상 처리하지 않았다.
- compare_vrm_pose_seating.py로 동일 정합 RGB에 동결 TorchScript+실제 presence gate(0.9)를 적용했다. 진단0.5 기준 정상77중0오경고, 불량15중15경고, 명시 EMPTY11중0착좌 경고. OR 융합은9오경고를 그대로 유지하고 AND는7불량을 놓쳤다. 단순 OR/AND나 현재 장면 보정으로 실제 규칙을 바꾸지 않았다.
- 별도 과거 holdout194959 원본 crop5개의 해시를 검증하여 실제 모델로 재추론: 정상4무경고이나 VRM5 실제 턱걸림은0.262354로 여전히 누락. 최근15/15를 완성 성능으로 보고하지 않는다. 이 장면은 학습에 편입하거나 정상 재라벨링하지 않았고 임계값도 낮추지 않았다. bridge metadata의 남은 제한 설명만 갱신, runtime_enabled=false/validated=false/ADVISORY_ONLY/비활성 sentinel 유지.
- 산출물 runtime/inspection/vrm_fixed_pose_offline_20260905/{candidate.json,evaluation.json,seating_comparison.json}; 스크립트2개 추가. 모델 재학습/실제 판정 변경/사진 촬영/로봇·컨베이어 명령 없음. 최종 제한: 과거 턱걸림 누락, 슬롯별 시점/외곽 편향, 독립 검증·임계값 검증 미완료. 관련 작업을 이 단일 묶음으로 기록함.

## 2026-09-05 VRM 위치 오경고 비교 작업 묶음

- 빈 슬롯134637/정상 VRM2 165914·170142 원본 크롭 비교, 정상170142 GPU YOLO+착좌 모델 재실행, 표면 패치 이동 비교 및 과거151315/턱걸림180801 수치 재생을 함께 검증했다. 기록은 개별 호출 대신 이 묶음 완료 시 정리한다.
- 정상170142에서도 VRM2 위치 오차1.02848mm 경고가 재현됐다. 165914 대비 표면 매칭은0도,dx0/dy0.5px(score0.7624); VRM5 실제 재배치는dx-7/dy-6.5px,3도로 다른 증거를 보였다. 이는 진단용 매칭이며 공인 위치·각도 측정값이 아니다.
- audit_vrm_pose_context.py는 과거 정상151315의 동일 중심/동일 슬롯 기준에서 공통 보정 유무만 바꾸면0.09169→0.72190mm로0.70mm 경고선을 넘는 것을 assertion으로 재현했다. 현재5개 부품 장면은 최소6개 조건 때문에 공통 보정이 꺼진다. 즉 부품 검출 수에 의존하는 보정과 그 후에 정의한 슬롯 기준의 적용 조건 불일치가 확인됐다. 경계/시점 편향도 남아 있어 이것만으로 모든 오경고 원인을 확정하지 않는다.
- 결과: vrm02_pose_boundary_review/{review.png,context_audit.json}, vrm_pose_texture_pair_170142_165914/motion.json, bridge report174122. 마지막 재생은 PatchCore를 의도적으로 생략한 geometry-only 진단이다. 모델/좌표/허용치/실제 판정 규칙 미변경, 최종UNKNOWN 유지. 촬영·로봇·컨베이어 명령 없음. 다음은 부품 수와 독립된 기판 기준 정합 및 고정 기준 보정 검증이며, 임계값 완화나 현재 장면의 중앙값 빼기로 결함을 제거하지 않는다.

## 2026-09-05 VRM2 pose warning arithmetic audit

- Added read-only audit_vrm_pose_report.py and verified five VRM residual calculations against GPU report172632 (SHA f36dc3b7ff6ff13fdd68eebbe027f540aef6a90940c38505399e9c99dbaab7f5). VRM2 warning originates from auxiliary YOLO position, not new seating classifier: raw offset[-0.609931,-0.766903]mm, fixed reference[-0.7187,0.2383]mm, residual[0.108769,-1.005203]mm, norm1.011070mm.
- Common-bias stage is inactive because only5 candidates exist versus6 required. Calibration was defined after common-bias correction, so sparse-scene applicability needs further verification. Removing fixed reference alone still leaves0.979876mm, above0.75mm: reference subtraction alone is NOT a demonstrated root-cause fix. Actual mask boundary/registration versus physical slot error remains unresolved.
- No thresholds, normal labels, active models or fusion rules changed; did not lower support count or normalize away placement defects. All five arithmetic assertions passed. No capture, training, robot or conveyor command. Next diagnostic is independent slot-boundary/reference validation on saved normal and defective scenes, not warning suppression.

## 2026-09-05 isolated full hybrid bridge replay

- Added run_vrm_bridge_report_test.py: saved165914 scene, candidate injected in memory only; disk runtime_enabled remains false, active model untouched. Initial sandbox replay lacked CUDA; escalated GPU replay completed with YOLO and PatchCore advisory providers available.
- Report runtime/inspection/vrm_bridge_full_report_test/20260905_172632_641217/hybrid_report.json and PNG visually checked.25 slots,22 candidates:20 actually absent components, VRM5 SEATING? (0.8757), plus an unwanted legacy VRM2 POSE? (YOLO offset1.011mm versus0.700mm candidate gate). Therefore full integration is NOT clean despite correct new seating evidence; do not promote or relax thresholds to hide this discrepancy.
- Heatmap is present on GPU replay; seating warning is classifier evidence, not guaranteed PatchCore heatmap activation. Final UNKNOWN, unvalidated ADVISORY_ONLY unchanged. No camera capture, robot or conveyor command. Remaining work: diagnose legacy geometric false warning and independent calibration/historical miss before deployment.

## 2026-09-05 actual VRM presence-chain replay

- Extended bridge harness --actual-presence to run existing vrm_state.torchscript.pt and actual _vrm_non_empty_confidence, instead of relying only on injected gate values.20 present crops all pass.90 nonempty gate; five empty134637 slots all blocked. New seating scores remain same as independent replay within4.77e-7.
- Uses actual saved-image state inference, but still isolated in-memory disabled bridge activation with diagnostic.5 threshold; no active metadata/file changes and not full25-stage inspection. Report integration_bridge/actual_presence_integration_test.json. All final states UNKNOWN/advisory; no authoritative promotion.
- No capture/training or robot/conveyor commands. Limited20present/5empty controls, not calibrated presence reliability. Full integrated image/report execution remains pending.


## 2026-09-05 real-crop bridge integration checks

- Added test_vrm_bridge_integration.py;20 real crops from165413/165642/165914/170142. Existing provider PIL preprocessing plus exported TorchScript versus NPZ replay max probability error4.76837e-7 (<1e-5); class/crop parity confirmed.
- Isolated in-memory harness injected presence.99/.1 and diagnostic seating.5; low presence produces UNKNOWN. Existing build_advisory_candidates shows SEATING? exactly on two warnings; fuse_required_stages remains UNKNOWN. Export metadata runtime_enabled=false confirmed unchanged before/after, active models untouched.
- No real presence-provider/end-to-end full25 inspection executed; this test does not establish actual presence gating success. Real-image conversion and advisory display compatibility now verified, calibration/historicalholdout limits remain. Report integration_bridge/real_crop_integration_test.json. No fit,capture,robot/conveyor commands.


## 2026-09-05 integration bridge preparation

- Read fusion contract and existing VrmSeatingClassifier/main path. Runtime expects TorchScript two-class logits, original registered crop pipeline and non-empty confidence>=.90. New NPZ spatial head cannot be dropped in directly. Existing display checks SEATING/statusFAIL while new diagnostic outputs UNKNOWN, so display integration still requires explicit advisory handling.
- Added export_vrm_multiscale_bridge.py: frozen layer5/final4x4 features plus stored logistic head, logits[0,z] preserving softmax/sigmoid equivalence. Separate integration_bridge under plus165057, source hash checked method/class, no overwrite; synthetic batch2 eager/trace max logiterror0.0.
- Export metadata runtime_enabled=false,validated=false,ADVISORY_ONLY, inactive threshold placeholders0/1. Active provider files untouched; no promotion. Real-crop parity and presence-gate/integrated visualization checks remain, as do threshold calibration and historicalholdout miss. No capture,training or robot/conveyor commands.


## 2026-09-05 normal reseating170142

- Fresh flash-off capture after user instructed to lift/reseat all5normal. Original viewed, overview restored. Alignment .979450, SHA f1c4963e01331fb25c5ddcc32a7620e042951219720a176c5b2ff0ca54cd08ef. Reserved validation only.
- Same frozen plus165057 f27f5fc8 model:0/5 warnings,max .003147. Postfreeze4physical scenes18normal0warnings/2defects2warnings. No reliability extrapolation to all orientations/lighting; historicalholdout miss remains. No fit,threshold or runtime changes.
- No robot/conveyor motion commands or camera settings edits. Keep scene for now; next software step should consolidate candidate evidence and validation gaps rather than request undirected repeated captures. UNKNOWN/advisory retained.


## 2026-09-05 isolated05 validation165914

- New flash-off capture inspected,overview restored.05 on-lip per setup,othersnormal; alignment .980483. SHAabb6d6bf2479200245a9f9ffacc37e34d37fb7fda80fc63c9b18632d14fed093 validation-only.
- Frozen plus165057 same f27f5fc8 artifact:05 .875697 onlywarning,other4 max .005083. Three postfreeze scenes:13normal0warnings,2defects2warnings; still limited same-session evidence, historicalholdout miss and near-threshold old03 remain limitations.
- No fit/threshold/promotion/runtime/camera changes, no robot/conveyor commands. Next fresh normal/repositioning control useful before any integration; no definitive PASS assigned.


## 2026-09-05 new04 validation165642

- Flash-off capture viewed, overview restored. New04left/on-lip per user,other4normal; alignment .980354. SHAd8a7e9022e9843a944b4e7f2529aedacbd7de2976f3a1ad705e604944efad259 reserved validation.
- Frozen plus165057 same hash:04 .811235 warning,other4 max .007826. No fitting/threshold/runtime edits. Two postfreeze scenes normal9 observations0warnings/defect1warning; too few for deployment qualification, no height metrology.
- No robot/conveyor commands or camera configuration changes. Next independent05 translation test after restoring04normal;05 not yet tested fresh with this candidate. UNKNOWN/advisory retained.


## 2026-09-05 post165057 normal165413

- Fresh flash-off capture viewed; allnormal per user,other20empty,overview restored. Alignment .979530, SHA7ba79883f29bf4ec9cf455aed88b78554583052e91985233ba87789439b33ba7 reserved validation.
- Frozen plus165057 SHA f27f5fc842dade6e48c1accb39243391b3e1b8289ea0d3d13a857e864a398002:0/5 normal warnings,max .013893. No training/threshold/runtime changes; UNKNOWN/advisory. One scene only, no reliability extrapolation.
- No robot/conveyor commands or camera setting changes. Next fresh isolated04 defect, other4normal, validation-only.


## 2026-09-05 training04 left165057

- Flash-off capture165057 inspected, overview restored. New explicitly designated04left/on-lip training,other4normal; SHA9f11647257c729e8ef0f2849d92b7a801fba134fada3cbdf6e088c324e84f2ee. Builder verified hashes/scene separation;30 crops6physical training scenes, no held-out scene fitted.
- Separate multiscale_plus_165057 trained106crops. Current development72/72 agreements (59normal/13defect), prior16434304 now .9731; historicalvalidation10/10,holdout4/5. Earlier15051703 score .5727 near diagnostic.5, so no unqualified robustness claim. Test-directed training collection makes this regression, not independent validation.
- Previous models retained, no runtime/threshold promotion. UNKNOWN/advisory remains; need fresh normal and isolated04 control after freeze. No robot/conveyor commands/camera configuration changes.


## 2026-09-05 VRM04 training coverage review

- Inspected six raw crops (normal163509,miss164343,empty134637,training153405/154302/163146), exported vrm04_training_review_164343/review.png and findings.json. Historical04 train15normal/0defect; current04 train3normal/2defect, overall04 18normal/2defect. Shared classifier also uses other slots, so this is not total training balance.
- Two04 defects visually cover rotation and rightward shift; fresh miss differs in gap/placement. Sparse04 defect diversity is a supported limitation, not proven sole cause. No relabeling/test ingestion/threshold changes. Need new explicitly designated leftward04 on-lip training scene, others normal;164343 stays reserved.
- No capture, training, runtime changes or robot/conveyor commands this turn.


## 2026-09-05 mixed01/04 postfreeze164343:04 miss

- New flash-off optical capture viewed, overview restored. User setup01/04 on-lip translations,others normal. Alignment .980647, SHA97370da15c717a9f5919abb8e572dac11335557dcb8bdd9b61a39b42a2363945 reserved validation only; no fitting.
- Same frozen plus163146 model01 .996606 warning,04 .441096 missed at unchanged diagnostic.5; normal02/03/05 max .048671. Four postfreeze scenes now16 normal0warnings,4 intended defects3warnings. Earlier success does not cover04; no threshold lowering or normal relabeling.
- Runtime disabled/advisory UNKNOWN retained. No camera configuration/motion commands. Current scene should remain unchanged while offline evidence reviewed; future training must use explicitly designated new physical setup, not this held-out failure.


## 2026-09-05 isolated03 postfreeze164022

- Captured flash-off, viewed original ROI, overview restored. Fresh03 displacement/on-lip per setup,others normal; alignment .981754. Image d7d39f3459905c09a1c4ae3663aaf779e60bd142beb4e8bb99dbb3271a205487 reserved validation only.
- Same frozen plus163146 candidate03 .996247 warning,other4 max .029882. No fit/threshold change. Three postfreeze scenes now one all-normal and two isolated defects,13 normal observations0warnings,2 defects2warnings; limited same-session sample, not deployment qualification. Historical holdout miss remains.
- No active model promotion, UNKNOWN/advisory retained. No robot/conveyor commands or camera setting changes. Next cross-slot mixed fresh control01/04 on-lip,02/03/05normal; no new training until explicitly designated.


## 2026-09-05 isolated02 postfreeze163741

- Flash-off optical capture visually checked, overview restored. Fresh isolated02 on-lip displacement per user; others normal. Alignment .979809, SHA31a523c5c1965fb552c93c15c49a53cbae156d595e9cfc655a4211971e0fc90b. Validation-only, no fit.
- Frozen plus163146 candidate same SHA9fb72c96:02 .998406 warning, remaining4 max .007381 no warnings. Clear displacement in this image does not establish smallest detectable on-lip offset. UNKNOWN/advisory maintained; no runtime/threshold/model changes.
- No robot/conveyor commands or camera configuration edits. Next isolated03 fresh displacement with02 restored; reserve from training.


## 2026-09-05 fresh normal control163509

- Flash-off optical capture completed, overview restored. Visually checked all5VRM normal per user setup; other20empty. Alignment .980084, image SHAbb25240eb2a0a4fc70bce65ed25476d6a1c632ee5ed19fa7833d7cb8b876f47b. Added validation-only record, no fit.
- Frozen multiscale_plus_163146 SHA9fb72c96f6cbbd1476cea7a62cacfe8f135a7d8416df1aab93a3dc6cee4a9239: five normal scores .001028/.008891/.001059/.004063/.003627, zero diagnostic warnings. This is one independent scene; not production validation. UNKNOWN/advisory maintained, no runtime/threshold edits.
- No robot/conveyor commands or camera configuration changes. Next fresh isolated02 on-lip displacement control, other4normal; do not add to training.


## 2026-09-05 explicit training163146 and regression improvement

- Flash-off optical capture163146 completed, overview restored. Image visually checked against user setup02/03 new on-lip translations,01/04/05 normal, rough faces up; physical height not measured. Source SHA99d03b6aa756fab7d71cd4677a9644656825ac2bab6758d67eb16f7bb6c9f745. Added training-only scene, builder verifies validation hashes/IDs excluded;25 crops5 training scenes.
- Separate multiscale candidate vrm_multiscale_seating_plus_163146 fitted101 training crops (historical76+current25). Historicalvalidation10/10,holdout4/5. Repeated current development52/52:43 normal no warnings,9 defective warnings; previously missed16002702 .8252 and15080703 .7590 at unchanged diagnostic.5. No held-out image fitted, but development directed by these failures, so NOT independent generalization proof.
- Old candidates retained; no active model replacement/threshold changes. ADVISORY_ONLY/UNKNOWN maintained; historicalholdout miss remains. Need fresh all-normal control followed by fresh defect control after this freeze. No robot/conveyor commands; camera settings unchanged.


## 2026-09-05 multiscale supervised seating candidate

- Added optional frozenB0 layer5+final pooled4x4 features to existing supervised evaluator, preserving original RGB geometry and train-only96 samples. Earlier feature maps retain finer spatial information; no transformations/CLAHE/validation fitting. Separate output required and existing candidate overwrite rejected.
- Candidate vrm_multiscale_seating_candidate_20260905: training96/96, historicalvalidation10/10, historicalholdout4/5, current development52 slots50 agreements (43normal no warnings,9defects7warnings). Still misses16002702 .480731 and15080703 .3721 at unchanged diagnostic.5;15550903 .5192 is marginal. Score separation is not proof of calibrated improvement.
- Frozen predictor supports matching layer5+final order; saved replay160027 agrees within1e-5 with evaluator. All statuses UNKNOWN/ADVISORY_ONLY, no deployment/model replacement or threshold tuning. Existing candidates preserved; no capture or motion commands. Need independent training evidence for subtle seating, not repeated threshold fitting to these failures.


## 2026-09-05 four normal warning review

- Exporter now accepts explicit case list/output with groups-of-three validation. Exported and visually reviewed four false-warning cases against same-slot normal154927 and empty134637; findings under runtime/inspection/vrm_false_warning_review_160027.
- Warnings:14363205 5px,15051705 1px,15080704/05 2px each. Last two raw/CLAHE edges agree within1px while both vertical edges shift, so not all warnings attributable to segmentation errors.14363205 has width/placement change and4px raw/CLAHE right-edge disagreement. Exact physical clearance/height remains unmeasured.
- Core limitation: leave-one-scene-out observed extrema are not mechanical tolerances; a held-out normal extreme can exceed them. Did not absorb test extremes then claim test success, relabel normal samples, or arbitrarily suppress slots. No capture/training/runtime/threshold or robot/conveyor commands. Deployment remains unverified.


## 2026-09-05 combined evidence retrospective audit

- Added audit_vrm_combined_evidence.py, merges fixed4x4 classifier artifact (SHA checked for new replay reports) and same-slot leave-scene-out edge excess. Ten scenes50 slots,43 normal7 defective; repeated development set, not independent deployment validation.
- Classifier-only:5/7 defect warnings,0/43 normal warnings. Edge-only:6/7,4/43. OR:7/7,4/43. AND:4/7,0/43. Thus edges recover both missed translations but introduce false warnings; requiring agreement misses more defects. No claim of completed detector.
- JSON runtime/inspection/vrm_combined_evidence_audit_160027.json records separate evidence and UNKNOWN. Missing evidence, positive evidence and absent warnings cannot produce PASS/FAIL; synthetic checks passed. Diagnostic OR/AND only, no runtime/model/threshold promotion, camera capture or robot/conveyor commands.


## 2026-09-05 raw boundary review

- Added export_vrm_boundary_review.py; exported six original fixed-slot crops and nearest-neighbor coordinate sheet (empty134637, normal143632/154927, defect160027). Visually inspected runtime/inspection/vrm_boundary_review_160027/review.png; findings.json distinguishes observed top-face edges from shadow/occluded socket wall.
- Empty socket and component both rectangular; texture supports presence, but visible top-face boundary is not verified full footprint/contact boundary.02 defect shows lateral/gap change; hidden on-lip height cannot be independently annotated from these images. User defect label retained; no pseudo-ground-truth masks generated or false normal relabeling.
- No model fit/threshold/runtime/camera/motion changes. Export completed, precise inner-wall annotation remains unresolved; automatic boundary estimates must remain advisory. Existing images sufficient to expose ambiguity, not to establish mechanical seating tolerance.


## 2026-09-05 slot-specific edge envelope validation

- Added audit_vrm_slot_edge_envelopes.py. Each scene excluded from its own same-slot normal-reference envelope; both opposing edges must exceed the envelope in the same direction. Descriptive development analysis only; reserved samples not fitted into a deployed artifact. Synthetic translation/opposite-edge expansion/in-range tests passed.
- Ten scenes50 crops: intended defect16002702 paired excess3px;15080703 4px;15550903 6px;15574503 10px. But normal14363205 excess5px, and rotated defect14401705 excess0. Normal max5px/defect min0 means no global threshold separates them. Translation diagnostic cannot replace rotation checks. Output runtime/inspection/vrm_edge_profiles_regression_160027/slot_envelopes.json.
- No runtime change, threshold selection, training, capture or robot/conveyor commands. UNKNOWN/ADVISORY_ONLY maintained. Slot-specific ranges alone do not solve ambiguous boundaries; next useful work is reviewing true part/socket boundary labels on existing crops, not requesting more repeated captures or tuning to these held-out failures.


## 2026-09-05 signed edge profile diagnostic

- Added audit_vrm_edge_profiles.py: fixed registered original crops, median central grayscale profiles and signed gradients; raw and local CLAHE measured separately. No image re-alignment, learned input change, threshold or runtime updates. Synthetic +4px translation test passed. Visual comparison inspected.
- Latest four-scene controls: raw normal edges change at most2px; defect02 both left/right -4px,03 -9/-9 and+11/+10. Prior missed15080703 also raw -7/-7. CLAHE instead selects different right edge by16px on02 and19px on15550903, supporting part/socket edge competition (not proof of neural-model causality).
- Expanded to10 scenes50 crops: earlier normal05 reaches+9px edge shift, normal04 vertical -9/-8. Therefore no universal tight baseline threshold promoted; slot-specific legitimate variation and boundary identification remain unresolved. Whole-board registration/crop coordinates untouched, all evidence UNKNOWN/ADVISORY_ONLY.
- Artifacts runtime/inspection/vrm_edge_profiles_160027 and vrm_edge_profiles_regression_160027. No capture/training or robot/conveyor commands. Next task: slot-specific normal edge envelopes plus independent corroboration, not simply lowering learned score thresholds.


## 2026-09-05 boundary comparison after160027

- Replayed unchanged sigma1 GrabCut/Hough diagnostic on154927 normal and155509/155745/160027 controls. Inspected raw/edge montage.03 defects center deltas7.28/10.61px, but missed02 only1.67px. Normal05 in160027 delta8.5px with fitted sizes shrinking to .921/.904 of reference; normal03 width .890. Visual mask undercoverage supports boundary instability; these are mask measurements, not physical displacement or height.
- Added audit_vrm_control_boundaries.py and boundary_deltas.json in runtime/inspection/vrm_outline_controls_160027. Synthetic translation, rectangle-axis equivalence and missing-boundary checks pass. Descriptive center-distance ranges overlap, so no center-only threshold promoted; exact learned model causal mechanism not established.
- No new capture, training, threshold, runtime or motion changes. ADVISORY_ONLY/UNKNOWN maintained. Need reliable component-vs-socket boundary evidence before geometric fallback; no claim that unseen physical on-lip height can be recovered from this top view.


## 2026-09-05 independent slot02 translation160027: missed

- Flash-off optical capture visually checked, overview restored. User-controlled02 on-lip translation,03 returned normal; alignment .980079. Frozen2/4 scores02 .439465/.404812 below unchanged diagnostic0.5: both miss intended defect. Other4 no warnings (2x2 normal05 .402850, close to defective02, so simply lowering threshold is not demonstrated separation).
- Archived validation only, same artifacts/no fitting. Prior successful03 scenes do not establish cross-slot reliability. Runtime remains disabled, all UNKNOWN/ADVISORY_ONLY; no promotion or normal-training ingestion. No robot/conveyor motion or camera setting changes. Need analyze slot-relative boundary evidence against normal control before further repetitive captures.


## 2026-09-05 opposite translation155745

- New flash-off capture visually checked, overview restored. User-controlled03 opposite translation/on-lip; other4 normal. Alignment .979740. Frozen2/4 spatial candidates03 .625382/.748617, only03 warning; other4 max .083649/.013129. Same artifacts and diagnostic0.5, no fit or threshold changes.
- Reserved validation manifest updated. Recent normal/left-right displacement controls agree, but previous150807 miss remains. ADVISORY_ONLY/UNKNOWN, no runtime promotion; no robot/conveyor commands. Next test use another slot to check slot-specific generalization; no claim of measured seating height.


## 2026-09-05 independent translation control155509

- Flash-off optical capture completed, overview restored. Original RGB image inspected; user-controlled03 translation/on-lip, remaining4 normal; alignment .980772. Reserved validation only, no fit.
- Frozen2x2/4x4 candidates warn only03 (.814386/.935997), other4 max .198393/.117343. Same artifact hashes as154927 control. Diagnostic0.5 unchanged, UNKNOWN/ADVISORY_ONLY retained. Earlier150807 translation miss still unresolved; one successful scene is not general reliability.
- No robot/conveyor motion commands, no runtime/camera configuration changes. Next independent test should change displacement direction without rotating, other slots unchanged.


## 2026-09-05 frozen normal control154927

- New normal VRM-only capture visually checked; alignment .981301. Frozen spatial2/4 replay (no fit) gives zero diagnostic warnings across five normal slots in each model; max scores .216794/.110814. One physical scene, not five independent trials. Archived validation-only with source hash.
- Added predict_vrm_spatial_seating.py: exact original RGB crop/features, artifact hash, class/dimension checks, registration rejection, no fitting, UNKNOWN/ADVISORY_ONLY. No model/threshold/runtime promotion; existing translation150807 miss remains unresolved. No robot/conveyor motion commands; camera configuration unchanged.


## 2026-09-05 even translation154302 / four-scene candidates

- User-ready02/04 translation-on-lip,odd normal captured flash-off and checked. SHAe5bd2cf330249b5edcb907c9b3c2fd46228a312c0fc56867f28675e1d4185031. Authorized20 crops4 scenes; reserved validation/invalid152604 excluded. Source all present; physical height per user not measured.
- Historical76+20 fit separately: 2x2 pooled candidate current normal26/26,defect5/6, historical validation9/10,holdout4/5. Translation15080703 .2373 remains miss. Added optional spatial pooling size;4x4 comparator same counts,03 .3964 still below diagnostic0.5. No improvement claim from score alone; no threshold lowered. No runtime promotion.
- Artifacts vrm_spatial_seating_four_scenes_154302 and vrm_spatial4_seating_four_scenes_154302, previous candidates preserved. Need fresh normal control before any integration; repeated session evaluation is development regression, not blind validation.
- Camera overview restored; no robot/conveyor commands, no normal PatchCore ingestion.

## 2026-09-05 translation training153909 / candidate comparison

- User-ready odd01/03/05 translation-on-lip,02/04 normal. Flash-off capture visually checked, source SHA8c535710bf64f1d4e77e5af6ff0f28ce8f4f68b70a5e8bb7a9d23614d1e00ef5. Added distinct training scene;15 crops/3 scenes, invalid152604 and reserved holdouts excluded.
- Historical76+explicit15 fit separate output vrm_spatial_seating_plus_translation_153909 via new --output option, preserving previous2-scene candidate. Current session normal26/26,defects5/6 at diagnostic0.5; rotation03 improves. Translation15080703 still missed(.1975). Historical validation regresses10/10->9/10,holdout4/5 unchanged. No production promotion or lowering thresholds.
- Normal current01 scores rise(.1792/.1299); score separation must not be overstated. Need complementary translation samples and fresh validation. All runtime authority unchanged, no normal PatchCore ingestion. Overview restored, no robot/conveyor commands.

## 2026-09-05 complementary training153405 and offline refit

- Captured flash-off153405, user-ready02/04 on lip,01/03/05 normal; image checked, SHA9c087d3c9c791352b14cdda0fd930695b243483dfd93096d28b1aeb7fd11b67c. Built10 crops from2 training scenes (5 normal/5 defective), invalid152604 omitted, all reserved session validation excluded.
- Added opt-in --include-session-training to spatial baseline; fit historical76+explicit10 training crops, saved separate candidate vrm_spatial_seating_plus_session_20260905. No active model replacement. Historical validation10/10/holdout4/5 unchanged; current holdout normal26/26, defects4/6 at uncalibrated0.5 (baseline1/6). Total30/32, not deployment readiness.
- Misses remain VRM03 rotation150517 score.3505 and translation150807 .1450. Other defects02=.9965,04=.8778,05=.8496,01=.7575. Do not lower threshold to validation misses. Need explicitly separate translation training, maintain heldout photos excluded.
- Overview restored, no robot/conveyor commands. Runtime advisory/UNKNOWN unchanged, no PatchCore normal ingestion.

## 2026-09-05 corrected supervised capture153051

- User-ready after correcting flipped01 and settled03; new flash-off ROI visually checked: odd slots rotated,01 rough face restored,02/04 normal per instruction. Hash cbeb5fb3a719250e20e251a91c16ae0395150fc111a81a9ecd819280e4222e2d. Height not measured from image.
- Added distinct training scene153051, labels DEFECT01/03/05,NORMAL02/04. Builder now explicitly skips excluded scenes; built5 RGB crops fromONE authorized scene. Reserved validation hashes/groups excluded; invalid152604 remains excluded/quarantined. No model training yet, no normal PatchCore ingestion.
- Camera overview restored; no robot/conveyor motion. Need complementary02/04 defects with odd slots normal to avoid slot-label shortcut.

## 2026-09-05 capture152604 INVALIDATED before fitting

- Captured flash-off and initially built5 supervised crops via new build_vrm_pose_session.py (source hash, reserved validation hash/group checks). User promptly corrected: VRM01 accidentally flipped, VRM03 settled into socket normally. Entire scene excluded, training_allowed=false, split excluded. Previous assumed three-defect labels NOT valid.
- Moved generated dataset to vrm_pose_session_20260905_quarantined_152604; recoverable quarantine, not deletion. No active training dataset at original path. No model fitting/replacement occurred. Original ROI retained only as provenance. Builder refuses training_allowed=false.
- Camera overview restored, no robot/conveyor motion. Need corrected physical capture before supervised fitting. Do not count these5 crops as usable training examples.

## 2026-09-05 frozen spatial seating supervised baseline

- Added evaluate_vrm_spatial_seating.py: historical vrm_seating_v3 TRAIN only76 crops, frozen ImageNetB0 features2x2 spatial pooling, balanced logistic C1. Preserved physical-scene split assertion and original RGB seating crop; current session never fitted. Candidate saved only runtime/inspection/vrm_spatial_seating_probe_20260905, no active model replacement.
- Binary0.5 diagnostic: train76/76 (not validation), historical validation10/10, holdout4/5. Current session27/32 = normal26/26, defects only1/6. Raw scores: latest translation03 .0350; rotated03 .0346; defect01 .1045,04 .2361,05 .0465,02 .5096. Overall accuracy masks poor defect recall. Scores uncalibrated, no threshold lowered.
- Historical seating task does not cover current subtle rotation/translation distribution sufficiently; distinct task mapping explicitly noted in report. Current fixed holdout training_allowed=false maintained. Runtime stays advisory/UNKNOWN, no capture, physical motion or production threshold edits.
- Next meaningful improvement requires separately designated current-camera supervised training scenes; do not consume today's reserved holdouts or relabel defects normal.

## 2026-09-05 static board registration residual audit

- Added audit_vrm_static_registration.py. Registered empty134637 vs normal143632/145643 and defect150807;31px static patches searched ±10px only where entire search support excludes component masks (2.5mm exclusion). Score>=.85, alternate-peak gap>=.03; no image/slot correction performed.
- Accepted all-board117/118/123, left-board71/72/74 matches. Left median displacement(0,0) in all3, abs95percentile(1,1)px, maxima(1,1)/(2,1)/(1,1).150807 static-arrows image visually inspected. Evidence does not support a wholesale board-registration shift explaining7..12px component/groove discrepancies; does not prove each inner wall is exact.
- Prior center variability must not be attributed solely to camera/registration; segmentation, true allowed placement, perspective/depth and groove identity remain unresolved candidates. No physical-height claim. Existing board registration kept unchanged.
- Artifacts vrm_static_registration_20260905; no capture/refit/threshold/runtime changes or robot/conveyor commands. Next: reliable part and actual inner-wall boundary, not extra component-local image warping.

## 2026-09-05 empty-socket groove reference audit

- Added audit_vrm_socket_reference.py. Empty134637 registered fixed crops; local grayscale median profiles pick four dark groove minima, then overlay unchanged coordinates on143632/145643 normal and150807 translated.20-panel montage visually inspected.
- VRM03 signed fitted-outline gap to detected left groove: normal143632/145643=-4px, defective150807=-12px. Normal already crosses selected groove, so this intensity minimum is NOT validated inner socket edge. No zero-overhang rule can safely grant FAIL from this reference. Right gap normal23..24px versus defective30px reinforces left shift but not actual seating/metrology.
- Do not silently update slot/reference coordinates, CAD allowance or runtime. Outputs vrm_socket_reference_audit_20260905/{comparison.jpg,reference.json}, all UNKNOWN. No capture/refit or robot/conveyor commands. Need proper inner-edge localization and registration uncertainty; mere dark-profile bounds insufficient.

## 2026-09-05 leave-scene-out position repeatability audit

- Added audit_vrm_position_ranges.py using only explicit normal labels and sigma1 measurements. Same scene removed from each comparison; entire latest150807 excluded from reference ranges. Results runtime/inspection/vrm_position_range_audit_20260905.json, all UNKNOWN.
- Translation defect15080703 lies7px outside observed normal x range,2px y. But normal leave-scene-out controls exceed ranges by5.11px x(14363205) or5.47px y(15051705). This is fit/capture/allowed-placement variation combined, not measured error alone. Too little separation to claim calibrated position accuracy from a7px cutoff. Rotated14401705 lies inside center range, confirming angle and center must remain independent.
- Existing unity_socket_clearance.json says VRM nominal11x14mm, socket12x15mm, center allowance0.5mm per axis. This is CAD-derived, not verified current printed-hole metrology. Existing hybrid adds vision uncertainty. Did not change these tolerances or reinterpret normal template center as socket center.
- No refit, capture, runtime thresholds or robot/conveyor motion commands. Further implementation needs socket-relative coordinates and measurement uncertainty, not label-specific threshold tuning.

## 2026-09-05 translation-only defect150807

- Flash-off capture after user-ready VRM03 translation onto lip; comparison visually checked. All five presence PRESENT (.999552/.993537/.998456/.994752/.979767). Frozen blur1 angle03=0deg: expected lack of rotation warning is NOT a normal placement verdict.
- Enclosing-center shift vs normal swapped145643:03=(-7.5,+2.0) registered pixels. Other normal controls01=(-4.26,+1.34),02=(2.06,1.28),04=(-1,-4.55),05=(-1.10,-2.74). Shows center changes also include fit/registration variation; do not equate delta with physical mm or set tolerance from this one case.
- Archived expected FAIL03 POSITION_SEATING_ERROR, other4 normal; runtime remains offline advisory UNKNOWN. Need slot-boundary/center tolerance verification before translation decision. Camera overview restored; no robot/conveyor commands, no refit/threshold edits.

## 2026-09-05 fresh blur1 holdout150517

- Flash-off user-ready VRM03 rotated, other4 normal. Montage visually inspected. Frozen presence5/5 (.999122/.992320/.996604/.997138/.962005); unchanged sigma1 outline deviations01..05=-.67/0/-7.31/+2.29/-.92deg.
- Frozen diagnostic3deg flags only03, matches user ground truth on this first post-selection physical scene. No threshold adjustment/refit. Normal04 +2.29deg exceeds development max1.82 but remains below diagnostic threshold; do not claim broad reliability or calibrated metrology.
- Archived holdout links and expected labels; runtime false, all authoritative statuses UNKNOWN. Translation-only/out-of-plane seating remain untested. Capture overview restored, no robot/conveyor motion commands. Next separate translation-only defective control necessary, not assumed covered by angle.

## 2026-09-05 foreground smoothing regression candidate

- Tested fixed sigma1/2/3 Gaussian foreground smoothing, unchanged geometry/seeds, seven scenes35 crops each. Selected sigma1 DEVELOPMENT candidate; not a blind performance claim. Sigma2/3 still miss14204902 (1.30/0deg). No learned input or production preprocessing modified.
- Sigma1 enclosing deviations for defects02/04/05/01:9.62/-11.31/-4.81/4.93deg. Present normal25 observations <=1.82deg absolute; six EMPTY excluded from pose correctness. Visually inspected montage: improves previously incomplete01, but05 still approximate. Cannot claim precise physical angles.
- Frozen offline candidate config vrm_outline_candidate_20260905.json: diagnostic warning3deg, no manufacturing tolerance claim, runtime false, validated false, ADVISORY_ONLY. No-warning never PASS. Empty presence gate mandatory; position/height not solved. Needs fresh post-selection defect/control without retuning.
- Artifacts vrm_outline_blur{1,2,3}_20260905. No capture/model refit/motion or production threshold changes.

## 2026-09-05 normal part swap145643 rejects single-texture pose dependency

- User-ready normal physical swap01/03 captured flash-off; reference/current montage visually checked. All five presence candidates PRESENT (.998526/.997772/.997577/.996596/.964442).
- Unchanged texture matcher loses swapped parts:01 score.192542 gap.004499,03 score.237506 gap.019127, arbitrary displacement/angles. Unchanged02/04/05 scores.550/.518/.510. Confirms part-specific texture dependency; cannot use these low-match angles as defects or require each production part to share a template texture. No automatic template update to this holdout.
- Independent outline enclosing deviations -.87/-.68/0/-.68/-1.85deg, normal under this diagnostic but still fails earlier defective01. Neither alternative solves general pose alone; do not selectively combine based on known answers. All providers remain advisory/offline UNKNOWN.
- Holdout normal labels archived, no training, model refit, threshold/runtime promotion. Camera overview restored, no robot/conveyor commands. Artifacts vrm_texture_motion_holdout_145643 and vrm_outline_holdout_145643. Next needs geometry/texture-independent boundary model rather than single-instance texture matching.

## 2026-09-05 texture-motion candidate (no pose normalization)

- Added audit_vrm_texture_motion.py: fixed normal143632 slot interior55%, grayscale local high-pass, template rotation search -20..20deg and translation NCC. Reports measured movement only; no inverse-warped inspection crop, no alteration of downstream appearance input. All UNKNOWN/ADVISORY_ONLY, runtime off.
- Seven-scene35-slot regression: known defects02(142049) -12deg/score.420;04(142337)+10/.479;05(144017)+11/.333;01(144513)-7/.484, dx17px. Unlike enclosing rectangle this tracks144513 movement. Angle sign is OpenCV template convention; not calibrated physical metrology.
- Same-session normal non-reference controls generally -1..1deg;135111 earlier normal parts do NOT match (scores.195..254, arbitrary angles/translations). Texture identity/lighting changes remain a limitation; must NOT infer defect from low-match angle. Empty slots similarly produce meaningless maxima. Need independent presence and match-quality gating and cross-part validation before any runtime use.
- Visual15-pair montage checked in vrm_texture_motion_visual_20260905; rectangle denotes measured interior patch, not whole-part boundary. Reference self-match is not independent validation. Other reports vrm_texture_motion_20260905/motion.json.
- Synthetic unit tests4/4 passed: identity, signed rotations/translations, blank UNKNOWN, input immutable. Initial test import path fixed before passing. No new physical capture, learned-model fitting, thresholds promoted or robot/conveyor commands.
- Next physical control: restore normal seating and swap normal VRM01/03 to test part-specific texture dependence; no defects in that control. Do not change architecture or silently add per-part teaching requirement.

## 2026-09-05 boundary-segment regression / foreground failure isolated

- Extended offline outline audit with approxPolyDP2px contour segments (length>=.25*min slot size), length-weighted median axis and saved masks. Seven-scene35-crop replay completed, artifacts vrm_boundary_segments_20260905. No image pose normalization.
- Defective144513 VRM01 enclosing angle1.21deg versus boundary median2.96deg; mask visually inspected: missing/cut-off right/top component regions. Foreground segmentation is incomplete, so changing rectangle fit alone cannot establish correct pose.
- Regression counterexample142049 defectiveVRM02 boundary median0deg (previous rectangle6.18deg); method would lose existing detection. Other defects04 -9.83deg,05 -10.20deg. Normal144513 VRM03 -2.12deg; no threshold calibrated or promoted. Keep diagnostics separate, don't combine selectively per known label.
- No capture, model refit, production edits or robot/conveyor commands. Next requires reliable foreground boundary evidence or supervised pose examples; current contour-only candidate not validated.

## 2026-09-05 VRM01 defect144513 reveals outline limitation

- Flash-off capture after explicit VRM01 rotate/rest-on-lip instruction, montage visually checked. All5 present by frozen candidate (.999342/.998848/.989831/.985860/.956241); other slots normal as instructed.
- Unchanged outline residuals01..05=+1.21/-.77/-.65/-.74/0deg;01 fill .83. Visually fitted rectangle does not accurately follow the tilted boundary. This contradicts generalizing the earlier successful2/4/5 results. An angle-only threshold cannot reliably identify this known defect; lowering it would overlap earlier normal deviations up to2.96deg.
- Archived FAIL01 ground truth, no relabel/refit/threshold changes. Prototype remains offline UNKNOWN, NOT production ready. Next work must address boundary fit/slot overhang, not request stronger rotation to make detection easier. Camera overview restored; no robot/conveyor commands.

## 2026-09-05 resolved144017 physical label

- User confirms accidentally rotated VRM05, not requested01. Archived144017 as PRESENT all5, pose FAIL05 and unchanged normal01..04. Prior pending identity resolved without software slot remap.
- Frozen outline result -10.89deg on05 matches defective slot; normal controls 0/-1.40/0/-1.74deg. Presence all5 correct. No calibrated automatic FAIL claim, no threshold/refit/runtime changes. No capture or motion commands this update. Training excluded.

## 2026-09-05 capture144017 slot identity discrepancy

- Flash-off capture after request to rotate VRM1; overview restored, no motion commands. Frozen presence all PRESENT (.999160/.998791/.992877/.997586/.991215).
- Unchanged outline fit: software01 0deg,02 -1.40,03 0,04 -1.74,05 -10.89deg; comparison montage visually confirms rotated crop is software05, not01. Ground truth deliberately NOT assigned pending physical numbering confirmation. Do not silently change slot map or mark normal01 defective.
- Separate outputs vrm_outline_holdout_144017 and blind_144017.json. No threshold/model/runtime changes. Need user clarify whether physical top slot was rotated; software fixed IDs may differ from user's numbering.

## 2026-09-05 fresh all-flat outline control143632

- User-confirmed all five VRMs flat, flash-off capture and ROI visually verified. Frozen presence all PRESENT, scores .997559/.998632/.987746/.979946/.969708.
- Unchanged GrabCut outline method on fresh scene: image-axis residuals 0/-.77/0/-.86/0deg, fill .96/.85/.97/.88/.95. Visually checked fit montage. Contrasts with prior defective +6.18/-11.31deg, but no calibrated threshold/authoritative PASS yet; one fresh physical scene only. Crops remain slot-relative.
- Added --stamps/--output to offline audit to keep prior artifacts intact. Saved separate vrm_outline_holdout_143632 and holdout manifest ground truth; no normal-training ingestion/refit/runtime promotion. Overview restored; no robot/conveyor commands.
- Next independent defect check should use another slot, with all other VRMs flat; test same method without retuning.

## 2026-09-05 seeded foreground outline prototype

- Extended offline audit_vrm_outline.py with deterministic central-seeded GrabCut and minAreaRect; no component rotation correction. Local original BGR foreground extraction, CLAHE only edge diagnostic. Six initial raw/overlay pairs visually checked: component fit follows both rotated parts, unlike mixed Hough edges.
- Fitted axis deviations: defective142049 VRM02 +6.18deg; defective142337 VRM04 -11.31deg. Initial four normal controls -0.39..0deg. Expanded five-scene/25-slot replay: 11 present normal controls -2.96..0deg; 2 known rotated. These are image-plane fitted angles, not calibrated physical metrology. No threshold promoted.
- Critical limitation: foreground seed also returns a rectangle for EMPTY slots (e.g.142337 EMPTY01 -11deg). Must gate on independently validated presence and outline quality; never equate a fitted rectangle with a present part. Prototype stays offline UNKNOWN. Need fresh all-flat scene before promotion; current images are development data.
- No camera/robot/conveyor commands, runtime edits or learned-model refit. Artifacts remain vrm_outline_audit_20260905. Log user request: minimize intermediate reports; request only necessary physical setup.

## 2026-09-05 VRM outline feasibility audit

- Added offline audit_vrm_outline.py: board registration only, fixed 1.5x crops, local grayscale CLAHE/Canny/Hough edge candidates. Compared 141603 normal02/04, 142049 defective02/control04, 142337 control02/defective04. Six crop pairs visually inspected in runtime/inspection/vrm_outline_audit_20260905/comparison.jpg.
- Defective component outlines visibly rotate relative to sockets, but detected lines also include socket walls and rough texture. Unassigned Hough angles cannot be promoted to measured component angles or a defect threshold; no successful automated pose verdict claimed.
- OpenCV line-output shape variation handled with reshape(-1,4); rerun completed. Output edges.json is diagnostic only, all UNKNOWN. No runtime modifications, refit, capture or robot/conveyor motion. Next requires edge ownership/contour validation rather than a strongest-line angle rule.

## 2026-09-05 existing VRM pose provider regression

- Added audit_vrm_pose_holdout.py, offline registered RGB regression over four holdout scenes; preserves model metadata and disabled seating provider. Output runtime/inspection/vrm_pose_holdout_audit_20260905.json. No refit or threshold changes.
- Confirmed FAIL examples: 142049 VRM02 raw CORRECT=.765802, ROTATED=.148054; 142337 VRM04 raw CORRECT=.843660, ROTATED=.124398. Both below minimum .9 => UNKNOWN. Existing state classifier misses both subtle rotations; presence improvement does not solve pose. Lowering confidence threshold would make incorrect CORRECT candidates, not fix defects.
- Seating remains DISABLED due earlier regressions. This is provider-only audit, not full hybrid execution or calibrated final inspection. All results advisory UNKNOWN. No capture, robot/conveyor commands. Next: independent slot-relative outline/pose candidate with normal controls, retain these defect labels.

## 2026-09-05 explicit rotation-defect labels / 142337

- User explicitly confirms both 142049 VRM02 and 142337 VRM04 must be defective despite slight rotation. Added expected_pose FAIL and ROTATION_POSITION_ERROR separately from PRESENT; never normal training examples. These are user ground truth, NOT successful model pose predictions.
- New flash-off capture visually checked; VRM04 rotated, VRM02 restored. Frozen presence 5/5, p=.011650/.994873/.020993/.994625/.008243. Presence-only probe returns UNKNOWN authority; pose detection remains unverified. No runtime promotion.
- Camera overview restored; no robot/conveyor motion. Next work must evaluate pose against these defective examples, not claim presence accuracy establishes inspection success.

## 2026-09-05 VRM02 slight rotation 142049

- User substituted slight rotation for requested 90 degrees. Flash-off capture visually confirms rotated VRM02, present VRM04, other VRMs empty. Exact angle and seating height not measured.
- Frozen presence candidate 5/5: scores .004740/.993660/.162735/.997186/.029237. EMPTY03 score increased but remains EMPTY; no recalibration. Three post-freeze scenes 15/15 slot labels, not independent 15 trials.
- Holdout only; not normal-placement training. Presence success does not validate pose inspection. Runtime remains advisory/offline, final UNKNOWN. Camera overview restored; no robot/conveyor motion commands.

## 2026-09-05 frozen presence complementary scene 141603

- Saved ROI visually confirms VRM01/03/05 EMPTY, 02/04 PRESENT; other parts empty.
- Frozen candidate unchanged: 5/5 matched; present scores .014097/.996073/.011641/.998411/.004037, ALIGN .981977. Two fresh physical scenes total: EMPTY5/5, PRESENT5/5 (10 slots, not 10 independent scenes).
- Holdout labels archived, training excluded. No refit, runtime promotion or authoritative PASS/FAIL. Presence does not establish correct seating or orientation; next requires physically misseated/rotated present parts. No robot/conveyor commands.

## 2026-09-05 frozen presence candidate fresh scene

- 141311 flash-off capture; visual confirms VRM02/04 EMPTY, VRM01/03/05 PRESENT.
- No-refit frozen candidate: 5/5 correct. P(PRESENT) .998149/.010204/.997115/.044818/.985054 (01..05). First post-freeze scene, not independent 5-trial validation.
- Label file vrm_presence_context_holdout_20260905.json excludes training. Report blind_141311.json includes model/input SHA. Authority remains advisory/UNKNOWN. Camera overview restored; no motion commands.

## 2026-09-05 VRM dual-region presence candidate locked

- evaluate_vrm_texture_presence.py --context: concatenate frozen B0 RGB features
  from .55x central and 1.30x contextual slot crops, balanced logistic C1.
  Historical-only fit 5 EMPTY/65 PRESENT; scene-out 70/70. Today's previously
  inspected development regression: EMPTY 6/6, PRESENT 34/34; scores EMPTY
  .001513–.036670, PRESENT .961077–.999745. Not fresh blind validation.
- Fixed input stress gain .85/1.15 and ±3px x/y: 0 errors/240 synthetic
  observations (not physical samples). No session image fitted. Candidate NPZ
  saved under runtime/inspection/vrm_presence_context_stress_20260905.
- predict_vrm_presence_context.py loads frozen coefficients without refitting;
  replay score delta <1e-9. Outputs UNKNOWN/ADVISORY_ONLY plus binary candidate,
  never presence==good seating. No production integration or threshold promotion.
- No camera/motion commands. Next: fresh physical mixed presence to verify the
  locked candidate, especially VRM02/04 EMPTY. User requests minimal updates.

## 2026-09-05 source sampling audit

- audit_vrm_source_sampling.py composes inverse raw→ROI H with ECC reference→ROI warp; direct source quadrilateral verified visually. H is raw-image coordinates, not upright preview coordinates (diagnostic initial mismatch corrected before final artifacts).
- VRM02 central 69x88 canonical maps to only 54x68–69 source pixels in all three captures 134637/135454/135111. ROI is enlarging this area, not shrinking a high-detail source. Direct crop does not reveal substantially new detail visually. No classifier performance claim: direct crops were not scored with the old pipeline model.
- Prior suggestion that full-board downscale lost detail is unsupported for these captures. Native source pixel budget is the limit here; source crop alone is no demonstrated fix. Artifacts runtime/inspection/vrm_source_sampling_20260905. No runtime/settings/threshold edits, no physical commands.

## 2026-09-05 VRM02 crop audit

- Tool: slot_classifier/audit_vrm02_crops.py; artifacts runtime/inspection/vrm02_crop_audit_20260905/{audit.json,comparison.png,*native.png}.
- 134637/135454 EMPTY: both ROI interior, same canonical geometry; native central input 69x88 pixels. ALIGN .98025/.98107; gray mean 53.339/51.616, std 3.670/3.120, LapVar 6.595/6.028; MAE 2.500, correlation .724.
- 135111 PRESENT mean 57.944/std 5.389/LapVar 10.529. Visual crop audit: no obvious wrong-slot or edge inclusion. Central crop is low detail; expansion to 224 doesn't add texture information.
- Probability .579→.057 despite small image difference establishes candidate sensitivity, not a proven exposure-only cause. Registration/subpixel resampling and image acquisition remain confounded. No thresholds/model/camera settings changed. No physical commands. Need robustness/high-resolution source assessment before more captures or deployment.

## 2026-09-05 — VRM02 단독 제거 검증

- 135454 플래시 OFF 촬영 후 아래에서 두 번째 VRM02 빈칸과 나머지 VRM
  4개 존재를 영상 확인, 세션 라벨 기록. overview 복귀 완료.
- 기존 학습 자료만 사용한 동일 중앙 질감 후보에서 새 장면은 EMPTY 1/1,
  PRESENT 4/4 정답. 오늘 누적 EMPTY 5/6, PRESENT 34/34 관측이다.
  전체 빈 기판에서는 VRM02 오탐이 있었으므로 이번 성공만으로 안정화를
  선언하지 않는다. 새 사진은 평가 전용, 운영 활성화·임계값 변경 없음.
- 결과 vrm_texture_presence_probe_vrm02_20260905/evaluation.json.
  로봇·컨베이어 구동 명령 없음.

## 2026-09-05 — VRM만 조립한 장면 검증

- 플래시 OFF 135111 촬영, VRM 5개 존재 및 다른 부품 빈 상태를 영상 확인했다.
  세션 라벨 보존, overview 복귀 확인. 동일 과거 학습 자료의 중앙 질감 후보는
  신규 VRM 5/5 PRESENT로 판단했다. 오늘 누적 PRESENT 30/30, EMPTY 4/5.
- 주변 부품이 없는 이 장면에서도 존재 판단은 유지됐으나 조명·위치도 달라질 수
  있어 배경 영향이 전혀 없다는 증명은 아니다. VRM02 빈칸 오탐은 여전히 남는다.
  결과 vrm_texture_presence_probe_only_20260905/evaluation.json. 새 사진 학습 없음,
  운영 활성화·판정 변경 없음. 로봇·컨베이어 구동 명령 없음.

## 2026-09-05 — 전체 빈 기판 신규 유무 검증

- 사용자가 25개 부품 모두 제거했다고 확인한 후 134637을 플래시 OFF로 촬영,
  ROI에서 빈 기판 상태 확인 및 overview 복귀 완료. 세션 파일에 전체 누락을 명시했다.
- 기존 중앙 질감 후보를 동일 학습 자료로 평가했고 새 사진은 학습하지 않았다.
  빈 VRM 4/5 정답; VRM02는 P(PRESENT)=0.578704로 오탐했다.
  VRM04도 P(PRESENT)=0.430278로 경계에 가깝다. 앞선 PRESENT 25/25 유지.
  이는 0.5 이진 후보 평가이며 확정 PASS/FAIL이나 보정된 신뢰도가 아니다.
- 결과는 vrm_texture_presence_probe_empty_20260905/evaluation.json에 저장.
  후보 비활성 유지, 임계값 변경 없음. 로봇·컨베이어 구동 명령 없음.

## 2026-09-05 — VRM 중앙 질감 유무 분류 오프라인 후보

- `evaluate_vrm_texture_presence.py` 추가: 정합 슬롯 중앙 55%의 원본 RGB를
  frozen EfficientNet-B0에 입력하고 이진 logistic 분류기를 평가한다.
  EMPTY 이외 CORRECT/ROTATED는 모두 PRESENT이며 위치·걸침과 분리했다.
  CLAHE나 부품 상대 위치 정합은 사용하지 않는다.
- 기존 70개 관측(EMPTY 5, PRESENT 65)을 scene_id 단위 leave-one-out 평가:
  EMPTY 5/5, PRESENT 62/65. 오늘의 정상·걸침·복귀 5장은 학습에서 제외했고
  25개 관측 모두 PRESENT였다. 이 중 걸침도 유무에는 PRESENT가 맞다.
- 결과: `runtime/inspection/vrm_texture_presence_probe_20260905/evaluation.json`.
  빈칸 자료가 슬롯당 한 장뿐이고 오늘 검증에는 빈칸이 없으므로 안정적인
  유무 판별 완성으로 간주하지 않는다. 신규 빈칸 검증이 필요하다.
  후보는 ADVISORY_ONLY, runtime_enabled=false; 운영 모델·융합 기준 변경 없음.
  CPU 오프라인 실행 완료, 촬영·로봇·컨베이어 명령 없음.

## 2026-09-05 — 新 정상·걸침 5장 평가 결과

- VRM01 정상 복귀 133256 촬영 완료. 플래시 OFF, overview 복귀 확인.
- v4 후보를 CPU 메모리에만 로드하고 기판 정합 및 기존 non-empty 게이트를
  포함해 5장의 VRM 25개 관측을 평가했다. 정합 0.9865–0.9868 모두 OK.
  VRM05는 정상 0.008784 → 걸침 0.081363 → 복귀 0.006891로 구분했다.
  VRM01 걸침은 0.059623으로 UNKNOWN, 복귀는 0.040985로 FLAT이었다.
- 정상 23개 관측 중 FLAT 20, UNKNOWN 3, 거짓 SEATING 0이었다.
  UNKNOWN 3개는 모두 정상 VRM04의 non-empty 확률이 0.90 미만이라
  걸침 검사를 실행하지 못한 경우다. 실제 걸침 2개 중 SEATING 1, UNKNOWN 1.
  동일 세션·반복 슬롯 관측이므로 독립 샘플 25개 성능으로 일반화하지 않는다.
- 임계값 변경·학습·운영 활성화 없음. 기존 혼합 장면 오탐도 남아 있으므로
  완료 모델로 승격하지 않는다. 로봇·컨베이어 구동 명령 없음.

## 2026-09-05 — VRM01 걸침 검증 촬영

- 사용자 준비 확인 후 124122를 플래시 OFF로 촬영하고 ROI에서 맨 아래
  VRM01 배치 변화를 확인했다. 사용자 지시 확인에 따른 SEATING 정답을
  세션 파일에 저장했다. 총 4장, 학습 편입 금지·평가 대기 상태다.
- 촬영 및 overview 복귀 완료. 로봇·컨베이어 구동 명령, 판정 기준 변경 없음.

## 2026-09-05 — VRM05 정상 복귀 촬영

- 사용자 정상 복귀 준비 확인 후 122706 촬영·ROI 저장 및 영상 확인 완료.
  정상–걸침–정상 복귀 3장을 세션 정답 파일에 보존했다. 나머지 슬롯은
  재배치하지 않았으므로 모든 슬롯의 독립 표본으로 간주하지 않는다.
  학습·판정 변경 없음. 플래시 OFF 촬영, overview 복귀 확인;
  로봇·컨베이어 구동 명령 없음. 모델 평가는 아직 미수행이다.

## 2026-09-05 — 새 VRM 정상·VRM05 걸침 검증 사진 확보

- 사용자 배치 준비 확인 후 플래시 없이 122212 정상, 122437 VRM05 걸침을
  촬영했다. 원본 4000×3000 및 ROI 저장, overview 복귀 확인.
- 슬롯별 사용자 확인 정답을 `vrm_seating_session_20260905.json`에 보존했다.
  두 장은 아직 평가·학습하지 않았으며 학습 자동 편입을 금지했다.
  GPU 위 흰 조각 때문에 기판 전체 정상으로 간주하지 않는다.
- 카메라 촬영 명령만 실행했고 로봇·컨베이어 구동 명령은 보내지 않았다.

## 2026-09-05 — VRM 걸침 입력 리사이즈 일치 및 오탐 재확인

- VRM seating 추론의 OpenCV INTER_AREA 축소를 학습과 동일한 PIL bilinear로
  변경했다. 원본 RGB와 고정 슬롯 좌표, 융합 계약은 유지했다.
- 저장된 정합 이미지 4장에 비활성 후보를 메모리에서만 진단 로드했다.
  194959의 VRM05는 SEATING 0.101769, 180910의 VRM01/02는 각각
  0.999291/0.999806이었다. 하지만 혼합 145130의 정상 VRM01도
  SEATING 0.108095로 오탐했고 정상 193555의 VRM01은 UNKNOWN 0.052844였다.
  따라서 입력 불일치만으로 오탐이 해결되지 않았고 임계값 재조정·운영 활성화는 하지 않았다.
- 진단은 존재 게이트를 강제로 통과시킨 분류기 단독 실험이다. 빈 VRM03의
  SEATING 출력은 통합 검사의 결과가 아니며 존재 게이트의 필요성을 재확인했다.
- 단위 테스트 65개 통과. 카메라 촬영·로봇·컨베이어 명령 없음.
  다음은 물리적으로 확인한 새 정상/걸침 장면으로 독립 검증할 데이터 확보다.

## 2026-09-04 — VRM 턱걸림 분류 후보 v4 개발·교차 회귀 실패로 비활성

- 기존 VRM 상태 모델의 `EMPTY / CORRECT / ROTATED` 세 클래스로는
  부품이 있고 2-D 방향도 맞지만 소켓 턱에 걸린 결함을 표현할 수 없어,
  S22 정합 원본 RGB 슬롯을 사용하는 독립 `FLAT / SEATING / UNKNOWN`
  EfficientNet-B0 후보를 추가했다. 실행 시 VRM 상태 모델의 non-empty
  확률이 `0.90` 이상일 때만 이 검사를 수행하도록 통합했다.
- 물리 장면 ID로 split을 묶어 동일 배치의 연속 촬영이 train/
  validation/회귀에 나뉘지 않게 했다. v3 dataset은 train
  `FLAT 68 / SEATING 8`, 독립 정상 validation `FLAT 10`, 고정 회귀
  `FLAT 4 / SEATING 1` 구성이다. `194959`는 최초 후보 비교에 이미
  사용되어 더 이상 블라인드 holdout이 아니며, 고정 회귀로만 표기했다.
- v4의 판정 구간은 `P(SEATING) <= 0.052442` = FLAT,
  `0.052442 < P(SEATING) < 0.078663` = UNKNOWN,
  `P(SEATING) >= 0.078663` = SEATING으로 설정했다. train `76/76`,
  독립 정상 `10/10`, 고정 회귀 `5/5`를 맞춰고, 25슬롯 통합
  재실행에서 정상 `193555`는 후보 0개, VRM05 턱걸림 `194959`는
  `vrm_05 SEATING?` 1개, VRM01·02 턱걸림 `180910`은 해당 2개만 표시했다.
- 그러나 기존 혼합 회귀 장면 `145130`에서 정상인 `vrm_01`을
  `SEATING?`(`P=0.0955`)로 추가 오탐했다. 따라서 v4는 운영 모델로
  승격하지 않고 `runtime_enabled=false`,
  `DEVELOPMENT_ONLY_FAILED_CROSS_SCENE_REGRESSION`으로 고정했다. 통합 코드도
  메타데이터의 명시적 활성 플래그가 없으면 후보를 로드하지 않는다.
  실패한 초기 모델도 `vrm_seating_candidate_v1_failed`로 보존했다.
- 통합 모델의 `ADVISORY_ONLY` 권한과 PASS/FAIL/UNKNOWN fail-safe 계약은
  변경하지 않았다. Python/shell 구문 검사와 단위 회귀 64개가 통과했다.
  추가 학습 장면을 임의로 정상 처리하지 않았고, 카메라 촬영·로봇·
  컨베이어 제어 명령도 보내지 않았다. 남은 제한은 새로 재배치한
  독립 턱걸림·정상 장면으로 교차 재검증하기 전에는 자동 PASS/FAIL 권한을
  부여할 수 없다는 점이다.

## 2026-09-04 — S22 하이브리드 검사 결과 DB 전달 패키지

- 비전 담당자가 검사 결과만 DB 담당자에게 전달할 수 있도록
  `run_export_latest_inspection_for_db.sh`와
  `vision_assembly/integration/export_inspection_result.py`를 추가했다. 최신
  `s22_hybrid_aoi_v1` 보고서를 `ksmc.vision-inspection.v1` 계약으로 변환하고,
  25개 전체 슬롯 결과, 불량/재검 후보의 부품명·내부 슬롯 ID·조립 레시피 슬롯
  코드, 표준 불량 코드, 위치·각도·존재·표면 측정값을 한 JSON에 보존한다.
- 조립 레시피와 동일하게 `GPU-01`, `HBM-01~08`, `PM-01~04`, `CAP-01~05`,
  `IND-01~02`, `VRM-01~05`로 변환한다. 후보 코드는
  `COMPONENT_MISSING / POSITION_ERROR / DIRECTION_ERROR / SEATING_ERROR /
  PIN_DEFECT / SURFACE_ANOMALY`로 번역하되, 원래 `authority`, `decision`,
  `confirmed_defect`를 함께 보내 의미가 바뀌지 않게 했다.
- 원본 ROI, 정합 기판, 3단 표시 보고서, 후보 히트맵·오버레이, 슬롯 진단, GPU 핀
  진단을 상대경로와 SHA-256으로 복사하고 원본 하이브리드 JSON, manifest와 함께
  ZIP을 만든다. DB PC에서 접근할 수 없는 `/home/hc/...` 경로를 업무 이미지 URL로
  사용하지 않는다. 검사 입력 SHA-256도 원본 보고서와 다시 대조한다.
- HTTP 주소가 없을 때는 `runtime/inspection/db_outbox/`에 오프라인 패키지만
  생성하고, 주소가 정해지면 `--endpoint` 및 선택적 Bearer token으로 multipart
  전송한다. `inspection_id`와 `Idempotency-Key`를 고정해 실패 후 같은 패키지를
  재전송해도 중복 검사 건을 만들지 않도록 했다. DB 적용 명세와 대책서 필드 매핑은
  `team_handoff/vision_inspection_db/`에 정리했다.
- 고정 융합 계약은 변경하지 않았다. 현재 모든 후보는 `ADVISORY_ONLY`이므로 실제
  샘플에서도 `UNKNOWN`, `confirmed_defect=false`,
  `formal_defect_report_allowed=false`로 유지된다. 따라서 DB는 현재 후보를 바로
  불량 수량이나 자동 불량 대책서로 승격하면 안 되고 재촬영/보류로 저장해야 한다.
- 알려진 혼합 장면 `145130`으로 패키지를 생성해 HBM-04 방향, IND-01 방향,
  PM-01 위치, VRM-03 누락의 4개 후보와 25개 슬롯, 이미지 7종을 확인했다.
  모든 파일의 SHA-256 검증이 통과했고, 변환·중복 재시도·authoritative fail 격리·
  multipart 요청을 포함한 테스트 `5 passed`, Python compile, shell/JSON 구문 검사가
  통과했다. 실제 DB endpoint가 없어 외부 전송은 하지 않았고 카메라 촬영,
  로봇·컨베이어 명령도 보내지 않았다. DB 측 endpoint/auth 및 실제 cycle/job/board
  ID 계약 확정과 컨베이어 자동 트리거의 최신 하이브리드 경로 연결은 남아 있다.

## 2026-09-04 — VRM05 턱걸림 미검출 원인 확정

- 사용자가 가장 위 `vrm_05`를 실제 소켓 턱에 걸친 불량으로 배치한
  `194959`를 S22로 촬영했다. RTX GPU 전체 검사 결과 정합 score는
  `0.9807`로 유효했지만 advisory 후보는 0개였으므로, 이 장면은 정상이나
  허용 유격이 아니라 확정된 VRM05 턱걸림 false negative다.
- 운영 VRM v6은 해당 슬롯을 `CORRECT 0.9712`로 분류했다. 모델 metadata와
  학습 코드를 재확인한 결과 클래스는 `EMPTY / CORRECT / ROTATED` 세 개뿐이고
  `SEATING` 또는 턱걸림 클래스가 없다. 같은 크롭을 과거 v2–v6 후보에
  재입력해도 모두 CORRECT(`0.7628/0.9933/0.9554/0.9002/0.9717`)였으므로,
  최근 모델 교체로 생긴 회귀가 아니라 처음부터 학습하지 않은 불량 형태다.
- YOLO 보조 외곽은 VRM05를 실제 부품으로 검출했지만 보정 위치 오차
  `0.493 mm`, 횡방향 `0.444 mm`, mask `21513.5 px`로 기존 2-D 위치 조건을
  넘지 않았다. PatchCore score `0.6441`도 직전 정상 VRM05 `0.6532`보다
  오히려 낮아 단독 threshold로 턱걸림을 구분할 수 없다. 즉 검정색 정사각
  부품의 원근·높이 변화가 2-D 중심과 정상 외관 분포에 흡수됐다.
- 이전 VRM01·02 턱걸림은 VRM 상태 모델이 아니라 두 슬롯에서 반복 확보한
  위치·외곽·PatchCore 다중근거 전용 규칙이 잡은 것이다. 해당 규칙은 검증
  자료가 없는 VRM03–05로 의도적으로 일반화하지 않았기 때문에 VRM05에는
  적용되지 않았다.
- 현재 `194959`는 학습에 섞지 않고 새 턱걸림 검사의 독립 holdout으로
  보존한다. 위치 threshold를 한 장에 맞춰 낮추지 않으며, 해결 방향은 기존
  누락·방향 v6을 유지한 채 별도의 `FLAT / SEATING / UNKNOWN` 고정 슬롯
  provider를 만들고 VRM01·02 턱걸림으로 학습한 뒤 VRM05를 블라인드 검증하는
  것이다. 모델·threshold·권한은 아직 변경하지 않았고 모두
  `ADVISORY_ONLY`, 최종 판정은 `UNKNOWN`이다. 로봇·컨베이어·카메라 제어
  명령은 보내지 않았다.

## 2026-09-04 — VRM 5슬롯 오배치 다중근거 융합 및 기록 정정

- 사용자가 `185451` 촬영의 VRM 5개가 모두 오배치라고 정답을 확정했다.
  수정 전 통합 검사는 `vrm_03 DIR?` 하나만 표시해 1/5에 그쳤다. 원시
  증거를 다시 확인하니 VRM02·05는 보정 전 중심 이탈, VRM03·04는 회전
  분류, VRM01은 커진 외곽과 PatchCore 반응이 각각 존재했지만 기존 화면
  후보 융합이 이를 충분히 사용하지 않고 있었다.
- 이전에 VRM 정상 반복 사진으로 기록한 `183712`도 영상과 슬롯 수치를
  재감사한 결과 `185451`과 같은 VRM 5개 오배치 물리 장면이었다. 따라서
  VRM 정상 근거에서 제외하고, 이 사실을 아래 기존 기록에도 정정했다.
  HBM은 해당 장면에서 움직이지 않았으므로 HBM 정상 중심 보정 자료로만
  제한해 사용할 수 있다.
- 사용자 확인 정상 6프레임의 공통 프레임 편향을 제거한 뒤 VRM03–05의
  슬롯별 보조 외곽 중심 기준을 각각 `[-0.5865,0.0089]`,
  `[-0.3705,-0.1425]`, `[-0.5780,-0.2489] mm`로 추가했다. 기존 VRM01·02
  기준도 유지했다. 정상 6프레임의 슬롯별 최대 잔차는
  `0.116/0.113/0.252/0.250/0.115 mm`였고, 별도 정상 `183405`에서도 최대
  `0.413 mm`였다. CAD+측정 위치 허용치 `0.75 mm`는 바꾸지 않았으며,
  `0.70 mm`는 허용치 경계 부근을 사람이 재확인할 수 있게 표시하는
  advisory 후보 기준일 뿐 자동 불량 기준이 아니다.
- VRM 후보 융합을 다음처럼 보강했다. 보정 중심 이탈은 non-empty
  `>=0.90` 및 외곽 confidence `>=0.20`과 함께 `POSE?`로 표시한다. 원시
  회전 확률 `>=0.75`인 약한 방향 증거는 PatchCore `>=0.85`가 동시에
  지지할 때만 `DIR?`로 표시한다. 중심 이탈로 구분되지 않은 VRM01에는
  non-empty `>=0.90`, mask 면적 `>=23000 px`, PatchCore `>=0.85`의
  외곽·외관 합의가 있을 때만 `POSE?`를 표시한다. 기존 턱걸림 조건과
  겹치면 중복 후보 대신 `SEATING?` 하나만 유지한다.
- 재실행 결과 `185451`과 반복 촬영 `183712` 모두 정확히 5개 후보를 냈다:
  `VRM01 POSE? / VRM02 POSE? / VRM03 DIR? / VRM04 DIR? / VRM05 POSE?`.
  독립 정상 `183405`는 VRM을 포함해 후보 0개였다. 기존 VRM01·02 턱걸림
  `180910`은 정확히 두 `SEATING?`만 유지했고, 혼합 불량 `145130`도 기존
  네 후보만 유지해 정상 회귀를 추가하지 않았다.
- 사용자가 이후 VRM 5개를 모두 슬롯 중앙에 평평하게 다시 놓고 새 독립
  정상 `193555`를 촬영했다. RTX GPU에서 전체 경로를 재실행한 결과 정합
  score `0.9831`, VRM 상태는 5/5 모두 `CORRECT` confidence
  `0.9825–0.9982`, 보정 위치 오차는 슬롯 순서대로
  `0.218/0.255/0.378/0.452/0.096 mm`로 전부 `0.75 mm` 이내였으며 후보는
  정확히 0개였다. VRM PatchCore score `0.469–0.757`은 제어 불량 threshold가
  없어 surface `UNKNOWN`으로 유지했고 단독 이상 판정에는 사용하지 않았다.
- 관련 전체 검사 `65 passed`와 Python/JSON/diff 검사를 통과했다. 새
  기준은 모두 `ADVISORY_ONLY`이고 최종 보드 판정은 fail-safe `UNKNOWN`을
  유지한다. `183712`와 `185451`은 같은 물리 오배치를 반복 촬영한 것이므로
  5개 슬롯 자동 FAIL 근거로 세지 않는다. 독립 재배치 정상 `193555` 한 장은
  확보했지만, 반복 정상·조명 변화와 슬롯별 다양한 오배치를 더 확보해야 한다.
  로봇·컨베이어 제어 명령은 보내지 않았고 사용자가 촬영한 저장 사진만
  검사했다.

## 2026-09-04 — VRM01·02 정상 복구 확인 및 HBM 슬롯별 중심 편향 보정

- 사용자가 VRM01·02를 소켓 안에 평평하게 복구한 뒤 S22 3.5배 망원·플래시
  OFF로 `183405`를 블라인드 촬영했다. 원본은 4000×3000/환산 69 mm,
  보드 직사각형도 `0.909`, 통합 정합 score `0.9822`였다. 당시 후속
  `183712`도 같은 정상 상태로 기록했지만, 이후 사용자 정답과 원본을
  재감사해 VRM 5개가 이미 오배치된 장면임을 확인했다. `183712`는 VRM
  정상 검증에서는 제외한다.
- 수정 전 전체 PatchCore 검사에서 VRM01·02는 정상 복구되어 `SEATING?`
  후보가 모두 사라졌지만, 육안상 정상인 HBM01의 YOLO mask 중심이 프레임마다
  고정 슬롯 중심에서 치우쳐 가짜 `POSE?`가 발생했다. 같은 정상 HBM01도
  공통 프레임 편향 보정 후 잔차가 `0.633/1.270/0.930 mm`로 흔들려,
  실제 부품 이동보다 슬롯별 segmentation 중심 편향이 주원인임을 확인했다.
- 사용자 확인 정상 8프레임에서 공통 편향을 제거한 YOLO 중심의 슬롯별
  중앙값을 HBM01–08 고정 기준으로 추가했다: `[0.7368,0.1766]`,
  `[0.7546,-0.0468]`, `[0.5694,0.1915]`, `[-0.0527,0.1728]`,
  `[0.0521,-0.4582]`, `[-0.0563,-0.5857]`, `[0.0107,0.0285]`,
  `[-0.0709,-0.2939] mm`. CAD 슬롯 좌표와 기존 위치 허용치 `0.75 mm`는
  바꾸지 않았으며, 공통 정합 뒤 고정 검출 편향만 제거한다.
- HBM 보정 후 `183405`와 `183712`의 HBM 8슬롯 위치 잔차는 각각 최대
  `0.513/0.485 mm`로 전부 기존 허용치 안에 있었다. `183405`의 전체
  advisory 후보 0개와 VRM01·02 정상 복구는 유효하다. 반면 당시
  `183712`의 후보 0개는 VRM 정상 통과가 아니라 오배치 미검출이었으며,
  위의 VRM 다중근거 융합으로 5개 후보가 모두 표시되도록 바로잡았다.
- 정답이 확정된 혼합 불량 `145130` 회귀에서는 정확히
  `HBM04 DIR? / Inductor01 DIR? / Power Module01 POSE? / VRM03 MISSING?`
  네 후보가 유지됐다. 특히 HBM04의 180도 방향 오류는 흰색 기준점이
  `upper_right`에 검출되어, 중심 보정과 무관하게 계속 잡혔다.
- 관련 하이브리드·VRM 데이터 검사 `60 passed`와 JSON/diff 검사를 통과했다.
  모든 모델과 새 HBM 기준은 계속 `ADVISORY_ONLY`이며 최종 보드 판정은
  fail-safe `UNKNOWN`이다. 기준값은 여러 촬영이지만 한 HBM 물리 배치에서
  얻은 값이므로, 독립 재배치 정상과 제어 위치 불량을 더 모으기 전에는
  자동 FAIL 권한을 부여하지 않는다. 로봇·컨베이어 실제 명령은 보내지
  않았고 촬영 시 S22 overview만 일시 해제·복구했다.

## 2026-09-04 — VRM02 턱걸림 블라인드 반복 검증 및 슬롯별 보정

- 사용자가 `power_module_01`의 현재 위치는 허용 가능하다고 확인한 뒤,
  `vrm_02`(왼쪽 VRM 열에서 아래에서 두 번째)의 한쪽 모서리를 소켓 턱에
  걸쳐 둔 물리 장면을 S22 3.5배 망원·플래시 OFF로 `180328`, `180801`,
  `180910` 세 번 촬영했다. 세 원본은 모두 4000×3000/환산 69 mm,
  보드 직사각형도 `0.909`, 통합 정합 score `0.9842–0.9845`였다.
- 촬영 후 슬롯 크롭을 직전 정상 기준과 직접 비교했다. VRM02는 정상보다
  한쪽으로 크게 밀려 있었고, 사용자가 정상으로 복구하려던 VRM01도 직전
  턱걸림 크롭과 사실상 같은 치우침이 남아 있었다. 따라서 이번 장면의
  물리 정답은 VRM01·VRM02 두 슬롯의 착좌 이상으로 취급했다.
- 검증 정상 6장의 공통 프레임 편향 보정 후 VRM02 YOLO 중심 중앙값
  `[-0.7187, 0.2383] mm`를 슬롯 고정 기준으로 추가했다. 보정 후 정상
  VRM02 횡방향 잔차는 `0.017–0.100 mm`였지만, 이번 턱걸림은 3회 모두
  `1.115–1.191 mm`였다. 정상 PatchCore score는 `0.229–0.517`, 턱걸림은
  3회 모두 `1.000`이었다. mask 면적은 정상과 겹치므로 결함 분리 기준이
  아니라 부품 외곽이 실제 검출됐다는 보조 조건으로만 사용했다.
- VRM02에 한해 non-empty 확률 `>=0.90`, 보정 횡방향 이탈 `>=1.00 mm`,
  보조 외곽 confidence `>=0.25`, mask 면적 `>=21000 px`, PatchCore
  `>=0.80`을 모두 만족할 때 `SEATING?`를 표시한다. VRM01은 동일 장면에서
  상태 분류가 CORRECT와 ROTATED 사이를 오갔지만 EMPTY 확률은 낮았으므로,
  기존 CORRECT 단일 confidence 대신 `1 - P(EMPTY) >=0.90`을 사용해 실제
  착좌 후보가 깜빡이지 않게 했다.
- 최종 코드 재실행에서 세 장 모두 정확히 `vrm_01 SEATING?`와
  `vrm_02 SEATING?` 두 후보를 냈다. VRM01 횡방향 이탈은
  `0.784–0.840 mm`, VRM02는 `1.115–1.191 mm`였다. 가장 까다로운 정상
  `151315` 회귀에서는 후보 0개였고, VRM01/02 잔차는 각각
  `0.035/0.091 mm`였다. 관련 통합 검사 50개와 VRM 데이터·학습 10개,
  총 `60 passed` 및 Python/JSON 구문 검사를 통과했다.
- 두 규칙은 계속 `ADVISORY_ONLY`이고 최종 보드 판정은 fail-safe
  `UNKNOWN`이다. VRM02 한 가지 물리 턱걸림 장면을 세 번 반복한 결과이므로
  자동 FAIL이나 VRM03–05 일반화 근거는 아니다. 다음에는 VRM01·02를 완전히
  평평하게 복구한 독립 정상 배치와 반대쪽 턱걸림을 추가 검증해야 한다.
  로봇·컨베이어 실제 명령은 보내지 않았고 촬영 중 S22 overview만 일시
  해제·복구했다.

## 2026-09-04 — PM01 슬롯 중심 보정 및 VRM01 턱걸림 다중근거 검사

- 사용자가 현재 `power_module_01` 위치는 조립 허용 상태이고, `vrm_01`은
  소켓 턱에 일부 걸려 기울어진 불량 상태라고 확인했다. 같은 배치를 S22
  3.5배 망원·플래시 OFF로 `173934`에 촬영했다. 원본은 4000×3000/환산
  69 mm, 기판 직사각형도 `0.909`, 통합 정합 score `0.9861`이었다.
- 수정 전 보조 외곽 중심은 허용 PM01을 `1.273 mm` 위치 오류로 보았고,
  VRM v6은 턱걸림 VRM01을 `CORRECT 0.9044`로 보았다. VRM01은 평면 장축
  오차가 0°여서 방향 분류만으로는 이 높이/착좌 불량을 구분할 수 없었지만,
  PatchCore score는 `1.000`이고 소켓 가장자리에 heat가 국소화됐다.
- YOLO mask 중심과 실제 부품 중심의 고정 편향을 물리 허용 오차로 잘못
  해석하지 않도록, 공통 프레임 편향을 뺀 뒤 슬롯별 고정 기준 편향을 한 번
  더 빼는 구조를 추가했다. PM01 기준 `[0.7629, 0.0062] mm`는 사용자가
  확인한 동일 정상 5회(`101656–101935`), VRM01 기준
  `[-0.5634, 0.6974] mm`는 정상 6회의 중앙값이다. CAD+측정 위치 허용치
  `0.75 mm` 자체와 슬롯 좌표는 변경하지 않았다.
- 보정 후 현재 허용 PM01 잔차는 `0.584 mm`로 PASS가 되었고 화면 후보에서
  사라졌다. 과거 실제 PM01 대이탈 `144923`은 잔차 `2.411 mm`로 계속
  `POSE?`였다. 따라서 허용 위치를 넓혀 불량까지 통과시킨 것이 아니라
  슬롯별 검출 중심 편향만 제거했다.
- VRM01 턱걸림은 PatchCore 점수 단독 threshold로 판정하지 않는다. 추가
  정상 10슬롯을 재실행했을 때 정상 VRM01 score 최대 `0.7680`과 턱걸림
  score `0.7293–1.000`이 겹쳤기 때문이다. 대신 VRM01에 한해 원시 상태가
  CORRECT 계열 `>=0.80`, 보정 횡방향 이탈 `>=0.70 mm`, 외곽 confidence
  `>=0.25`, mask 면적 `>=21800 px`, PatchCore score `>=0.70`을 모두
  만족할 때만 `SEATING?` 보조 후보를 표시한다.
- 현재 `173934`는 횡방향 `0.774 mm`, mask `22207.5 px`, PatchCore
  `1.000`으로 VRM01 단독 `SEATING?`가 되었고, 이전 반복 `172955`도
  `0.741 mm / 22032.5 px / 0.801`로 재현됐다. 가장 까다로운 정상
  `151315`은 PatchCore `0.7680`이어도 횡방향 `0.035 mm`, mask
  `21510 px`라 후보 0개였다.
- 이 규칙은 자동 FAIL이 아닌 `ADVISORY_ONLY`이며 최종 보드 결과는 계속
  fail-safe `UNKNOWN`이다. 한 물리 턱걸림 배치를 반복한 자료이므로 VRM01
  외 슬롯과 다른 높이·방향·조명에는 일반화하지 않는다. 관련 검사/VRM
  회귀 테스트 `55 passed`와 Python/JSON 구문 검사를 통과했다. 로봇·컨베이어
  실제 명령은 보내지 않았고 촬영 중 S22 overview만 일시 해제·복구했다.

## 2026-09-04 — VRM03 누락 독립 블라인드 검증

- v6에 포함되지 않은 새 배치에서 VRM03만 제거하고 VRM04와 PM02를 정상으로
  복구했다. S22 3.5배 망원·플래시 OFF로 `171123`, `171205`, `171554`
  세 장을 촬영했다. 모두 4000×3000/환산 69 mm, 직사각형도
  `0.908–0.909`, 정합 score `0.9865–0.9868`이었다.
- 학습 추가 전에 기본 v6 통합 경로로 먼저 검사했다. VRM03은 3/3 모두
  `EMPTY 0.9609–0.9867`로 `MISSING?`이었고, 다른 VRM 12개 판정은 모두
  `CORRECT`였다. 정상 VRM의 최저 confidence도 `0.9790`이었다.
- 최신 `171554` 전체 PatchCore 검사에서도 VRM03 score `1.0`과 빈 소켓
  국소 heatmap이 나와 분류기 누락 증거와 일치했다. 결과는
  `runtime/inspection/hybrid_vrm_v6_blind_empty03_full_171554/20260904_171918_011151/`
  에 보관했다.
- PM01은 세 장 모두 중심 오차 `1.230–1.367 mm`로 0.75 mm 허용치를
  넘었지만 보조 화면 후보는 마지막 프레임에서만 표시됐다. VRM 검증과는
  분리하고 다음 장면 전에 중앙으로 복구하기로 했다. 이번 VRM03 장면은
  학습에 넣지 않고 독립 holdout으로 유지한다.
- 모델·threshold·권한 변경은 없으며 v6은 계속 `ADVISORY_ONLY`, 최종
  결과는 `UNKNOWN`이다. 로봇·컨베이어 명령은 보내지 않았고 촬영 중 S22
  overview만 일시 해제·복구했다.

## 2026-09-04 — VRM04 회전 보완·과거 라벨 감사·v6 운영 배치

- 다른 부품을 정상으로 복구하고 왼쪽 VRM 열 위에서 두 번째 `VRM04`만
  반시계 방향 90도로 둔 상태를 `163721`, `163814`, `163931` 세 번
  촬영했다. S22 3.5배 망원·플래시 OFF, 4000×3000/환산 69 mm였고
  기판 직사각형도는 `0.903–0.909`였다. 세 반복 프레임은 하나의 물리 scene
  `vrm04_90ccw_20260904_1637`로 등록하고 preview를 직접 확인했다.
- 교체 전 운영 VRM 모델은 해당 회전을 세 프레임 모두 확정하지 못했다.
  raw 예측은 `CORRECT 0.545`, `CORRECT 0.724`, `ROTATED 0.429`였다.
  동시에 나온 `PM02 POSE?`는 실제 중심 이탈 약 `1.70 mm`가 허용치
  `0.75 mm`를 넘은 상태로 확인됐다.
- VRM04 scene을 더한 v5 후보는 holdout accuracy `0.90`, macro recall
  `0.9444`, EMPTY/CORRECT/ROTATED recall `1.0/0.8333/1.0`이었지만 과거
  CORRECT crop 하나를 회전으로 분류했다. 해당 원본과 preview 및 Unity의
  정상 장축을 다시 대조해 `vrm_state_ambient_01`에서 VRM04와 VRM05의
  라벨이 서로 바뀌어 있던 데이터 오류를 발견했다.
- 원본 사진은 삭제하거나 수정하지 않고, ambient-01의 실제 상태를
  `VRM01 EMPTY / VRM05 ROTATED / VRM02·03·04 CORRECT`로 바로잡았다.
  두 crop의 class 경로와 manifest에 이전 라벨·교정 근거
  `POST_CAPTURE_VISUAL_AUDIT_CORRECTED`를 남기고 preview를 재생성했다.
  잘못된 라벨로 학습된 구 v2는
  `slot_classifier/models/vrm_state_v2_pre_label_audit_20260904/`에 백업했다.
- 교정 데이터와 VRM02·04·05 90도 독립 scene을 사용한 v6 후보를 35 epoch
  학습했다. 물리 scene holdout accuracy/macro recall과 세 클래스 recall은
  모두 `1.0`이었다. holdout 최소 정답 확률이 `0.6707`이므로 자동 계산된
  낮은 문턱은 사용하지 않고 운영 confidence를 `0.90`으로 고정했다.
- 실제 통합 검사 경로의 스테이징에서 정상 3장(`151315/151404/151508`)의
  VRM 15/15가 `CORRECT`, 후보 0건, 최저 confidence `0.9715`였다. VRM04
  90도 3장은 모두 `ROTATED 0.9999+`였고 다른 VRM 오검은 없었다. 같은 고정
  crop 경로에서 VRM02와 VRM05 90도도 각각 3/3 검출했다.
- v6을 기본 `models/vrm_state.*`에 배치한 뒤 운영 기본 경로에서도 정상
  `151508` 후보 0건과 불량 `163931`의 `VRM04 DIR? 0.9999`를 재현했다.
  모델 권한은 계속 `ADVISORY_ONLY`, `validated=false`이고 0.90 미만은
  UNKNOWN이다. 계약의 구조와 융합 권한은 유지하고 현재 provider 상태명만
  `VRM_STATE_V6_ADVISORY`로 갱신했다. 회귀 테스트 `50 passed`를 확인했다.
  로봇·컨베이어 명령은 보내지 않았고 촬영 중 S22 overview만 일시
  해제·복구했다.

## 2026-09-04 — VRM02 90도 데이터 확장과 v4 후보 교차검증

- 왼쪽 VRM 열의 아래에서 두 번째 `VRM02`만 슬롯 중앙에서 시계 방향 90도로
  돌린 상태를 `160933`, `161049`, `161133` 세 번 촬영했다. S22 3.5배
  망원·플래시 OFF, 4000×3000/환산 69 mm였고 직사각형도는
  `0.905–0.906`이었다.
- 세 프레임을 독립 표본으로 부풀리지 않고 단일 물리 scene
  `vrm02_90cw_20260904_1609`로 VRM 상태 데이터셋에 추가했다. preview에서
  VRM02=`rotated`, VRM01·03·04·05=`correct` crop을 확인했다.
- GPU01 180도와 PM01 위치 이탈은 아직 물리적으로 남아 있어 통합 검사에서도
  함께 표시됐다. VRM crop에는 들어가지 않지만 이 촬영은 전체 정상 자료로는
  사용하지 않는다. 기존 운영 모델은 VRM02를 모두 raw `ROTATED` 쪽으로
  분류했으나 confidence가 `0.595/0.522/0.982`라 현재 확정 기준에서는
  1/3만 `DIR?`였다.
- 운영 경로와 분리한 `vrm_state_v4_candidate`를 35 epoch 학습했다. holdout
  accuracy `0.90`, macro recall `0.8333`, 정상·빈 슬롯 recall `1.0`, 회전
  recall `0.50`이었다.
- v4는 새 VRM05·VRM02 90도 각각 3/3과 직전 정상 장면 VRM 15/15를 맞혔지만,
  기존 holdout의 슬롯 밖 회전 VRM03을 `CORRECT 0.809`로 놓쳤다. 따라서
  v4는 운영에 배포하지 않고 `ADVISORY_ONLY` 후보로 보관했다.
- 운영 모델, confidence threshold, PASS/FAIL/UNKNOWN 융합 권한은 변경하지
  않았다. 다음은 다른 슬롯의 순수 90도와 위치 이탈 동반 회전을 서로 다른
  물리 scene으로 추가하는 단계다. 로봇·컨베이어 명령은 보내지 않았고 S22
  overview만 촬영 중 일시 해제·복구했다.

## 2026-09-04 — 비-SMD 보완 혼합 불량과 VRM 90도 일반화 검증

- 정상 상태에서 `GPU01 180도`, `HBM02 누락`, `VRM05 90도`,
  `Inductor02 누락`을 만들고 Power Module 한 개는 90도 회전 대신 슬롯보다
  위로 이동했다. 현재 번호 규칙을 실제 영상과 대조한 결과 사용자가 이동한
  하단 가로 부품은 `PM03`이고, 상단 가로 `PM04`는 정상이다. 좌측 세로
  `PM01`도 직전 정상 사진보다 실제로 이동해 있었다.
- S22 3.5배 망원·플래시 OFF 촬영 `153507`, `153559`, `153718`은 모두
  4000×3000/환산 69 mm, 직사각형도 `0.905–0.908`, 정합
  `0.8824–0.8860`이었다.
- 세 번의 빠른 검사에서 공통으로 `GPU01 DIR? / HBM02 MISSING? /
  Inductor02 MISSING? / PM01 POSE? / PM03 POSE?`가 검출됐다. PM03 중심
  이탈은 약 `3.25–3.30 mm`, PM01은 약 `2.71–2.72 mm`였고 정상인 PM04는
  `0.12–0.34 mm`였다. 반면 기존 VRM 상태 모델은 VRM05 90도를 확정하지
  못했다.
- 최신 전체 검사는
  `runtime/inspection/hybrid_nonsmd_complement_full_153718/20260904_154645_057770/`
  에 저장했다. VRM05 PatchCore `0.8304`는 직전 정상 최대 `0.5663`보다
  높았지만 검증된 fail threshold가 아니므로 독립 FAIL 근거로 승격하지 않았다.
- 반복 촬영 3장은 하나의 실제 배치이므로 단일 scene
  `vrm05_90deg_20260904_1535`로 VRM 데이터셋에 보관했다. 운영 모델은
  유지한 채 `vrm_state_v3_candidate`를 별도 학습했다.
- 후보는 새 VRM05 90도 프레임 3/3, 직전 독립 정상 프레임의 VRM 15/15를
  맞혔다. 그러나 물리 scene holdout accuracy는 `0.70`, macro recall은
  `0.7222`, ROTATED recall은 `0.50`이었다. confidence `0.80` 기준에서는
  기존 회전 holdout 2개를 모두 확정하지 못하고 정상 하나를
  `ROTATED 0.977`로 오검했다.
- 이 후보는 성능 부족으로 운영 경로에 배포하지 않았다. 운영 모델과 threshold,
  fail-safe 융합 계약은 변경하지 않았으며 다음 단계는 다른 VRM 슬롯을 각각
  90도로 둔 독립 물리 scene 수집이다. 모델은 계속 `ADVISORY_ONLY`, 최종
  상태는 `UNKNOWN`이다. 로봇·컨베이어 명령은 보내지 않았고 촬영 중 S22
  overview만 일시 해제·복구했다.

## 2026-09-04 — 비-SMD 혼합 시험 후 전체 정상 복귀 확인

- 직전 제어 불량이었던 HBM04, Inductor01, Power Module01, VRM03을 모두
  정상 슬롯과 방향으로 복구했다. SMD 5개와 다른 모든 부품도 정상 상태로
  유지했다.
- S22 3.5배 망원·플래시 OFF 촬영 `151315`, `151404`, `151508`은 모두
  4000×3000/환산 69 mm, 기판 직사각형도 `0.909–0.910`이었다.
- 세 장의 고정 슬롯·방향·보조 외곽 검사는 모두 후보 0개였고 정합 score는
  `0.9865–0.9888`, YOLO provider error는 0개였다.
- 최신 `151508`에 PatchCore까지 포함한 GPU 전체 검사를 실행한 결과도 후보
  0개, provider error 0개였다. 결과 화면은
  `runtime/inspection/hybrid_nonsmd_recovery_full_151508/20260904_152856_272283/`
  에 저장했으며 Heatmap과 오버레이가 비어 있음을 직접 확인했다.
- 코드·모델·threshold는 변경하지 않았다. 모든 미검증 근거는 계속
  `ADVISORY_ONLY`라 최종 상태는 계약대로 `UNKNOWN`이다. 로봇·컨베이어
  실제 명령은 보내지 않았고 S22 overview만 촬영 중 일시 해제·복구했다.

## 2026-09-04 — 비-SMD 4종 혼합 불량 및 Power Module 원인 보정

- 정상 SMD를 유지하고 `VRM 03 누락`, `HBM 04 180도 역방향`,
  `Inductor 01 90도 회전`, `Power Module 01 슬롯 밖 측면 이탈`을 한 기판에
  동시에 구성했다.
- S22 3.5배 망원·플래시 OFF 촬영 `144923`, `145046`, `145130`은 모두
  4000×3000/환산 69 mm였고, 1600×1266 보드 ROI의 직사각형도는
  `0.908–0.909`, 통합 정합 score는 `0.9061–0.9266`이었다.
- 반복 3회에서 HBM04는 흰점 우측 상단으로 `DIR? 1.0`, Inductor01은 검정
  마커 방향 오류로 `DIR? 0.295–0.329`, VRM03은 `EMPTY 0.951–0.997`로
  `MISSING?`이 모두 재현됐다.
- 슬롯 밖 Power Module01은 외곽 confidence `0.598–0.606`, mask
  `98,384–98,821 px²`, 중심 오차 `3.163–3.219 mm`로 실제 부품과 큰 이탈이
  명확했다. 반면 슬롯 중심 기반 분류기는 `LOW_CONFIDENCE EMPTY
  0.524–0.762`를 내 기존 화면에서 `MISSING?`가 우선되는 문제가 있었다.
- Power Module에만 `LOW_CONFIDENCE EMPTY + pose FAIL + 외곽 confidence
  >=0.55 + 중심 오차 >=2.0 mm + mask >=90,000 px²` 교차 조건을 추가해,
  이 경우 표시 원인을 `POSE?`로 바로잡았다. 확신도 높은 실제 EMPTY나 외곽
  증거가 약한 경우의 `MISSING?`는 그대로 유지하며 모든 provider 권한도
  `ADVISORY_ONLY`로 유지한다.
- GPU로 YOLO 보조 외곽과 부품별 PatchCore까지 실행한 세 결과는 모두 다른
  오검 없이 정확히 `HBM04 DIR? / Inductor01 DIR? / PM01 POSE? /
  VRM03 MISSING?` 네 슬롯이었다. 대표 리포트는
  `runtime/inspection/hybrid_nonsmd_mixed_full_gpu_145130/20260904_150337_441684/`
  이다.
- 정상 보드 `142508` 회귀 결과는 후보 0개, PatchCore provider error 0개였고
  `runtime/inspection/hybrid_nonsmd_mixed_normal_regression/20260904_150441_933238/`
  에 저장했다. Python compile 및 테스트 `42 passed`를 확인했다.
- 최종 상태는 검증 계약에 따라 계속 `UNKNOWN`이며 이번 변경은 자동 판정을
  추가하지 않는다. 로봇·컨베이어 실제 명령은 보내지 않았고 S22 overview만
  촬영 과정에서 일시 해제·복구했다.

## 2026-09-04 — SMD 누락·회전·턱걸림 혼합 불량 동시 검증

- 단일 불량 시험 이후 한 장면에 `SMD 05 누락`, `SMD 03 90도 회전`,
  `SMD 01 소켓 턱걸림`을 동시에 구성했다. SMD02·04 및 다른 부품은 정상
  상태로 유지했다.
- S22 3.5배 망원·플래시 OFF 촬영 `143229`, `143333`, `143450`은 모두
  4000×3000/환산 69 mm, 기판 직사각형도 `0.909`, 정합 score
  `0.9870–0.9874`였다.
- 빠른 고정 슬롯 검사는 세 장 모두 세 오류만 분리했다. SMD05는 `EMPTY`
  confidence `0.9999998–1.000`, SMD03은 각도 오차 `90°`, SMD01은 횡방향
  이탈 `1.259–1.338 mm`였다.
- PatchCore 포함 검사에서 SMD03은 `0.504–0.608`, 빈 SMD05는
  `0.474–0.595`로 반응했다. SMD01은 이전 턱걸림보다 낮은
  `0.155–0.214`였으나 Heatmap이 실제 들린 몸체와 소켓 경계에 집중됐다.
  검증 정상 SMD01 8장의 최대치는 `0.0038`이었다.
- 두 종류의 실측 턱걸림을 포함하기 위해 SMD01에만 PatchCore 하한을
  `0.25→0.10`으로 조정했다. presence `>=0.90`, 외곽 confidence `>=0.20`,
  mask 면적 `>=4400 px²`의 나머지 세 독립 조건은 유지했다.
- 조정 후 혼합 불량 3/3 모두 정확히 `SMD 01 SEATING?`, `SMD 03 POSE?`,
  `SMD 05 MISSING?` 세 후보였다. 대표 결과는
  `runtime/inspection/hybrid_smd_mixed_verified/20260904_144104_172098/`에
  저장했다. 새 기준으로 직전 정상 `142508`도 재검사했고 후보 0개였으며
  결과는
  `runtime/inspection/hybrid_smd_mixed_normal_regression/20260904_144223_393938/`
  에 저장했다.
- Python compile과 테스트 `40 passed`를 통과했다. threshold는 같은 날의
  제한된 조명·기판 자료에 기반하므로 `ADVISORY_ONLY`, 최종 `UNKNOWN`을
  유지한다. 로봇·컨베이어 명령은 보내지 않았고 촬영 중 S22 overview만
  일시 해제·복구했다.

## 2026-09-04 — 전체 SMD 정상 복구 3회 회귀 검증

- SMD01 턱걸림 시험 후 SMD 5개를 전부 정상 안착시켜 `142332`, `142427`,
  `142508` 세 장을 S22 3.5배 망원·플래시 OFF로 촬영했다. 모두
  4000×3000/환산 69 mm, 기판 직사각형도 `0.909`, 정합 score
  `0.9875–0.9879`였다.
- 세 장 모두 고정 슬롯 존재·geometry 및 부품별 PatchCore를 포함한 전체
  검사를 수행했고 결과는 advisory 후보 0개였다. 다섯 SMD의 PatchCore도
  3회 모두 `0.000`으로 확인됐다.
- 정상 촬영 변동으로 SMD01 mask 면적은 최대 `4494 px²`, SMD04는 최대
  `4687.5 px²`까지 측정됐지만 PatchCore와 나머지 독립 근거가 동시에
  성립하지 않아 `SEATING?` 오검이 발생하지 않았다. 모든 SMD의 횡이탈은
  최대 `0.612 mm`로 0.84 mm 표시 기준 이하였다.
- 최신 정상 화면은
  `runtime/inspection/hybrid_all_smd_recovery_full_142508/20260904_142746_328777/`
  에 저장했다. 후보 Heatmap은 비어 있고 오버레이에도 불량 색상이 없음을
  직접 확인했다.
- 코드와 threshold는 이번 작업에서 변경하지 않았다. 모델 권한은 계속
  `ADVISORY_ONLY`라 최종 상태는 계약대로 `UNKNOWN`이며, 이는 정상 장면의
  오류를 뜻하지 않는다. 로봇·컨베이어 명령은 보내지 않았고 S22 overview만
  촬영 중 일시 해제·복구했다.

## 2026-09-04 — SMD 01 턱걸림 안착 불량 슬롯별 확장

- SMD05를 정상 복구한 뒤 오른쪽 아래 가로형 `SMD Capacitor 01`만 소켓 턱에
  걸쳐 기울였다. S22 3.5배 망원·플래시 OFF로 `140754`, `140856`,
  `141001` 세 장을 촬영했으며 모두 4000×3000/환산 69 mm, 기판
  직사각형도 `0.908–0.909`, 정합 score `0.9865–0.9874`였다.
- 기존 고정 슬롯 횡방향 검사만으로도 세 장 모두 SMD01 하나를 `POSE?`로
  검출했다. 횡이탈은 `0.846–0.870 mm`로 표시 기준 0.840 mm를 넘었고,
  전체 중심 오차도 `1.089–1.176 mm`였다.
- 같은 불량의 presence는 `0.9592–0.9905`, 외곽 confidence는
  `0.264–0.348`, mask 면적은 `4574–4644 px²`, PatchCore는
  `0.399–0.486`이었다. Heatmap은 오른쪽 아래 SMD01의 들린 가장자리와
  소켓 턱에 집중됐다.
- 정상 5장 실측 범위는 외곽 confidence 최대 `0.311`, mask 면적 최대
  `4215 px²`, PatchCore 최대 `0.0038`, 횡이탈 최대 `0.263 mm`였다. 이
  분리를 근거로 SMD01에서 presence `>=0.90`, 외곽 confidence `>=0.20`,
  mask 면적 `>=4400 px²`, PatchCore `>=0.25`가 모두 맞을 때만
  `SEATING?`을 표시하도록 했다.
- 가장 낮은 불량 PatchCore를 가진 `140754` 실제 전체 재검사에서는 SMD01만
  후보였고 주 원인은 `SEATING?`, 원래의 횡이탈은 `POSE?` 보조 근거로 함께
  기록됐다. 정상 mask 최대 프레임 `101935` 재검사는 후보 0개였다. 결과
  화면은
  `runtime/inspection/hybrid_smd01_lip_seating_verified/20260904_141847_556412/`
  와
  `runtime/inspection/hybrid_smd01_lip_worst_normal_regression/20260904_141942_759205/`
  에 저장했다.
- Python compile과 테스트 `40 passed`를 통과했다. 규칙은 네 독립 근거가
  동시에 맞을 때만 동작하며 `ADVISORY_ONLY`, 최종 `UNKNOWN` 계약을
  유지한다. 로봇·컨베이어 명령은 보내지 않았고 S22 overview만 촬영 중
  일시 해제·복구했다.

## 2026-09-04 — SMD 05 턱걸림·기울어짐 안착 불량 슬롯별 확장

- SMD02를 정상으로 복원한 뒤 우측 세로열 맨 위 `SMD Capacitor 05`만 소켓
  턱 위에 걸쳐 기울였다. S22 3.5배 망원·플래시 OFF로 `134552`, `134812`,
  `134919` 세 장을 촬영했으며 모두 4000×3000/환산 69 mm, 정합 score
  `0.9861–0.9869`였다.
- 제어 불량 3회의 SMD05 presence는 `PRESENT 0.9966–0.9997`, 외곽
  confidence는 `0.547–0.613`, mask 면적은 `4811.0–4845.5 px²`, PatchCore는
  `0.341–0.368`로 반복됐다. Heatmap도 들린 SMD05와 노출된 소켓 턱에
  집중됐다. 반면 2D 중심 오차는 `0.515–0.556 mm < 0.750 mm`라 평면 위치
  검사만으로는 정상처럼 보였다.
- 검증 정상 5장을 현재 코드로 다시 계측한 SMD05 최대치는 외곽 confidence
  `0.384`, mask 면적 `4438 px²`였고 PatchCore는 모두 `0.000`이었다. 정상과
  불량 사이에 둔 SMD05 전용 표시 조건은 presence `>=0.90`, 외곽 confidence
  `>=0.45`, mask 면적 `>=4600 px²`, PatchCore `>=0.25`이며 네 값이 모두
  성립해야 `SEATING?`을 만든다.
- 불량 중 가장 낮은 외곽 confidence를 보인 `134812` 전체 재검사에서 정확히
  `SMD 05 SEATING?` 한 건만 표시됐다. 정상 mask 최대 프레임 `101724`의 전체
  재검사에서는 후보 0개였다. 결과 화면은 각각
  `runtime/inspection/hybrid_smd05_lip_seating_verified/20260904_135902_468524/`
  및
  `runtime/inspection/hybrid_smd05_lip_worst_normal_regression/20260904_140210_168447/`
  에 저장했다.
- Python compile과 테스트 `38 passed`를 통과했다. 높이를 직접 재는 센서가
  아니라 세 시각 근거를 교차한 표시이므로 SMD05에만 적용하고 미검증 SMD01로
  확대하지 않았다. 권한은 계속 `ADVISORY_ONLY`, 최종 결과는 `UNKNOWN`이다.
  로봇·컨베이어 명령은 보내지 않았고 S22 촬영 중 overview만 일시
  해제·복구했다.

## 2026-09-04 — SMD 02 턱걸림 안착 불량 슬롯별 확장

- SMD04를 정상 복구한 뒤 우측 세로 SMD 중 맨 아래 `SMD Capacitor 02`를
  소켓 턱 위에 걸쳐 기울인 상태로 세 번 촬영했다(`132929`, `133042`,
  `133138`). 촬영은 S22 3.5배 망원·플래시 OFF였으며 원본 4000×3000,
  환산 69 mm, 기판 직사각형도 `0.909–0.910`, 정합 `0.9869–0.9873`이었다.
- 평면 중심의 횡이탈은 `0.791–0.874 mm`라 기존 0.84 mm 표시 기준에서
  1/3만 `POSE?`였다. 그러나 세 장의 mask 면적은 `4623.5–4667.0 px²`,
  PatchCore는 `0.305–0.404`, presence는 `>=0.9983`으로 반복됐고 미검증 전체
  Heatmap도 SMD02의 들린 몸체와 소켓 턱 경계에 집중됐다.
- 정상 5장 SMD02의 mask 면적은 최대 `4222.5 px²`, PatchCore는 모두
  `0.000`이었다. 이 분리를 근거로 SMD02 슬롯 규칙을 presence `>=0.90`,
  외곽 confidence `>=0.20`, mask 면적 `>=4500 px²`, PatchCore `>=0.25`의
  네 조건 교차로 추가했다.
- 수정 후 저장된 불량 3장 모두 주 후보가 `SMD 02 SEATING?`으로 일치했다.
  횡이탈이 큰 세 번째 장은 `POSE?`도 보조 근거로 유지되지만 화면 우선 원인은
  `SEATING?`이다. 실제 전체 재검사 결과는
  `runtime/inspection/hybrid_smd02_lip_seating_verified/20260904_133903_494206/`
  에 저장했다.
- 정상 자료 중 SMD02 면적이 가장 컸던 `101656`을 새 코드로 다시 전체 검사한
  결과 SMD02 면적 `4222.5 px²`, PatchCore `0.000`, 전체 후보 0개였다.
  Python compile과 테스트 `36 passed`를 통과했다.
- SMD02/SMD04는 서로 다른 실측 threshold를 사용하며 아직 검증하지 않은
  SMD01/03/05로 규칙을 확대하지 않았다. 모든 후보는 `ADVISORY_ONLY`, 최종
  상태는 계약대로 `UNKNOWN`이다. 로봇·컨베이어 명령은 보내지 않았다.

## 2026-09-04 — SMD 04 턱걸림·기울어짐 안착 불량 검출

- 사용자가 현재 `SMD Capacitor 04`는 허용 가능한 편심이 아니라 소켓 턱에
  걸쳐져 높이가 들리고 기울어진 제어 불량이라고 정답을 바로잡았다. 촬영한
  `125908`, `125954`, `130034` 세 장은 정상 학습 자료에서 제외하고
  `SEATING` 불량 증거로 보존했다.
- 단일 top-view 중심 검사에서는 이 상태의 보정 위치 오차가
  `0.523–0.602 mm < 0.750 mm`라 PASS였다. 반면 세 장의 SMD04는 presence
  `0.9986–0.9994`, 보조 외곽 confidence `0.710–0.726`, mask 면적
  `4809.5–4865.5 px²`, PatchCore score `0.188–0.273`으로 같은 방향의
  변화를 반복했다.
- 검증 정상 5장 기준 전체 SMD 외곽 confidence 최대는 `0.474`였고 SMD04
  자체는 최대 `0.298`; SMD04 mask 면적 최대 `4490 px²`, PatchCore 최대
  `0.146`이었다. 별도로 복원한 최신 정상 SMD04는 외곽 `0.261`, 면적
  `4416 px²`, PatchCore `0.000`이었다.
- 기존 SMD03용 `약한 외곽 + PatchCore` 안착 규칙은 유지했다. 새 규칙은
  검증된 SMD04에 한정해 presence `>=0.90`, 외곽 confidence `>=0.65`, mask
  면적 `>=4700 px²`, PatchCore `>=0.17`의 네 근거가 모두 맞을 때만
  `SEATING?`을 표시한다. 보조 pose JSON에는 `mask_area_px`와
  `normalized_slot_distance`를 추가했다.
- 수정된 전체 GPU 검사에서 불량 3/3이 모두 유일한 후보
  `smd_capacitor_04:SEATING?`으로 재현됐고 Heatmap은 턱에 걸린 SMD04 경계에
  국소화됐다. 정상 복귀 사진은 동일 코드에서 후보 0개였다. Python compile과
  테스트 `34 passed`를 통과했다.
- 높이를 직접 측정한 것이 아니라 투영 외곽·면적·PatchCore의 교차 증거이므로
  SMD04 이외 슬롯에는 아직 적용하지 않았으며 권한은 `ADVISORY_ONLY`다. 최종
  `PASS/FAIL/UNKNOWN` 계약은 바꾸지 않았고 로봇·컨베이어 명령은 보내지 않았다.

## 2026-09-04 — SMD 04 정상 복귀 반복 검증

- `SMD Capacitor 04`를 슬롯 안에 완전히 복원한 뒤 S22 3.5배 망원·플래시
  OFF로 세 번 새로 촬영했다(`121052`, `121150`, `121232`). 모두
  4000×3000/환산 69 mm였고 기판 직사각형도는 `0.908–0.909`였다.
- 세 프레임에서 SMD04 존재 confidence는 `0.9981–0.9987`, 횡방향 절대
  이탈은 `0.122–0.193 mm`, pose 상태는 모두 `PASS`였으며 전체 advisory
  후보도 매번 0개였다. 앞서 만든 오른쪽 반안착 불량의 `0.857–0.900 mm`와
  정상 복귀값이 반복 측정에서 분리됨을 확인했다.
- 최신 프레임은 모든 부품의 PatchCore까지 포함해 RTX GPU로 재검사했다.
  정합 score `0.9872`, SMD04 PatchCore score `0.000`, 후보 0개였고 결과는
  `runtime/inspection/hybrid_smd04_recovery_verified/20260904_121519_840006/`
  에 저장했다. 출력 화면도 원본·빈 후보 Heatmap·오버레이에 불량 색상이 없는
  상태로 직접 확인했다.
- 표시 후보가 0개여도 최종 결과가 `UNKNOWN`인 이유는 검사 제공자들이 아직
  계약상 `ADVISORY_ONLY`이기 때문이며, 정상 복귀 실패를 뜻하지 않는다.
  SMD05는 슬롯 고유 장축 편향 때문에 원시 위치 오차가 `0.860 mm`였지만
  횡방향은 `0.341 mm`라 SMD04 반안착 규칙의 후보로 오인되지 않았다.
- 판정 기준이나 권한은 이번 작업에서 바꾸지 않았다. 촬영 과정에서 S22
  overview만 일시 해제·복구했고 로봇·컨베이어 실제 명령은 전송하지 않았다.
  반대쪽 횡이탈과 조명 holdout 검증 전까지 현 규칙은 `ADVISORY_ONLY`다.

## 2026-09-04 — SMD 04 횡방향 반안착 표시 분리 검증

- `SMD Capacitor 04`를 오른쪽으로 절반가량 이탈시켜 한쪽이 들린 실제 제어
  불량을 플래시 없이 네 번 촬영했다(`114218`, `114714`, `114807`, `115741`).
  최신 원본은 4000×3000/환산 69 mm이고 기판 직사각형도 `0.909`, 정합
  score `0.987`이었다.
- 전체 중심거리만 낮춰 표시하는 임시 방식은 SMD04 불량 오차
  `0.908–0.926 mm`뿐 아니라 정상 SMD05의 장축 방향 편향
  `0.856–0.890 mm`도 함께 잡았다. 따라서 이 임시 threshold는 폐기하고
  장축 오차와 횡방향 오차를 분리했다.
- 각 pose evidence에 signed/absolute 장축·횡방향 오차를 추가했다. SMD의
  횡방향 `POSE?`는 별도 presence `PRESENT >=0.90`, YOLO 외곽 confidence
  `>=0.20`, 횡방향 절대 이탈 `>=0.84 mm`의 교차 근거를 요구한다. 이 값은
  작업자 후보 표시에만 적용되며 원래 0.75 mm 상태, 프레임 정합, 최종
  PASS/FAIL/UNKNOWN 계약은 바꾸지 않았다.
- 이전 정상 8장 재생 결과 SMD 표시 후보는 0개였고, 현재 불량 4장은 모두
  `SMD 04 POSE?` 한 개만 표시됐다. 불량 횡방향은 `0.857–0.900 mm`, 최신
  정상 SMD05 횡방향은 `0.369 mm`였다. 최종 리포트는
  `runtime/inspection/hybrid_smd04_transverse_verified/20260904_120532_114429/`
  에 저장했다.
- SMD04 PatchCore score가 최신 장면에서 `0.012`에 불과해 이번 검출을
  PatchCore 성공으로 기록하지 않는다. 정상 최대 `0.815 mm`와 불량 최소
  `0.857 mm` 간격도 좁으므로 다른 방향·날짜·조명에서 재검증하기 전까지
  `ADVISORY_ONLY`이며 자동 FAIL 권한은 없다.
- 회귀 테스트 `31 passed`, Python compile 및 RTX 전체 재추론을 통과했다.
  S22 촬영 시 overview 프로세스만 일시 해제·복구했고 로봇·컨베이어 실제
  명령은 전송하지 않았다.

## 2026-09-04 — SMD 03 누락·90도 방향 오류 반복 검증 및 HBM 경계 표시 안정화

- Power Module 02를 정상 위치로 복원하고 `SMD Capacitor 03`만 제거한 독립
  장면을 세 번 촬영했다(`104918`, `105220`, `105311`). 세 장 모두 정합 점수
  `0.9878–0.9884`였고, 존재 분류기는 SMD 03을 `EMPTY` confidence
  `0.99999976–0.99999988`로 반복 검출했다.
- 첫 번째 전체 검사에서는 SMD 03이 유일한 `MISSING?` 후보였으며 PatchCore
  고정 초과 Heatmap도 비어 있는 슬롯에 표시됐다. 즉 누락 위치와 시각 증거가
  같은 슬롯을 가리켰다.
- 세 번째 반복에서 정상 `HBM 06` 중심 오차가 허용 `0.750 mm` 대비
  `0.769 mm`로 단 `0.019 mm` 초과해 `POSE?`가 한 번 깜빡이는 현상을
  확인했다. 앞선 두 프레임은 `0.741/0.718 mm`로 PASS였다.
- 원시 pose 상태와 0.750 mm 허용치는 변경하지 않고, 작업자용 고신뢰
  `POSE?` 표시에만 위치 초과 `0.10 mm` 또는 각도 초과 `1.0°`의 최소 마진을
  요구하도록 했다. 방향점 검사의 `DIR?`, 누락 검사의 `MISSING?`, JSON 원시
  측정값과 fail-safe 융합 규칙은 그대로 유지된다.
- 보정 후 세 장 모두 표시 후보가 정확히 `SMD 03 MISSING?` 하나로 일치했다.
  회귀 테스트 `29 passed`와 Python compile을 통과했다. 모든 모델 및 후보는
  계속 `ADVISORY_ONLY`이며 로봇·컨베이어 실제 명령은 보내지 않았다. HBM의
  미세 위치 이탈 표시 마진은 추가 독립 불량 샘플로 검증하기 전까지 확정 판정
  기준으로 사용하지 않는다.
- 이어서 SMD 03을 복원한 뒤 슬롯 중심에서 90도로 회전한 상태를 세 번
  촬영했다(`111122`, `111328`, `111413`). 세 장 모두 존재는 `PRESENT`
  confidence `0.9942–0.9964`, 보조 geometry의 각도 오차는 정확히 `90.0°`,
  중심 오차는 `1.008–1.054 mm`였다. 세 번 모두 다른 후보 없이
  `SMD 03 POSE?` 하나만 표시됐다.
- 첫 회 전체 PatchCore 점수는 `0.629`였고 후보 게이트 Heatmap이 회전된 SMD 03
  슬롯에 표시됐다. 이 실측은 누락과 90도 오류를 구분해 보여 주지만, SMD용
  독립 방향 provider가 아직 보정되지 않아 최종 상태는 계약대로 `UNKNOWN`이다.
- 사용자가 SMD 03을 슬롯에서 절반가량 벗어나 들린 상태로 만든 안착 불량은
  기존 2D 중심 검사에서 `0.527–0.575 mm < 0.750 mm`, 각도 오차 `0°`로
  통과했다. 투영 중심과 평면 장축만으로 높이 방향 들림을 표현하지 못한 것이
  원인이었다.
- 같은 장면에서 존재 분류는 `PRESENT 0.9989–0.9993`이었지만 YOLO 외곽
  confidence는 `0.195–0.261`로 약해졌고, SMD PatchCore는 `0.399–0.448`로
  반응했다. 검증된 정상 5장×5슬롯의 최고 SMD 점수 `0.146`보다 분리됐다.
- SMD 표면 점수 단독 권한은 계속 차단하고, `PRESENT >=0.90`, 외곽 confidence
  `[0.10, 0.30)`, PatchCore `>=0.25`가 동시에 성립할 때만 작업자 화면에
  `SEATING?`을 표시하는 3중 advisory gate를 추가했다. 3회 모두 SMD 03만
  `SEATING?`으로 표시됐고 Heatmap도 노출된 슬롯 가장자리와 들린 부품에
  국소화됐다.
- 이 gate는 한 종류의 실측 안착 불량과 같은 날의 정상 데이터로 만든 후보이므로
  자동 FAIL 권한은 없다. 다른 슬롯·들림 방향·낮/밤 조명 독립 검증 전까지
  `ADVISORY_ONLY`와 최종 `UNKNOWN`을 유지한다. 테스트 `32 passed`, Python
  compile 통과. 로봇·컨베이어 실제 명령은 보내지 않았다.
- SMD 03을 완전히 다시 안착시킨 뒤 세 번 촬영해 복구 검사도 수행했다
  (`113249`, `113457`, `113546`). 존재 confidence는 `0.9989–0.9993`, 중심
  오차는 `0.620–0.656 mm`, PatchCore는 세 번 모두 `0.000`이었고 전체
  advisory 후보도 모두 0개였다.
- 정상 복구 장면의 외곽 confidence도 `0.230–0.268`로 낮았으므로 외곽 신뢰도
  단독 판정은 오탐을 만들 수 있다. PatchCore 이상과 존재 근거까지 모두
  요구하는 현재 3중 gate가 정상 복구를 올바르게 제외함을 확인했다.

## 2026-09-04 — 부품별 Heatmap 표시 경로 재검사

- 첨부 화면의 원본 `s22_inspection_roi_20260903_215217.png`를 직접 지정해 재검사했다.
  SMD 표면 오탐 방지 조건이 SMD anomaly map 생성 자체까지 막아, `SMD 05` 누락
  점수 `0.5842`가 있어도 Heatmap이 사라지던 것이 원인이었다.
- SMD PatchCore의 단독 `SURFACE?` 권한은 계속 차단하되 presence/pose가 독립적으로
  지목한 슬롯에서는 map을 표시하도록 분리했다. `SMD 05` 누락과 `SMD 03`
  17.30도 방향 오류가 각각 Heatmap에 표시되는 것을 확인했다.
- 전 부품 공통 confidence 0.80 표시 필터를 부품별 큰 위치이탈 조건으로 보완했다.
  `Power Module 01`은 위치 오차 `1.328 mm`가 허용 `0.750 mm`를 넘으므로
  `POSE?`와 Heatmap이 표시된다.
- 현재 두 Inductor는 모델 추론이 정상 수행됐으며 방향 마커는 허용 범위다.
  Inductor 02의 위치 초과는 측정 불확실도 수준인 `0.008 mm`라 작업자 화면의
  불량 후보로 올리지 않았다.
- 회귀 테스트 `24 passed`, RTX 재추론 정합 `0.980`을 확인했다. 모든 Heatmap과
  후보는 계속 `ADVISORY_ONLY`이며 로봇·컨베이어 명령은 보내지 않았다.

## 2026-09-03 — 하이브리드 검사 화면 오탐 및 Heatmap 정리

- 실제 S22 장면의 정답은 `VRM 03`, `SMD Capacitor 05` 누락이며 나머지 부품은
  존재하는 것으로 사용자와 확정했다. 존재 모델은 두 누락을 모두 맞혔고
  `VRM 02`만 저신뢰 `UNKNOWN`이었다.
- segmentation 중심의 공통 `0.898 mm` 투영 편향을 15개 고신뢰 슬롯의
  중앙값으로 보정했다. 계약 상한 `1.5 mm` 안에서 공통값만 제거하고 슬롯별
  실제 위치 잔차는 유지한다.
- 원형 Inductor의 무의미한 segmentation 장축 각도를 제외하고 검정 방향 마커
  검사를 유지했다. HBM 측면의 반복 핀 열을 방향점 후보에서 제외하고 큰 원형점을
  우선해 정상 `HBM 02` 방향 오탐을 제거했다.
- 정상 `VRM 02`의 `ROTATED 0.808929` 오분류를 근거로 VRM 상태 confidence
  기준을 `0.90`으로 올렸다. VRM 02는 불량 표시 없이 `UNKNOWN`, 실제 빈
  VRM 03은 `EMPTY 0.955024`로 남는다.
- 전체 미검증 PatchCore 상대 Heatmap은 개발 분석용으로 보존하고, 작업자용
  Heatmap은 존재·위치·방향 후보가 발생한 슬롯에만 표시한다. 정상 Inductor,
  GPU, HBM에 보이던 오해 소지가 있는 색은 메인 화면에서 제거했다.
- 최신 표시 후보는 `HBM 04 방향`, `SMD 03 위치/각도`, `VRM 03/SMD 05 누락`
  4개다. HBM 04의 큰 흰점은 영상상 우측 상단이며 고정 정방향 기준은 좌측
  하단이다.
- 불량 GPU 교체 사진에서 PatchCore는 정상 `0.693`, 불량 `0.743`으로 겹쳤지만,
  golden-reference 흰색 핀 연속성 검사는 정상 GPU 우측을 `RECHECK`, 불량 GPU
  우측 3번 핀 누락을 `LEG_PATTERN_DEFECT`로 구분했다. 이를 통합 화면의
  `GPU PINS?` 후보로 연결했다. 정상 오탐이 남은 HBM 핀 검사는 제외했다.
- 테스트 `21 passed`, RTX 전체 재추론과 불량 GPU 입력 정합 `0.980`을 확인했다. 모델은 아직
  `ADVISORY_ONLY`, 최종 판정은 `UNKNOWN`이며 로봇·컨베이어 명령은 보내지 않았다.

## 2026-09-03 — SMD 파지용 소형부품 검출 CHArUco 마커리스 전환

- `calibration/scripts/detect_small_part_dry_run.py`에서 CHArUco 추적 경로를 제거하고,
  `/camera/camera` 기반 RGB-D 기반 마커리스 검출로 전환했다.
- 검출은 `scan-all-black-cells`를 기본 동작으로 동작하며, 프레임 내 밝기/HSV +
  크기·비율 필터 + aligned depth 샘플링으로 후보를 걸러낸다.
- 기존 `run_object_approach`/`run_vertical_test` 체인에서 사용하는
  `part_center_base_mm`, `long_axis_angle_base_deg` 출력 형식을 유지해 실행 체인 변경 없이
  사용할 수 있게 유지했다.
- 목표 JSON은 기존 마커 기반 방식처럼 `calibration/data/smd_gripper_camera_last.json`
  사용하도록 동작한다. (`--dry-run`은 기존처럼 동작, `run_full_pick_place_same_spot` 연동 유지)

### 검증 및 제한

- 코드 정합성 검증으로 `python3 -m py_compile calibration/scripts/detect_small_part_dry_run.py` 통과.
- 실제 `/camera/camera` 토픽으로 실기기 온라인 확인은 아직 수행하지 않았다.
- 로봇/그리퍼 실동은 아직 수행하지 않았고, 실기기 실행은 `--execute --confirm-full-cycle` 동시 사용 조건을 유지한다.
- 현재는 실측 검출 성공률/오차를 현장 데이터로 추가 측정해야 한다.

## 2026-09-03 — 그리퍼 카메라 기반 SMD 파지 실행기 추가

- `/camera/camera`(컬러/카메라 info/aligned depth) 기준으로 동작하는
  `calibration/run_pick_smd_with_gripper_camera.sh`를 추가했다.
- 동작은 기존 `detect_small_part_dry_run` → `run_object_approach` → `run_vertical_test`
  → `run_grasp_place_cycle` → (선택) `run_return_to_teaching_point`로 이어지며,
  내부적으로는 `run_full_pick_place_same_spot.py`의 한 사이클을 재사용한다.
- `--slot-id`를 주면 `vision_assembly/config/physical_board.json`의
  `component_slot_overrides.SMD Capacitor.slots` nominal_size를 기준으로 기본
  `part_length_mm`, `part_width_mm`, `part_height_mm`를 자동 적용한다.
- 슬롯 치수는 S1 기준 `6.7527×3.8244×3.0238 mm`, S2~S5 기준 `3.8087×6.7805×3.0238 mm`
  (기존 실측 기반 후보치수)로 동작한다.
- 기본 검출 대상 프레임은 `calibration/data/smd_gripper_camera_last.json`으로 분리되어
  기존 `small_part_last.json` dry-run 결과와 혼재되지 않도록 했다.

### 검증 및 동작 제한

- 2026-09-03 기준 새 실행기는 구현 상태이며, 기본은 `--dry-run`으로 동작을
  점검했다.
- 실행 단계는 `--execute --confirm-full-cycle` 동시 지정이 필요하다.
- 실기기 로봇/그리퍼 및 컨베이어 실제 명령은 아직 수행하지 않았다.
- hand-eye 결과에 대한 기존 경고 메시지는 유지되므로 실제 생산 적용 전
  별도 정밀 검증이 필요하다.

## 2026-09-01 — SMD 제외 부품별 PatchCore 검사 후보 모델

- 기존 기판 전체를 640×512로 축소하는 PatchCore보다 작은 핀·부품 이상을 크게
  보기 위해, 기판 정합 후 슬롯별 고해상도 ROI를 생성하는 데이터 파이프라인을
  구현했다. CAD/실측 슬롯 좌표를 사용하며 긴 축을 수평으로 정규화한다.
- SMD는 현재 사용할 수 없고 기존 정상 데이터도 SMD 미장착 상태였으므로 이번
  모델과 판정 범위에서 명시적으로 제외했다.
- 정상 학습 ROI는 총 320개(GPU 16, HBM 128, Power Module 64, VRM 80,
  Inductor 32), 정상 검증 ROI는 80개다. 결함 보드 13장에서 얻은 260개 ROI는
  결함 슬롯 라벨이 없어 `unverified/mixed_defect`로 격리했다.
- RTX 5070 Ti에서 부품군별 PatchCore 5개를 학습하고 체크포인트, 슬롯별 추론기,
  현재 기판 overlay/JSON을 생성했다. 단위·회귀 테스트 18개가 통과했다.
- 현재 기판 정합은 `0.9745`로 성공했지만 20개 슬롯의 후보 점수가 모두 1.0으로
  포화됐다. 예전 정상 촬영과 현재 촬영의 조명·부품 위치·형상 분포 차이 때문에
  현 모델의 자동 임계값은 사용할 수 없다. 결과 상태는
  `UNVERIFIED_SCORE_ONLY`로 제한했으며 생산 PASS/FAIL과 연결하지 않았다.
- 로봇 및 컨베이어 실제 명령은 전송하지 않았다. 다음 단계는 현재 고정 카메라
  조건의 검증된 정상 기판을 추가 수집하고, 결함 사진에 슬롯 ID와 결함 종류를
  검수 라벨링한 뒤 부품별 임계값을 재보정하는 것이다.

### 현재 카메라 정상 데이터 v2

- 사용자가 정상 부품만 장착한 기판으로 기준 반복, 기판 전체 미세 이동·회전,
  GPU/HBM/Power Module/VRM/Inductor의 정상 소켓 공차, 최종 기준 복구를 순서대로
  촬영해 정확히 30장을 확보했다. SMD는 전 과정에서 제외·미장착 상태를 유지했다.
- 30개 ROI는 모두 1600×1266이며 기판 면적 비율 0.104285~0.106949,
  rectangularity 0.908050~0.910060으로 안정적이었다. 학습 24장/검증 6장으로
  고정하고 부품별 정상 학습 ROI 480개를 생성했다.
- v2 부품별 PatchCore 5개를 RTX GPU에서 재학습했다. 마지막 정상 기판 정합점수는
  0.988, 슬롯 점수 범위 0.000~0.260, 평균 0.126, 1.0 포화 슬롯 0개로 v1의 전
  슬롯 포화 문제가 해결됐다.
- 불량 슬롯별 정답과 독립 불량 검증 세트가 아직 없으므로 v2 역시
  `UNVERIFIED_SCORE_ONLY`이며 자동 PASS/FAIL에는 연결하지 않았다. 로봇·컨베이어
  명령은 전송하지 않았다.
- 단순 실행 명령이 과거 v1을 잘못 불러오지 않도록 통합 추론기의 기본 모델과
  출력 경로를 `pcb_components_current_v2`와 `component_live_v2`로 변경했다.

## 2026-08-26 — 부품 멀티클래스 OBB 중간 학습

- 완료 클래스: GPU, HBM, Power Module, VRM, Inductor
- 실제 영상 데이터: train 82장, validation 21장
- SMD Capacitor는 촬영·라벨링 진행 중이므로 중간 모델에서 제외
- 모델: YOLO26n-OBB, 960 px, 50 epochs, RTX 5070 Ti Laptop GPU
- 중간 검증 결과: 전체 mAP50 0.838, mAP50-95 0.769
  - GPU: mAP50 0.981
  - HBM: mAP50 0.895
  - Power Module: mAP50 0.878
  - VRM: mAP50 0.629
  - Inductor: mAP50 0.809
- 중간 가중치: `vision_assembly/obb/runs/parts_obb_preview/weights/best.pt`
- 비교 이미지: `vision_assembly/obb/runs/parts_obb_preview/parts_5class_preview.jpg`
- 확인된 제한사항: 동일 물체에 중복 OBB가 남아 예측 개수가 실제 개수보다 크게 표시됨. 최종 수량 검사 노드에 클래스별 rotated-IoU NMS/중복 병합을 적용해야 함.
- 다음 작업: SMD Capacitor 라벨링 완료 → 6클래스 최종 데이터셋 재구성 → 재학습 → 실제 실시간 영상 검증 → 중복 제거 및 클래스별 confidence 조정.

## 2026-08-27 — 통합 OBB 트레이 ROI 후처리 및 표시 개선

- 실제 전체 트레이 추론에서 트레이 밖 물체, 타 클래스 구역, 중복 후보가 함께 표시되어 검출 수가 과대 집계되는 문제를 확인함.
- `tray_layout.json`의 정규화 구역을 통합 OBB 노드에서 재사용하도록 수정함.
- 검출 허용 조건: 지정 클래스 구역 내부 중심점, 클래스별 최소 confidence, 학습 라벨 기반 정상 OBB 면적 범위, 클래스별 최대 예상 개수.
- 클래스별 색상 적용: GPU 파랑, HBM 자홍, Power Module 주황, VRM 빨강, Inductor 노랑, SMD 초록.
- 개별 부품 위의 긴 이름/점수 라벨을 제거하고 `G1`, `H1`, `P1`, `V1`, `I1`, `S1` 형식의 짧은 번호만 표시함.
- 상단 별도 패널에 클래스별 `검출 수/예상 수`와 평균 confidence를 표시해 부품 영상 가림을 줄임.
- 저장된 실제 D435 프레임 오프라인 점검: 원시 후보 80개 → ROI/크기/점수/개수 필터 후 33개(GPU 2, HBM 16, Power Module 8, Inductor 4, VRM 3).
- `vision_server` 테스트 23개 통과 및 ROS 2 패키지 재빌드 완료.
- 고정 화면 정규화 좌표를 직접 그리던 구조를 제거하고, 기존 트레이 뷰어와 동일한 기준 이미지·SIFT/Homography를 통합 OBB 노드에 적용함. 카메라 위치·각도가 변하면 6개 구역 polygon도 함께 변환되며, 등록이 끊긴 동안에는 잘못된 구역의 검출을 발행하지 않음.
- 저장된 실제 D435 프레임에서 트레이 등록을 재검증함: good match 24개, homography inlier 21개. 변환된 VRM·Power Module·Inductor·SMD·GPU·HBM 경계가 물리 칸막이와 일치함.
- 성능 조정: 960 px 검출 해상도는 유지하고 RTX GPU FP16 추론, 최대 후보 100개, SIFT 0.35배/1.5초 주기, 주석 영상 최대 폭 1600 px·JPEG 78, 최신 프레임 우선 15 FPS 설정을 적용함.
- 병목 분리 측정: GPU OBB 추론 약 4.7 ms, SIFT 약 8.7 ms, JPEG 약 2.0 ms. 실제 네트워크 D435 압축 입력은 측정 당시 약 6 FPS로 들어와 최종 화면 FPS의 주 병목은 원격 카메라 전송 상태였음.
- ROS 그래프에서 기존 `tray_section_viewer`가 2개 중복 실행된 상태를 확인함. 통합 검출 확인에는 `/vision/parts_obb/image/compressed`만 사용하고, 기존 뷰어는 중복 구독과 화면 혼동을 막기 위해 종료해야 함.
- 통합 YOLO 실행기의 PID 관리를 셸 PID에서 실제 Python ROS 노드 PID/프로세스 그룹 관리로 변경함. `Ctrl+C`, `stop_parts_obb_detector.sh`, 오류 종료 시 `SIGINT`로 정상 종료를 우선하고 제한 시간 초과 시에만 `SIGTERM`을 보내도록 수정함.
- 실제 실행·종료 검증 결과: Python 프로세스 종료, PID 파일 제거, ROS 그래프의 `/parts_obb_detector` 제거 및 종료 traceback 없음. 종료 후 남아 있던 `/tray_part_detector`는 별도 기존 트레이 검출 노드이므로 통합 YOLO 노드와 구분해야 함.
- 새 관측 화면에서 기준 이미지와의 SIFT good match가 10개로 감소해 `NOT REGISTERED`가 발생하고 모든 ROI 검출이 안전 차단되는 문제를 확인함. 단순 임계값 완화는 잘못된 homography를 만들어 사용하지 않음.
- SIFT 등록 실패 시 밝은 트레이 외곽 사각형을 검출하고 기준 외곽과의 homography로 내부 6개 구역을 복원하는 기하학 fallback을 추가함. 실제 새 화면에서 VRM·Power Module·Inductor·SMD·GPU·HBM 경계가 물리 칸막이에 맞는 것을 오프라인 확인함. 이 fallback은 분류 ROI 전용이며 로봇 좌표 계산에는 사용하지 않음.
- 수정 노드 재실행 후 42프레임 처리를 확인했으나 이후 원격 D435 입력이 끊겨 `/vision/parts_obb/status`가 `missing camera input: d435`로 전환됨. 카메라 전송 재개 후 실제 실시간 검출 수 재확인이 필요함.
- 사용자 확인 결과 트레이 구역은 카메라 자세 추정으로 이동시키지 않고, 이전에 수동 확정한 `tray_layout.json` 박스를 그대로 유지하는 것이 요구사항임을 재확인함. 통합 노드를 `registration_mode: fixed`로 전환해 1280×720 등 현재 영상 크기에 정규화 좌표만 비례 적용하도록 수정함. SIFT/외곽 추정은 현재 실행 경로에서 사용하지 않으며 상단 상태는 `FIXED LAYOUT`으로 표시됨.
- 현재 고정 D435 화면과 과거 기준 이미지의 내부 칸막이 위치가 세로 방향으로 약 10~22 px 달라 기존 정규화 값도 실제 칸과 어긋나는 것을 확인함. 현재 화면에서 물리 칸막이 경계를 다시 읽어 `tray_layout.json`의 6개 고정 polygon을 보정함. 특히 Inductor/SMD 하단, GPU/HBM 상단 및 두 우측 구역 경계를 실제 벽에 맞춤. 오프라인 overlay로 6개 경계 일치를 확인했으며 통합 YOLO는 종료된 상태로 인계함.
- YOLO 실행 시 원격 D435와 팀원 PC 화면까지 느려지는 문제를 조사함. 원본 압축 RGB 토픽에 기존 `tray_part_detector` 1개와 `tray_section_viewer` 2개가 이미 중복 구독 중이며, AI YOLO가 네 번째 원본 영상 구독을 추가하는 구조를 확인함.
- 카메라 호스트 전용 `d435_ai_stream` 노드를 추가함. D435 로컬 raw RGB에서 최신 프레임만 8 FPS로 선택하고 JPEG 82로 압축해 `/camera/camera/color/image_ai/compressed`로 발행함. 통합 OBB 입력을 이 전용 토픽으로 변경하고 주석 화면은 1280 px/JPEG 72로 조정함. 원본 15 FPS 압축 스트림을 원격에서 직접 받는 것보다 AI 방향 네트워크 프레임 수를 약 47% 줄이는 설정임.
- 팀원 PC와 노트북 모두에서 통합 YOLO 화면이 생성되지 않는 문제를 재점검함. ROS domain 5에서 D435·AI relay·YOLO 노드가 모두 보이지 않았고, 최적화 설정이 `/camera/camera/color/image_ai/compressed` 중계 토픽만 기다리도록 된 것을 확인함.
- `run_parts_obb_detector.sh`에 ROS_DOMAIN_ID 5 기본값과 입력 자동 선택을 추가함. 카메라 PC의 `/d435_ai_stream`이 보이면 8 FPS 경량 중계를 사용하고, 중계가 없으면 기존 `/camera/camera/color/image_raw/compressed`로 자동 대체해 화면이 완전히 안 나오는 상태를 방지함. 중계 실행기에도 같은 domain 기본값을 추가함.
- 추가한 direct fallback 설정은 RGB 압축 토픽만 8 FPS로 구독하며, 원격 PC에서 대용량 depth/raw 토픽을 불필요하게 구독하지 않도록 분리함. 카메라 없는 상태에서도 YOLO 모델 로드, direct 입력 선택, `/vision/parts_obb/image/compressed` 출력 publisher 생성까지 정상임을 확인함.
- 통합 YOLO 화면 복구 후 고정 트레이 ROI를 실제 화면 기준으로 추가 미세 보정함. 6개 구역을 전체적으로 약 4~5 px 아래로 이동하고, VRM–Power Module, Inductor–SMD, GPU–HBM 등 인접 ROI가 같은 경계선을 공유하지 않도록 3~8 px 정도의 시각적 간격을 추가함. 검출 후보 중심이 물리 칸 안에서 필터링되는 기존 구조는 유지함.
- 사용자 화면 확인 후 ROI를 한 번 더 아래로 미세 이동하고, 기존 GPU–HBM(파랑–보라) 경계의 간격을 표준으로 삼아 모든 인접 ROI 선 사이를 기준 1920×1080 해상도에서 10 px로 통일함. 좌우 경계(VRM–Power Module, Inductor–SMD, GPU–HBM)와 상하 경계(VRM–Inductor, Power Module–HBM, Inductor/SMD–GPU)를 모두 분리함.
- 최종 화면 미세 조정: GPU(파랑)·Inductor(노랑)·VRM(빨강) ROI의 왼쪽 경계를 기준 해상도에서 6 px 확장하고, VRM·Power Module(주황) ROI의 상단을 4 px 아래로 조정해 상단 높이를 줄임. 인접 ROI 사이 10 px 간격은 유지함.
- 트레이 전체가 카메라 화면에서 약간 기울어 보이는 상태를 반영함. VRM(빨강) ROI의 왼쪽 상단 `(524, 89)` px을 고정 회전점으로 삼아 6개 ROI 모든 꼭짓점을 화면 기준 시계방향 5°로 동일하게 회전함. 축 정렬 사각형 대신 회전 polygon을 검출 필터와 주석 화면에 직접 사용하며, 기존 ROI 사이 10 px 간격은 rigid transform에 의해 유지됨.
- 5° 회전이 과도하다는 실화면 확인을 반영해 -3° 상대 보정함. 누적 회전으로 인한 좌표 오차를 피하기 위해 회전 전 원본 ROI에서 다시 계산했으며, 최종 회전값은 같은 기준점 기준 화면 시계방향 2°임.
- 추가 -1° 상대 보정 요청을 반영해 회전 전 원본 ROI 기준으로 모든 polygon을 다시 계산함. 최종 회전값은 VRM 왼쪽 상단 `(524, 89)` px 기준 화면 시계방향 1°임.
- GPU(파랑)와 HBM(보라) ROI에만 -1° 추가 보정을 적용해 최종 0° 축 정렬 사각형으로 복원함. 회전 1°를 유지하는 상단 ROI와 선이 겹치지 않도록 GPU 상단을 781 px, HBM 상단을 613 px로 정리했고, GPU–HBM 좌우 간격은 10 px, 두 ROI 하단은 1020 px로 맞춤.
- 실제 트레이 외곽이 완전한 직사각형이 아니어도 된다는 요청을 반영해 GPU·HBM을 수동 원근 polygon으로 재정의함. HBM 상단은 Power Module 하단선에서 약 10 px 아래로 평행하게 맞추고, GPU 상단은 Inductor/SMD 하단선을 따라가도록 설정함. GPU 왼쪽면은 Inductor 왼쪽면의 기울기를 연장하고, GPU–HBM 인접 경계를 왼쪽으로 이동하면서 10 px 간격을 유지함. 두 ROI 하단은 트레이 하단 기울기에 맞게 연속적으로 정렬함.
- HBM(보라) ROI의 우측 하단 꼭짓점만 5 px 위로 미세 조정함. 나머지 세 꼭짓점과 GPU–HBM 경계 간격은 변경하지 않음.

## 2026-08-27 — SMD Capacitor 포함 6클래스 OBB 학습

- SMD Capacitor 실영상 15장의 OBB 라벨을 완료함. 모든 이미지에 10개씩 총 150개 인스턴스가 있으며, 누락 파일·잘못된 클래스 ID·좌표 필드 오류가 없음을 검사함.
- 기존 학습 실행기에 남아 있던 `smd_capacitor` 제외 옵션을 제거하고, 6클래스 학습 결과가 `parts_obb_6class` 경로에 재현 가능하게 저장되도록 실행 옵션을 정리함.
- 최종 데이터셋: train 94장, validation 24장, 총 820개 인스턴스(GPU 72, HBM 224, Power Module 144, VRM 150, Inductor 80, SMD Capacitor 150).
- RTX 5070 Ti Laptop GPU에서 YOLO26n-OBB, 960 px, 100 epochs로 학습 완료. 최종 전체 성능은 Precision 0.929, Recall 0.950, mAP50 0.984, mAP50-95 0.824임.
- 클래스별 mAP50: GPU 0.990, HBM 0.991, Power Module 0.948, VRM 0.993, Inductor 0.995, SMD Capacitor 0.987.
- SMD Capacitor는 mAP50은 높지만 작은 물체 특성상 mAP50-95가 0.399로 낮으므로, 실제 D435 영상에서 중심·각도·중복·수량 안정성을 추가 검증해야 함.
- 활성 통합 OBB 모델을 `vision_assembly/obb/runs/parts_obb_6class/weights/best.pt`로 변경함. 기존 모델 파일은 비교 및 복구용으로 보존함.
- 실시간 주석 화면의 OBB 떨림과 Inductor/SMD 순간 깜빡임을 줄이기 위해 표시 전용 temporal stabilization을 추가함. 중심·가로/세로 길이·180° 주기 각도에 EMA(alpha 0.35)를 적용하고, 일반 클래스는 2프레임, Inductor/SMD는 3프레임까지 순간 미검출을 화면에서만 유지함.
- 안전을 위해 temporal hold 결과는 `/vision/parts_obb/image/compressed` 주석 화면에만 적용하고, 로봇 및 검사 로직이 구독하는 `/vision/parts_obb/detections`에는 현재 프레임의 원본 검출 결과만 발행하도록 분리함.
- 기존 `vision_server` 테스트 23개 통과, 표시 안정화 단위 동작(좌표 평활화 및 SMD 3프레임 유지 후 제거) 확인, ROS 2 패키지 재빌드 완료.
- 실제 통합 화면에서 개별 `G1/H1/...` 텍스트와 큰 십자 중심표시가 소형 부품 및 OBB를 가리고, 강한 ROI 경계와 겹쳐 복잡해 보이는 문제를 확인함. 개별 ID 텍스트를 기본 비활성화하고 작은 중심점만 남겼으며, OBB는 검은 외곽 4 px + 클래스 색상 2 px, ROI는 기존 색상의 62% 밝기로 분리해 가독성을 개선함. 수량과 평균 점수는 상단 패널에서만 표시함.
- Inductor/SMD 실시간 순간 누락 보완을 위해 YOLO 후보 confidence를 0.15→0.08로 낮추되 ROI·정상 면적·클래스별 최대 수량 필터는 유지함. Inductor와 SMD의 최종 클래스 임계값은 각각 0.10으로 조정하고 표시 유지 시간을 4프레임으로 늘림.
- D435 15 FPS 입력이 시간 경계 오차 때문에 실질적으로 7.5 FPS로 샘플링될 수 있는 문제를 수정함. 프레임 제한 판정에 10% scheduling tolerance를 적용하고 AI relay 및 direct fallback의 YOLO 입력을 8→15 FPS로 변경함. 추론 해상도 960과 입력 JPEG 82는 소형 SMD 정확도를 위해 유지하고, 주석 영상은 기존 1280 px/JPEG 72로 전송량을 제한함.
- 변경 후 Python/YAML 검사, `vision_server` 테스트 23개 통과 및 ROS 2 패키지 재빌드 완료. 실제 D435 연결 환경에서 Inductor/SMD 검출 수와 체감 FPS를 재확인해야 함.
- 실시간 FPS 재진단 결과 최적화 중계 `/camera/camera/color/image_ai/compressed`가 발행되지 않아 direct fallback으로 동작 중이었고, D435 원본 압축 토픽은 약 2.7 FPS, 기존 YOLO 주석 출력은 약 0.67~3 FPS까지 저하됨.
- GPU 단독 벤치마크에서 6클래스 OBB 모델은 960 px 기준 약 214 FPS를 기록해 모델 추론이 병목이 아님을 확인함. ROS 그래프에는 원본 D435를 구독하는 `parts_obb_detector`, `tray_part_detector`, `tray_live_renderer`, `tray_section_viewer`가 동시에 존재하고 `tray_section_viewer` 3개·`tray_live_renderer` 2개의 중복 노드 이름도 확인됨.
- D435 실제 설정은 1280×720×15 FPS, compressed JPEG 95였음. 해상도와 센서 FPS는 유지하면서 JPEG 품질을 85로 조정하자 원격 원본 입력이 약 2.7→8.2 FPS로 개선됨.
- 구버전 8 FPS 제한으로 실행 중이던 통합 OBB 프로세스를 종료하고 15 FPS 및 scheduling tolerance가 적용된 빌드로 재시작함. 재시작 후 `/vision/parts_obb/image/compressed`는 약 8~13 FPS를 확인함. 남은 변동은 원격 입력 간격이 순간 0.3~0.4초까지 벌어지는 전송 버스트이며, 카메라 호스트에서 `d435_ai_stream`을 실행하고 레거시 중복 트레이 노드를 종료하는 것이 다음 최적화 단계임.

## 2026-08-28~31 — S22 고화질 검사 촬영 및 전수검사 파이프라인

- 기존 저화질 스마트폰 연결 경로를 대체하는 공식 scrcpy 4.1 카메라 경로를
  추가했다. S22 후면 메인 카메라를
  3840×2160·30 FPS·50 Mbps H.264로 입력받고, 최신 프레임만 골라 ROS 실시간
  화면(1280×720), 분석 화면(1920×1080), 요청 시 4K 무손실 캡처로 분리했다.
- 컨베이어 감시 화면은 저지연 최신 프레임을 사용하고, 검사는 Samsung Camera의
  실제 3× 망원 렌즈를 선택한 뒤 3.5×로 촬영한다. EXIF 초점거리와 해상도를
  확인하고 원본 JPEG를 보존한다.
- 촬영된 기판 외곽에서 지그 손잡이를 제외하고 139×110 mm 비율로 원근 보정한
  1600×1266 PNG를 생성한다. 검사자 화면 방향과 맞도록 180° 회전한 ROI와 외곽
  디버그 영상을 함께 저장하며, 기판 모서리가 원본 경계에 닿으면 최신 검사 ROI로
  채택하지 않는다.
- 정상 기준 이미지와 Unity 소켓 여유를 이용해 25개 슬롯의 부품 누락·위치·방향을
  검사하는 OpenCV 기반 전수검사기를 구현했다. GPU/HBM은 흰 방향점과 다리,
  Inductor는 검정 표시, 나머지는 색·명암·형상 규칙을 조합한다. S22에서 판정하기
  어려운 VRM/미세 크랙은 D435 근접 재검사 대상으로 분리한다.
- 현재 출력은 개발용 판정이다. 3D 프린트 편차와 원근 때문에 HBM 흰 다리 기준을
  추가 튜닝해야 하며, 실제 불량 샘플 데이터가 충분하지 않아 생산 판정 모델로
  확정하지 않았다.

## 2026-08-31 — 구 스마트폰 카메라 연결 경로 폐기

- 화질과 안정성이 부족해 더 이상 사용하지 않는 구 스마트폰 앱 기반 USB·Wi-Fi
  연결 코드, 저장 IP·포트 설정, 설치 소스와 실행기를 프로젝트에서 제거했다.
- S22는 `run_s22_conveyor_hq.sh`의 USB scrcpy 경로만 사용한다. 공용 ROS 영상
  발행기는 `camera2_scrcpy/`로 이전했고, `/dev/video10`의 v4l2loopback은 scrcpy
  영상 sink로 계속 사용한다.
- 컨베이어 정지선·망원 검사 촬영·ROI 추출 토픽과 서비스 계약은 유지되며, 로봇과
  컨베이어 이동 명령은 이번 정리 과정에서 전송하지 않았다.
- S22에서 구 앱 패키지를 제거하고 PC 클라이언트·부팅 설정도 삭제했다. 이후 새
  HQ 실행기를 18초간 무동작 검증해 3840×2160 입력 약 29.8 FPS, ROS 15 FPS와
  컨베이어 ROI 시작을 확인했으며 종료 후 잔여 프로세스는 없었다.

## 2026-08-31 — 검사 정지 자동 촬영·판정 연동

- 컨베이어의 비전검사 정지 trigger가 들어오면 0.35초 안정화 후 S22 망원 촬영,
  기판 ROI 추출, 전수검사, JSON/디버그 영상 저장을 순서대로 실행하는 통합
  파이프라인을 추가했다.
- 같은 기판에서 trigger가 유지되어도 한 번만 실행하고, 기판이 정지선에서 충분히
  벗어난 상태가 유지된 뒤에만 다음 검사를 허용한다. 중복 프로세스 잠금과 이전
  `latest` 파일 재사용 방지 검사도 포함한다.
- 실제 컨베이어 구동에서 검사 위치 정지와 자동 촬영·검사 흐름을 확인했다. 세부
  불량 판정 임계값은 계속 보정해야 하며, 자동 검사 실행기는 모터 이동 명령을
  직접 보내지 않는다.

## 2026-08-31 — 빈 기판 25개 조립 슬롯 좌표 고정

- 조립 위치에 정지한 빈 기판 외곽을 20프레임 수집하고 중앙값을 사용해 S22
  4K 원본에 25개 부품 슬롯을 투영하는 무동작 좌표 캡처기를 추가했다. 결과는
  board-relative mm, S22 pixel, 부품 장축 방향, JSON/CSV/오버레이로 저장한다.
- 최초 결과에서 Unity 후보 좌표를 현재 물리 기판 축에 그대로 적용해 Inductor와
  SMD가 상하 반전된 오류를 확인했다. 해당 JSON/CSV/PNG와 아카이브 사본을 삭제했다.
- 이전 D435 실측 SMD 값과 현재 S22 빈 기판·완성 기판 대조값을
  `physical_board.json`의 공용 override로 승격했다. 번호는 `S1=오른쪽 아래 안쪽
  가로 홈`, `S2~S5=오른쪽 세로열 아래→위`, `I1~I2=오른쪽 아래 원형 홈 위→아래`로
  고정했다.
- 새 캡처의 기판 외곽 최대 흔들림은 약 2.01 px이며 오버레이에서 7개 홈 중심과
  방향을 직접 확인했다. 좌표/검사 단위 테스트 20개가 통과했다. S22→FR5 Base
  평면 캘리브레이션 파일은 아직 없으므로 현재 결과는 로봇 Base XYZ가 아니며,
  자동 하강 전 모든 슬롯의 TCP 상공 검증이 필요하다.

## 2026-08-31 — 컨베이어 정지 연동 AOI 데이터 수집 모드

- 불량 부품이 섞인 과거 촬영물을 정상 학습 데이터로 오인할 위험을 차단하기 위해,
  기존 OpenCV 전수검사 판정과 분리된 촬영 전용 파이프라인을 추가했다.
- 검사 정지 trigger 뒤 0.35초 안정화하고 S22 실제 3× 망원 렌즈의 3.5×·플래시
  OFF 사진을 한 번 촬영한다. 새 원본 JPEG, 원근 보정 ROI, upright 이미지,
  외곽 디버그 이미지와 ROI 메타데이터가 모두 갱신된 경우에만 한 샘플로 보관한다.
- 모든 샘플은 최초에 `UNVERIFIED`, `normal_training_allowed=false`로 저장한다.
  작업자가 알고 있는 상태는 별도 주석으로만 기록하며, 현재 SMD를 사용할 수 없는
  기판은 `known_defect / missing_smd`로 분리해 누락 검출 검증용으로 활용한다.
- 조명 조건을 `evening_indoor`, `daylight_noon`처럼 디렉터리와 manifest에 기록해
  햇빛 조건이 다른 자료를 무분별하게 섞지 않도록 했다. 같은 기판의 trigger 유지,
  이전 `latest` 파일 재사용 및 촬영 중복도 차단한다.
- 촬영 보관·태그·trigger gate 단위 테스트 5개가 통과했다. 이번 코드 검증 중에는
  실제 컨베이어 이동 명령을 보내지 않았으며, 실물 1회 운전은 사용자가 실행할
  다음 단계로 남아 있다.

## 2026-08-31 — S22 컨베이어 정지 지연 제거 및 fail-safe 강화

- 검사 기판이 정지선을 통과한 사례를 계기로 S22 입력부터 `/cmd_vel`까지의 지연
  경로를 분리했다. 기존에는 4K overview를 디코딩하고 15 FPS로 재표본화했으며,
  정지 trigger도 대시보드 렌더링·JPEG 압축 뒤에 발행되는 구조였다.
- overview를 1920×1080@30 FPS H.264 20 Mbps로 변경하고, 제어 전용 영상을
  960×540/JPEG 84로 즉시 발행한다. 정확한 검사용 4000×3000 망원 사진과
  1600×1266 보정 ROI의 품질은 변경하지 않았다.
- 동일한 30 Hz 타이머끼리 엇갈려 새 프레임을 건너뛰던 폴링을 제거하고, V4L2 새
  프레임 수신 즉시 제어 publisher를 깨우도록 수정했다. 무동작 실측 제어 FPS는
  약 22에서 28.9~29.8로 개선됐고, 정지선 UI 구독 중에도 29.2~29.8을 유지했다.
- 기판 검출·trigger·heartbeat를 UI보다 먼저 발행한다. 0.20초보다 오래된 영상은
  폐기하고, 0.25초 동안 새 비전 상태가 없으면 컨베이어 제어기가 속도 0을 보낸다.
  `/cmd_vel`은 reliable KEEP_LAST(1), 제어 타이머는 50 Hz로 변경했다.
- Full-HD 분석 토픽은 별도 스레드·5 FPS로 제한했다. 운전 중에는 정지선 토픽만
  사용하며 분석 토픽 부하로 오래된 프레임이 생겨도 fail-safe 정지한다.
- 관련 테스트 30개와 ROS 패키지 빌드가 통과했다. 실측은 S22와 정지선 노드만
  실행했으며 실제 컨베이어 모터 명령은 보내지 않았다.

## 2026-08-31 — PCB 이상탐지 v1 데이터셋 분리

- S22 실제 3× 망원 렌즈 3.5× 촬영에서 생성된 1600×1266 원근 보정 기판 ROI를
  PatchCore/MVTec 형식으로 분리했다. 정상 20장은 `train/good` 16장과
  `test/good` 4장, 다양한 불량 13장은 `test/mixed_defect`로 구성했다.
- 불량 촬영에는 부품 누락, 방향 오류, 흰색 핀 누락·변형이 섞여 있으나 촬영 당시
  사진별 세부 유형을 기록하지 않았으므로 현재는 generic abnormal 평가에만
  사용한다. 세부 결함 분류 학습 전에는 manifest를 사후 검수해야 한다.
- 원본은 `runtime/inspection`에 그대로 보존하고 데이터셋에는 복사본만 만들었다.
  총 33장의 존재, 1600×1266 해상도 통일, 파일 중복 없음이 확인됐다. 이번
  데이터 정리에서는 로봇과 컨베이어 명령을 보내지 않았다.

## 2026-08-31 — PatchCore PCB 전체 기판 1차 기준 모델

- Anomalib 2.6.0 PatchCore와 ImageNet 사전학습 Wide-ResNet50-2를 사용해
  1600×1266 보정 ROI를 640×512로 입력하는 GPU 기준 모델을 구성했다. 정상
  16장으로 memory bank를 만들고 test 일부는 임계값 보정용 validation으로
  분리했다.
- RTX 5070 Ti 실측에서 image AUROC 0.9583, image F1 0.5455가 나왔다. 전체
  시각화 17장을 다시 추론했을 때 정상 4장은 모두 GOOD, 알려진 불량 13장 중
  7장은 ANOMALY, 6장은 GOOD으로 판정됐다.
- 원본·heatmap·overlay 패널과 이미지별 점수 CSV, checkpoint, 요약 JSON을
  `runtime/inspection/patchcore/pcb_anomaly_v1`에 저장했다. 높은 AUROC와 달리
  낮은 F1 및 불량 6장 미검출 때문에 현재 모델은 생산 합불 판정에 사용할 수 없다.
- 전체 기판 축소 모델은 큰 부품 누락·회전 확인용 1차 단계로만 사용한다. GPU/HBM
  흰 핀처럼 작은 결함은 부품별 고해상도 ROI PatchCore/전용 검사를 추가해야 한다.
- 전용 환경에서 cuDNN 9.20과 시스템 CUDA가 충돌한 문제를 기존 YOLO GPU 검증
  조합인 cuDNN 9.24로 정렬해 해결했다. 이번 학습에서는 로봇·컨베이어 명령을
  전송하지 않았다.

## 2026-09-01 — S22 1.5배 정지 위치 재보정 및 정지 응답 강화

- 새 고정 시점의 S22 overview를 메인 카메라 1.5배로 확정했다. 정지 상태에서
  두 기판을 동시에 검출했으며 960px 제어 좌표의 초기 trailing edge 실측값
  `175.69px`, `574.67px`를 조립·검사 목표 위치로 저장했다. 정규화 좌표는
  각각 `0.18301061`, `0.59861813`이다.
- 같은 위치에서 S22 실제 3배 망원렌즈의 3.0/3.5/4.0배 4000×3000 원본을
  비교했다. 기판 전체가 들어오면서 ROI 선명도가 가장 높았던 3.5배를 검사 촬영
  기본값으로 확정하고, 4.0배 제스처는 화면 표시를 직접 확인해 별도 선택값으로
  유지했다.
- 사용자의 0.10m/s 실제 구동에서 기존 10px 선행 트리거 후에도 기판이 선을
  지나 정지하는 현상이 보고되어 선행 보상을 20px로 늘렸다. 지연 프레임 차단과
  ready/trigger heartbeat 제한도 각각 0.15초로 단축했다.
- 최신 1프레임 QoS, 1프레임 crossing 판정, UI보다 제어 토픽 우선 발행은
  유지했다. 관련 테스트 `35 passed`와 실행 스크립트 구문 검사를 통과했다.
  변경 적용 중 로봇·컨베이어 명령은 보내지 않았으며, 20px 값은 실제 0.10m/s
  재주행 후 잔차를 보고 최종 미세조정해야 한다.

## 2026-09-01 — 3.5배 검사 프레이밍 기준 최종 검사 위치 이동

- 사용자가 새 검사 위치에 기판을 배치한 뒤 S22 3.5배 망원 원본과 1600×1266
  원근 보정 ROI를 다시 생성했다. 기판 전체와 모든 부품 영역이 포함됐고 검출
  면적 비율 `0.1067`, rectangularity `0.907`을 확인했다.
- 같은 물리 위치의 1.5배 overview에서 기판 trailing edge는 960px 기준
  `503.7585px`였다. 비전 검사 정지선을 `0.59861813`에서 `0.52474848`로
  이동하고 조립선 `0.18301061`, trigger lead 20px는 유지했다.
- 정지선 간격 `0.34173787`은 설정된 안전 간격을 만족했고 회귀 테스트
  `35 passed`를 확인했다. 설정 적용 중 로봇·컨베이어 명령은 보내지 않았다.

## 2026-09-01 — 비전 검사선 최신 수동 위치 미세조정

- 최신 수동 배치 기판의 1.5배 overview trailing edge를 `485.0px/960px`로
  측정해 검사선을 `0.50520833`으로 변경했다. 조립선과 20px 선행 trigger는
  유지했다.
- 새 정지선 간격 `0.32219772`는 안전 기준을 만족했고 테스트 `35 passed`를
  확인했다. 사용자 요청에 따라 노드는 재시작하지 않았고 모터 명령도 보내지
  않았다.

## 2026-09-01 — PatchCore 최신 기판 단일 추론 실행기

- 기존 PatchCore v3 checkpoint와 최신 `s22_inspection_roi_latest.png`를 이용해
  한 장만 GPU 추론하고 원본·heatmap·overlay, label, anomaly score를 저장하는
  `vision_assembly/run_predict_pcb_patchcore.sh`를 추가했다.
- 현재 SMD가 없는 최신 기판 ROI의 결과는 `GOOD`, score `0.45852470`이었다.
  누락 SMD를 검출하지 못했으므로 기존 whole-board baseline이 생산 합불이나
  부품 누락 전수검사에 부적합하다는 제한을 다시 확인했다.
- 실행 결과는 `runtime/inspection/patchcore/live`에 저장한다. 추론 중 로봇과
  컨베이어 명령은 보내지 않았다.

## 2026-09-01 — SMD 포함 부품별 PatchCore v3

- SMD 5개가 모두 장착된 정상 기판 53장을 확정했다. 기판 위치와 각 부품의 허용
  위치 변화를 포함하며 전체 영상은 1600×1266, 면적 비율
  `0.103961~0.107039`, rectangularity `0.903334~0.910599` 범위였다.
- 39장은 학습, 14장은 held-out normal로 분리했다. GPU 39, HBM 312, Power
  Module 156, VRM 195, Inductor 78, SMD Capacitor 195개로 총 975개 정상
  고해상도 ROI를 만들고 RTX 5070 Ti에서 부품별 PatchCore 6개를 학습했다.
- 마지막 held-out 정상 기판에서 정합 점수 `0.98399`, 25개 슬롯 anomaly score
  `0.0000~0.45183`, 평균 `0.21880`을 확인했다. SMD 5개 점수는 모두 0.0으로
  정상 memory bank와 매우 가까웠다.
- 기본 통합 추론기를 v3 체크포인트와 `component_live_v3` 결과 경로로 전환했다.
  과거 mixed-defect 자료에는 결함 슬롯 라벨이 없고 SMD 촬영 조건도 다르므로
  학습 중 AUROC/F1은 생산 성능 근거로 사용하지 않는다. 현재 결과는
  `UNVERIFIED_SCORE_ONLY`이며 슬롯별 통제 불량으로 임계값을 검증하기 전에는
  자동 PASS/FAIL에 연결하지 않는다. 로봇·컨베이어 명령은 보내지 않았다.

## 2026-09-01 — S22 촬영과 25슬롯 PatchCore 검사 통합

- `run_s22_component_patchcore_inspection.sh`를 추가해 검사 위치의 S22 3.5배 광학
  사진 촬영, 1600×1266 기판 ROI 생성, 6개 부품별 PatchCore v3의 25슬롯 추론을
  한 번에 실행하도록 했다.
- 각 단계의 파일 identity를 비교해 새 사진이나 새 결과가 만들어지지 않으면 즉시
  실패한다. 따라서 카메라 촬영 실패 후 이전 기판 사진을 잘못 검사 결과로 사용할
  수 없다.
- 기존 최신 ROI를 사용한 `--skip-capture` 통합 검증에서 정합 `0.98399`, 25개
  슬롯 결과 및 overlay/JSON/event 생성을 확인했고 테스트 `4 passed`를 통과했다.
  실제 광학 촬영은 사용자가 명령을 실행하도록 남겼으며 로봇·컨베이어 명령은
  보내지 않았다. 결함 임계값 검증 전 상태는 `UNVERIFIED_SCORE_ONLY`다.

## 2026-09-01 — 부품별 PatchCore Heatmap 기판 좌표 합성

- 기존 25슬롯 점수 박스 외에 각 부품 모델의 pixel anomaly map을 추출하도록
  변경했다. 세로형 부품 ROI에 적용된 회전·크기 정규화를 역변환하고 각 map을 실제
  기판 슬롯에 재투영한다. 최초 결과의 검은 사각형은 학습용 22% 문맥 여백까지
  표시한 합성 오류였으며, 최종본은 여백을 잘라 실제 부품 몸체만 표시한다.
- 단일 실행 결과로 원본, 상대 Heatmap, Heatmap overlay의 3단 패널과 순수
  Heatmap·overlay·슬롯 점수 이미지를 모두 저장한다. 최신 실제 ROI에서 정합
  `0.98277`, 25슬롯 시각화 생성과 테스트 `7 passed`를 확인했다.
- 현재 색상 범위는 서로 다른 모델을 섞지 않고 부품 타입별 2~99.5 percentile로
  상대 정규화한다. 빨간 영역이
  곧 확정 불량이라는 뜻은 아니며, 통제된 슬롯별 불량 자료로 임계값을 검증할 때까지
  `UNVERIFIED_SCORE_ONLY`를 유지한다. 로봇·컨베이어 명령은 보내지 않았다.

## 2026-09-01 — SMD 포함 전체 기판 PatchCore v4

- SMD 포함 정상 기판 53장을 39장 학습·14장 held-out normal로 분리해 전체 기판
  PatchCore v4를 학습했다. 입력은 `960×768`, coreset ratio는 `0.03`이며 전체
  기판 이상과 부품별 미세 이상을 서로 보완하도록 기존 부품별 v3를 유지했다.
- 과거 mixed-defect 13장 기준 참고 지표는 image AUROC `1.0`, F1 `0.76923`이다.
  결함 종류·슬롯 라벨과 SMD 조건이 맞지 않아 생산 성능 근거로 사용하지 않는다.
- 최신 정상 기판의 전체 결과는 `GOOD`, score `0.27388602`였으며 전체 Heatmap
  생성을 확인했다. 단일 S22 검사 명령에서 전체 기판 v4를 먼저 실행하고 이어서
  6종 부품별 v3의 25슬롯 검사를 수행하도록 통합했다.
- 촬영/전체 결과/부품 결과마다 새 파일 생성 여부를 확인해 과거 결과 재사용을
  차단한다. `--skip-capture` 통합 검증과 테스트 `7 passed`를 완료했으며, 확정
  불량 임계값 전에는 자동 PASS/FAIL로 사용하지 않는다. 로봇·컨베이어 명령은
  보내지 않았다.

## 2026-09-01 — 전체 기판 중심 기본 검사 확정

- 부품별 v3 합성 Heatmap은 정상 부품에도 상대 색이 생기고 모델 간 색상 의미가
  일관되지 않아 기본 검사에서 제외했다. `run_s22_whole_board_inspection.sh`는
  S22 광학 촬영과 전체 기판 v4만 실행하며, 부품별 검사는 `--with-components`
  선택 옵션으로 보존했다.
- 최신 ROI 전체 검사 score는 `0.49285376`였다. 일부 부품 변화가 있는 조건에도
  자동 threshold가 `GOOD`을 반환한 반례를 확인해 결과 화면을
  `MODEL GOOD | UNVERIFIED`로 표시하도록 수정했다. 따라서 현재 출력은 합격 판정이
  아니라 모델 참고값이다.
- 테스트 `8 passed`; 로봇·컨베이어 명령은 보내지 않았으며 통제된 불량별 자료로
  임계값을 확정하기 전 자동 공정 분기에는 사용하지 않는다.

## 2026-09-01 — 촬영 간 전체 Heatmap 색상 기준 고정

- 테스트 모델 시각화에서 사진별 anomaly map min/max를 매번 0~255로 재확장하던
  동작 때문에 촬영마다 색 기준이 바뀌는 문제를 확인했다. 전체 기판 v4 모델은
  유지하고 해당 프레임별 정규화만 제거했다.
- 모든 촬영에서 모델의 고정 `0~1` anomaly 값을 동일한 TURBO 색상 범위로
  변환한다. 최신 부품 변화 기판은 `MODEL ANOMALY | UNVERIFIED`, score
  `0.63822502`로 출력됐고 전체 Heatmap을 직접 확인했다.
- 테스트 `10 passed`; 재학습이나 로봇·컨베이어 명령은 수행하지 않았다. 고정
  색상은 촬영 간 비교를 가능하게 하지만 생산 PASS/FAIL 임계값 검증을 대신하지
  않는다.

## 2026-09-01 — 전체 기판 이상점수 3단계 튜닝

- 실측 score 분포는 held-out 정상 14장 `0.0`, 확인 정상 `0.27388602`, 과거
  mixed-defect 13장 `0.45584026~0.68317264`, 현재 확실한 부품 변화 기판
  `0.63822502`였다.
- 1차 기준을 `NORMAL_CANDIDATE <= 0.40`, `RECHECK 0.40~0.55`,
  `ANOMALY_CANDIDATE >= 0.55`로 설정했다. 기존 정상 14/14는 정상 후보, 불량
  13/13은 재검 7개·이상 후보 6개로 정상 통과에서 제외됐다.
- pixel anomaly `0.35` 이하는 정상 잡색으로 overlay에서 숨긴다. 확인 정상은
  `0.2739`로 색이 사라지고 현재 변화 기판은 `0.6382`로 이상 위치가 표시되는
  것을 별도 출력에서 확인했다. 설정은 JSON으로 분리했고 테스트 `13 passed`다.
- 현재는 세부 결함 라벨이 없는 1차 선별 기준이며 자동 PASS/FAIL 또는 컨베이어
  명령에는 연결하지 않았다. 확정 기준에는 동일 조건의 통제 불량을 한 종류씩
  촬영해 재검 구간을 줄이는 추가 검증이 필요하다.

## 2026-09-01 — strict golden 정상 PatchCore v5 후보 검증

- 기존 53장 중 부품을 움직인 38장을 정상에서 제외했다. 정확 조립과 기판 위치
  변화만 있는 10장 학습·5장 정상 검증, 38장 controlled deviation 및 13장 과거
  mixed defect 이상 검증으로 strict 데이터셋을 구성했다.
- strict v5는 `960×768`, coreset `0.1`, image AUROC `0.79570`, F1 `0.84211`이며
  현재 확실한 변화 기판을 score `1.0`으로 검출했다.
- 정상 score `0.39559~0.51147`과 미세 변화 score `0.42534~0.74627`이 겹쳐
  전역 임계값 하나로 완전 자동 합불을 확정할 수 없었다. 검증되지 않은 모델로 기본
  v4를 덮지 않고 v5는 후보 경로에 보존했다.
- 최종 목표는 무인 검사다. 사람은 개발 중 정답 라벨 검수에만 필요하며 운영 판정에
  포함하지 않는다. strict 정상 추가 촬영과 슬롯별 위치·방향 판정을 결합해야 한다.
  로봇·컨베이어 명령은 보내지 않았다.

## 2026-09-01 — S22 독립형 하이브리드 AOI 설계 계약 확정

- 팀원의 Segmentation 모델은 D435 영상으로 학습되어 S22 검사 영상에 그대로
  사용할 수 없을 가능성이 있으므로 필수 의존성에서 제외했다. 나중에 S22로
  재학습한 외부 모델은 동일 출력 계약을 만족할 때 선택 provider로만 연결한다.
- 고정 조합은 `S22 촬영 품질 확인 → 기판 원근 정합 → 25슬롯 부품 유무·중심·각도
  → GPU/HBM 흰점 등 독립 방향 특징 → GPU/HBM 흰 핀 및 슬롯별 고해상도 외관 이상
  → 전체 기판 strict-normal 이상탐지 → fail-safe 결과 융합`이다.
- 부품 유무·위치·각도 provider는 S22 Segmentation, S22 OBB, 슬롯 제한 기하 후보를
  교체 가능하게 두고, 외관 모델은 PatchCore와 FR-PatchCore를 교체 가능하게
  정의했다. FR-PatchCore의 정합은 외관 변화에만 사용하며 부품의 슬롯 상대 위치·
  방향 오류를 정상 변화로 지우는 용도로 사용하지 않는다.
- 모든 검사기는 `PASS/FAIL/UNKNOWN + confidence + calibration_id + evidence`를
  출력한다. 성능 미검증·저신뢰 모델은 `ADVISORY_ONLY`이며 합격이나 불합격을 단독
  확정하지 않는다. 최종 PASS는 모든 필수 검사가 보정 완료·실행 가능·PASS일 때만
  허용한다. 필수 결과 누락·충돌·저신뢰는 자동 재촬영하고 재시도 한도 후
  `NG_UNCERTAIN` 또는 라인 정지로 처리하며 작업자 육안 PASS는 목표 운영 흐름에
  넣지 않는다.
- 기존 strict v5 실측에서 정상 `0.39559~0.51147`과 미세 변화
  `0.42534~0.74627`가 겹친 근거에 따라 전체 PatchCore 하나를 최종 합불기로 쓰지
  않는다. 정상 학습에는 검수된 정상 조립 S22 사진만 허용하고 부품 이동·누락·
  방향 오류·핀 불량을 정상 variation으로 넣지 않는다.
- 공식 계약은 `vision_assembly/config/inspection_fusion_contract.json`, 설명은
  `vision_assembly/inspection/README.md`에 저장했다. 이번 작업은 설계와 기록만
  고정했으며 전체 runtime fusion 구현 완료를 의미하지 않는다. 로봇·컨베이어 실제
  명령은 보내지 않았다.

## 2026-09-02 — S22 전용 YOLO Segmentation 준비

- D435 학습 이미지와 완전히 분리된 `vision_assembly/segmentation` 경로를 만들고,
  S22 3.5배 광학 촬영 후 생성되는 `1600×1266` 원근 보정 기판 ROI를 GPU, HBM,
  Power Module, VRM, Inductor, SMD Capacitor 6클래스로 수집·라벨링·학습하도록
  준비했다.
- 새 촬영 실행기는 latest ROI 링크가 실제로 새 파일로 교체됐는지 확인해 과거 사진
  재사용을 거부한다. 원본 PNG, 촬영 metadata, SHA-256, 장면명, 기판 상태,
  예상 가시 부품 수와 선명도를 함께 보관하며 동일 ROI 중복 등록도 기본 차단한다.
- 폴리곤 라벨러는 부품 몸체만 표시하고 소켓·그림자·GPU/HBM 흰 핀·흰 방향점은
  제외하도록 기준을 고정했다. 텍스트를 영상 오른쪽 패널로 분리했고, 정상 예상
  25개와 라벨 수가 다르면 저장을 막는다. 의도한 누락 사진은 확인 후 강제 저장할
  수 있으며, 정합된 다음 사진에는 이전 25개 폴리곤을 복사하고 바뀐 부품만 삭제·
  재작성할 수 있다.
- 데이터 빌더는 검수 완료 표시가 있는 사진만 포함하고, 동일 `scene`의 연속 사진이
  train/val 양쪽으로 새지 않도록 장면 단위로 분리한다. class ID, 정규화 좌표,
  polygon 면적, 이미지·라벨 대응과 6클래스 존재 여부를 모두 검사한다.
- 학습 기본값은 공식 사전학습 `yolo26n-seg.pt`, 1280px, batch 4, 150 epochs이며
  방향 정보를 인위적으로 뒤집지 않도록 수평·수직 flip을 비활성화하고 정합 오차만
  반영하는 약한 augmentation을 사용한다. 학습 결과는
  `s22_parts_seg_candidate.pt`로 연결하지만 슬롯 매칭·통제 불량 검증 전까지
  `ADVISORY_ONLY`다.
- 추론기는 깨끗한 mask/중심 시각화와 클래스별 수량, mask 중심, 무방향 장축 각도,
  면적, polygon을 검사 provider 계약 JSON으로 출력한다. 현재는 `slot_id=null`,
  `status=UNKNOWN`이며 단독 PASS/FAIL을 만들지 않는다.
- 폴리곤 round-trip·25부품 recipe·장축 각도 단위 테스트 `3 passed`, 임시 10장
  데이터의 장면 분리 `train 8 / val 2`, YOLO26n-Seg 구조 `3,126,280 parameters`를
  검증했다. 기존 최신 ROI의 임시 보관 테스트 선명도는 `77.54`였고 테스트 자료는
  `/tmp`에서 제거했다. 실제 신규 촬영·라벨링·GPU 학습과 슬롯 매칭은 남아 있으며,
  로봇·컨베이어 명령은 보내지 않았다.

## 2026-09-02 — S22 UI 수동 촬영·일괄 라벨링 입력 추가

- YOLO Segmentation 데이터 수집 시 노트북에서 S22의 Samsung Camera 화면을 직접
  조작할 수 있는 `run_capture_s22_segmentation_manual.sh`를 추가했다. 관리형
  컨베이어 overview가 실행 중이면 카메라 점유를 잠시 해제하고, 검증된 실제 3배
  망원렌즈 기반 3.5배 프레이밍과 플래시 OFF를 설정한 뒤 일반 scrcpy 조작창을
  연다.
- 한 물리 배치에서 사용자가 UI로 2~3장을 촬영하고 창을 닫으면 세션 시작 이후
  `/sdcard/DCIM/Camera`에 생긴 JPEG만 USB ADB로 원본 그대로 가져온다. 각 사진은
  35mm 환산 초점거리 60mm 이상인지 확인하고, 기판을 `1600×1266`으로 원근 보정한
  뒤 scene·board state·예상 부품 수·원본 촬영 metadata와 함께 기존 S22
  Segmentation 라벨링 저장소에 등록한다.
- `--label-after`를 지정하면 전송·ROI 생성이 끝난 뒤 기존 6클래스 폴리곤 라벨러를
  바로 연다. 동일 물리 배치는 같은 scene으로 묶고, 부품을 움직인 뒤에는 새
  scene으로 다시 실행하도록 해 train/validation 누수를 방지한다.
- 도움말과 shell 문법을 확인했으며 실제 S22 촬영·사진 전송은 아직 실행하지
  않았다. 로봇·컨베이어 실제 명령도 보내지 않았고, 모델 권한은 계속
  `ADVISORY_ONLY`다.

## 2026-09-02 — 수동 촬영 14장 복구 및 종료 처리 수정

- 최초 실기동에서 사용자가 scrcpy 창을 닫았을 때 viewer의 종료 코드 때문에
  `set -e`가 사진 가져오기 전에 실행기를 끝내는 문제를 확인했다. scrcpy 종료
  상태와 무관하게 세션 전·후 DCIM 차이를 확인하고, 새 JPEG 존재 여부를 실제
  성공 조건으로 사용하도록 수정했다.
- 휴대폰에 남아 있던 `10:50:34~10:53:00` 촬영 14장을 원본 손실 없이 복구했다.
  전부 `4000×3000`, physical focal length `7.0mm`, 35mm 환산 `69mm`로 실제
  망원렌즈 촬영임을 확인했다. EXIF 기준 flash fired 5장, flash 미발광 9장이며
  동일 물리 배치이므로 모두 `normal_pose_01` scene으로 묶고 조명 metadata만
  구분했다.
- 기판 ROI 추출은 14/14 성공했고 rectangularity `0.908~0.910`, Segmentation
  원본 선명도 Laplacian 분산 `75.68~125.24`였다. 14장을 정상 25부품 라벨링
  대기 목록에 등록하고 라벨러를 실행했다. 관련 단위 테스트 `3 passed`이며,
  로봇·컨베이어 실제 명령은 보내지 않았다.

## 2026-09-02 — SAM2 드래그 자동 폴리곤 라벨링

- 기존 점찍기 폴리곤 라벨러에 박스 프롬프트 기반 SAM2.1 Tiny를 결합했다. 선택할
  부품 몸체를 마우스로 타이트하게 드래그하면 자동 mask를 실제 외곽 폴리곤으로
  변환해 현재 클래스에 추가한다. 짧은 클릭은 기존 수동 점 입력으로 남기고,
  부정확한 자동 결과는 `D` 또는 `U`로 지운 뒤 다시 그릴 수 있다.
- 공식 `sam2.1_t.pt` 74.5MB를 로컬 ignored models 경로에 설치했다. 실행기는 YOLO
  venv를 자동 선택하며 CUDA가 있으면 RTX GPU, 없으면 CPU를 사용한다. prompt
  주변만 허용하는 mask crop과 연결 contour 선택을 적용해 기판 전체나 인접 부품이
  라벨에 들어갈 위험을 줄였다.
- 최신 S22 ROI의 HBM, VRM, SMD, Inductor에서 GPU box-prompt 실측을 수행했다.
  각각 유효 폴리곤이 생성됐고 HBM 17점/면적 20684px², VRM 13점/21303px²,
  SMD 13점/4865.5px², Inductor 25점/11315px²였다. 작은 SMD와 검정 기판 위 검정
  VRM에서도 몸체 외곽을 분리했다.
- 자동 mask도 소켓·그림자·GPU/HBM 흰 핀·흰 방향점을 제외하는 기존 라벨 기준과
  25개 count guard를 그대로 적용한다. 테스트 `5 passed`; 모델 학습이나
  로봇·컨베이어 실제 명령은 수행하지 않았다.

## 2026-09-02 — 잘못된 기판 위치 촬영분 학습 제외

- 사용자가 기판을 잘못된 위치에 놓고 촬영했다고 확인해 `normal_pose_01` 14장을
  활성 Segmentation 원본·metadata·manifest에서 제외했다. 아직 label/review는
  0개여서 학습용 polygon 손실은 없다.
- 즉시 삭제하지 않고 원본 등록 이미지와 metadata, 변경 전 manifest를
  `runtime/inspection/quarantine/wrong_board_position_20260902_1050`에 옮겨
  복구 가능하게 보존했다. 활성 라벨링 이미지와 해당 scene manifest record는
  각각 0개임을 확인했다.
- 다음 수동 UI 촬영부터 각 JPEG의 EXIF flash 값을 자동 읽어 metadata notes에
  기록하도록 보완했다. 따라서 한 scene에서 일반·플래시 버전을 함께 찍어도 실제
  발광 여부를 구분할 수 있다. 로봇·컨베이어 명령은 보내지 않았다.

## 2026-09-02 — 올바른 검사 위치 12장 재촬영 등록

- 올바른 검사 위치에서 다시 촬영한 12장을 확인했다. 일반 6장과 EXIF flash fired
  6장이며 모두 `4000×3000`, physical focal length `7.0mm`, 35mm 환산 `69mm`다.
  기판 전체가 사진 안에 있고 동일 물리 배치임을 contact sheet로 확인했다.
- `normal_correct_pose_01` 한 scene으로 12/12 ROI 추출·등록에 성공했다. 기판
  rectangularity는 `0.907~0.909`, Laplacian sharpness는 `71.29~110.47`이며
  활성 라벨링 입력은 12장이다. 잘못된 이전 14장은 quarantine에 그대로 분리했다.
- scrcpy 창만 닫는 동작이 데스크톱 환경에 따라 viewer 프로세스를 남기는 경우가
  있어, 앞으로는 촬영을 마치고 실행 터미널에서 Enter를 누르면 viewer만 종료하고
  DCIM import를 확실하게 시작하도록 변경했다. 창 닫기도 보조 종료 방식으로
  유지한다. 로봇·컨베이어 명령은 보내지 않았다.

## 2026-09-02 — Segmentation 라벨 클래스 선택 입력 수정

- 실기 라벨링에서 숫자 `1`을 눌러도 선택 클래스가 GPU에서 바뀌지 않는 문제를
  확인했다. OpenCV `waitKey` 대신 확장 키코드 `waitKeyEx`를 사용해 상단 숫자키와
  X11 숫자패드 `0~5`를 모두 처리하도록 수정했다.
- 키보드 입력 방식과 무관하게 오른쪽 패널의 GPU/HBM/Power Module/VRM/Inductor/
  SMD 클래스 행을 마우스로 클릭해 선택할 수 있게 했다. 선택 직후 상단 selected와
  상태 메시지가 함께 바뀌므로 다음 드래그 전에 클래스를 확인할 수 있다.
- 기존 라벨러는 저장 전 GPU polygon 한 개만 있던 상태에서 종료해 학습 label이나
  review 파일 변화는 없었다. 로봇·컨베이어 명령은 보내지 않았다.

## 2026-09-02 — 정상 위치 scene 12장 Segmentation 라벨 완료

- `normal_correct_pose_01`의 일반 6장·플래시 6장, 총 12장을 SAM2 드래그 보조로
  라벨링 완료했다. image/label/review는 각각 12개이며 강제 count override는
  0개다.
- 모든 사진이 클래스별 `GPU 1 / HBM 8 / Power Module 4 / VRM 5 /
  Inductor 2 / SMD 5`, 총 25개 guard를 통과했다. 전체 polygon instance는
  `300개`이며 클래스 합계는 `12/96/48/60/24/60`이다.
- 현재 12장은 동일 물리 배치의 한 scene이므로 train/validation에 나눠 넣지 않는다.
  데이터셋 build·학습 전에 다른 물리 배치 scene을 추가해야 한다. 모델 학습이나
  로봇·컨베이어 명령은 아직 수행하지 않았다.

## 2026-09-02 — 정상 보드 추가 6 scene 수집·등록

- 올바른 검사 위치에서 부품 배치를 조금씩 바꿔 촬영한 12장을 원근 보정 contact
  sheet로 비교했다. 촬영 시각별 일반광·플래시 한 쌍이 같은 배치이며, 총 6개의
  서로 다른 물리 배치임을 확인해 `normal_correct_pose_02~07`로 분리 등록했다.
- 12장 모두 `4000×3000` S22 원본에서 `1600×1266` 표준 ROI를 생성했고 정상 보드
  25개 부품을 기대값으로 기록했다. 일반광 sharpness는 `85.76~115.37`, 플래시는
  `64.73~80.35`로 이번 수집에서는 일반광이 전반적으로 더 선명했다.
- 활성 Segmentation 입력은 기존 라벨 완료 12장과 신규 미라벨 12장을 합쳐 24장,
  물리 scene은 7개가 됐다. 신규 scene은 아직 사람 검수 polygon 라벨이 필요하며
  학습·PASS/FAIL 판정·로봇·컨베이어 실제 명령은 수행하지 않았다.

## 2026-09-02 — 추가 정상 6 scene Segmentation 라벨 완료

- `normal_correct_pose_02~07`의 일반광·플래시 사진 총 12장에 대한 polygon 라벨링을
  완료했다. 각 사진은 `GPU 1 / HBM 8 / Power Module 4 / VRM 5 / Inductor 2 /
  SMD 5`, 총 25개 count guard를 통과했다.
- 신규 12장 모두 review 상태 `COMPLETE`, expected-count override `false`이며 총 신규
  instance는 300개다. 전체 활성 데이터는 image/label/review 각각 24개, 서로 다른
  물리 scene은 7개다.
- scene 단위로 train/validation을 분리할 수 있는 최소 구조는 확보했지만 정상 변화
  범위를 넓히기 위해 추가 배치 수집이 유효하다. 아직 데이터셋 build·학습·생산
  PASS/FAIL 판정 및 로봇·컨베이어 실제 명령은 수행하지 않았다.

## 2026-09-02 — S22 6클래스 Segmentation v1 후보 학습

- 7개 물리 scene, 24장, 600 polygon을 scene 단위로 분리해 train 18장/450개,
  validation 6장/150개 데이터셋을 생성했다. 같은 scene의 일반광·플래시 사진이
  train/validation에 나뉘지 않으므로 동일 배치 누수를 막았다.
- RTX 5070 Ti에서 YOLO26n-seg, 입력 `1280`, 150 epoch 학습을 완료했다. 미사용
  3개 scene 검증에서 전체 Box P/R/mAP50/mAP50-95는 `0.799/0.841/0.914/0.843`,
  Mask는 `0.799/0.841/0.914/0.864`였다. 후보 가중치는
  `segmentation/models/s22_parts_seg_candidate.pt`로 연결했다.
- 현재 ROI 원시 추론에서 YOLO26 end-to-end 중복 후보가 발생해 동일 클래스 box
  IoU 기반 명시적 중복 제거를 추가했다. 42개가 23개로 정리되어 GPU/HBM/VRM/
  Inductor는 `1/8/5/2`로 맞았지만 Power Module은 3/4, SMD는 4/5로 각각 하나씩
  누락됐다. 따라서 모델은 계약대로 `ADVISORY_ONLY`이며 단독 PASS/FAIL 권한이 없다.
- 테스트 `5 passed`, 문법 검사 통과. 로봇·컨베이어 실제 명령은 수행하지 않았다.

## 2026-09-02 — Segmentation 클래스별 threshold·고정 슬롯 매칭

- 같은 train ROI에서도 왼쪽 Power Module `0.185`, 하단 가로 SMD `0.146`이 공통
  confidence `0.20` 아래라 누락된 것을 실측했다. 모델 floor는 `0.01`로 낮춰 후보를
  보존하고, Power Module/SMD는 `0.10`, 나머지 클래스는 `0.20`을 적용했다.
- `full_board_inspection.json`, Unity layout, SMD/Inductor 물리 override에서 25개
  고정 슬롯 중심·크기를 읽어 같은 클래스의 슬롯 허용 범위 안 후보만 배정한다.
  동일 부품 중복 후보는 IoU로 제거하고 슬롯마다 가장 가까운 후보 하나만 남긴다.
- polygon 꼭짓점 단순 평균이었던 화면 내부 점은 실제 면적 중심과 달라질 수 있어
  OpenCV 모멘트 중심으로 수정했다. 중심과 목표 슬롯 좌표는 JSON evidence에 남기되
  결과 이미지에서는 혼동과 가림을 줄이기 위해 중심 마커를 제거했다. 미검출 슬롯만
  빨간 X로 표시한다.
- 기존과 같은 최신 train ROI 재검증에서 `GPU/HBM/Power Module/VRM/Inductor/SMD =
  1/8/4/5/2/5`, 총 25/25가 됐다. 모든 출력 상태는 통제 불량 검증 전까지 `UNKNOWN`,
  모델 권한은 `ADVISORY_ONLY`다. 테스트 `7 passed`; 로봇·컨베이어 명령은 없었다.

## 2026-09-02 — VRM 고정 슬롯 존재 분류기로 검사 계약 보강

- 정상 조립 24장만 본 Segmentation이 빈 VRM 소켓의 검정 사각형과 재질을
  VRM 몸체로 반복 검출했다. 고정 슬롯의 `PRESENT/EMPTY`는 전체 보드 mask보다
  고해상도 슬롯 crop 분류기가 주 판정을 맡도록 융합 계약의 provider 순서를
  변경했다. Segmentation/OBB는 형상 후보 `ADVISORY_ONLY`로 유지하며, 슬롯
  분류기도 통제 검증 전에는 단독 PASS/FAIL 권한이 없다.
- `run_capture_vrm_presence.sh`와 `slot_classifier/vrm_presence_dataset.py`를 추가했다.
  표준 `1600×1266` S22 ROI에서 Unity+물리 보정 기반 `vrm_01~05` crop을 각각
  `256×256`으로 저장하고, 사용자가 명시한 빈 슬롯만 `empty`, 나머지는
  `present`로 manifest에 기록한다. 동일 이미지 hash는 중복 등록하지 않는다.
- EfficientNet-B0는 최종 현장 표준으로 확정한 것이 아니라 전이학습 기준 모델로
  사용하며, 동일 실물 scene 분리 데이터로 EfficientNetV2-S 등과 비교해 빈 슬롯
  recall·오검출률이 좋은 모델을 채택할 계획이다. 오프라인 테스트 `2 passed`,
  임시 scene에서 `present 4 / empty 1` crop·manifest 생성을 확인했다. 실제 학습
  데이터는 아직 등록하지 않았고, 모델 학습·로봇·컨베이어 명령도 수행하지
  않았다.

## 2026-09-02 — 25-slot S22 하이브리드 검사 런타임 4모듈 통합

- `hybrid_inspection/preprocessor_and_cropper.py`, `opencv_inspectors.py`,
  `patchcore_inspector.py`, `main.py`로 고정 슬롯 중심 검사를 통합했다. S22
  원본 또는 이미 보정된 `1600×1266` ROI를 호모그래피·ECC로 기준 프레임에
  정합하고 Unity+물리 override의 25개 슬롯을 YOLO 성공 여부와 관계없이 전부
  crop한다.
- 학습 provider와 PatchCore는 CLAHE를 적용하지 않은 S22 원본 색상을 사용한다.
  OpenCV 국소 특징에만 `clipLimit=2.0`, `tileGridSize=(8,8)` 회색 CLAHE를 적용했고,
  CLAHE tile 포화가 실물 검정 마커 대비를 지우는 경우만 raw grayscale로 교차
  확인한다. 방향 오류를 전처리로 제거하지 않도록 슬롯 crop은 회전하지 않고,
  PatchCore에만 학습 당시와 같은 정규화 crop을 따로 제공한다.
- GPU/HBM은 모서리 흰점과 양쪽 흰 핀 component evidence, Inductor는 흰 상판 내
  검정 마커의 방사 각도를 사용한다. 최신 실제 불량 배치 ROI에서 HBM 우상단
  흰점과 Inductor 2개의 반대 마커를 오류 후보로 출력했지만 통제 검증 전이므로
  `ADVISORY_ONLY`를 유지했다.
- Anomalib 2.6.0의 부품별 PatchCore 체크포인트를 재사용하고, 부품별
  `pass_max/fail_min/authority`가 있는 통제 불량 임계값 파일이 없으면 score·heatmap만
  출력하고 `UNKNOWN`을 내도록 했다. 추론 시 완전한 ckpt를 읽으면서도 timm이
  외부 사전학습 파일을 재조회하던 동작은 `pre_trained=False`+오프라인 모드로
  차단했다.
- 개발 샌드박스에서 최신 ROI 정합 score `0.971996`, 25/25 slot 저장, provider
  비활성 시 `UNKNOWN 25`를 확인했다. 관련 테스트 `12 passed`, Python·shell·JSON
  문법 및 diff check를 통과했다. 샌드박스는 CUDA가 격리되어 실제 GPU YOLO/PatchCore
  추론은 노트북에서 추가 확인이 필요하다. 존재 분류기·통제 불량 PatchCore
  임계값은 아직 없어 생산 PASS는 발행하지 않는다. 로봇·컨베이어 실제 명령은
  수행하지 않았다.

## 2026-09-02 — 하이브리드 검사 3패널 오류 증거 시각화

- 기존 리포트는 검증되지 않은 provider 때문에 25개 슬롯을 전부 노란색
  `UNKNOWN`으로 그렸고, PatchCore map은 슬롯별 `5~99 percentile`로 독립
  정규화해 정상 부품에도 강한 색이 항상 나왔다. 이 색은 불량 강도로
  해석할 수 없음을 확인했다.
- 출력을 `정합 원본 / 정상 기준 초과 PatchCore map / 원본+증거 overlay`
  3패널로 교체했다. 열지도는 부품별 held-out 정상 데이터의 픽셀
  `p99.9`를 초과한 값만 절대 스케일로 표시하며, 슬롯별로 색을 임의로
  늘리지 않는다.
- 방향·누락 의심 `DIR?/MISSING?`, 강한 보조 위치 의심 `POSE?`, 정상
  score p99 초과 `SURFACE?`를 서로 다른 색으로 표시한다. 모든 항목은
  `ADVISORY_ONLY`, `confirmed_defect=false`로 JSON에도 기록하며 최종
  `PASS/FAIL/UNKNOWN` 융합 규칙과 판정 기준은 변경하지 않았다.
- PatchCore/YOLO 비활성 드라이런에서 alignment `0.971996`, 방향 증거 후보
  3개, 3패널 PNG·절대 초과 map·overlay·진단용 25-slot PNG·JSON 생성을
  확인했다. 단위 테스 `7 passed`, Python·shell 문법 검증을 통과했다.
  실제 GPU PatchCore 색 분포는 노트북에서 재실행해 확인해야 하며,
  로봇·컨베이어 실제 명령은 수행하지 않았다.

## 2026-09-02 — VRM EMPTY/CORRECT/ROTATED 고정 슬롯 분류 수집 시작

- 같은 물리 불량 배치를 S22 플래시 on/off로 비교했다. 플래시 입력은 보드
  정합 score가 기존 일반광 `0.971996`에서 `0.937809`로 낮아졌고, advisory
  후보가 `22→25`, VRM 5-slot PatchCore score가 모두 `1.0`으로 포화되어
  빈 소켓·회전 VRM 구분에 사용할 수 없었다. 따라서 생산 VRM 상태
  분류 입력은 플래시 없는 ambient S22 ROI로 고정했다.
- `vrm_state_dataset.py`/`run_capture_vrm_state.sh`를 추가해 5개 고정 슬롯을
  `EMPTY/CORRECT/ROTATED` 3상태로 명시 등록한다. 빈 슬롯과 회전 슬롯은
  사용자가 정확한 ID를 지정하고, 둘이 겹치거나 알 수 없는 ID면 fail-closed로
  저장을 거부한다.
- 최신 ambient scene을 `vrm_state_ambient_01`로 등록했다. 당시에는 VRM04
  회전·VRM05 정상으로 기록했으나, 2026-09-04 원본·preview·Unity 방향
  재감사에서 두 라벨이 뒤바뀐 것을 확인했다. 실제 정답인
  `vrm_01=EMPTY`, `vrm_05=ROTATED`, `vrm_02/03/04=CORRECT`로 crop과
  manifest를 교정했다. count `1/1/3`은 동일하고 교정 이력도 남겼다.
- EfficientNet-B0 3-class 학습기와 TorchScript export를 추가했다. 물리 scene
  단위로 train/validation을 분리하고, 방향 라벨을 파괴하는 90° 회전·flip
  증강은 금지했다. 클래스별 독립 scene 4개 미만이면 학습을 거부하며,
  현재 1 scene에서 이 guard가 정상 동작함을 확인했다.
- 하이브리드 런타임에 VRM 상태 provider를 연결해 향후 `EMPTY`는 존재
  오류, `ROTATED`는 방향 오류, `CORRECT`는 정상 증거로 분리한다. 모델이
  없거나 미검증이면 기존처럼 `UNKNOWN/ADVISORY_ONLY`를 유지한다. 테스트
  `16 passed`, Python·shell 문법 검증을 통과했다. S22 사진 촬영만
  수행했고 로봇·컨베이어 실제 명령은 보내지 않았다.

## 2026-09-02 — VRM 3상태 ambient scene 02 등록

- 플래시를 끄고 `4000×3000`, 35 mm 환산 `69 mm` S22 망원 사진을
  새로 촬영했다. 보드 ROI rectangularity는 `0.908`이었고 촬영 후
  컨베이어 overview는 복구됐다.
- 미리보기와 실물을 교차 확인해 `vrm_02=EMPTY`, `vrm_05=ROTATED`,
  `vrm_01/03/04=CORRECT`를 `vrm_state_ambient_02`로 등록했다. 누적
  2 scene/10 crop이며 label count는 `EMPTY 2 / ROTATED 2 / CORRECT 6`이다.
- 최소 4 scene/class guard를 아직 만족하지 않으므로 학습·모델 교체는
  수행하지 않았다. S22 촬영 외 로봇·컨베이어 실제 명령은
  보내지 않았다.

## 2026-09-02 — VRM 3상태 ambient scene 03 등록

- 플래시 off S22 망원 촬영(`4000×3000`, 69 mm 환산)과 보드 ROI
  rectangularity `0.909`를 확인했다.
- 미리보기에서 `vrm_03=EMPTY`, `vrm_01=ROTATED`, `vrm_02/04/05=CORRECT`를
  확인한 뒤 `vrm_state_ambient_03`으로 등록했다. 누적은 3 physical
  scenes/15 crops, `EMPTY 3 / ROTATED 3 / CORRECT 9`이다.
- 아직 클래스별 최소 4 scene과 5개 슬롯 전체 상태 순환을 완료하지
  않아 학습은 수행하지 않았다. S22 촬영 외 로봇·컨베이어 실제
  명령은 보내지 않았다.

## 2026-09-02 — VRM 3상태 ambient scene 04 등록

- 플래시 off S22 ROI(rectangularity `0.908`)의 미리보기에서
  `vrm_04=EMPTY`, `vrm_02=ROTATED`, `vrm_01/03/05=CORRECT`를 확인하고
  `vrm_state_ambient_04`로 등록했다.
- 누적은 4 physical scenes/20 crops, `EMPTY 4 / ROTATED 4 / CORRECT 12`다.
  클래스별 최소 scene guard는 충족했지만 `vrm_05 EMPTY`, `vrm_03 ROTATED`를
  추가해 5-slot 전체 상태 순환을 마친 뒤 첫 후보 학습을 수행하기로 했다.
- 학습·모델 교체·로봇·컨베이어 실제 명령은 수행하지 않았다.

## 2026-09-02 — VRM 3상태 v2 분류기 학습·통합 검사 검증

- 다섯 번째 ambient 장면을 `vrm_state_ambient_05`로 등록했다. 정답은
  `vrm_05=EMPTY`, `vrm_03=ROTATED`, `vrm_01/02/04=CORRECT`이다. 이후
  2026-09-04 라벨 감사로 기존 5개 scene은 EMPTY만 각 슬롯 한 번씩이며,
  ROTATED는 VRM01/02/03 한 번, VRM05 두 번, VRM04 0번이었던 것으로
  정정했다. VRM04는 새 scene `vrm04_90ccw_20260904_1637`에서 보완했고,
  당시의 오염된 v2 모델은 백업 후 교정 데이터 기반 v6으로 교체했다.
- 첫 v1 모델은 crop 25개 중 argmax 정답이 24개였지만 정답 확률이
  `0.372~0.828`에 머물렀고, 실제 하이브리드 경로에서는 장면 05가
  `0.427~0.621`로 모두 기준 `0.80` 미만이었다. 원인은 같은 macro recall
  동점에서 가장 이른 저신뢰 checkpoint를 저장한 것과, 수집 시 원본 ROI
  crop과 검사 시 ECC 정합 후 crop이 서로 달랐던 것이다. 신뢰도 문턱을
  임의로 낮추지 않고 입력·학습 경로를 수정했다.
- 수집과 추론이 모두 전역 정합 보드에서 동일한 `getRectSubPix`, margin
  `0.24`, square `256×256`을 호출하도록 공통 crop 계약 v2를 만들었다.
  기존 v1 원본과 명시 라벨은 보존하고 v2 crop만 재생성했다. 학습기의
  checkpoint는 recall 우선, 동점이면 validation loss가 가장 낮은 epoch를
  선택하며 state tensor를 clone한다. v1 모델은
  `slot_classifier/models/vrm_state_v1_backup/`에 보존했다.
- EfficientNet-B0 v2는 장면 04 전체를 holdout으로 둔 검증에서
  EMPTY/CORRECT/ROTATED recall이 각각 `1.0`, 정답 확률 최저 `0.8520`, 평균
  `0.9476`이었다. 학습 장면의 deterministic accuracy/recall도 `1.0`, 정답
  확률 최저 `0.9690`이었다.
- 실제 하이브리드 입력 경로에서 학습 장면 05는 5개 상태를 모두 맞혔고
  신뢰도 `0.9844~0.9997`, 학습에서 제외한 장면 04도
  `vrm_02=ROTATED`, `vrm_04=EMPTY`를 포함해 모두 맞혔으며 신뢰도
  `0.8770~0.9984`였다. 기본 모델을 v2로 승격했고 raw class 확률도 JSON
  evidence에 기록한다.
- 아직 데이터가 5개 물리 장면이고 holdout도 1개 장면뿐이므로 모델은
  `ADVISORY_ONLY`, `validated=false`다. 다른 필수 provider를 끈 분리 검증의
  최종 보드 결과가 `UNKNOWN`인 것은 fail-safe 계약상 정상이다. 추가 인쇄물,
  낮/저녁 조명, 미세 위치 편차의 독립 통제 데이터로 오검출·미검출률을
  검증하기 전에는 단독 생산 PASS/FAIL 권한을 주지 않는다.
- 관련 테스트 `16 passed`, Python·JSON·shell 문법 검증을 통과했다. 이번
  작업은 저장 사진 재처리·AI 학습·오프라인 검사만 수행했으며 로봇·컨베이어
  실제 명령은 보내지 않았다.

## 2026-09-02 — S22 실시간 촬영→전체 25슬롯 하이브리드 검사 통합

- `run_s22_live_hybrid_inspection.sh`를 추가했다. S22 현재 화면에서 플래시 OFF,
  기본 3.5배 망원 정지 사진을 새로 촬영하고, `1600×1266` 보드 ROI 생성 여부와
  이전 latest ROI 재사용 여부를 확인한 뒤 전체 하이브리드 검사를 실행한다.
  `--skip-capture`는 저장 ROI 진단용이며 기본 실행은 반드시 새 사진을 요구한다.
- 실제 연결된 S22로 전체 흐름을 검증했다. 원본은 `4000×3000`, 7.0mm/
  35mm 환산 69mm 망원, 플래시 OFF였고 보드 검출 rectangularity `0.907`의
  ROI `s22_inspection_roi_20260902_183049.png`를 생성했다. 실행 중 managed
  conveyor overview를 일시 정지하고 촬영 후 정상 복구했다.
- 새 ROI에서 GPU 1/HBM 8/Power Module 4/VRM 5/Inductor 2/SMD 5, 총 25개
  슬롯을 모두 순회했고 정합 score는 `0.983396`이었다. 6개 부품별 PatchCore
  모델은 CUDA에서 모두 로드·추론됐고 결과 PNG/JSON latest 링크를 갱신했다.
- 최종 결과는 `UNKNOWN`, advisory 후보는 15개다. 이는 실행 실패가 아니라
  YOLO/PatchCore/VRM 상태 모델 등 전체 provider가 아직 검증 전이어서
  `ADVISORY_ONLY`, `confirmed_defect=false`인 fail-safe 결과다. 특히 현재
  PatchCore는 정상 기준 초과 후보가 많아 통제 검증 전 생산 불량 판정으로
  사용할 수 없다.
- shell 문법·도움말과 실제 fresh-ROI guard를 확인했다. 카메라 촬영과 overview
  pause/resume만 수행했으며 로봇·컨베이어 실제 이동 명령은 보내지 않았다.

## 2026-09-02 — 비VRM 20슬롯 PRESENT/EMPTY 수집 준비

- 최신 전체 검사 JSON을 단계별로 계측했다. VRM 외 GPU/HBM/Power Module/
  Inductor/SMD 20개 슬롯이 모두
  `PRESENCE_MODEL_OR_VALIDATION_METADATA_MISSING`이었고, advisory code는
  `DIR? 2 / MISSING? 1 / POSE? 6 / SURFACE? 13`이었다. 따라서 PatchCore
  색을 줄이는 것보다 고정 슬롯 존재 provider 확보를 우선했다.
- `component_presence_common.py`, `component_presence_dataset.py`,
  `run_capture_component_presence.sh`를 추가했다. 플래시 OFF 새 S22 사진을
  요구하고 전역 정합 뒤 20개 비VRM 슬롯을 부품별 margin으로 sub-pixel crop해
  `256×256` 원본 RGB로 저장한다. 수집과 향후 runtime이 공유할 crop pipeline
  ID도 manifest에 기록한다.
- 사용자가 `--empty`로 명시한 슬롯만 EMPTY, 나머지는 PRESENT로 저장한다.
  방향·핀·표면 불량이어도 몸체가 있으면 PRESENT이며, `--all-present`와
  `--empty` 동시 사용, 잘못된 슬롯 ID, 중복 사진, 낮은 보드 정합, 플래시
  입력은 fail-closed로 거부한다. VRM은 기존 3상태 모델이 담당하므로 제외했다.
- 과거 무작위 불량 사진은 장면별 정확한 슬롯 정답이 기록되지 않아 학습
  데이터로 전환하지 않았다. 새 수집기의 테스트를 포함해 전체 관련 테스트
  `19 passed`, Python·shell 문법과 도움말을 확인했다. 아직 첫 명시 장면을
  등록하거나 모델을 학습하지 않았으며 로봇·컨베이어 명령도 보내지 않았다.

## 2026-09-02 — 비VRM 존재 데이터 오라벨 정정

- 실물 배치 재확인 결과 `component_presence_scene_20260902_192359_989158`은
  `power_module_01`만 비어 있고 `hbm_01`은 존재하는 장면이었다. manifest의
  `hbm_01`을 EMPTY에서 PRESENT로 정정하고 crop도 PRESENT 경로로 옮겼다.
- 정정 후 장면별 EMPTY 목록에서 해당 장면에 `power_module_01`만 남는 것을
  확인했다. 로봇·컨베이어 실제 명령은 보내지 않았다.

## 2026-09-02 — 비VRM 20슬롯 PRESENT/EMPTY 1차 수집 완료

- S22 3.5배 망원·플래시 OFF 고정 조건에서 GPU 1, HBM 8, Power Module 4,
  Inductor 2, SMD Capacitor 5의 모든 비VRM 슬롯을 최소 한 번씩 EMPTY로
  촬영했다. 현재 dataset은 23개 물리 장면, 460개 고정 슬롯 crop이다.
- 마지막 SMD 장면 5개는 `smd_capacitor_01~05`가 각각 단독 EMPTY로 manifest에
  저장된 것을 확인했다. 전체 EMPTY coverage도 20/20 슬롯이다.
- 이는 coverage 확보 단계이며 GPU EMPTY처럼 클래스별 예제가 1장뿐인 경우가
  있어 아직 생산 검증용 모델 학습 완료로 간주하지 않는다. 다음 단계는 서로
  다른 혼합 EMPTY 배치와 독립 holdout 장면을 추가하는 것이다.
- 촬영을 위해 managed S22 overview만 일시 정지·복구했으며 로봇·컨베이어 실제
  이동 명령은 보내지 않았다.

## 2026-09-02 — 비VRM presence 혼합 EMPTY 장면 추가

- 단독 EMPTY 수집 뒤 9개 혼합 배치를 추가해 dataset을 32 scenes/640 slot
  crops로 확장했다. 혼합 장면은 GPU EMPTY 9개를 추가하고 HBM/Power Module/
  Inductor 및 일부 SMD EMPTY를 서로 다른 조합으로 포함한다.
- 9개 preview를 contact sheet로 대조했고 manifest의 EMPTY 박스와 실제 빈 슬롯이
  일치했다. 일부 장면의 SMD는 실제로 존재하며 manifest도 PRESENT이므로
  오라벨이 아니다. 현재 class별 crop 수는 GPU E10/P22, HBM E17/P239,
  PM E14/P114, Inductor E11/P53, SMD E9/P151이다.
- 이는 candidate 학습용 데이터이며 동일 날짜·동일 실물 중심이므로 별도 물리
  holdout 검증 전 생산 권한은 부여하지 않는다. 로봇·컨베이어 명령은 없었다.

## 2026-09-02 — 비VRM PRESENT/EMPTY 후보 모델 학습 및 runtime 연결

- 32개 장면을 scene 단위 train/validation으로 분리하고 EfficientNet-B0 기반
  GPU/HBM/Power Module/Inductor/SMD 이진 모델을 CUDA에서 각각 20 epochs
  학습했다. class-weighted loss를 사용했고 crop 단위 누출은 허용하지 않았다.
- 혼합 preview 감사에서 실제 빈 SMD 5개가 PRESENT로 잘못 기록된 것을 발견해
  원본 crop으로 확인 후 EMPTY로 정정했다. SMD만 재학습한 holdout은 EMPTY/PRESENT
  recall 1.0/1.0, minimum true probability 0.9981이었다.
- runtime이 수집기와 같은 `registered_board_getRectSubPix_component_margin_square256_v1`
  crop을 사용하도록 연결하고 pipeline mismatch는 UNKNOWN으로 fail-closed 처리했다.
  최신 혼합 장면에서 SMD 01~04 PRESENT 0.997~0.999, SMD 05 EMPTY 0.9999999였고,
  나머지 비VRM EMPTY/PRESENT도 실제 배치와 일치했다.
- 결과가 높아도 동일 날짜·동일 인쇄물 중심 holdout이므로 모든 모델은
  `ADVISORY_ONLY`, `validated=false`다. 전체 검사는 계약에 따라 UNKNOWN을
  유지하며 독립 촬영 검증 전 단독 PASS/FAIL 권한은 없다. 로봇·컨베이어 실제
  명령은 보내지 않았다.

## 2026-09-02 — 전 부품 PRESENT 신규 촬영 검증

- 학습 데이터에 자동 추가하지 않은 새 S22 3.5배/플래시 OFF 사진을 촬영해
  비VRM presence 후보 20슬롯을 검사했다. GPU 1/HBM 8/PM 4/Inductor 2/SMD 5
  전부 PRESENT를 맞혔고 신뢰도 범위는 `0.99398~0.99976`이었다.
- VRM state는 02~05가 CORRECT `0.8658~0.9287`, VRM 01은 raw CORRECT지만
  `0.7159`로 confidence 기준 미달 UNKNOWN이었다. 최종 보드 UNKNOWN은
  비VRM presence 오검출이 아니라 미검증 authority와 비활성화한 YOLO/PatchCore
  등 필수 단계 때문이다.
- 원본은 4000×3000, 7.0mm/69mm-equivalent, board rectangularity 0.911이며
  overview는 촬영 후 복구됐다. 로봇·컨베이어 실제 명령은 보내지 않았다.

## 2026-09-02 — 임의 제거 블라인드 presence 검증 1

- 사용자가 제거 슬롯을 사전에 공개하지 않은 새 S22 장면에서 모델은
  `inductor_02` EMPTY 0.9999999, `power_module_01` EMPTY 0.9999996,
  `smd_capacitor_03` EMPTY 0.9999999, `vrm_02` EMPTY 0.9571을 보고했다.
- 사용자가 사후 공개한 실제 제거 부품 4개와 완전히 일치했고 GPU/HBM 등 나머지
  비VRM 슬롯은 PRESENT였다. VRM 01/05는 PRESENT 계열이지만 state confidence가
  낮아 계약대로 UNKNOWN을 유지했다.
- 이 장면은 학습 데이터에 추가하지 않은 blind holdout이며 단일 장면 결과만으로
  authority를 승격하지 않는다. 로봇·컨베이어 실제 명령은 보내지 않았다.

## 2026-09-02 — 임의 제거 블라인드 presence 검증 2

- 두 번째 정답 비공개 새 장면에서 `ai_gpu`, `hbm_04`, `hbm_06`,
  `inductor_01`, `power_module_03`, `smd_capacitor_01`, `vrm_01`, `vrm_05`를
  EMPTY로 검출했고 사용자 사후 정답과 8/8 일치했다.
- 비VRM confidence는 0.99979 이상, VRM EMPTY는 0.9544 이상이었다. VRM 03은
  ROTATED raw prediction 0.7792로 threshold 미달 UNKNOWN, VRM 04는 CORRECT
  raw prediction 0.7976로 UNKNOWN이었다.
- 이 장면도 학습 데이터에 추가하지 않았고 모델 권한은 ADVISORY_ONLY를
  유지한다. 로봇·컨베이어 실제 명령은 보내지 않았다.

## 2026-09-02 — 방향·미세 pose 블라인드 검증

- 실제 조작 정답은 GPU 180°, HBM 04 180°/06·08 미세 틀어짐, PM 03 미세
  틀어짐, VRM 01 미세 틀어짐/05 90°, Inductor 01 90°/02 180°, SMD 01 옆
  이동이었다. 정답 공개 전 OpenCV 방향 단계는 HBM 04와 Inductor 01·02를
  FAIL로 잡았으나 GPU는 UNKNOWN, VRM 05는 EMPTY 오분류였다.
- 같은 사진에서 S22 YOLO auxiliary pose를 켜자 HBM 06 angle error 6.04°,
  HBM 08 3.09°, PM 03 4.48°/0.93mm, SMD 01 1.57mm를 모두 OUTSIDE_LIMIT로
  검출했다. Inductor 01·02도 axis error 90°로 검출했다.
- GPU와 HBM 04도 pose FAIL이었지만 segmentation mask에 맞춘 회전 사각형의
  장축은 180° 대칭 방향을 구분하지 못하므로 해당 FAIL은 작은 중심 오차에
  의한 보조 증거일 뿐 180°
  방향의 독립 근거로 사용하지 않는다. VRM은 YOLO 후보가 없어 미세 pose를
  설명하지 못했다.
- 결론적으로 미세 위치·장축 각도는 YOLO segmentation mask 기반 pose가 유효하고, GPU/HBM 180°는
  흰점/학습형 방향 state, VRM 회전은 추가 state 데이터가 필요하다. 모든
  결과는 ADVISORY_ONLY이며 로봇·컨베이어 명령은 없었다.

## 2026-09-02 — 방향 오류 장면 PatchCore 실측

- 동일 방향 오류 장면에서 기존 부품별 PatchCore 6개를 CUDA로 실행했다.
  GPU 180° score 0.9866, HBM 04 180° 0.9963, VRM 05 90° 1.0,
  Inductor 01/02 회전은 각각 1.0으로 강한 anomaly가 나타나 방향 이상 검출
  가능성은 확인됐다.
- 그러나 정상 Power Module 01도 1.0으로 오검출했고, HBM 08 미세 회전 0.8180은
  정상 HBM 07의 0.8465보다 낮았다. SMD 01 이동은 0.226으로 다른 정상 SMD
  0~0.092보다 높았지만 controlled-defect threshold가 없어 확정 판정은 못 한다.
- 따라서 PatchCore는 GPU/HBM/VRM 180°·90° 방향 이상에 유효한 독립 증거지만,
  현재 공유 component 모델과 미검증 score를 단독 FAIL로 사용하지 않는다.
  고정 슬롯별 strict-normal 데이터와 controlled-defect validation으로 threshold를
  정한 뒤 authority를 평가한다. 로봇·컨베이어 실제 명령은 없었다.
## 2026-09-03 S22 strict-normal 촬영 세트 확정

- 사용자가 정상 조립 상태로 촬영 완료한 S22 3.5배, 플래시 OFF 후보 14장을 확인했다.
- 구성은 2026-09-02 저녁 2장과 2026-09-03 오전 12장이며, 마지막 `s22_inspection_roi_20260903_102613.png`도 포함한다.
- 접촉 시트 육안 검수에서 명백한 부품 누락이나 역방향은 보이지 않았다. 다만 현재 슬롯 pose 기준에는 계통적인 중심 오프셋이 남아 있으므로 자동 pose 결과를 정상 승인 근거로 사용하지 않았다.
- 해당 촬영분은 fixed-slot strict-normal PatchCore 재학습용 원본 후보로 보존하며, 미검증 모델에는 여전히 단독 PASS/FAIL 권한을 부여하지 않는다.
- 로봇 및 컨베이어 실제 구동 명령은 실행하지 않았다.

## 2026-09-03 fixed-slot strict-normal PatchCore v4 후보 학습

- 확정한 정상 기판 14장을 11장 train/3장 시간대 holdout으로 분리하고, 모든 슬롯을 고정 좌표 RGB crop으로 추출했다. 위치·방향 오류를 지우는 정합이나 CLAHE는 적용하지 않았다.
- `s22_inspection_roi_20260902_211811.png`에서 사용자가 공개한 실제 조작 슬롯 10개만 `test/controlled_defect`로 등록했다. 정상 Power Module 등 조작하지 않은 슬롯을 불량 정답으로 넣지 않았다.
- 데이터셋은 `pcb_components_strict_v4`, 후보 모델은 `runtime/inspection/patchcore/pcb_components_strict_v4`에 생성했다. HBM AUROC 1.0, PM 1.0, SMD 약 1.0이었으나 제어 불량이 각각 3/1/1개뿐이다. GPU 0.5, Inductor 0.60, VRM 0.875로 추가 데이터가 필요하다.
- 방향 오류 장면 전체 추론에서 주요 조작 위치에 anomaly 반응을 확인했지만, 부품군별 상대 heatmap은 정상 부품도 밝게 보이게 만들며 GPU score scale도 불안정하다. 따라서 런타임 기본 모델과 판정 threshold는 교체하지 않았고 v4는 `ADVISORY_ONLY`로 유지했다.
- 로봇 및 컨베이어 실제 명령은 실행하지 않았다.

## 2026-09-03 PatchCore v4 고정 절대 히트맵

- 정상 holdout 3개 기판에서 부품군별 anomaly score 분포와 pixel p99.9를 계산해 `normal_calibration.json`으로 저장했다.
- 독립 실행 시각화의 프레임별/부품군별 min-max 정규화를 제거하고, 해당 부품군 정상 pixel p99.9를 넘는 초과 반응만 동일한 절대 스케일로 표시하도록 변경했다. 따라서 정상 슬롯에도 항상 색이 생기던 문제와 촬영마다 색 기준이 바뀌던 문제를 줄였다.
- 방향 오류 장면 재검증에서 GPU 180°는 중앙 표면 전체, HBM04/06/08·VRM05·Inductor는 해당 슬롯에 반응했고 정상 HBM·VRM·SMD 대부분은 억제됐다. Power Module 경계와 Inductor 배경 잔여 반응은 추가 정상/제어 불량 데이터가 필요하다.
- 고정 시각화 테스트 7개가 통과했다. 판정 임계값과 런타임 기본 모델은 변경하지 않았으며 결과는 계속 `ADVISORY_ONLY`다.
- 로봇 및 컨베이어 실제 명령은 실행하지 않았다.

## 2026-09-03 Inductor 제어 불량 확장 및 재학습

- 정상 방향에서 두 Inductor를 소켓 허용 범위 안에서 함께 움직인 정상 후보 5장을 확보했다.
- 각 슬롯별 90°/180°/270° 회전 5장씩과 위치 허용범위 초과 19장씩을 확보했다. Inductor 02 위치 오류 촬영 초반 4장의 잘못된 `inductor_01` 태그는 원본을 유지한 채 해당 매니페스트를 `inductor_02_outside_tolerance`로 수정하고 index에 correction event를 남겼다.
- strict v4 Inductor 데이터는 train normal 30, normal holdout 8, controlled defect 70 crop으로 재구성했다. Inductor PatchCore만 GPU 재학습한 탐색 평가에서 image AUROC/F1이 1.0/1.0이었다.
- 마지막 Inductor 02 위치 오류 holdout에서 정상 Inductor 01 반응은 억제되고, 이동한 Inductor 02의 부품 외곽과 새로 드러난 슬롯 경계에 고정 초과 heat가 국소화됐다.
- 단일 촬영 세션 중심 데이터이므로 모델은 계속 `ADVISORY_ONLY`이며, 독립 재배치 holdout 검증 전에는 자동 FAIL 권한을 주지 않는다. 로봇·컨베이어 명령은 실행하지 않았다.

## 2026-09-03 Inductor 독립 블라인드 검증

- 첫 정상 장면에서 Inductor 01/02 score는 각각 0.1999/0.1447로 정상 holdout p99 0.3091 이하였다.
- 두 번째 장면은 실제 조작 내용을 공개하지 않은 채 먼저 판독했으며, Inductor 01은 정상(score 0.1851), Inductor 02만 이상(score 0.7128)으로 예측했다.
- 사용자 사후 정답은 Inductor 02가 중심에는 맞지만 반시계 방향으로 미세 회전된 상태였으며 모델의 이상 슬롯 판독과 일치했다. 고정 초과 heat도 Inductor 02에만 국소화됐다.
- 독립 블라인드 1건 성공은 유효한 근거지만 오류 형태·조명별 반복 수가 아직 부족하므로 `ADVISORY_ONLY`를 유지한다. PatchCore 단독으로 위치 오류와 방향 오류의 종류를 확정하지 않는다.
- 로봇 및 컨베이어 실제 명령은 실행하지 않았다.

- 추가 블라인드 장면에서 모델은 두 슬롯 모두 이상으로 선판독했다. Inductor 01 score 0.5961, Inductor 02 score 0.9662였고 정상 p99 0.3091을 모두 초과했다.
- 사용자 사후 정답은 Inductor 01이 방향은 거의 정상이지만 기준 위치보다 우측 상단으로 미세 이동, Inductor 02는 제자리 180° 회전이었다. 모델은 두 종류의 오류를 동시에 놓치지 않았고 180° 회전에 더 높은 score를 부여했다.
- 두 번의 독립 오류 블라인드에서 슬롯 식별은 모두 일치했지만, 현재 score만으로 오류 종류를 명명하지 않고 geometry/marker 단계와 융합한다.

- 오류 배치 후 두 Inductor를 정상으로 복구한 독립 장면에서 score가 0.1506/0.1316으로 다시 정상 p99 0.3091 아래로 내려왔고 고정 초과 heat도 억제됐다.
- 현재 세션의 정상→단일 미세 회전→복합 위치/180° 오류→정상 복귀 순서에서 모두 실제 상태와 일치했다. 따라서 Inductor PatchCore v4는 융합 검사의 보조 anomaly evidence로 사용할 수 있으나 단독 자동 판정 권한은 부여하지 않는다.

## 2026-09-03 Inductor PatchCore v4 통합 검사 연결

- fixed-slot 하이브리드 검사에서 Inductor만 `runtime/inspection/patchcore/pcb_components_strict_v4`를 사용하도록 부품별 모델 root override를 추가했다. 다른 부품의 기본 PatchCore 모델은 변경하지 않았다.
- 정상 복귀 실측 이미지로 통합 실행한 결과 Inductor 01/02 score는 0.1504/0.1312였고, 정상 holdout p99 0.3091 이하였다. 정합 score는 0.9847였다.
- 리포트에 기본 모델 root와 부품별 override root를 명시하도록 했다. 현재 controlled-defect 판정 threshold는 미확정이므로 surface 결과는 `UNKNOWN/ADVISORY_ONLY`를 유지한다.
- 기존 보조 pose가 원형 Inductor 축을 90°로 오판하는 현상을 확인했다. 이 pose 결과 또한 `ADVISORY_ONLY`이며 단독 FAIL을 발생시키지 않는다.
- 관련 회귀 테스트 12개가 모두 통과했다. 로봇·컨베이어 실제 명령은 없었다.

## 2026-09-03 GPU strict v4 데이터 확장 및 후보 재학습

- 정상 방향을 유지하면서 소켓 허용 범위 안의 중앙·상하좌우·네 모서리 변화를 포함한 GPU 정상 후보 18장을 검수했다.
- 실제 지그에서 가능한 180° 역방향, 시계/반시계 미세 회전, 상하좌우 허용범위 이탈로 제어 불량 52장을 검수했다. 지그 구조상 불가능한 90° 회전은 데이터 계획에서 제외했다.
- strict v4 GPU crop은 train normal 25, normal holdout 7, controlled defect 53으로 재구성했다. GPU PatchCore만 재학습한 탐색 평가에서 image AUROC/F1은 1.0/1.0이었다.
- GPU도 Inductor와 동일한 strict v4 모델 root를 사용하도록 통합 검사에 연결했다. 단일 촬영 세션의 탐색 평가이므로 독립 블라인드 검증 전까지 `ADVISORY_ONLY`를 유지한다.
- 로봇·컨베이어 실제 명령은 없었다.

## 2026-09-03 저장 비전 모델 전체 일괄 재검증

- S22 플래시 OFF 현재 장면과 독립 정상 1장, 실제 GPU 긁힘 2장을 기준으로 저장 학습 산출물 50개를 재실행했다. 범위는 YOLO best 7개, PatchCore checkpoint 30개, TorchScript 존재/VRM 상태 모델 13개이며 결과는 `runtime/inspection/model_audit_20260903/README.md`에 정리했다.
- 현재 장면 정합 score는 0.9866이었다. S22 segmentation fixed-slot 결과는 실제 누락된 `vrm_03`만 제외한 GPU 1, HBM 8, Power Module 4, VRM 4, Inductor 2, SMD 5로 실제 존재 수와 일치했다. VRM v2도 `vrm_03=EMPTY`를 confidence 0.9838로 식별했다.
- 트레이/Unity OBB 6개는 조립 기판에서 모두 0검출이었다. 해당 모델을 조립 검사에 재사용하지 않고 트레이/합성 도메인으로 제한한다.
- 전체 기판 PatchCore 5개와 GPU PatchCore 6세대를 정상/긁힘에 교차 적용했다. 구형 모델은 포화했고 최신 모델도 정상과 긁힘 score가 역전 또는 중첩됐다. GPU 크랙 전용 v1도 네 입력 모두 1.0이었고 기존 AUROC 0.5 실패를 재확인했다. 어떤 모델도 크랙 위치에만 안정적으로 열을 국소화하지 못했다.
- 기존 OpenCV 전체/핀 검사는 실제 GPU 핀 이상과 함께 정상 HBM·Power Module을 오검출했다. 하이브리드 결과는 `vrm_03 MISSING?`, `ai_gpu SURFACE?`를 포함했지만 총 13개 advisory candidate가 발생해 최종 `UNKNOWN`이었다.
- 모델 authority와 threshold는 변경하지 않았고 모든 미검증 모델은 계속 `ADVISORY_ONLY`다. 로봇·컨베이어 실제 명령은 실행하지 않았다.

- S22 원본은 4000×3000이지만 기판 실제 투영 영역은 약 1240×980픽셀이며, 1600×1266 정합 ROI는 원본 기판을 약 1.29배 보간 확대한다. 원본 재크롭만으로 추가 크랙 세부정보를 얻을 수 없음을 확인했다.
- GPU 내부 표면에 CLAHE·unsharp·black-hat·edge 진단을 적용했으나, 미세 크랙 후보보다 3D 프린트 대각선 적층결이 전 영역에서 더 강하게 나타났다. 정상/불량 GPU가 서로 다른 출력 개체라 개체별 표면결 차이도 크랙 신호보다 크다.
- 따라서 현재 고정 카메라와 정면 실내조명만으로 위치 미지의 검정 표면 미세 크랙을 신뢰성 있게 자동 판정할 수 있다고 주장하지 않는다. 사광 또는 다중 조명 획득 전까지 크랙 단계는 `UNKNOWN/ADVISORY_ONLY`로 유지한다.

## 2026-09-03 GPU 검정 표면 크랙 전용 PatchCore v1 탐색

- 기존 정상 GPU 18장 중 14장만 학습에 사용하고, 나머지 4장과 독립 정상 5장을 normal holdout으로 분리했다. 최근 실제 불량 GPU 2장은 학습에서 완전히 제외하고 `test/crack` 블라인드 평가에만 사용했다.
- 핀·소켓 영향을 줄이기 위해 GPU 패키지 내부 ROI를 별도로 생성하고, 미세 특징 보존을 위해 PatchCore `layer1/layer2` 후보를 학습했다.
- 탐색 결과 image AUROC 0.5, F1 0.364로 정상과 크랙을 분리하지 못했다. 히트맵은 실제 미세 크랙보다 핀 경계와 3D 프린트 표면 결에 넓게 반응했다.
- 따라서 이 모델은 통합 검사에 연결하지 않았고 자동 판정 또는 크랙 검출 성공으로 기록하지 않는다. 현재 S22 촬영에서 검정 표면 크랙의 대비·픽셀 폭이 충분하지 않거나 ROI 마스킹이 아직 부정확한 것이 남은 제한사항이다.
- 로봇·컨베이어 실제 명령은 없었다.

- GPU 독립 정상 복귀 블라인드 검증에서 기하 오차는 위치 0.612 mm, 각도 0.37°로 정상 범위였지만 PatchCore score는 0.644로 normal holdout p99 0.468을 초과했다. 따라서 학습 내부 AUROC/F1 1.0은 독립 일반화 성능을 보장하지 않으며 GPU v4는 정상 오검출을 줄이지 못했다.
- 동일한 독립 정상 배치를 유지하고 5장을 추가 촬영한 결과 score는 0.597~0.652로 모두 normal p99 0.468을 초과했다. 제어 불량 53장의 score 범위도 0.500~1.000이어서 정상과 불량이 중첩된다.
- 따라서 GPU에서 PatchCore score threshold만으로 위치·방향 양부판정을 하지 않는다. 위치·각도는 fixed-slot geometry, 방향은 흰점 기준을 우선하고 PatchCore는 표면·핀 이상 보조 근거로만 유지한다.

## 2026-09-03 GPU/HBM 흰점 방향 검사 보정

- 기존 모서리 점수가 GPU 흰점보다 핀열·로고에 더 크게 반응하던 원인을 확인했다. 모서리 영역 내의 면적·원형도 조건을 만족하는 단일 연결 요소를 우선하도록 바꾸었다.
- GPU 정상 후보 18장과 독립 정상 holdout 5장은 모두 `lower_left/PASS`, 180° 역방향 7장은 모두 `upper_right/FAIL`로 분리됐다.
- 위치 이탈·미세 회전 샘플은 흰점이 정상 모서리에 있으면 방향 PASS로 남는다. 이는 의도된 역할 분리이며 위치·각도는 geometry provider가 판정한다.
- 이전 실물 HBM 장면에서도 정상 7개는 PASS, 180° 역방향 HBM 03만 `upper_right/FAIL`로 분리됐다. 회귀 테스트 12개가 통과했고 로봇·컨베이어 명령은 없었다.

## 2026-09-03 SMD 미검증 표면 히트맵 숨김

- 현재 SMD PatchCore의 normal pixel p99.9가 0.011로 너무 낮아 압축 노이즈와 반사가 미세 크랙처럼 표시되는 문제를 확인했다.
- SMD surface score와 raw evidence는 JSON에 보존하되, 정상/불량 임계값을 다시 검증하기 전까지 운영자 히트맵과 `SURFACE?` 후보에서는 제외했다. SMD 누락·위치 단계는 계속 실행된다.
- GPU 검정 패키지 미세 크랙은 현재 일반 PatchCore와 분리한 고해상도 내부 표면 ROI 전용 모델로 구성하기로 했다. 실제 크랙 샘플 검증 전이므로 아직 판정 권한은 없다.
- 로봇·컨베이어 실제 명령은 없었다.

## 2026-09-03 그리퍼 D435 마커리스 SMD 깊이 기반 파지 보강

- ChArUco 없이 RGB 크기·색·윤곽으로 SMD 중심/장축을 찾고, `/camera/camera/aligned_depth_to_color/image_raw`의 중심 7×7 패치 중앙값으로 Camera/Base 3D 좌표를 계산하는 흐름을 유지했다.
- 각 프레임의 depth 유효 비율과 국소 MAD, 30프레임 기준 depth 최대 흔들림 및 Base 3D 최대 흔들림을 품질 근거로 추가했다. 기본 허용값은 유효 비율 0.55 이상, 국소 MAD 2.0 mm 이하, 프레임 depth 흔들림 2.0 mm 이하, Base 흔들림 0.5 mm 이하이다. 하나라도 벗어나면 새 target JSON을 기록하지 않고 검출 프로세스가 실패 코드로 끝나 이전 좌표 재사용을 막는다.
- 접근과 하강은 `depth_quality.accepted=true`인 최신 target만 허용한다. 최종 하강은 고정 100+5 mm 누적 이동 대신 현재 TCP Z와 검출 Base Z의 차이를 다시 계산해 한 번에 이동하며, 기본 최종 TCP Z는 검출 표면보다 5 mm 아래이고 계산 하강량·XY 오차·target age를 제한한다.
- Python `py_compile` 5개와 관련 shell `bash -n` 4개는 통과했다. 실제 ROS graph에서는 `/camera/camera/depth/image_rect_raw/compressedDepth`만 확인됐고 필요한 color, CameraInfo, aligned raw depth, `/nonrt_state_data`는 확인되지 않아 실영상 검출과 로봇 dry-run은 수행할 수 없었다.
- 로봇·그리퍼·컨베이어 실제 명령은 실행하지 않았다. 5 mm 파지 오프셋은 기존 동작값을 유지한 값이며, 실제 TCP/핑거 형상과 작업면 기준으로 저속 단발 검증 후 확정해야 한다. D435 깊이만으로 완전한 파지를 보장할 수 없고 파지 성공 센서 피드백은 아직 없다.

## 2026-09-03 SMD 5 cm 상부 정렬 접근 모드

- `run_smd_approach_5cm.sh`를 추가했다. 마커리스 RGB-D 검출 후 부품 장축에 선택한 그리퍼 tool 축을 정렬하고, 검출된 부품 Base Z보다 정확히 50 mm 높은 TCP 위치에서 정지한다.
- 전용 실행의 기본 속도는 수평 20%, 수직 15%, 회전 20%로 낮췄다. 이 모드에서는 그리퍼 열기/닫기, 파지 높이 하강, 리프트, 제자리 놓기, teaching point 복귀 명령을 전혀 보내지 않는다.
- 실제 이동에는 `--execute --confirm-approach-only`가 모두 필요하며 full-cycle 확인 옵션과 함께 사용할 수 없다. Python 구문과 shell 구문 검증만 수행했고 로봇·그리퍼·컨베이어 실제 명령은 실행하지 않았다.
- 채팅에서 여러 줄 명령을 복사할 때 옵션 앞 들여쓰기가 인자 문자열에 포함되어 argparse가 거부한 현상을 확인했다. 전용 wrapper에서 전달 인자의 바깥쪽 공백만 제거하도록 보완했으며, 한 줄 실행도 지원한다. 카메라 수신 전에 발생한 CLI 파싱 오류였고 로봇 명령은 없었다.
- 부품별 PatchCore override를 쓸 때 score 기준은 override calibration을 사용하면서 pixel heatmap 기준만 기본 모델 calibration을 참조하던 오류를 수정했다. GPU 후보는 계속 `ADVISORY_ONLY`이며 현재 자동 PASS/FAIL 권한을 부여할 수 없다.

## 2026-09-04 정상 보드 5회 반복검증 및 Power Module 후보 표시 보정

- 처음 촬영한 5장에는 사용자가 실수로 `hbm_04`를 180도 역방향으로 둔 상태가 포함되어 정상 기준에서 제외했다. 해당 장면의 방향 검사는 흰점을 좌측 하단이 아닌 우측 상단에서 찾아 `hbm_04 DIR?`를 정확히 표시했다.
- `hbm_04`를 정상 방향으로 복구한 뒤 S22 3.5배 망원·플래시 OFF·동일 고정 위치에서 신규 정상 사진 5장(`20260904_101656`, `101724`, `101821`, `101851`, `101935`)을 촬영했다. 원본은 모두 4000x3000, EXIF 환산 초점거리는 69 mm였고, ROI 직사각형도는 0.908~0.909, 하이브리드 정합 score는 0.9847~0.9869였다.
- 수정 전 5회 모두 실제 정상인 `power_module_02`만 `POSE?` 후보로 반복됐다. 검출 각도 오차는 0.12~0.13도였고, CAD+측정 허용치 0.75 mm 대비 위치 초과량은 0.36~0.47 mm였다. 이전 사용자가 위치 이상으로 확인한 `power_module_01` 제어 장면의 초과량은 0.58 mm였다.
- CAD 기반 0.75 mm pose 검사와 JSON 원시 evidence는 변경하지 않았다. 운영자 화면의 미검증 Power Module `POSE?` 후보 게이트만 초과량 0.30 mm에서 0.50 mm로 조정해 반복 정상 오표시를 숨기되, 기존 제어 위치 이상은 계속 표시하도록 했다. 이는 `ADVISORY_ONLY` 표시 조정이며 PASS/FAIL 권한이나 fail-safe 융합 계약 변경이 아니다.
- 마지막 정상 사진 전체 재실행 결과 정합 score 0.9869, advisory candidate 0개였다. 모든 필수 제공자가 아직 검증·승격되지 않았으므로 최종 상태는 의도대로 `UNKNOWN`이다.
- 이후 사용자가 PM02만 소켓 중심에서 왼쪽으로 이동한 독립 제어 불량을 만들었다. 첫 측정은 위치 오차 1.464 mm, 허용치 초과 0.714 mm였지만, 이동으로 YOLO 외곽 confidence가 0.138까지 낮아져 기존 표시 필터가 후보를 숨기는 문제가 드러났다.
- 큰 이탈 보조 경로를 추가했다. Power Module 존재 분류기가 `PRESENT` confidence 0.90 이상으로 교차 확인하고, YOLO 외곽 confidence 0.10 이상이며 허용치 초과가 0.60 mm 이상이면 낮은 외곽 confidence만으로 `POSE?`를 숨기지 않는다. 이 경로도 `ADVISORY_ONLY`이며 자동 FAIL 권한은 없다.
- 동일 PM02 불량을 3회 독립 촬영/정합해 모두 PM02 단독 `POSE?`로 재현했다. 위치 오차는 1.464~1.570 mm, 존재 confidence는 0.9957~0.9969였고 첫 전체 실행의 PatchCore score는 0.774였다. 정상 5회는 후보 0개를 유지했다.
- PM02를 완전히 제거한 별도 누락 장면도 3회(`20260904_104219`, `104424`, `104500`) 반복했다. 세 번 모두 다른 슬롯 오표시 없이 PM02만 `MISSING?`였고, 존재 분류기는 `EMPTY` confidence 0.9999996~0.9999998, YOLO 외곽은 미검출로 일치했다. 첫 전체 실행의 PatchCore score는 1.000이며 빈 PM02 슬롯 전체에 고정 초과 Heatmap이 표시됐다.
- 회귀 테스트 27개와 Python 구문 검사를 통과했다. 촬영 중 로봇·컨베이어 실제 명령은 보내지 않았다. 현재 정상/이 위치 불량은 분리되지만 다른 방향·거리와 별도 날짜/조명 조건 검증 전까지 자동 판정 권한은 부여하지 않는다.

## 2026-09-04 마커리스 SMD 파지 안전 재검토 및 폐루프 보강

- 재검토에서 단발 절대좌표 이동, 전체 화면의 동형 부품 혼동, 7×7 depth가 지지면을 읽어도 통과하는 문제, 180° 대칭축 평균 오류, 10 mm 파지 XY 허용값, 이동 후 도착 확인 부재를 확인했다.
- 최초 검출은 화면 중심에 가장 가까운 후보만 선택하고 가까운 후보가 둘이면 중단한다. 프레임 간 중심 이동은 12 px로 제한한다. 50 mm 상공 이동 후 이전 Base 목표를 현재 영상으로 투영해 같은 부품을 추적하고, `15 mm/20°`, 이어 `5 mm/8°` 범위의 근거리 보정을 두 번 수행한 후 세 번째 RGB-D 검출로 위치 1.0 mm·각도 1.0° 이내를 확인한다.
- 깊이는 부품 내부 median과 주변 annulus의 강건 평면을 분리한다. 내부 유효 비율, 내부 MAD, 주변 평면 MAD, 프레임 Z 흔들림뿐 아니라 Base Z로 환산한 관측 높이가 입력 부품 높이와 기본 ±2.0 mm 안에서 일치해야 target을 원자적으로 갱신한다. 합성 3 mm 단차는 3.0 mm로 복원했고 평평한 배경은 부품 높이 불일치로 거부했다.
- 직사각형 장축 평균을 double-angle 방식으로 수정하고 최대 각도 흔들림 5°를 추가했다. `-89°/+89°` 합성 입력은 잘못된 0°가 아니라 동등한 -90° 축으로 계산됐다.
- target에 활성 Hand-eye SHA-256과 경고를 기록하고 이후 모든 이동 단계에서 fingerprint를 다시 확인한다. 활성 파일은 여전히 로봇 이동 전 검증 경고가 있으므로 전체 파지는 기본 차단한다. 전체 파지를 명시적으로 허용하더라도 실측한 `--grasp-z-offset-mm` 없이는 시작할 수 없다. 5 cm 비접촉 접근만 별도 확인 옵션으로 허용한다.
- 접근은 로봇/충돌 상태를 확인하고 모든 waypoint 도착 위치·자세를 검증한다. 파지 직전 XY/Z/축 허용값은 각각 1.0 mm/1.0 mm/1.5°로 강화했다. 그리퍼 열기와 닫기는 상태값 1/2 및 fault/error를 확인하는 전용 노드로 변경했다.
- `calibration/tests/test_smd_pick_safety.py` 6개가 통과했고 전체 calibration Python compile 및 관련 shell 구문 검사가 통과했다. 실제 D435 영상의 마커리스 검출 성공률과 실제 TCP 파지 Z는 측정하지 않았으며, 로봇·그리퍼·컨베이어 실제 명령은 보내지 않았다. 그리퍼에는 물체 보유 센서가 없어 파지 성공 자체는 아직 자동 확정할 수 없다.

## 2026-09-04 D435 그리퍼 카메라 6종 부품 프로파일 구현

- 기존 SMD 폐루프 흐름을 `gpu`, `hbm`, `vrm`, `power_module`, `inductor`, `smd_capacitor` 6종 프로파일 실행기로 확장했다. `run_pick_part_with_gripper_camera.sh`가 부품별 크기·형상·분할·자세 정책을 불러오고, `run_part_approach_5cm.sh`가 동일한 수평 20%·수직 15%·회전 20% 비접촉 접근을 제공한다. ChArUco와 팀원 YOLO 모델은 필수 의존성이 아니다.
- 규격 근거는 `vision_assembly/config/part_specs_candidate.json`이다. GPU 57×27×6 mm는 사용자 실측값이며 HBM 14.310×10.247×9.815 mm, VRM 14×11×5.203 mm, Power Module 59.989×12.130×4.785 mm, Inductor 9.369×9.369×8.522 mm, SMD 6.801×3.836×3.024 mm는 CAD 후보로 명시했다.
- GPU/HBM/VRM은 어두운 외형, Power Module은 주황 HSV, SMD는 밝은 외형을 후보로 사용하고 모두 윤곽 내부와 주변 지지면 RGB-D 높이를 교차 검증한다. 밝은 지지면과 외형 구분이 어려운 Inductor에는 강건한 영상 좌표계 지지 평면에서 돌출 높이를 찾는 depth-first 분할을 추가했다.
- 원형 Inductor는 `minAreaRect` 각도를 파지 자세로 사용하지 않는다. target에 `orientation_mode=preserve`, 각도 `null`을 기록하고 접근·하강·파지 단계가 현재 TCP 자세를 유지하며 장축 검사만 생략한다. 직사각형 5종은 기존 180° 대칭 장축 정렬과 흔들림 검사를 유지한다.
- target에는 프로파일 ID, 입력 크기, 형상, 분할 방식, 자세 정책을 저장한다. 후속 단계의 요청값과 하나라도 다르면 이전 target 재사용을 차단한다. 모든 새 프로파일은 `detection_validated=false`, `full_pick_validated=false`이며, 첫 5 cm 검증 이동도 명시적 미검증 프로파일 해제를 요구한다. 접촉 동작은 추가로 부품별 실측 `--gripper-close-position`, `--grasp-z-offset-mm`와 기존 Hand-Eye 안전 게이트까지 통과해야 명령 경로가 열린다.
- 경사 depth 평면 위 8 mm 합성 돌출 검출, 평평한 경사면 오검출 거부, 검정/주황 외형 분리, 6종 규격 원본 일치, 별칭, Inductor 무축 자세, 상·하위 실행기의 미검증 접근·접촉 차단, 명시적 전체 파지 명령 생성 및 기존 SMD 안전 회귀를 포함해 17개 테스트가 통과했다. Python compile, shell 구문, JSON 구문도 통과했다.
- 이번 작업은 구현·정적/합성 검증만 수행했다. 실제 D435 영상 검출, 5 cm 이동, 그리퍼 접촉, 로봇 및 컨베이어 명령은 실행하지 않았다. CAD 후보 치수, 부품별 핑거 폭/힘, 파지 Z, 칸막이 충돌 여유, 현재 Hand-Eye 경고와 물체 보유 센서 부재가 남은 제한사항이다.

## 2026-09-04 기본 트레이 RGB-D 비-SMD 50 mm 상공 접근

- 기본 트레이 대기 화면용 `run_tray_part_hover_5cm.sh`를 추가했다. 현재 실행 중인 팀 `tray_part_detector`의 `/vision/tray/unity_state`와 `/vision/tray/registration`을 사용하므로 ChArUco와 추가 D435 실행이 필요 없다. GPU, HBM, VRM, Power Module, Inductor만 지원하며 SMD는 기존 전용 경로로 분리했다.
- 실행 직전에 `TRACKING`, `at_trayhome=true`, `VALID_COORDINATES_ONLY`, `base_link/mm`, 최소 10 관측 프레임을 확인한다. 최신 5개 RGB-D/Base 표면 좌표의 최대 흔들림 2.0 mm와 직사각형 장축 흔들림 3.0°를 통과해야 원자적으로 목표를 저장한다. 네트워크에서 등록 상태가 최대 2.645초 늦게 도착한 실측을 근거로 live 상태 만료는 3.5초, 고정 목표 만료는 15초로 설정했다.
- 현재 화면의 실시간 검출 수는 VRM 5, Power Module 4, Inductor 2, GPU 1, HBM 8이다. 현재 보이는 비-SMD 표면 Base 범위는 X `-748.308~-506.620`, Y `-227.068~-24.103`, Z `-47.836~-40.702 mm`였다. 20개 기준점의 영상→Base 평면 적합 최대 잔차는 1.893 mm였고, 빈 슬롯까지 포함한 전체 비-SMD ROI 투영 범위 X `-786.945~-457.330`, Y `-258.050~121.221 mm`에 여유를 둔 작업공간 밖 좌표는 이동 전에 거부한다.
- 각 종류 1번을 5프레임씩 다시 측정했다. GPU 표면 `[-517.075,-188.968,-41.705] mm`, 흔들림 0.498 mm, 50 mm 상공 Z 8.295 mm; VRM `[-748.318,-221.332,-47.236]`, 0.008 mm, Z 2.764 mm; Power Module `[-731.061,-68.837,-45.358]`, 0.016 mm, Z 4.642 mm; Inductor `[-622.520,-227.111,-45.211]`, 0.019 mm, Z 4.789 mm; HBM `[-593.687,-49.682,-47.798]`, 0.010 mm, Z 2.202 mm였다. 직사각형 장축의 수집 창 내 최대 흔들림은 모두 0.000°로 출력됐다.
- 이동 경로는 필요 시 안전 Z 수직 상승, 안전 Z 장축 정렬, 수평 이동, 표면 Base Z+50 mm 수직 접근뿐이다. 0.05°를 넘는 정렬은 수평 이동 전에 분리하고 각 waypoint 도착을 XYZ 1.5 mm와 회전행렬 자세 1.0°로 함께 확인한다. 기본 속도는 수평 20%, 수직 15%, 회전 20%이며 30% 초과와 50 mm 외 접근값을 차단한다. GPU/HBM/VRM/Power Module은 Tool Y를 장축에 맞추고 원형/정사각형 Inductor는 현재 TCP 자세를 유지한다. 실제 이동에는 `--execute --confirm-hover-only`가 모두 필요하다.
- 신규 10개 테스트와 기존 calibration 17개, 총 27개가 통과했고 Python·shell·JSON 구문 검사도 통과했다. 라이브 검증은 모두 `--dry-run`으로 수행했으며 로봇 서비스 호출, `MoveCart`, `MoveGripper`, 그리퍼, 컨베이어 실제 명령은 전송하지 않았다. 만료된 4개 목표가 15초 게이트에서 모두 거부되는 것도 확인했다.
- 기존 다품종 실제 파지 코드는 별도 `calibration` 경로에 보존했지만 새 트레이 실행기에서는 호출하지 않는다. 실제 로봇 도착 위치와 물리 50 mm 간격, Hand-Eye 절대 정확도, 핑거/칸막이 여유는 아직 실측하지 않았으므로 최초 실제 이동은 비상정지 가능한 감독 상태에서 종류별로 검증해야 한다.
- 로봇+D435 PC 전달본은 `transfer/robot_d435_tray_hover_5cm_20260904/`와 동명의 `tar.gz`로 생성했다. 현장 Hand-Eye와 팀 카메라/검출 코드는 포함하지 않아 덮어쓰지 않으며, 37개 전달 파일 manifest와 압축본 SHA-256 `515fa26b66d98bf9abcb110a6113bfa33d808a12d4b308bc75748d541c095e18` 검증을 통과했다.
