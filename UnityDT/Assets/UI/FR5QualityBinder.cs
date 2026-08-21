// 역할: QUALITY 페이지(FR5Quality.uxml)를 채운다. 지금은 채울 값이 하나도 없다.
//
//   실연결 : 없음
//   미연결 : 슬롯별·부품별 불량률 · 레시피 전후 · 대책서 목록 — 어떤 조회가
//            필요한지만 자리마다 적는다  [TODO(API)]
//
// Unity 는 DB 에 직접 접속하지 않는다(Architecture.md). 이 페이지의 값은 ROS2 스트림으로
// 올 수 없고, Architecture 가 확장점으로 남겨 둔 HTTP 어댑터가 필요하다.
//
//   GET /parts/defect-rate?from=&to=&product=   → 슬롯·부품별 집계
//   GET /alerts?status=                          → defect_report.alerts
//
// 어댑터가 생기면 Reload() 안의 빈 상태를 응답 렌더링으로 바꾸고 source 배지를 실데이터로
// 돌린다. 화면을 먼저 만들어 두는 이유는, 무엇이 없는지가 보여야 응답 형태가 정해지기 때문이다.

using UnityEngine;
using UnityEngine.UIElements;

namespace MainUnity.UI
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(UIDocument))]
    public sealed class FR5QualityBinder : MonoBehaviour
    {
        [Header("데이터 소스")]
        [SerializeField] UIMaster uiMaster;

        bool built;

        void OnEnable() => built = false;

        void Update()
        {
            // UIDocument 는 활성화된 뒤에야 rootVisualElement 를 만든다.
            if (built) return;
            Build();
        }

        void Build()
        {
            VisualElement root = GetComponent<UIDocument>().rootVisualElement;
            if (root == null) return;
            if (uiMaster == null) uiMaster = GetComponentInParent<UIMaster>();

            Button refresh = root.Q<Button>("refresh-button");
            if (refresh != null) refresh.clicked += () => Reload(root);

            Reload(root);
            built = true;
        }

        void Reload(VisualElement root)
        {
            // TODO(API): 여기서 조회 어댑터를 호출한다. 조회 성격이라 실시간 갱신은 필요 없다.
            Label source = root.Q<Label>("source-text");
            VisualElement chip = root.Q<VisualElement>("source-chip");
            if (source != null) source.text = FR5EmptyState.Title;
            chip?.EnableInClassList("chip--bad", true);

            FR5EmptyState.Dash(root.Q<Label>("filter-count"));
            // 필터 값도 조회가 있어야 고를 수 있다. 기본값을 적어 두면 그 조건으로 집계된 줄 안다.
            FR5EmptyState.Dash(root.Q<Label>("filter-period"));
            FR5EmptyState.Dash(root.Q<Label>("filter-product"));
            FR5EmptyState.Dash(root.Q<Label>("filter-recipe"));
            FR5EmptyState.Dash(root.Q<Label>("filter-defect"));
            FR5EmptyState.Fill(root.Q<VisualElement>("slot-grid"), "GET /parts/defect-rate — 슬롯별 불량률", 190f);
            FR5EmptyState.Fill(root.Q<VisualElement>("part-list"), "GET /parts/defect-rate — 부품·불량유형별", 190f);
            FR5EmptyState.Fill(root.Q<VisualElement>("recipe-compare"), "레시피 버전별 집계 조회 필요", 160f);
            FR5EmptyState.Fill(root.Q<VisualElement>("alert-list"), "GET /alerts — 대책서 발행 목록", 160f);

            FR5EmptyState.Detail(root.Q<Label>("recipe-note"), "verification_status 조회 필요");
            FR5EmptyState.Dash(root.Q<Label>("alert-summary"));
            FR5EmptyState.Detail(root.Q<Label>("slot-threshold"), "임계 — defect_report.thresholds 조회 필요");
        }
    }
}
