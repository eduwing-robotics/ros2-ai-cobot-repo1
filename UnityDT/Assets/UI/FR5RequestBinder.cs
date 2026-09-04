// 역할: JOBS 페이지의 영속 작업 큐, 최근 이력, 신규 Job 등록을 담당한다.
// Job 등록 성공은 DB의 PENDING 생성이며 실제 조립 완료를 뜻하지 않는다.

using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using MainUnity.Runtime.Robot;
using MainUnity.Runtime.Robot.Status;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UIElements;

namespace MainUnity.UI
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(UIDocument))]
    public sealed class FR5RequestBinder : MonoBehaviour
    {
        const string RecipeVersion = "assembly-r1";

        [Serializable] sealed class ProductListResponse { public Product[] data; }
        [Serializable] sealed class ProductResponse { public ProductDetail data; }
        [Serializable] sealed class RequirementListResponse { public Requirement[] data; }
        [Serializable] sealed class JobListResponse { public Job[] data; }
        [Serializable] sealed class AssemblyResponse { public AssemblyResult data; }

        [Serializable] sealed class Product
        {
            public int product_id;
            public string product_code;
            public string product_name;
            public string product_version;
            public int buildable_quantity;
        }

        [Serializable] sealed class ProductDetail
        {
            public int product_id;
            public string product_code;
            public string product_name;
            public string product_version;
            public Slot[] slots;
        }

        [Serializable] sealed class Slot
        {
            public string part_id;
            public string part_name;
        }

        [Serializable] sealed class Requirement
        {
            public string part_id;
            public int required_quantity;
            public int stock_quantity;
            public int shortage_quantity;
        }

        [Serializable] sealed class Job
        {
            public string job_id;
            public string product_code;
            public string product_name;
            public string product_version;
            public string job_status;
            public int requested_quantity;
            public int attempted_quantity;
            public int completed_quantity;
            public int running_quantity;
            public int failed_quantity;
            public int inspection_failed_quantity;
            public string requested_at;
        }

        [Serializable] sealed class StartCommand
        {
            public string command;
            public string job_id;
            public string product_code;
            public string product_version;
            public int requested_quantity;
            public string recipe_version;
        }

        [Serializable] sealed class AssemblyResult
        {
            public bool accepted;
            public string job_id;
            public string status;
        }

        [Header("데이터 소스")]
        [SerializeField] UIMaster uiMaster;
        [SerializeField] RobotStatusManager statusManager;
        [SerializeField] string mainServerBaseUrl = "http://127.0.0.1:8000";

        [Header("요청")]
        [SerializeField, Min(1)] int quantity = 1;

        [Header("완성체 미리보기")]
        [SerializeField] RenderTexture productPreview;

        VisualElement jobList, interlockList, slotList, previewEmpty;
        Image previewImage;
        Label jobCount, jobError, productName, productMeta, productSlotCount,
              previewSource, previewDesc, qtyValue, startReason;
        Button start, filterAll, filterQueue, filterAttention, filterDone;
        FR5PageRouter pageRouter;

        Product[] products = Array.Empty<Product>();
        ProductDetail selectedProduct;
        Requirement[] requirements = Array.Empty<Requirement>();
        Job[] jobs = Array.Empty<Job>();

        bool cached, requirementsLoaded, jobsLoading, registerInFlight;
        string productError, selectedFilter = "ALL", interlockSignature, pendingJobId, actionJobId;

        void OnEnable()
        {
            cached = false;
            products = Array.Empty<Product>();
            selectedProduct = null;
            requirements = Array.Empty<Requirement>();
            jobs = Array.Empty<Job>();
            requirementsLoaded = false;
            jobsLoading = false;
            registerInFlight = false;
            actionJobId = null;
            productError = null;
            interlockSignature = null;
        }

        void OnDisable() => StopAllCoroutines();

        void Update()
        {
            if (!cached)
            {
                Build();
                if (!cached) return;
            }
            RefreshInterlocks();
        }

        void Build()
        {
            VisualElement root = GetComponent<UIDocument>().rootVisualElement;
            if (root == null) return;

            uiMaster ??= GetComponentInParent<UIMaster>();
            statusManager ??= uiMaster != null ? uiMaster.StatusManager : null;
            pageRouter = GetComponentInParent<FR5PageRouter>();

            jobList = root.Q<VisualElement>("job-list");
            interlockList = root.Q<VisualElement>("interlock-list");
            slotList = root.Q<VisualElement>("slot-list");
            previewImage = root.Q<Image>("product-preview");
            previewEmpty = root.Q<VisualElement>("product-preview-empty");
            jobCount = root.Q<Label>("job-count");
            jobError = root.Q<Label>("job-error");
            productName = root.Q<Label>("product-name");
            productMeta = root.Q<Label>("product-meta");
            productSlotCount = root.Q<Label>("product-slot-count");
            previewSource = root.Q<Label>("preview-source");
            previewDesc = root.Q<Label>("product-preview-desc");
            qtyValue = root.Q<Label>("qty-value");
            startReason = root.Q<Label>("start-reason");
            start = root.Q<Button>("start-button");
            filterAll = root.Q<Button>("filter-all");
            filterQueue = root.Q<Button>("filter-queue");
            filterAttention = root.Q<Button>("filter-attention");
            filterDone = root.Q<Button>("filter-done");

            if (start != null) start.clicked += OnRegister;
            root.Q<Button>("job-refresh").clicked += () => StartCoroutine(LoadJobs());
            if (filterAll != null) filterAll.clicked += () => SetFilter("ALL");
            if (filterQueue != null) filterQueue.clicked += () => SetFilter("QUEUE");
            if (filterAttention != null) filterAttention.clicked += () => SetFilter("ATTENTION");
            if (filterDone != null) filterDone.clicked += () => SetFilter("DONE");

            quantity = Mathf.Max(1, quantity);
            if (qtyValue != null) qtyValue.text = quantity.ToString();
            RefreshPreview();
            RefreshProduct();
            BuildSlots();
            BuildJobs();
            cached = true;
            StartCoroutine(LoadProducts());
            StartCoroutine(PollJobs());
        }

        IEnumerator PollJobs()
        {
            while (isActiveAndEnabled)
            {
                yield return LoadJobs();
                yield return new WaitForSecondsRealtime(2f);
            }
        }

        IEnumerator LoadJobs()
        {
            if (jobsLoading) yield break;
            jobsLoading = true;
            using var request = UnityWebRequest.Get(ApiUrl("/api/v1/jobs?limit=20"));
            request.timeout = 5;
            yield return request.SendWebRequest();

            if (isActiveAndEnabled)
            {
                if (request.result == UnityWebRequest.Result.Success)
                {
                    try
                    {
                        jobs = JsonUtility.FromJson<JobListResponse>(request.downloadHandler.text)?.data
                            ?? Array.Empty<Job>();
                        if (!string.IsNullOrEmpty(actionJobId) &&
                            Array.Exists(jobs, job => job.job_id == actionJobId && job.job_status != "PENDING"))
                            actionJobId = null;
                        if (jobError != null) jobError.text = "";
                        BuildJobs();
                    }
                    catch (Exception)
                    {
                        SetJobError("MainServer 응답 형식 오류");
                    }
                }
                else SetJobError("MainServer 조회 실패 · " + request.responseCode);
            }
            jobsLoading = false;
        }

        void SetJobError(string message)
        {
            if (jobError != null) jobError.text = message;
            if (jobs.Length == 0) FR5EmptyState.Fill(jobList, message, 120f);
        }

        void BuildJobs()
        {
            if (jobList == null) return;
            jobList.Clear();
            int visible = 0;
            foreach (Job job in jobs)
            {
                if (!MatchesJob(job, selectedFilter)) continue;
                visible++;
                jobList.Add(JobRow(job));
            }

            if (visible == 0)
                FR5EmptyState.Fill(jobList, jobs.Length == 0 ? "등록된 Job 없음" : "해당 조건의 Job 없음", 120f);
            if (jobCount != null) jobCount.text = visible + " / " + jobs.Length;
            RefreshFilters();
        }

        VisualElement JobRow(Job job)
        {
            var row = new VisualElement();
            row.AddToClassList("trow");
            if (job.job_status == "RUNNING") row.AddToClassList("trow--sel");
            if (IsAttention(job)) row.AddToClassList("trow--bad");

            var status = new Label(job.job_status);
            status.AddToClassList("job-status");
            status.AddToClassList("job-status--" + job.job_status.ToLowerInvariant());
            status.style.width = 104;
            row.Add(status);

            AddCell(row, ShortJobId(job.job_id), 150);
            AddCell(row, ProductText(job), 260);
            AddCell(row, job.completed_quantity + " / " + job.requested_quantity, 112, true);
            AddCell(row, ResultText(job), 148);
            AddCell(row, FormatTime(job.requested_at), 126);

            var links = new VisualElement();
            links.AddToClassList("row");
            links.style.width = 132;

            if (job.job_status == "PENDING")
            {
                bool actionPending = actionJobId == job.job_id;
                var start = new Button(() => StartJob(job))
                {
                    text = actionPending ? "STARTING…" : "START"
                };
                start.AddToClassList("job-link");
                start.SetEnabled(!actionPending && string.IsNullOrEmpty(actionJobId) && uiMaster?.Scenario != null);
                links.Add(start);

                var cancel = new Button(() => StartCoroutine(CancelJob(job.job_id))) { text = "CANCEL" };
                cancel.AddToClassList("job-link");
                cancel.SetEnabled(!actionPending && string.IsNullOrEmpty(actionJobId));
                links.Add(cancel);
            }
            else if (job.job_status == "RUNNING")
            {
                var run = new Button(() => pageRouter?.OpenMonitor()) { text = "RUN" };
                run.AddToClassList("job-link");
                links.Add(run);
            }
            else
            {
                var inspect = new Button(() => pageRouter?.OpenInspect(job.job_id)) { text = "검사" };
                inspect.AddToClassList("job-link");
                links.Add(inspect);
            }
            row.Add(links);
            return row;
        }

        async void StartJob(Job job)
        {
            if (!string.IsNullOrEmpty(actionJobId) || uiMaster?.Scenario == null) return;
            actionJobId = job.job_id;
            BuildJobs();
            try
            {
                await uiMaster.Scenario.RunQueuedAsync(job.job_id);
            }
            catch (Exception exception)
            {
                SetJobError("Job 시작 실패 · " + exception.Message);
            }
            finally
            {
                actionJobId = null;
                if (isActiveAndEnabled) StartCoroutine(LoadJobs());
            }
        }

        IEnumerator CancelJob(string jobId)
        {
            if (!string.IsNullOrEmpty(actionJobId)) yield break;
            actionJobId = jobId;
            BuildJobs();
            using var request = UnityWebRequest.Delete(ApiUrl("/api/v1/jobs/" + Uri.EscapeDataString(jobId)));
            request.timeout = 5;
            yield return request.SendWebRequest();
            if (isActiveAndEnabled && request.result != UnityWebRequest.Result.Success)
                SetJobError("Job 취소 실패 · HTTP " + request.responseCode);
            actionJobId = null;
            if (isActiveAndEnabled) yield return LoadJobs();
        }

        static void AddCell(VisualElement row, string text, float width, bool numeric = false)
        {
            var cell = new Label(text);
            cell.AddToClassList("tcell");
            if (numeric) cell.AddToClassList("tcell--num");
            cell.style.width = width;
            row.Add(cell);
        }

        static bool MatchesJob(Job job, string filter)
        {
            return filter == "ALL"
                || filter == "QUEUE" && (job.job_status == "PENDING" || job.job_status == "RUNNING")
                || filter == "ATTENTION" && IsAttention(job)
                || filter == "DONE" && (job.job_status == "COMPLETED" || job.job_status == "CANCELLED");
        }

        static bool IsAttention(Job job) =>
            job.job_status == "FAILED" || job.failed_quantity > 0 || job.inspection_failed_quantity > 0;

        static string ShortJobId(string jobId) =>
            string.IsNullOrEmpty(jobId) ? "—" : jobId.Substring(0, Mathf.Min(8, jobId.Length)).ToUpperInvariant();

        static string ProductText(Job job) =>
            string.IsNullOrEmpty(job.product_name)
                ? job.product_code + " · " + job.product_version
                : job.product_name + " · " + job.product_version;

        static string ResultText(Job job)
        {
            if (job.inspection_failed_quantity > 0) return "검사 FAIL " + job.inspection_failed_quantity;
            if (job.failed_quantity > 0) return "실행 실패 " + job.failed_quantity;
            if (job.job_status == "COMPLETED") return "완료";
            return "시도 " + job.attempted_quantity;
        }

        static string FormatTime(string value)
        {
            if (!DateTime.TryParse(value, out DateTime time)) return "—";
            return time.ToLocalTime().ToString("MM-dd HH:mm");
        }

        void SetFilter(string filter)
        {
            selectedFilter = filter;
            BuildJobs();
        }

        void RefreshFilters()
        {
            filterAll?.EnableInClassList("job-filter--on", selectedFilter == "ALL");
            filterQueue?.EnableInClassList("job-filter--on", selectedFilter == "QUEUE");
            filterAttention?.EnableInClassList("job-filter--on", selectedFilter == "ATTENTION");
            filterDone?.EnableInClassList("job-filter--on", selectedFilter == "DONE");
        }

        IEnumerator LoadProducts()
        {
            yield return Get("/api/v1/products", json =>
            {
                products = JsonUtility.FromJson<ProductListResponse>(json)?.data ?? Array.Empty<Product>();
                if (products.Length == 0)
                {
                    SetProductError("products 조회 결과 없음");
                    return;
                }
                StartCoroutine(LoadProduct(products[0].product_id));
            }, SetProductError);
        }

        IEnumerator LoadProduct(int productId)
        {
            yield return Get("/api/v1/products/" + productId, json =>
            {
                selectedProduct = JsonUtility.FromJson<ProductResponse>(json)?.data;
                productError = selectedProduct == null ? "제품 응답 없음" : null;
                RefreshProduct();
                BuildSlots();
                StartCoroutine(LoadRequirements(productId));
            }, SetProductError);
        }

        IEnumerator LoadRequirements(int productId)
        {
            requirementsLoaded = false;
            yield return Get("/api/v1/products/" + productId + "/requirements?quantity=" + quantity, json =>
            {
                requirements = JsonUtility.FromJson<RequirementListResponse>(json)?.data
                    ?? Array.Empty<Requirement>();
                requirementsLoaded = true;
                BuildSlots();
                interlockSignature = null;
            }, SetProductError);
        }

        IEnumerator Get(string path, Action<string> onSuccess, Action<string> onError)
        {
            using var request = UnityWebRequest.Get(ApiUrl(path));
            request.timeout = 5;
            yield return request.SendWebRequest();
            if (!isActiveAndEnabled) yield break;

            if (request.result != UnityWebRequest.Result.Success)
            {
                onError("MainServer 조회 실패 · " + request.responseCode);
                yield break;
            }

            try { onSuccess(request.downloadHandler.text); }
            catch (Exception) { onError("MainServer 응답 형식 오류"); }
        }

        void SetProductError(string message)
        {
            productError = message;
            selectedProduct = null;
            requirements = Array.Empty<Requirement>();
            requirementsLoaded = false;
            RefreshProduct();
            BuildSlots();
            interlockSignature = null;
        }

        void RefreshProduct()
        {
            if (selectedProduct == null)
            {
                FR5EmptyState.Missing(productName);
                FR5EmptyState.Detail(productMeta, productError ?? "제품 조회 중");
                FR5EmptyState.Detail(productSlotCount, "product_slots 조회 대기");
                return;
            }

            FR5EmptyState.Present(productName, selectedProduct.product_name);
            FR5EmptyState.Detail(productMeta,
                selectedProduct.product_code + " · " + selectedProduct.product_version);
            int slotCount = selectedProduct.slots?.Length ?? 0;
            int partCount = selectedProduct.slots == null ? 0 : GroupByPart(selectedProduct.slots).Count;
            FR5EmptyState.Detail(productSlotCount, slotCount + " 슬롯 · " + partCount + " 부품");
        }

        sealed class PartGroup
        {
            public string PartId;
            public string PartName;
            public int Count;
        }

        void BuildSlots()
        {
            if (slotList == null) return;
            if (selectedProduct?.slots == null || selectedProduct.slots.Length == 0)
            {
                FR5EmptyState.Fill(slotList, productError ?? "제품 구성 조회 중", 110f);
                return;
            }

            slotList.Clear();
            foreach (PartGroup group in GroupByPart(selectedProduct.slots))
                slotList.Add(PartTile(group));
        }

        static List<PartGroup> GroupByPart(Slot[] slots)
        {
            var groups = new List<PartGroup>();
            var index = new Dictionary<string, PartGroup>(StringComparer.OrdinalIgnoreCase);
            foreach (Slot slot in slots)
            {
                string partId = string.IsNullOrEmpty(slot.part_id) ? "—" : slot.part_id;
                if (!index.TryGetValue(partId, out PartGroup group))
                {
                    group = new PartGroup { PartId = partId, PartName = slot.part_name };
                    index.Add(partId, group);
                    groups.Add(group);
                }
                group.Count++;
            }
            return groups;
        }

        VisualElement PartTile(PartGroup group)
        {
            var tile = new VisualElement();
            tile.AddToClassList("parttile");
            tile.AddToClassList("parttile--compact");
            tile.tooltip = string.IsNullOrEmpty(group.PartName) ? group.PartId : group.PartName;

            var icon = new VisualElement();
            icon.AddToClassList("parttile__icon");
            icon.AddToClassList("parttile__icon--" + group.PartId.ToLowerInvariant());
            var fallback = new Label(Initials(group.PartId));
            fallback.AddToClassList("parttile__fallback");
            icon.Add(fallback);
            tile.Add(icon);

            var line = new VisualElement();
            line.AddToClassList("parttile__line");
            var name = new Label(group.PartId.ToUpperInvariant());
            name.AddToClassList("parttile__name");
            line.Add(name);
            var count = new Label("×" + group.Count);
            count.AddToClassList("parttile__count");
            line.Add(count);
            tile.Add(line);

            Requirement stock = Array.Find(requirements,
                item => string.Equals(item.part_id, group.PartId, StringComparison.OrdinalIgnoreCase));
            var stockText = new Label(stock == null ? "재고 조회 중" : "보유 " + stock.stock_quantity);
            stockText.AddToClassList("parttile__stock");
            if (stock != null && stock.shortage_quantity > 0) stockText.AddToClassList("bad");
            tile.Add(stockText);
            return tile;
        }

        static string Initials(string partId)
        {
            if (string.IsNullOrEmpty(partId)) return "—";
            return partId.Substring(0, Mathf.Min(3, partId.Length)).ToUpperInvariant();
        }

        void RefreshPreview()
        {
            bool ready = productPreview != null;
            if (previewImage != null)
            {
                previewImage.image = ready ? productPreview : null;
                previewImage.style.display = ready ? DisplayStyle.Flex : DisplayStyle.None;
            }
            if (previewEmpty != null)
                previewEmpty.style.display = ready ? DisplayStyle.None : DisplayStyle.Flex;
            FR5EmptyState.Detail(previewSource,
                ready ? productPreview.width + "×" + productPreview.height : "카메라 미지정");
            if (!ready) FR5EmptyState.Detail(previewDesc, "기판 RenderTexture를 연결하세요");
        }

        void RefreshInterlocks()
        {
            if (interlockList == null) return;

            bool productReady = selectedProduct != null && requirementsLoaded;
            bool stockReady = productReady && Array.TrueForAll(requirements, item => item.shortage_quantity == 0);
            bool mock = uiMaster != null && uiMaster.IsSimulated;
            string signature = productReady + "|" + stockReady + "|" + mock + "|" + registerInFlight;
            if (signature == interlockSignature)
            {
                ApplyRegisterState(productReady, stockReady, mock);
                return;
            }

            interlockSignature = signature;
            interlockList.Clear();
            AddCheck("제품 · recipe 조회", productReady);
            AddCheck("목표 수량분 재고", stockReady);
            AddCheck("모드 = MOCK", mock);
            ApplyRegisterState(productReady, stockReady, mock);
        }

        void AddCheck(string label, bool ok)
        {
            var line = new VisualElement();
            line.AddToClassList("row");
            line.style.height = 30;
            var dot = new VisualElement();
            dot.AddToClassList("dot");
            dot.AddToClassList(ok ? "dot--good" : "dot--bad");
            line.Add(dot);
            var text = new Label(label);
            text.style.marginLeft = 10;
            text.style.color = ok ? new Color(0.62f, 0.69f, 0.75f) : new Color(1f, 0.56f, 0.61f);
            line.Add(text);
            interlockList.Add(line);
        }

        void ApplyRegisterState(bool productReady, bool stockReady, bool mock)
        {
            bool ready = productReady && stockReady && mock && !registerInFlight;
            start?.SetEnabled(ready);
            if (start != null) start.text = registerInFlight ? "REGISTERING…" : "REGISTER JOB";
            if (startReason == null || registerInFlight) return;
            startReason.text = !productReady
                ? productError ?? "제품과 재고를 조회하고 있습니다."
                : !stockReady
                ? "목표 수량에 필요한 재고가 부족합니다."
                : !mock
                ? "Real Sequencer 연결 전에는 Job 등록이 비활성화됩니다."
                : "DB에 PENDING Job으로 등록됩니다.";
        }

        void OnRegister()
        {
            if (!registerInFlight && selectedProduct != null)
                StartCoroutine(RegisterJob());
        }

        IEnumerator RegisterJob()
        {
            registerInFlight = true;
            interlockSignature = null;
            pendingJobId ??= Guid.NewGuid().ToString();

            var command = new StartCommand
            {
                command = "start",
                job_id = pendingJobId,
                product_code = selectedProduct.product_code,
                product_version = selectedProduct.product_version,
                requested_quantity = quantity,
                recipe_version = RecipeVersion,
            };

            using var request = new UnityWebRequest(ApiUrl("/api/v1/assemblies"), "POST");
            request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(JsonUtility.ToJson(command)));
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            request.timeout = 5;
            yield return request.SendWebRequest();

            if (isActiveAndEnabled)
            {
                if (request.result == UnityWebRequest.Result.Success)
                {
                    try
                    {
                        AssemblyResult result = JsonUtility.FromJson<AssemblyResponse>(
                            request.downloadHandler.text)?.data;
                        if (result == null || !result.accepted) throw new InvalidOperationException();
                        if (startReason != null)
                            startReason.text = "JOB " + ShortJobId(result.job_id) + " · " + result.status;
                        pendingJobId = null;
                        StartCoroutine(LoadJobs());
                    }
                    catch (Exception)
                    {
                        if (startReason != null)
                            startReason.text = "등록 응답을 확인하지 못했습니다. 같은 Job ID로 재시도합니다.";
                    }
                }
                else if (startReason != null)
                    startReason.text = "Job 등록 실패 · HTTP " + request.responseCode;
            }

            registerInFlight = false;
            interlockSignature = null;
        }

        string ApiUrl(string path) => mainServerBaseUrl.TrimEnd('/') + path;

        [ContextMenu("API/Self Check")]
        void ApiSelfCheck()
        {
            Debug.Assert(ApiUrl("/api/v1/jobs") == "http://127.0.0.1:8000/api/v1/jobs");
            Debug.Assert(MatchesJob(new Job { job_status = "PENDING" }, "QUEUE"));
            Debug.Assert(!MatchesJob(new Job { job_status = "COMPLETED" }, "QUEUE"));
        }
    }
}
