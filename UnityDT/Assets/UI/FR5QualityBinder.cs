// 역할: QUALITY 페이지(FR5Quality.uxml)의 슬롯·부품 불량률을 표시한다.
//
//   실연결 : assemblies/current → jobs → products/{product_id}/quality/slot-rates
//   미연결 : 레시피 전후 · 대책서 목록
//
// Unity 는 DB 에 직접 접속하지 않고 MainServer HTTP 조회만 사용한다.
// 레시피 비교와 대책서는 대응 조회 계약이 생길 때까지 빈 상태로 남긴다.

using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UIElements;

namespace MainUnity.UI
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(UIDocument))]
    public sealed class FR5QualityBinder : MonoBehaviour
    {
        [Serializable] sealed class AssemblyResponse { public AssemblySnapshot data; }
        [Serializable] sealed class JobResponse { public Job data; }
        [Serializable] sealed class SlotRatesResponse { public SlotRate[] data; }
        [Serializable] sealed class AssemblySnapshot { public int job_id; }
        [Serializable] sealed class Job
        {
            public int product_id;
            public string product_code;
            public string product_version;
            public string recipe_version;
            public string job_status;
            public string requested_at;
            public string job_finished_at;
        }
        [Serializable] sealed class SlotRate
        {
            public string slot_code;
            public string part_id;
            public string part_name;
            public int inspected_quantity;
            public int defective_quantity;
            public float defect_rate_percent;
        }
        sealed class PartTotal { public string name; public int inspected; public int defective; }
        [Header("데이터 소스")]
        [SerializeField] UIMaster uiMaster;
        [SerializeField] string mainServerBaseUrl = "http://127.0.0.1:8000";

        bool built;
        VisualElement root;
        Button refresh;
        Coroutine loadRoutine;

        void OnEnable() => built = false;

        void OnDisable()
        {
            if (loadRoutine != null) StopCoroutine(loadRoutine);
            loadRoutine = null;
            if (refresh != null) refresh.clicked -= Reload;
            refresh = null;
            root = null;
        }
        void Update()
        {
            // UIDocument 는 활성화된 뒤에야 rootVisualElement 를 만든다.
            if (built) return;
            Build();
        }

        void Build()
        {
            root = GetComponent<UIDocument>().rootVisualElement;
            if (root == null) return;
            if (uiMaster == null) uiMaster = GetComponentInParent<UIMaster>();

            refresh = root.Q<Button>("refresh-button");
            if (refresh != null)
            {
                refresh.clicked -= Reload;
                refresh.clicked += Reload;
            }

            Reload();
            built = true;
        }

        void Reload()
        {
            if (loadRoutine != null || !isActiveAndEnabled) return;
            Label source = root.Q<Label>("source-text");
            VisualElement chip = root.Q<VisualElement>("source-chip");
            if (source != null) source.text = "조회 중";
            chip?.EnableInClassList("chip--good", false);
            chip?.EnableInClassList("chip--bad", false);

            FR5EmptyState.Dash(root.Q<Label>("filter-count"));
            FR5EmptyState.Dash(root.Q<Label>("filter-period"));
            FR5EmptyState.Dash(root.Q<Label>("filter-product"));
            FR5EmptyState.Dash(root.Q<Label>("filter-recipe"));
            FR5EmptyState.Dash(root.Q<Label>("filter-defect"));
            FR5EmptyState.Fill(root.Q<VisualElement>("slot-grid"), "MainServer 조회 중", 190f);
            FR5EmptyState.Fill(root.Q<VisualElement>("part-list"), "MainServer 조회 중", 190f);
            FR5EmptyState.Fill(root.Q<VisualElement>("recipe-compare"), "레시피 버전별 집계 조회 필요", 160f);
            FR5EmptyState.Fill(root.Q<VisualElement>("alert-list"), "GET /alerts — 대책서 발행 목록", 160f);
            FR5EmptyState.Detail(root.Q<Label>("recipe-note"), "verification_status 조회 필요");
            FR5EmptyState.Dash(root.Q<Label>("alert-summary"));
            FR5EmptyState.Detail(root.Q<Label>("slot-threshold"), "임계 — defect_report.thresholds 조회 필요");
            loadRoutine = StartCoroutine(Load());
        }

        IEnumerator Load()
        {
            AssemblySnapshot snapshot = null;
            yield return Get("/api/v1/assemblies/current", json =>
                snapshot = JsonUtility.FromJson<AssemblyResponse>(json)?.data);
            if (!isActiveAndEnabled) yield break;
            if (snapshot == null || snapshot.job_id <= 0)
            {
                ShowEmpty("활성 또는 최근 작업 없음");
                loadRoutine = null;
                yield break;
            }

            Job job = null;
            yield return Get($"/api/v1/jobs/{snapshot.job_id}", json =>
                job = JsonUtility.FromJson<JobResponse>(json)?.data);
            if (!isActiveAndEnabled) yield break;
            if (job == null || job.product_id <= 0)
            {
                ShowEmpty($"JOB #{snapshot.job_id} 제품 정보 없음");
                loadRoutine = null;
                yield break;
            }
            ShowFilters(job);

            SlotRate[] rates = null;
            yield return Get($"/api/v1/products/{job.product_id}/quality/slot-rates", json =>
                rates = JsonUtility.FromJson<SlotRatesResponse>(json)?.data ?? Array.Empty<SlotRate>());
            if (isActiveAndEnabled && rates != null) ShowRates(rates);
            loadRoutine = null;
        }

        IEnumerator Get(string path, Action<string> onSuccess)
        {
            using var request = UnityWebRequest.Get(ApiUrl(path));
            request.timeout = 5;
            yield return request.SendWebRequest();
            if (!isActiveAndEnabled) yield break;
            if (request.result == UnityWebRequest.Result.Success)
            {
                try { onSuccess(request.downloadHandler.text); }
                catch (Exception) { ShowEmpty("MainServer 응답 형식 오류"); }
                yield break;
            }
            ShowEmpty($"MainServer 조회 실패 · {request.responseCode}");
        }

        /// <summary>
        /// 아래 수치가 "무엇을 집계한 것인지"를 머리글이 말한다. 값 없이 표만 있으면
        /// 어느 제품 · 어느 레시피의 불량률인지 화면만 보고는 알 수 없다.
        /// 네 칸 모두 jobs/{job_id} 한 번의 응답에서 나온다 — 이미 부르던 조회다.
        /// </summary>
        void ShowFilters(Job job)
        {
            FR5EmptyState.Present(root.Q<Label>("filter-product"),
                string.IsNullOrEmpty(job.product_code) ? FR5EmptyState.Title : job.product_code);
            FR5EmptyState.Present(root.Q<Label>("filter-recipe"),
                string.IsNullOrEmpty(job.recipe_version) ? FR5EmptyState.Title : job.recipe_version);

            // 끝나지 않은 작업은 끝 시각이 없다. 없는 시각을 오늘로 채우면 집계 구간을
            // 지어내는 것이 되므로 "진행 중"이라고 적는다.
            string from = Day(job.requested_at);
            string to = Day(job.job_finished_at);
            FR5EmptyState.Present(root.Q<Label>("filter-period"),
                from == null ? FR5EmptyState.Title : (to == null ? from + " ~ 진행 중" : (to == from ? from : from + " ~ " + to)));

            // 불량 유형은 고르는 칸인데 고를 경로가 없다. 줄표 대신 무엇이 없는지 적는다.
            FR5EmptyState.Detail(root.Q<Label>("filter-defect"), "전체 · 유형 필터 계약 없음");
        }

        /// <summary>timestamptz 문자열에서 날짜만 뗀다. 시각까지는 이 칸에 들어가지 않는다.</summary>
        static string Day(string timestamp)
        {
            if (string.IsNullOrEmpty(timestamp)) return null;
            int split = timestamp.IndexOf('T');
            return split > 0 ? timestamp.Substring(0, split) : timestamp;
        }

        void ShowRates(SlotRate[] rates)
        {
            Label source = root.Q<Label>("source-text");
            VisualElement chip = root.Q<VisualElement>("source-chip");
            if (source != null) source.text = "MainServer";
            chip?.EnableInClassList("chip--good", true);
            chip?.EnableInClassList("chip--bad", false);
            Label count = root.Q<Label>("filter-count");
            if (count != null) count.text = $"{rates.Length} SLOT";

            VisualElement slots = root.Q<VisualElement>("slot-grid");
            slots?.Clear();
            if (rates.Length == 0) slots?.Add(new Label("검사 이력 없음"));
            foreach (SlotRate rate in rates)
            {
                var item = new Label($"{rate.slot_code}\n{rate.defect_rate_percent:0.##}% · {rate.defective_quantity}/{rate.inspected_quantity}");
                item.AddToClassList("slotchip");
                if (rate.defective_quantity > 0) item.AddToClassList("slotchip--bad");
                slots?.Add(item);
            }

            var parts = new Dictionary<string, PartTotal>();
            foreach (SlotRate rate in rates)
            {
                if (!parts.TryGetValue(rate.part_id, out PartTotal total))
                    parts[rate.part_id] = total = new PartTotal { name = rate.part_name };
                total.inspected += rate.inspected_quantity;
                total.defective += rate.defective_quantity;
            }
            VisualElement list = root.Q<VisualElement>("part-list");
            list?.Clear();
            if (parts.Count == 0) list?.Add(new Label("검사 이력 없음"));
            foreach (KeyValuePair<string, PartTotal> pair in parts)
            {
                PartTotal total = pair.Value;
                var row = new VisualElement();
                row.AddToClassList("trow");
                AddCell(row, total.name, 300);
                AddCell(row, pair.Key, 200);
                AddCell(row, $"{total.defective} / {total.inspected}", 140, true);
                AddCell(row, total.inspected == 0 ? "—" : $"{100f * total.defective / total.inspected:0.##}%", 100, true);
                if (total.defective > 0) row.AddToClassList("trow--bad");
                list?.Add(row);
            }
        }

        void ShowEmpty(string message)
        {
            Label source = root.Q<Label>("source-text");
            if (source != null) source.text = FR5EmptyState.Title;
            VisualElement chip = root.Q<VisualElement>("source-chip");
            chip?.EnableInClassList("chip--good", false);
            chip?.EnableInClassList("chip--bad", true);
            FR5EmptyState.Dash(root.Q<Label>("filter-count"));
            FR5EmptyState.Fill(root.Q<VisualElement>("slot-grid"), message, 190f);
            FR5EmptyState.Fill(root.Q<VisualElement>("part-list"), message, 190f);
        }

        /// <summary>
        /// 표의 한 칸이다. 수치 칸은 머리글과 같이 오른쪽 정렬한다 — 머리글만 tcell--num 이라
        /// 값과 머리글이 서로 다른 축에 서 있었고, 자릿수가 어긋나 불량률을 눈으로 못 비볐다.
        /// </summary>
        static void AddCell(VisualElement row, string text, float width, bool num = false)
        {
            var cell = new Label(text);
            cell.AddToClassList("tcell");
            if (num) cell.AddToClassList("tcell--num");
            cell.style.width = width;
            row.Add(cell);
        }

        string ApiUrl(string path) => $"{mainServerBaseUrl.TrimEnd('/')}{path}";
    }
}
