// 역할: QUALITY 페이지(FR5Quality.uxml)의 슬롯 파레토와 선택 슬롯 상세를 그린다.
//
//   실연결 : assemblies/current → jobs/{job_id} → products/{product_id}/quality/slot-rates
//   미연결 : 임계(defect_report.thresholds) · 불량 유형별 집계 · 대책서
//
// Unity 는 DB 에 직접 접속하지 않고 MainServer HTTP 조회만 쓴다.
//
// 화면이 답하는 두 질문과 그 분업 (Docs/ui/mock-05-quality-pareto.svg).
//   좌 파레토는 "어디부터"를 정한다. 누적 %가 성립하려면 반드시 건수로 그려야 한다.
//   우 상세는 "그게 뭔지"를 말한다. 여기서 분모가 나온다.
//   둘을 나눈 이유: 슬롯마다 검사 수가 같아도 부품마다 슬롯 수가 달라, 건수 순위와
//   부품 불량률 순위가 어긋난다. 한쪽 화면에 섞으면 둘 중 하나가 반드시 거짓말을 한다.
//
// 색을 주지 않는 이유. 임계 조회 계약이 없어 "넘었다"를 판정할 근거가 없다. 대신
// 누적 80% 안에 드는 막대만 밝게 둔다 — 이건 임계가 아니라 데이터에서 바로 나온다.

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

        /// <summary>한 부품의 슬롯 전체를 합친 값. 우측 "부품 합계" 칸이 이걸 쓴다.</summary>
        sealed class PartTotal
        {
            public int slots;
            public int inspected;
            public int defective;
            public int defectiveSlots;
        }

        // 그림 영역 크기는 UXML 이 픽셀로 못박아 두었다. 여기 상수는 그 값과 같아야 한다.
        const float PlotWidth = 918f;
        const float PlotHeight = 370f;

        // 막대를 몇 개까지 세울지. 넘는 것은 "나머지 N 슬롯" 한 칸으로 접는다.
        // 25 슬롯을 전부 세우면 칸이 36px 이라 슬롯 코드가 들어가지 않는다.
        const int MaxBars = 8;

        // 막대 머리 위 건수 라벨이 차지하는 높이. 막대에서 이만큼 빼야 라벨을 포함한
        // 기둥 전체가 값 높이와 맞는다. 1위와 격차가 크면 뺀 값이 음수가 되므로 바닥을 둔다.
        const float CountLabelHeight = 26f;
        const float MinBarHeight = 4f;

        /// <summary>
        /// FR5Theme.uss 의 .parttile__icon--* 규칙이 있는 part_id 다. 여기 없는 부품은
        /// 배경 그림이 붙지 않으므로 이니셜 글자로 대신한다 — 빈 칸이 되지 않는다
        /// (FR5EmptyState 2번 규칙). USS 에 규칙을 추가하면 여기도 같이 늘려야 한다.
        /// </summary>
        static readonly HashSet<string> IconParts = new(StringComparer.OrdinalIgnoreCase)
            { "HBM", "PM", "GPU", "CAP", "IND", "VRM" };

        [Header("데이터 소스")]
        [SerializeField] UIMaster uiMaster;
        [SerializeField] string mainServerBaseUrl = "http://127.0.0.1:8000";

        bool built;
        VisualElement root;
        Button refresh;
        Coroutine loadRoutine;
        ParetoCurve curve;

        SlotRate[] rates = Array.Empty<SlotRate>();
        Dictionary<string, PartTotal> parts = new();
        List<SlotRate> ranked = new();     // 지금 그려져 있는 막대들 (필터 적용 후)
        int totalDefective;                // 필터 적용 후 불량 합계 — 누적 %의 분모
        int selected = -1;
        string partFilter;                 // null 이면 전체

        void OnEnable() => built = false;

        void OnDisable()
        {
            if (loadRoutine != null) StopCoroutine(loadRoutine);
            loadRoutine = null;
            if (refresh != null) refresh.clicked -= Reload;
            refresh = null;
            curve = null;
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

            // 누적선은 막대 위에 겹친다. 막대가 클릭을 받아야 하므로 선은 픽킹에서 빠진다.
            VisualElement plot = root.Q<VisualElement>("pareto-plot");
            if (plot != null)
            {
                curve = new ParetoCurve();
                curve.style.position = Position.Absolute;
                curve.style.left = 0;
                curve.style.top = 0;
                curve.style.width = PlotWidth;
                curve.style.height = PlotHeight;
                plot.Add(curve);
            }

            FR5EmptyState.Detail(root.Q<Label>("source-note"),
                "출처: MainServer HTTP · production units / unit_defects / product_slots      ·      "
                + "임계 · 불량 유형별 집계 · 대책서는 조회 계약이 생길 때까지 빈 상태로 존재한다.");

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

            partFilter = null;
            selected = -1;
            FR5EmptyState.Dash(root.Q<Label>("filter-count"));
            FR5EmptyState.Dash(root.Q<Label>("filter-period"));
            FR5EmptyState.Dash(root.Q<Label>("filter-product"));
            FR5EmptyState.Dash(root.Q<Label>("filter-recipe"));
            FR5EmptyState.Dash(root.Q<Label>("pareto-total"));
            FR5EmptyState.Dash(root.Q<Label>("filter-state"));
            ShowChartEmpty("MainServer 조회 중");
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

            SlotRate[] loaded = null;
            yield return Get($"/api/v1/products/{job.product_id}/quality/slot-rates", json =>
                loaded = JsonUtility.FromJson<SlotRatesResponse>(json)?.data ?? Array.Empty<SlotRate>());
            if (isActiveAndEnabled && loaded != null) ShowRates(loaded);
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
        /// 아래 수치가 "무엇을 집계한 것인지"를 머리글이 말한다. 값 없이 그림만 있으면
        /// 어느 제품 · 어느 레시피의 불량률인지 화면만 보고는 알 수 없다.
        /// 세 칸 모두 jobs/{job_id} 한 번의 응답에서 나온다 — 이미 부르던 조회다.
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
        }

        /// <summary>timestamptz 문자열에서 날짜만 뗀다. 시각까지는 이 칸에 들어가지 않는다.</summary>
        static string Day(string timestamp)
        {
            if (string.IsNullOrEmpty(timestamp)) return null;
            int split = timestamp.IndexOf('T');
            return split > 0 ? timestamp.Substring(0, split) : timestamp;
        }

        void ShowRates(SlotRate[] loaded)
        {
            rates = loaded;
            Label source = root.Q<Label>("source-text");
            VisualElement chip = root.Q<VisualElement>("source-chip");
            if (source != null) source.text = "MainServer";
            chip?.EnableInClassList("chip--good", true);
            chip?.EnableInClassList("chip--bad", false);

            // 부품 합계는 필터와 무관하게 전체로 낸다 — 우측 "부품 합계" 칸은
            // "이 부품 전체가 어떤가"를 묻는 자리이지 지금 보고 있는 막대들의 합이 아니다.
            parts = new Dictionary<string, PartTotal>(StringComparer.Ordinal);
            foreach (SlotRate rate in rates)
            {
                string key = rate.part_id ?? FR5EmptyState.Title;
                if (!parts.TryGetValue(key, out PartTotal total))
                    parts[key] = total = new PartTotal();
                total.slots++;
                total.inspected += rate.inspected_quantity;
                total.defective += rate.defective_quantity;
                if (rate.defective_quantity > 0) total.defectiveSlots++;
            }

            int defects = 0;
            foreach (SlotRate rate in rates) defects += rate.defective_quantity;
            FR5EmptyState.Present(root.Q<Label>("filter-count"), $"{rates.Length} SLOT");
            FR5EmptyState.Present(root.Q<Label>("pareto-total"),
                $"불량 {defects}건 · 슬롯 {rates.Length}");

            BuildChips();
            Rebuild();
        }

        /// <summary>
        /// 부품 칩. 누르면 그 부품의 슬롯만 남는다 — 파레토의 축은 슬롯 그대로 두고
        /// 범위만 좁힌다. 부품을 축으로 삼으면 항목이 예닐곱 개뿐이라 누적선이 할 일이 없다.
        /// </summary>
        void BuildChips()
        {
            VisualElement host = root.Q<VisualElement>("part-chips");
            if (host == null) return;
            host.Clear();

            foreach (KeyValuePair<string, PartTotal> pair in parts)
            {
                string id = pair.Key;
                var chipEl = new VisualElement();
                chipEl.AddToClassList("pchip");
                chipEl.Add(PartIcon(id, "pchip__icon"));

                var name = new Label(id);
                name.AddToClassList("pchip__name");
                chipEl.Add(name);

                var n = new Label(pair.Value.defectiveSlots.ToString());
                n.AddToClassList("pchip__n");
                chipEl.Add(n);

                chipEl.userData = id;
                chipEl.RegisterCallback<ClickEvent>(_ =>
                {
                    partFilter = partFilter == id ? null : id;
                    Rebuild();
                });
                host.Add(chipEl);
            }
        }

        /// <summary>필터가 바뀌거나 자료가 새로 오면 순위 · 막대 · 상세를 통째로 다시 만든다.</summary>
        void Rebuild()
        {
            foreach (VisualElement el in root.Q<VisualElement>("part-chips")?.Children() ?? Array.Empty<VisualElement>())
                el.EnableInClassList("pchip--on", partFilter != null && (string)el.userData == partFilter);

            FR5EmptyState.Detail(root.Q<Label>("filter-state"),
                partFilter == null ? "전체 · 필터 없음" : $"{partFilter} 만 표시");

            // 불량 0 인 슬롯은 파레토에 세우지 않는다. 높이 0 인 막대는 자리만 먹고
            // 아무것도 말하지 않으며, 누적 %도 이미 100 에 닿아 있다.
            ranked = new List<SlotRate>();
            foreach (SlotRate rate in rates)
            {
                if (rate.defective_quantity <= 0) continue;
                if (partFilter != null && !string.Equals(rate.part_id, partFilter, StringComparison.Ordinal)) continue;
                ranked.Add(rate);
            }
            ranked.Sort((a, b) =>
            {
                int byCount = b.defective_quantity.CompareTo(a.defective_quantity);
                if (byCount != 0) return byCount;
                int byRate = b.defect_rate_percent.CompareTo(a.defect_rate_percent);
                return byRate != 0 ? byRate : string.CompareOrdinal(a.slot_code, b.slot_code);
            });

            totalDefective = 0;
            foreach (SlotRate rate in ranked) totalDefective += rate.defective_quantity;

            if (ranked.Count == 0 || totalDefective == 0)
            {
                ShowChartEmpty(partFilter == null ? "검사 이력에 불량 없음" : $"{partFilter} 에 불량 없음");
                return;
            }

            selected = 0;   // 1위 자동 선택 — 아무것도 누르지 않아도 화면이 완성돼 있어야 한다.
            DrawChart();
            DrawDetail();
        }

        void DrawChart()
        {
            VisualElement plot = root.Q<VisualElement>("pareto-plot");
            VisualElement axis = root.Q<VisualElement>("pareto-axis");
            if (plot == null || axis == null) return;

            Hide(root.Q<VisualElement>("pareto-empty"));
            ClearExcept(plot, curve);
            axis.Clear();

            int bars = Mathf.Min(ranked.Count, MaxBars);

            // 접히는 꼬리. 막대로 세우지 않은 슬롯 전부다 — 불량 0 인 슬롯도 여기 든다.
            // "나머지가 있다"를 적지 않으면 상위 8개가 슬롯 전부인 줄로 읽힌다.
            int matching = 0;
            foreach (SlotRate rate in rates)
            {
                if (partFilter != null && !string.Equals(rate.part_id, partFilter, StringComparison.Ordinal)) continue;
                matching++;
            }
            int shownDefects = 0;
            for (int i = 0; i < bars; i++) shownDefects += ranked[i].defective_quantity;
            int hidden = Mathf.Max(0, matching - bars);
            int hiddenDefects = totalDefective - shownDefects;
            int columns = bars + (hidden > 0 ? 1 : 0);
            float pitch = PlotWidth / columns;
            float barWidth = Mathf.Min(54f, pitch * 0.55f);

            var axisLine = new VisualElement();
            axisLine.AddToClassList("paxis");
            axisLine.style.left = 0;
            axisLine.style.top = 0;
            axisLine.style.width = PlotWidth;
            axis.Add(axisLine);

            int maxCount = ranked[0].defective_quantity;
            var cumulative = new float[bars];
            int running = 0;

            // 가로 눈금. 세로축 최대는 1위 건수라, 눈금은 그 값을 나눠 쓴다.
            for (int step = 1; step <= 4; step++)
            {
                var grid = new VisualElement();
                grid.AddToClassList("pgrid");
                grid.style.left = 0;
                grid.style.width = PlotWidth;
                grid.style.top = PlotHeight - PlotHeight * step / 4f;
                plot.Add(grid);
            }

            for (int i = 0; i < bars; i++)
            {
                SlotRate rate = ranked[i];
                running += rate.defective_quantity;
                cumulative[i] = 100f * running / totalDefective;

                var col = new VisualElement();
                col.AddToClassList("pbar-col");
                col.style.left = pitch * i + (pitch - barWidth) / 2f;
                col.style.width = barWidth;
                col.style.height = PlotHeight;

                var count = new Label(rate.defective_quantity.ToString());
                count.AddToClassList("pbar-count");
                col.Add(count);

                var bar = new VisualElement();
                bar.AddToClassList("pbar");
                bar.style.height = Mathf.Max(MinBarHeight,
                    PlotHeight * rate.defective_quantity / maxCount - CountLabelHeight);
                col.Add(bar);

                int index = i;
                col.RegisterCallback<ClickEvent>(_ => Select(index));
                plot.Add(col);

                axis.Add(SlotLabel(rate, index, pitch * i, pitch));
            }

            // 접힌 꼬리. "나머지가 있다"를 적지 않으면 상위 8개가 전부인 줄로 읽힌다.
            if (hidden > 0)
            {
                var tail = new Label($"나머지 {hidden} 슬롯 · {hiddenDefects}건");
                tail.AddToClassList("ptail");
                tail.style.left = pitch * bars;
                tail.style.width = pitch;
                tail.style.top = PlotHeight - 26f;
                plot.Add(tail);
            }

            curve?.SetData(cumulative, columns);
            DrawKnee(plot, cumulative, columns);
            ApplySelection();
        }

        /// <summary>
        /// 무릎 설명. 이 화면이 실제로 내는 결론이라 그림 위에 글로 적는다 —
        /// 곡선만 두면 80% 선을 어디서 자르는지 눈으로 재야 한다.
        /// </summary>
        void DrawKnee(VisualElement plot, float[] cumulative, int columns)
        {
            int knee = curve?.KneeIndex ?? -1;
            if (knee < 0) return;

            int covered = 0;
            for (int i = 0; i <= knee; i++) covered += ranked[i].defective_quantity;
            float center = ParetoCurve.ColumnCenter(PlotWidth, columns, knee);
            float y = PlotHeight - PlotHeight * cumulative[knee] / 100f;

            var head = new Label($"상위 {knee + 1} 슬롯 = {cumulative[knee]:0.0}%");
            head.AddToClassList("pknee");
            head.style.left = center - 140f;
            head.style.width = 280f;
            head.style.top = Mathf.Max(0f, y - 58f);
            plot.Add(head);

            var sub = new Label($"여기까지 고치면 {totalDefective}건 중 {covered}건");
            sub.AddToClassList("pknee__sub");
            sub.style.left = center - 140f;
            sub.style.width = 280f;
            sub.style.top = Mathf.Max(16f, y - 38f);
            plot.Add(sub);
        }

        /// <summary>축 아래 한 칸. 막대와 같은 것을 가리키므로 여기도 눌러서 고를 수 있다.</summary>
        VisualElement SlotLabel(SlotRate rate, int index, float left, float pitch)
        {
            var cell = new VisualElement();
            cell.AddToClassList("pslot");
            cell.style.left = left;
            cell.style.width = pitch;

            var mark = new VisualElement();
            mark.AddToClassList("pslot__mark");
            cell.Add(mark);

            cell.Add(PartIcon(rate.part_id, "pslot__icon"));

            var code = new Label(rate.slot_code);
            code.AddToClassList("pslot__code");
            cell.Add(code);

            var value = new Label($"{rate.defect_rate_percent:0.##}%");
            value.AddToClassList("pslot__rate");
            cell.Add(value);

            cell.RegisterCallback<ClickEvent>(_ => Select(index));
            return cell;
        }

        void Select(int index)
        {
            if (index < 0 || index >= ranked.Count || index == selected) return;
            selected = index;
            ApplySelection();
            DrawDetail();
        }

        /// <summary>
        /// 강조색은 "지금 여기"에만 쓴다. 심각도는 막대 밝기가 따로 말하므로
        /// 두 채널이 겹치지 않는다 (FR5Theme.uss 머리말).
        /// </summary>
        void ApplySelection()
        {
            VisualElement plot = root.Q<VisualElement>("pareto-plot");
            VisualElement axis = root.Q<VisualElement>("pareto-axis");
            int knee = curve?.KneeIndex ?? -1;

            int i = 0;
            foreach (VisualElement col in plot?.Children() ?? Array.Empty<VisualElement>())
            {
                if (!col.ClassListContains("pbar-col")) continue;
                VisualElement bar = col.Q<VisualElement>(className: "pbar");
                bar?.EnableInClassList("pbar--major", knee >= 0 && i <= knee);
                bar?.EnableInClassList("pbar--sel", i == selected);
                col.Q<Label>(className: "pbar-count")?.EnableInClassList("pbar-count--dim", i != selected);
                i++;
            }

            int j = 0;
            foreach (VisualElement cell in axis?.Children() ?? Array.Empty<VisualElement>())
            {
                if (!cell.ClassListContains("pslot")) continue;
                cell.EnableInClassList("pslot--sel", j == selected);
                j++;
            }
        }

        void DrawDetail()
        {
            if (selected < 0 || selected >= ranked.Count) return;
            SlotRate rate = ranked[selected];
            parts.TryGetValue(rate.part_id ?? FR5EmptyState.Title, out PartTotal part);

            Hide(root.Q<VisualElement>("detail-empty"));
            Show(root.Q<VisualElement>("detail-body"));

            VisualElement icon = root.Q<VisualElement>("detail-icon");
            if (icon != null)
            {
                icon.Clear();
                icon.ClearClassList();
                icon.AddToClassList("pick__icon");
                if (IconParts.Contains(rate.part_id ?? string.Empty))
                    icon.AddToClassList($"parttile__icon--{rate.part_id.ToLowerInvariant()}");
                else
                    icon.Add(FallbackInitial(rate.part_id, 20));
            }

            FR5EmptyState.Present(root.Q<Label>("detail-code"), rate.slot_code);
            FR5EmptyState.Present(root.Q<Label>("detail-part"),
                string.IsNullOrEmpty(rate.part_name) ? rate.part_id : $"{rate.part_id} · {rate.part_name}");
            FR5EmptyState.Present(root.Q<Label>("detail-rate"), $"{rate.defect_rate_percent:0.##}%");
            FR5EmptyState.Present(root.Q<Label>("detail-den"),
                $"{rate.defective_quantity} / {rate.inspected_quantity}");

            // TODO(API): thresholds 가 붙으면 여기서 초과를 판정하고 막대에 색을 준다.
            FR5EmptyState.Detail(root.Q<Label>("detail-threshold"), "임계 미연결 · 색 판정 보류");

            // 막대는 이 화면에서 제일 나쁜 슬롯을 1로 놓은 상대 길이다. 절대 기준(임계)이
            // 없으므로 "얼마나 나쁜가"가 아니라 "누구에 비해 나쁜가"만 말한다.
            VisualElement gauge = root.Q<VisualElement>("detail-gauge");
            if (gauge != null)
            {
                float top = ranked[0].defect_rate_percent;
                gauge.style.width = new Length(top <= 0f ? 0f : 100f * rate.defect_rate_percent / top, LengthUnit.Percent);
            }

            int running = 0;
            for (int i = 0; i <= selected; i++) running += ranked[i].defective_quantity;

            VisualElement rows = root.Q<VisualElement>("detail-rows");
            rows?.Clear();
            AddRow(rows, "누적 기여",
                $"{100f * running / totalDefective:0.0}% · {totalDefective}건 중 {running}건 · {selected + 1}위");
            if (part != null)
            {
                AddRow(rows, "부품 합계",
                    part.inspected == 0
                        ? $"{part.defective} / {part.inspected}"
                        : $"{part.defective} / {part.inspected} · {100f * part.defective / part.inspected:0.##}%");
                AddRow(rows, "부품 내 분포", $"슬롯 {part.slots}개 중 {part.defectiveSlots}곳에서 불량");
            }
            // TODO(API): 불량 유형별 집계. defect_type 은 /jobs/{id}/units 에만 있고 잡 단위라
            // 이 화면(제품 누적)과 분모가 어긋난다. 유형별 조회 계약이 생기기 전까지는 비운다.
            AddRow(rows, "불량 유형", FR5EmptyState.Title, "유형별 집계 계약 없음");

            FR5EmptyState.Detail(root.Q<Label>("detail-note"),
                part == null || part.slots <= 1
                    ? "왼쪽 순서는 건수가, 이 칸의 비율은 분모가 정한다."
                    : $"{rate.part_id} 은 슬롯 {part.slots}개로 나뉘어 있어 부품 불량률({(part.inspected == 0 ? 0f : 100f * part.defective / part.inspected):0.##}%)과 "
                      + $"슬롯 불량률({rate.defect_rate_percent:0.##}%)의 분모가 다르다. 왼쪽 순서는 건수가, 이 칸은 분모가 말한다.");

            // TODO(API): GET /alerts — 이 슬롯에 걸린 대책서
            FR5EmptyState.Detail(root.Q<Label>("detail-alert"),
                $"{FR5EmptyState.Title} — GET /alerts · 대책서 발행 목록");
        }

        static void AddRow(VisualElement host, string key, string value, string miss = null)
        {
            if (host == null) return;
            var row = new VisualElement();
            row.AddToClassList("prow");

            var k = new Label(key);
            k.AddToClassList("prow__key");
            row.Add(k);

            var v = new Label(miss == null ? value : $"{value} · {miss}");
            v.AddToClassList("prow__val");
            if (miss != null) v.AddToClassList("prow__val--miss");
            row.Add(v);

            host.Add(row);
        }

        /// <summary>USS 에 그림 규칙이 없는 부품이다. 이니셜 글자를 대신 세운다.</summary>
        static Label FallbackInitial(string partId, int size)
        {
            string text = string.IsNullOrEmpty(partId) ? "?" : partId.Substring(0, 1).ToUpperInvariant();
            var label = new Label(text);
            label.AddToClassList("parttile__fallback");
            label.style.fontSize = size;
            return label;
        }

        VisualElement PartIcon(string partId, string sizeClass)
        {
            var icon = new VisualElement();
            icon.AddToClassList(sizeClass);
            if (IconParts.Contains(partId ?? string.Empty))
                icon.AddToClassList($"parttile__icon--{partId.ToLowerInvariant()}");
            else
                icon.Add(FallbackInitial(partId, 11));
            return icon;
        }

        /// <summary>
        /// 빈 상태 칸은 그림·상세 위에 절대 배치로 겹쳐 있다. 자식만 지우면 칸 자체는
        /// 크기를 유지한 채 남아 아래 막대의 클릭을 가로챈다. 그래서 display 로 끈다.
        /// </summary>
        static void Hide(VisualElement el)
        {
            if (el == null) return;
            el.Clear();
            el.style.display = DisplayStyle.None;
        }

        static void Show(VisualElement el)
        {
            if (el == null) return;
            el.style.display = DisplayStyle.Flex;
        }

        /// <summary>누적선 요소는 남기고 막대만 걷는다. 다시 만들면 그릴 대상을 잃는다.</summary>
        static void ClearExcept(VisualElement host, VisualElement keep)
        {
            for (int i = host.childCount - 1; i >= 0; i--)
            {
                if (host[i] == keep) continue;
                host.RemoveAt(i);
            }
        }

        void ShowChartEmpty(string message)
        {
            curve?.ClearData();
            VisualElement plot = root.Q<VisualElement>("pareto-plot");
            if (plot != null) ClearExcept(plot, curve);
            root.Q<VisualElement>("pareto-axis")?.Clear();
            VisualElement chartEmpty = root.Q<VisualElement>("pareto-empty");
            FR5EmptyState.Fill(chartEmpty, message, PlotHeight);
            Show(chartEmpty);

            Hide(root.Q<VisualElement>("detail-body"));
            VisualElement detailEmpty = root.Q<VisualElement>("detail-empty");
            FR5EmptyState.Fill(detailEmpty, message, 300f);
            Show(detailEmpty);
        }

        void ShowEmpty(string message)
        {
            Label source = root.Q<Label>("source-text");
            if (source != null) source.text = FR5EmptyState.Title;
            VisualElement chip = root.Q<VisualElement>("source-chip");
            chip?.EnableInClassList("chip--good", false);
            chip?.EnableInClassList("chip--bad", true);
            FR5EmptyState.Dash(root.Q<Label>("filter-count"));
            FR5EmptyState.Dash(root.Q<Label>("pareto-total"));
            root.Q<VisualElement>("part-chips")?.Clear();
            ShowChartEmpty(message);
        }

        string ApiUrl(string path) => $"{mainServerBaseUrl.TrimEnd('/')}{path}";
    }
}
