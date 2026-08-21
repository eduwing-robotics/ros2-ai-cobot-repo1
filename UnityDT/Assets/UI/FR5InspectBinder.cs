// 역할: INSPECT 페이지(FR5Inspect.uxml)의 카메라 상태와 판정 표시를 담당한다.
//
//   실연결 : 모드 · 비전 스트리밍 상태 · 프레임 경과 · 빈 상태 전환
//   미연결 : 판정 · 항목별 결과 · 불량 슬롯 · 유닛 목록 — 값을 지어내지 않고
//            FR5EmptyState 로 필요한 조회 이름을 적는다  [TODO(API)]
//
// 카메라 텍스처 자체는 CamVisionReceiver 가 `camera-image` Image 요소에 직접 넣는다.
// 이 바인더는 "지금 영상이 살아 있는가"와 판정 표시만 맡는다.

using MainUnity.Runtime.Camera;
using MainUnity.Runtime.Robot;
using UnityEngine;
using UnityEngine.UIElements;

namespace MainUnity.UI
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(UIDocument))]
    public sealed class FR5InspectBinder : MonoBehaviour
    {
        [Header("데이터 소스")]
        [SerializeField] UIMaster uiMaster;
        [SerializeField] CamVisionReceiver vision;

        [Tooltip("이 시간을 넘겨 프레임이 없으면 영상 없음으로 봅니다.")]
        [SerializeField] float staleSeconds = 2f;

        VisualElement cameraEmpty, detectBox, checkList, defectGrid, unitStrip;
        Label cameraStats, cameraEmptyDesc, verdictTitle, verdictValue, verdictScore, defectSql, unitsSummary, jobSummary;
        bool cached;

        void OnEnable() => cached = false;

        void Update()
        {
            // UIDocument 는 활성화된 뒤에야 rootVisualElement 를 만든다.
            if (!cached) { Build(); if (!cached) return; }
            ResolveReferences();
            RefreshVision();
        }

        void ResolveReferences()
        {
            if (uiMaster == null) uiMaster = GetComponentInParent<UIMaster>();
            if (vision == null && uiMaster != null) vision = uiMaster.VisionImage;
        }

        void Build()
        {
            VisualElement root = GetComponent<UIDocument>().rootVisualElement;
            if (root == null) return;

            cameraEmpty = root.Q<VisualElement>("camera-empty");
            cameraEmptyDesc = root.Q<Label>("camera-empty-desc");
            detectBox = root.Q<VisualElement>("detect-box");
            cameraStats = root.Q<Label>("camera-stats");
            checkList = root.Q<VisualElement>("check-list");
            defectGrid = root.Q<VisualElement>("defect-grid");
            unitStrip = root.Q<VisualElement>("unit-strip");
            verdictTitle = root.Q<Label>("verdict-title");
            verdictValue = root.Q<Label>("verdict-value");
            verdictScore = root.Q<Label>("verdict-score");
            defectSql = root.Q<Label>("defect-sql");
            unitsSummary = root.Q<Label>("units-summary");
            jobSummary = root.Q<Label>("job-id");

            BuildVerdict();
            BuildDefects();
            BuildUnits();
            cached = true;
        }

        /// <summary>판정은 검사 노드가 내린다. 화면이 PASS/FAIL 을 지어내면 그게 가장 위험하다.</summary>
        void BuildVerdict()
        {
            if (verdictTitle != null) verdictTitle.text = "INSPECTION RESULT";
            FR5EmptyState.Missing(verdictValue);
            FR5EmptyState.Dash(verdictScore);
            FR5EmptyState.Fill(checkList, "units.inspection_result 조회 필요 — 항목별 판정", 200f);
        }

        /// <summary>정상 슬롯은 행을 만들지 않는다는 DB 규칙을 화면도 따른다 — 불량만 색을 얻는다.</summary>
        void BuildDefects()
        {
            FR5EmptyState.Fill(defectGrid, "unit_defects 조회 필요 — 슬롯별 불량", 200f);
            FR5EmptyState.Detail(defectSql, "unit_defects(unit_id, slot_code, defect_type) 조회 경로 없음");
        }

        void BuildUnits()
        {
            FR5EmptyState.Fill(unitStrip, "units 조회 필요 — 대별 판정", 66f);
            FR5EmptyState.Dash(unitsSummary);
            FR5EmptyState.Missing(jobSummary);
        }


        void RefreshVision()
        {
            bool received = vision != null && vision.HasReceivedImage;
            double age = vision != null ? Time.realtimeSinceStartupAsDouble - vision.LastReceiveTimeSeconds : -1;
            bool fresh = received && age >= 0 && age < staleSeconds;

            cameraEmpty?.EnableInClassList("empty", true);
            if (cameraEmpty != null)
                cameraEmpty.style.display = fresh ? DisplayStyle.None : DisplayStyle.Flex;
            // 검출 박스는 좌표를 주는 계약이 없다. 영상이 있다고 해서 고정 사각형을
            // 띄우면 "무엇을 인식했다"는 거짓말이 된다. 계약이 생길 때까지 그리지 않는다.
            // TODO(API): 비전 노드의 검출 결과(bbox · score)가 생기면 여기에 싣는다.
            if (detectBox != null)
                detectBox.style.display = DisplayStyle.None;

            if (cameraEmptyDesc != null)
                cameraEmptyDesc.text = vision == null
                    ? "CamVisionReceiver 미연결"
                    : "/vision/board/image 수신 대기";

            // TODO(API): 해상도·FPS 는 수신 메시지 헤더에서 읽는다. 지금은 경과만 실측이다.
            if (cameraStats != null)
                cameraStats.text = fresh
                    ? $"수신 중 · 마지막 프레임 {age * 1000:0} ms 전"
                    : "수신 없음";
        }
    }
}
