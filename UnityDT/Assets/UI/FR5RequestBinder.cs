// 역할: JOBS 페이지의 영속 작업 큐, 최근 이력, 신규 Job 등록을 담당한다.
// Job 등록 성공은 DB의 PENDING 생성이며 실제 조립 완료를 뜻하지 않는다.

using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using System.Threading.Tasks;
using MainUnity.Runtime.Robot.Interface;
using MainUnity.Runtime.Robot.Assembly;
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
            public string requested_by;
        }

        [Serializable] sealed class StartCommand
        {
            public string command;
            public string job_id;
            public string product_code;
            public string product_version;
            public int requested_quantity;
            public string recipe_version;
            public string requested_by;
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
        string jobQueryError, jobActionError, registrationResult;
        Button start, filterAll, filterQueue, filterAttention, filterDone;
        FR5PageRouter pageRouter;
        Label queryState, selectedStatus, selectedName, selectedId, selectedProgress, selectedAttempts, selectedResults, selectedReason;
        Button refreshJobs, selectedStart, selectedCancel, selectedMonitor, selectedInspect, selectedForceCancel;
        string selectedJobId, lastJobsResponse;
        readonly Dictionary<string, Label> jobStatusLabels = new Dictionary<string, Label>();

        Product[] products = Array.Empty<Product>();
        ProductDetail selectedProduct;
        Requirement[] requirements = Array.Empty<Requirement>();
        string requirementsQueriedAt;
        Job[] jobs = Array.Empty<Job>();

        bool cached, requirementsLoaded, jobsLoading, jobsLoaded, registerInFlight;
        TextField requestedBy;
        string pendingRequestedBy;
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
            jobsLoaded = false;
            registerInFlight = false;
            actionJobId = null;
            selectedJobId = null;
            lastJobsResponse = null;
            jobQueryError = null;
            productError = null;
            interlockSignature = null;
        }

        TaskCompletionSource<AssemblySceneConfirmation> sceneConfirmation;
        VisualElement sceneDialog;

        void OnDisable()
        {
            StopAllCoroutines();
            sceneConfirmation?.TrySetCanceled();
            sceneConfirmation = null;
            sceneDialog?.RemoveFromHierarchy();
            sceneDialog = null;
        }

        async Task<AssemblySceneConfirmation> ConfirmSceneAsync(string executionId, string requester)
        {
            if (!isActiveAndEnabled || sceneConfirmation != null)
                throw new InvalidOperationException("현장 준비 확인 화면을 열 수 없습니다.");
            if (string.IsNullOrWhiteSpace(requester))
                throw new InvalidOperationException("요청자가 기록되지 않은 작업입니다. 요청자를 입력해 새 작업을 등록하세요.");
            var host = GetComponent<UIDocument>().rootVisualElement.Q<VisualElement>("job-detail");
            if (host == null) throw new InvalidOperationException("작업 상세 영역을 찾을 수 없습니다.");
            var completion = new TaskCompletionSource<AssemblySceneConfirmation>();
            sceneConfirmation = completion;
            var panel = new VisualElement();
            sceneDialog = panel;
            panel.AddToClassList("scene-confirmation");
            panel.AddToClassList("scene-confirmation--inline");
            var title = new Label("현장 준비 확인 · 작업 " + ShortJobId(actionJobId));
            title.AddToClassList("scene-confirmation__title");
            panel.Add(title);
            var instruction = new Label("요청자 " + requester + " · 이번 PCB의 준비 상태를 직접 확인한 뒤 실행하세요.") { enableRichText = false };
            instruction.AddToClassList("scene-confirmation__instruction");
            panel.Add(instruction);
            var gripper = new Toggle { text = "그리퍼가 비어 있습니다" };
            var pcb = new Toggle { text = "PCB의 조립 슬롯이 비어 있습니다" };
            var tray = new Toggle { text = "트레이에 부품 25개가 준비되어 있습니다" };
            var fixture = new Toggle { text = "고정 지그와 작업영역을 확인했습니다" };
            var checks = new VisualElement();
            checks.AddToClassList("scene-confirmation__checks");
            checks.Add(gripper); checks.Add(pcb); checks.Add(tray); checks.Add(fixture);
            panel.Add(checks);
            var confirm = new Button(() =>
            {
                if (!completion.TrySetResult(new AssemblySceneConfirmation
                    {
                        operator_id = requester.Trim(), execution_id = executionId,
                        confirmed_unix = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000d
                    })) return;
                pageRouter?.OpenMonitor();
            }) { text = "확인하고 실행 요청" };
            confirm.AddToClassList("scene-confirmation__submit");
            var progress = new Label();
            progress.AddToClassList("scene-confirmation__progress");
            void Refresh()
            {
                int count = (gripper.value ? 1 : 0) + (pcb.value ? 1 : 0) +
                    (tray.value ? 1 : 0) + (fixture.value ? 1 : 0);
                progress.text = $"준비 확인 {count} / 4";
                confirm.SetEnabled(count == 4);
            }
            foreach (var toggle in new[] { gripper, pcb, tray, fixture })
            {
                toggle.AddToClassList("scene-confirmation__check");
                toggle.RegisterValueChangedCallback(_ =>
                {
                    toggle.EnableInClassList("scene-confirmation__check--checked", toggle.value);
                    Refresh();
                });
            }
            Refresh();
            panel.Add(progress);
            var actions = new VisualElement();
            actions.AddToClassList("scene-confirmation__actions");
            actions.Add(confirm);
            var cancel = new Button(() => completion.TrySetCanceled()) { text = "취소" };
            cancel.AddToClassList("scene-confirmation__cancel");
            actions.Add(cancel);
            panel.Add(actions);
            host.Add(panel);
            gripper.Focus();
            try { return await completion.Task; }
            finally
            {
                panel.RemoveFromHierarchy();
                if (sceneConfirmation == completion) { sceneConfirmation = null; sceneDialog = null; }
            }
        }

        double nextStatusRefresh;

        void Update()
        {
            if (!cached)
            {
                Build();
                if (!cached) return;
            }
            RefreshInterlocks();
            if (Time.realtimeSinceStartupAsDouble >= nextStatusRefresh)
            {
                nextStatusRefresh = Time.realtimeSinceStartupAsDouble + 0.25d;
                RefreshSelectedActions();
                var frame = uiMaster?.AssemblyProgress?.Latest;
                foreach (var job in jobs)
                    if (jobStatusLabels.TryGetValue(job.job_id, out var label))
                    {
                        bool live = frame?.JobId == job.job_id && (job.job_status == "RUNNING" || job.job_status == "PAUSED");
                        string text = live ? frame.DisplayStatus : StatusText(job.job_status);
                        int separator = text.IndexOf('·');
                        label.text = separator < 0 ? text : text.Substring(0, separator).Trim();
                        label.tooltip = text;
                        label.EnableInClassList("job-status--failed", live ? !string.IsNullOrEmpty(frame.ErrorCode) &&
                            frame.ErrorCode != "QUALITY_HOLD" && frame.ErrorCode != "SCENE_CONFIRMATION_REQUIRED" &&
                            frame.ErrorCode != "EXECUTION_CANCELLED" : job.job_status == "FAILED");
                    }
            }
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
            requestedBy = root.Q<TextField>("requested-by");
            startReason = root.Q<Label>("start-reason");
            start = root.Q<Button>("start-button");
            filterAll = root.Q<Button>("filter-all");
            filterQueue = root.Q<Button>("filter-queue");
            filterAttention = root.Q<Button>("filter-attention");
            filterDone = root.Q<Button>("filter-done");

            queryState = root.Q<Label>("job-query-state");
            selectedStatus = root.Q<Label>("selected-job-status");
            selectedName = root.Q<Label>("selected-job-product");
            selectedId = root.Q<Label>("selected-job-id");
            selectedProgress = root.Q<Label>("selected-job-progress");
            selectedAttempts = root.Q<Label>("selected-job-attempts");
            selectedResults = root.Q<Label>("selected-job-results");
            selectedReason = root.Q<Label>("selected-job-reason");
            refreshJobs = root.Q<Button>("job-refresh");
            selectedStart = root.Q<Button>("selected-job-start");
            selectedCancel = root.Q<Button>("selected-job-cancel");
            selectedForceCancel = root.Q<Button>("selected-job-force-cancel");
            if (selectedForceCancel != null) selectedForceCancel.clicked += () =>
            {
                if (selectedJobId != null) ForceCancelJob(selectedJobId);
            };
            selectedMonitor = root.Q<Button>("selected-job-monitor");
            selectedInspect = root.Q<Button>("selected-job-inspect");
            foreach (Label label in new[] { jobError, selectedName, selectedId, selectedReason, productName, productMeta })
                if (label != null) label.enableRichText = false;

            if (start != null) start.clicked += OnRegister;
            if (refreshJobs != null) refreshJobs.clicked += () =>
            {
                StartCoroutine(LoadJobs());
                if (selectedProduct == null) StartCoroutine(LoadProducts());
                else if (!requirementsLoaded) StartCoroutine(LoadRequirements(selectedProduct.product_id));
            };
            if (selectedStart != null) selectedStart.clicked += () => { var job = SelectedJob(); if (job != null) StartJob(job); };
            if (selectedCancel != null) selectedCancel.clicked += () =>
            {
                if (selectedJobId == null) return;
                if (SelectedJob()?.job_status == "PENDING") StartCoroutine(CancelJob(selectedJobId));
                else CancelActiveJob(selectedJobId);
            };
            if (selectedMonitor != null) selectedMonitor.clicked += () => pageRouter?.OpenMonitor();
            if (selectedInspect != null) selectedInspect.clicked += () => pageRouter?.OpenInspect(selectedJobId);
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
            RefreshJobError();
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
            refreshJobs?.SetEnabled(false);
            if (!jobsLoaded && string.IsNullOrEmpty(jobQueryError)) BuildJobs();
            using var request = UnityWebRequest.Get(ApiUrl("/api/v1/jobs?limit=20"));
            SetRuntimeModeHeader(request);
            request.timeout = 5;
            yield return request.SendWebRequest();

            if (isActiveAndEnabled)
            {
                if (request.result == UnityWebRequest.Result.Success)
                {
                    try
                    {
                        ApplyJobsResponse(request.downloadHandler.text);
                    }
                    catch (Exception)
                    {
                        SetJobError("조회 실패 · 서버 응답을 확인할 수 없습니다.");
                    }
                }
                else SetJobError("조회 실패 · 서버 연결을 확인하세요. (HTTP " + request.responseCode + ")");
            }
            jobsLoading = false;
            refreshJobs?.SetEnabled(true);
        }

        void ApplyJobsResponse(string json)
        {
            // 같은 응답의 행을 2초마다 재생성하면 글꼴 렌더링과 키보드 포커스가 초기화된다.
            if (json == lastJobsResponse && string.IsNullOrEmpty(jobQueryError))
            {
                RefreshSelectedActions();
                return;
            }
            Job[] response = JsonUtility.FromJson<JobListResponse>(json)?.data;
            if (response == null || Array.Exists(response, job => job == null || string.IsNullOrEmpty(job.job_id)
                || string.IsNullOrEmpty(job.job_status)))
                throw new FormatException("Invalid jobs response.");
            jobs = response;
            if (!string.IsNullOrEmpty(actionJobId) &&
                Array.Exists(jobs, job => job.job_id == actionJobId && job.job_status != "PENDING"))
                actionJobId = null;
            jobsLoaded = true;
            jobQueryError = null;
            RefreshJobError();
            BuildJobs();
            lastJobsResponse = json;
        }

        void SetJobError(string message)
        {
            jobQueryError = message;
            RefreshJobError();
            BuildJobs();
        }

        void RefreshJobError()
        {
            if (jobError == null) return;
            jobError.text = string.IsNullOrEmpty(jobActionError) ? jobQueryError ?? ""
                : jobActionError + (string.IsNullOrEmpty(jobQueryError) ? "" : "\n" + jobQueryError);
            jobError.style.display = string.IsNullOrEmpty(jobError.text) ? DisplayStyle.None : DisplayStyle.Flex;
            jobError.tooltip = jobError.text;
        }

        void BuildJobs()
        {
            if (jobList == null) return;
            string focusedJobId = (jobList.panel?.focusController?.focusedElement as VisualElement)?.userData as string;
            jobList.Clear();
            jobStatusLabels.Clear();
            if (!Array.Exists(jobs, job => job.job_id == selectedJobId && MatchesJob(job, selectedFilter)))
                selectedJobId = null;
            int visible = 0;
            foreach (Job job in jobs)
            {
                if (!MatchesJob(job, selectedFilter)) continue;
                visible++;
                VisualElement row = JobRow(job);
                jobList.Add(row);
                if (job.job_id == focusedJobId) row.Focus();
            }

            if (visible == 0)
                jobList.Add(new Label(!string.IsNullOrEmpty(jobQueryError) ? "조회가 복구되면 작업 목록이 표시됩니다."
                    : !jobsLoaded ? "작업 목록 조회 중…"
                    : jobs.Length == 0 ? "등록된 작업이 없습니다." : "해당 조건의 작업이 없습니다."));
            if (jobCount != null) jobCount.text = !jobsLoaded ? "—" : visible + "건 표시 / 최근 " + jobs.Length + "건";
            if (queryState != null) queryState.text = !string.IsNullOrEmpty(jobQueryError)
                ? (jobsLoaded ? "갱신 실패 · 마지막 조회 기록 표시 · 실행과 취소가 제한됩니다." : "조회 실패 · 새로고침으로 다시 시도하세요.")
                : !jobsLoaded ? "작업 목록 조회 중…" : jobs.Length == 0 ? "작업 없음 · 오른쪽에서 새 작업을 등록하세요."
                : "최근 20건 범위 · 2초마다 갱신 · 행을 선택하면 아래에 상세 표시";
            RefreshFilters();
            RefreshSelectedJob();
        }

        VisualElement JobRow(Job job)
        {
            var row = new Button(() => { if (sceneConfirmation != null) return; selectedJobId = job.job_id; BuildJobs(); });
            row.userData = job.job_id;
            row.AddToClassList("jobs-row");
            row.EnableInClassList("jobs-row--selected", job.job_id == selectedJobId);
            row.tooltip = ProductText(job) + " · " + job.job_id;

            var status = new Label(StatusText(job.job_status)) { enableRichText = false };
            status.AddToClassList("job-status");
            status.AddToClassList("job-status--" + job.job_status.ToLowerInvariant());
            status.style.width = 110;
            jobStatusLabels[job.job_id] = status;
            row.Add(status);
            var product = new VisualElement();
            product.AddToClassList("jobs-product-cell");
            var name = new Label(ProductText(job)) { enableRichText = false, tooltip = ProductText(job) };
            name.AddToClassList("tcell");
            product.Add(name);
            var id = new Label(ShortJobId(job.job_id)) { enableRichText = false };
            id.AddToClassList("jobs-row-id");
            product.Add(id);
            row.Add(product);
            AddCell(row, job.completed_quantity + " / " + job.requested_quantity, 130, true);
            AddCell(row, job.attempted_quantity + "회", 88, true);
            AddCell(row, ResultText(job), 160);
            AddCell(row, FormatTime(job.requested_at), 132);
            return row;
        }

        Job SelectedJob() => Array.Find(jobs, job => job.job_id == selectedJobId);

        void RefreshSelectedJob()
        {
            Job job = SelectedJob();
            if (selectedStatus != null)
            {
                selectedStatus.text = job == null ? "선택 전" : StatusText(job.job_status);
                foreach (string state in new[] { "running", "pending", "failed", "completed", "cancelled" })
                    selectedStatus.EnableInClassList("job-status--" + state,
                        job != null && string.Equals(job.job_status, state, StringComparison.OrdinalIgnoreCase));
            }
            if (selectedName != null) { selectedName.text = job == null ? "목록에서 작업을 선택하세요" : ProductText(job); selectedName.tooltip = selectedName.text; }
            if (selectedId != null) { selectedId.text = job == null ? "—" : "작업 " + ShortJobId(job.job_id) + " · 등록 " + FormatTime(job.requested_at); selectedId.tooltip = job == null ? "" : job.job_id + " · 요청자 " + (string.IsNullOrEmpty(job.requested_by) ? "기록 없음" : job.requested_by); }
            if (selectedProgress != null) selectedProgress.text = job == null ? "—" : job.completed_quantity + " / " + job.requested_quantity;
            if (selectedAttempts != null) selectedAttempts.text = job == null ? "—" : job.attempted_quantity + "회";
            if (selectedResults != null) selectedResults.text = job == null ? "—" : job.inspection_failed_quantity + "건 · " + job.failed_quantity + "건";
            RefreshSelectedActions();
        }

        void RefreshSelectedActions()
        {
            Job job = SelectedJob();
            bool pending = job?.job_status == "PENDING";
            string blocked = job == null ? "작업을 선택하세요." : StartBlockedReason(job);
            selectedStart?.SetEnabled(blocked == null);
            string forceReason = uiMaster?.Scenario?.GetControlBlockReason("force_cancel") ?? "실행 경로 없음";
            selectedForceCancel?.SetEnabled(!cancelInFlight && string.IsNullOrEmpty(jobQueryError) &&
                (job?.job_status == "RUNNING" || job?.job_status == "PAUSED") && string.IsNullOrEmpty(forceReason));
            if (selectedForceCancel != null)
            {
                selectedForceCancel.text = "관리자 기록 종료";
                selectedForceCancel.tooltip = string.IsNullOrEmpty(forceReason)
                    ? "설비 정지 확인 없는 기록 종료는 사용할 수 없습니다." : forceReason;
            }
            var frame = uiMaster?.AssemblyProgress?.Latest;
            bool matching = job != null && frame?.JobId == job.job_id;
            string cancelReason = pending ? "" : !matching ? "선택한 작업의 실행 상태를 확인 중입니다." :
                uiMaster?.Scenario?.GetControlBlockReason("cancel") ?? "실행 경로 없음";
            selectedCancel?.SetEnabled(string.IsNullOrEmpty(cancelReason) && !cancelInFlight &&
                (pending ? actionJobId != job.job_id : true) && string.IsNullOrEmpty(jobQueryError));
            if (selectedCancel != null)
            {
                selectedCancel.text = cancelInFlight ? "취소 결과 확인 중…" : pending ? "대기 작업 취소" : "작업 취소";
                selectedCancel.tooltip = string.IsNullOrEmpty(cancelReason)
                    ? pending ? "설비 상태와 무관하게 실행 전 대기열에서 취소합니다." : "취소를 요청하고 실제 정지와 기록 반영을 확인합니다."
                    : cancelReason;
            }
            if (selectedStatus != null && matching && (job.job_status == "RUNNING" || job.job_status == "PAUSED"))
                selectedStatus.text = frame.DisplayStatus;
            selectedMonitor?.SetEnabled((job?.job_status == "RUNNING" || job?.job_status == "PAUSED") && pageRouter != null);
            selectedInspect?.SetEnabled(job != null && job.attempted_quantity > 0 && pageRouter != null);
            if (selectedStart != null) { selectedStart.text = job != null && actionJobId == job.job_id ? "요청 처리 중…" : "작업 실행"; selectedStart.tooltip = blocked ?? "선택한 대기 작업을 실행합니다."; }
            if (selectedInspect != null) selectedInspect.tooltip = job != null && job.attempted_quantity > 0 ? "선택한 작업의 검사 기록을 엽니다." : "생산 시도가 있는 작업에서 확인할 수 있습니다.";
            if (selectedReason != null) selectedReason.text = job == null ? "선택한 작업의 진행과 가능한 동작을 확인합니다."
                : !string.IsNullOrEmpty(jobQueryError) ? "갱신 실패 · 마지막 조회 기록입니다. 새로고침 후 상태를 확인하세요."
                : pending ? blocked ?? "실행 요청 가능 · 설비 준비 미확인"
                : matching ? frame.DisplayStatus + (string.IsNullOrEmpty(cancelReason) ? " · 취소 가능" : " · 취소: " + cancelReason)
                : job.job_status == "RUNNING" ? "실행 상태 확인 중 · DB에는 실행 중으로 기록되어 있습니다."
                : "PASS만 목표 달성에 포함됩니다. 불합격과 실행 실패도 생산 시도 횟수에 포함됩니다.";
        }

        static string StatusText(string status) => status switch
        {
            "PENDING" => "실행 대기", "RUNNING" => "실행 중", "PAUSED" => "일시정지 또는 판정 대기", "COMPLETED" => "완료",
            "FAILED" => "실행 실패", "CANCELLED" => "취소", _ => "상태 확인 필요"
        };

        async void StartJob(Job job)
        {
            if (job == null || StartBlockedReason(job) != null) return;
            actionJobId = job.job_id;
            jobActionError = null;
            RefreshJobError();
            BuildJobs();
            try
            {
                await uiMaster.Scenario.RunQueuedAsync(job.job_id, executionId => ConfirmSceneAsync(executionId, job.requested_by));
            }
            catch (OperationCanceledException)
            {
                jobActionError = null;
                RefreshJobError();
            }
            catch (Exception exception)
            {
                jobActionError = "작업 실행 실패 · " + ShortJobId(job.job_id) + " · " + exception.Message;
                RefreshJobError();
                uiMaster?.RecordEvent("작업", jobActionError, true);
            }
            finally
            {
                actionJobId = null;
                if (isActiveAndEnabled) StartCoroutine(LoadJobs());
            }
        }

        bool cancelInFlight;

        async void ForceCancelJob(string jobId)
        {
            if (cancelInFlight || uiMaster?.Scenario == null || SelectedJob()?.job_id != jobId) return;
            cancelInFlight = true;
            jobActionError = null;
            RefreshJobError();
            try
            {
                await uiMaster.Scenario.ForceCancelAsync(jobId);
                uiMaster.RecordEvent("작업", "생산 기록 강제 취소 · 설비 정지 미확인 · " + ShortJobId(jobId), true);
            }
            catch (Exception error)
            {
                jobActionError = "강제 취소 미확정 · " + error.Message;
                RefreshJobError();
            }
            finally
            {
                cancelInFlight = false;
                if (isActiveAndEnabled) StartCoroutine(LoadJobs());
            }
        }

        async void CancelActiveJob(string jobId)
        {
            if (cancelInFlight || uiMaster?.AssemblyProgress?.Latest?.JobId != jobId ||
                uiMaster?.Scenario == null || !string.IsNullOrEmpty(uiMaster.Scenario.GetControlBlockReason("cancel"))) return;
            cancelInFlight = true;
            jobActionError = null;
            RefreshJobError();
            try
            {
                await uiMaster.Scenario.CancelAsync();
                uiMaster.RecordEvent("작업", "작업 취소 완료 · " + ShortJobId(jobId), false);
            }
            catch (Exception error)
            {
                jobActionError = "취소 미확정 · " + ShortJobId(jobId) + " · " + error.Message;
                RefreshJobError();
            }
            finally
            {
                cancelInFlight = false;
                if (isActiveAndEnabled) StartCoroutine(LoadJobs());
            }
        }

        IEnumerator CancelJob(string jobId)
        {
            Job job = Array.Find(jobs, item => item.job_id == jobId);
            if (job?.job_status != "PENDING" || actionJobId == jobId || cancelInFlight
                || !string.IsNullOrEmpty(jobQueryError)) yield break;
            cancelInFlight = true;
            jobActionError = null;
            RefreshJobError();
            BuildJobs();
            try
            {
                using var request = UnityWebRequest.Delete(ApiUrl("/api/v1/jobs/" + Uri.EscapeDataString(jobId)));
                SetRuntimeModeHeader(request);
                request.timeout = 5;
                yield return request.SendWebRequest();
                if (request.result != UnityWebRequest.Result.Success)
                {
                    string reason = request.responseCode == 409 ? "작업 상태가 변경되어 대기 취소할 수 없습니다."
                        : request.responseCode == 503 ? "서버의 대기 취소 처리에 실패했습니다."
                        : "응답 미확인 · 갱신된 작업 상태를 확인하세요.";
                    jobActionError = "대기 작업 취소 미완료 · " + ShortJobId(jobId) + " · " + reason + " (HTTP " + request.responseCode + ")";
                    RefreshJobError();
                    uiMaster?.RecordEvent("작업", jobActionError, true);
                }
            }
            finally { cancelInFlight = false; }
            if (isActiveAndEnabled) yield return LoadJobs();
        }

        static void AddCell(VisualElement row, string text, float width, bool numeric = false)
        {
            var cell = new Label(text) { enableRichText = false, tooltip = text };
            cell.AddToClassList("tcell");
            if (numeric) cell.AddToClassList("tcell--num");
            cell.style.width = width;
            // 동적으로 추가된 셀은 최초 레이아웃 이후 위치에 맞춰 텍스트 메시를 다시 그린다.
            cell.RegisterCallback<GeometryChangedEvent>(_ => cell.MarkDirtyRepaint());
            row.Add(cell);
        }

        static bool MatchesJob(Job job, string filter)
        {
            return filter == "ALL"
                || filter == "QUEUE" && (job.job_status == "PENDING" || job.job_status == "RUNNING" || job.job_status == "PAUSED")
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

        string ResultText(Job job)
        {
            if (job.inspection_failed_quantity > 0) return "불합격 " + job.inspection_failed_quantity + (job.failed_quantity > 0 ? " · 실행 실패 " + job.failed_quantity : "");
            if (job.failed_quantity > 0) return "실행 실패 " + job.failed_quantity;
            if (job.job_status == "FAILED") return "Job 실패 · 사유 미제공";
            if (job.job_status == "CANCELLED") return "사용자 취소";
            if (job.job_status == "COMPLETED") return "완료";
            if (job.job_status == "PENDING") return StartBlockedReason(job) ?? "실행 요청 가능 · 설비 준비 미확인";
            return "시도 " + job.attempted_quantity;
        }

        string StartBlockedReason(Job job)
        {
            if (job.job_status == "PAUSED") return "일시정지 또는 판정 대기 · 운전 화면에서 상태를 확인하세요.";
            if (job.job_status != "PENDING" && job.job_status != "RUNNING") return "완료된 작업은 실행할 수 없습니다.";
            if (!string.IsNullOrEmpty(jobQueryError)) return "작업 상태를 다시 조회한 뒤 실행하세요.";
            if (cancelInFlight) return "취소 요청 처리 중";
            if (!string.IsNullOrEmpty(actionJobId))
                return actionJobId == job.job_id ? "요청 처리 중" : "다른 요청 처리 중";
            Job runningJob = Array.Find(jobs, item => item.job_status == "RUNNING" || item.job_status == "PAUSED");
            if (runningJob != null && runningJob.job_id != job.job_id)
                return "JOB " + ShortJobId(runningJob.job_id) + " 실행 중";
            if (uiMaster?.Scenario == null) return "실행 경로 없음";
            if (uiMaster.Scenario.IsRunning) return "다른 작업 실행 중";
            return null;
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
                    SetProductError("등록 가능한 제품이 없습니다.");
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
                requirementsLoaded = requirements.Length > 0 && Array.TrueForAll(requirements,
                    item => item != null && !string.IsNullOrEmpty(item.part_id) &&
                        item.required_quantity > 0 && item.stock_quantity >= 0 && item.shortage_quantity >= 0);
                if (!requirementsLoaded) productError = "부품 요구사항 미확인 · 빈 응답 또는 누락";
                requirementsQueriedAt = requirementsLoaded ? DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") : null;
                BuildSlots();
                interlockSignature = null;
            }, SetProductError);
        }

        IEnumerator Get(string path, Action<string> onSuccess, Action<string> onError)
        {
            using var request = UnityWebRequest.Get(ApiUrl(path));
            SetRuntimeModeHeader(request);
            request.timeout = 5;
            yield return request.SendWebRequest();
            if (!isActiveAndEnabled) yield break;

            if (request.result != UnityWebRequest.Result.Success)
            {
                onError("조회 실패 · 서버 연결을 확인하세요. (HTTP " + request.responseCode + ")");
                yield break;
            }

            try { onSuccess(request.downloadHandler.text); }
            catch (Exception) { onError("조회 실패 · 서버 응답을 확인할 수 없습니다."); }
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
                FR5EmptyState.Present(productName, string.IsNullOrEmpty(productError) ? "제품 조회 중…" : "제품 조회 실패");
                FR5EmptyState.Detail(productMeta, productError ?? "제품 조회 중");
                FR5EmptyState.Detail(productSlotCount, "제품 구성 확인 전");
                return;
            }

            FR5EmptyState.Present(productName, selectedProduct.product_name);
            FR5EmptyState.Detail(productMeta,
                selectedProduct.product_code + " · " + selectedProduct.product_version);
            int slotCount = selectedProduct.slots?.Length ?? 0;
            int partCount = selectedProduct.slots == null ? 0 : GroupByPart(selectedProduct.slots).Count;
            FR5EmptyState.Detail(productSlotCount, selectedProduct.slots == null
                ? "제품 슬롯 구성 미확인" : slotCount + " 슬롯 · " + partCount + " 부품");
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
                item => requirementsLoaded && item != null && string.Equals(item.part_id, group.PartId, StringComparison.OrdinalIgnoreCase));
            var stockText = new Label(stock == null ? "재고 미확인" : "조회 당시 재고 " + stock.stock_quantity);
            stockText.tooltip = stock == null ? "유효한 재고 조회 결과 없음" : "DB 조회 " + requirementsQueriedAt + " · 실시간 실물 수량 아님";
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
                ready ? productPreview.width + "×" + productPreview.height : "미리보기 없음");
            if (!ready) FR5EmptyState.Detail(previewDesc, "조립체 미리보기가 연결되지 않았습니다.");
        }

        void RefreshInterlocks()
        {
            if (interlockList == null) return;

            bool productReady = selectedProduct?.slots != null && selectedProduct.slots.Length > 0 && requirementsLoaded &&
                Array.TrueForAll(selectedProduct.slots, slot => slot != null && !string.IsNullOrEmpty(slot.part_id) &&
                    Array.Exists(requirements, item => item != null && string.Equals(item.part_id, slot.part_id, StringComparison.OrdinalIgnoreCase)));
            bool stockReady = productReady && Array.TrueForAll(requirements, item => item.shortage_quantity == 0);
            bool modeKnown = uiMaster != null;
            string signature = productReady + "|" + stockReady + "|" + modeKnown + "|" + registerInFlight;
            if (signature == interlockSignature)
            {
                ApplyRegisterState(productReady, stockReady, modeKnown);
                return;
            }

            interlockSignature = signature;
            interlockList.Clear();
            AddCheck("제품 · 요구 부품 조회", productReady);
            AddCheck("조회 당시 목표 수량분 재고", stockReady);
            AddCheck("요청 모드 확인", modeKnown);
            ApplyRegisterState(productReady, stockReady, modeKnown);
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

        void ApplyRegisterState(bool productReady, bool stockReady, bool modeKnown)
        {
            bool hasRequester = !string.IsNullOrWhiteSpace(pendingRequestedBy ?? requestedBy?.value);
            requestedBy?.SetEnabled(!registerInFlight && pendingJobId == null);
            bool ready = productReady && stockReady && modeKnown && hasRequester && !registerInFlight;
            start?.SetEnabled(ready);
            if (start != null) start.text = registerInFlight ? "등록 중…" : "작업 등록";
            if (startReason == null || registerInFlight) return;
            startReason.text = !productReady
                ? productError ?? "제품과 재고를 조회하고 있습니다."
                : !stockReady
                ? "목표 수량에 필요한 재고가 부족합니다."
                : !modeKnown
                ? "요청 모드를 확인할 수 없습니다."
                : !hasRequester ? "요청자 이름을 입력하세요."
                : "등록한 작업은 실행 대기 상태로 추가됩니다.";
            if (!string.IsNullOrEmpty(registrationResult))
                startReason.text = registrationResult + "\n" + startReason.text;
        }

        void OnRegister()
        {
            if (!registerInFlight && selectedProduct != null)
                StartCoroutine(RegisterJob());
        }

        IEnumerator RegisterJob()
        {
            string requester = pendingRequestedBy ?? requestedBy?.value?.Trim();
            if (string.IsNullOrWhiteSpace(requester)) yield break;
            pendingRequestedBy = requester;
            registerInFlight = true;
            registrationResult = null;
            if (startReason != null) startReason.text = "작업 등록 중…";
            interlockSignature = null;
            pendingJobId ??= Guid.NewGuid().ToString();

            var command = new StartCommand
            {
                command = "start",
                job_id = pendingJobId,
                requested_by = pendingRequestedBy,
                product_code = selectedProduct.product_code,
                product_version = selectedProduct.product_version,
                requested_quantity = quantity,
                recipe_version = RecipeVersion,
            };

            using var request = new UnityWebRequest(ApiUrl("/api/v1/assemblies"), "POST");
            SetRuntimeModeHeader(request);
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
                        registrationResult = "작업 등록 완료 · " + ShortJobId(result.job_id) + " · " + result.status;
                        uiMaster?.RecordEvent("작업", registrationResult, false);
                        pendingJobId = null;
                        pendingRequestedBy = null;
                        StartCoroutine(LoadJobs());
                    }
                    catch (Exception)
                    {
                        registrationResult = "등록 응답을 확인하지 못했습니다. 같은 Job ID로 재시도합니다.";
                    }
                }
                else
                    registrationResult = "작업 등록 실패 · HTTP " + request.responseCode + " · 같은 Job ID로 재시도합니다.";
            }

            registerInFlight = false;
            interlockSignature = null;
        }

        string ApiUrl(string path) => mainServerBaseUrl.TrimEnd('/') + path;

        void SetRuntimeModeHeader(UnityWebRequest request) =>
            request.SetRequestHeader("X-Runtime-Mode",
                uiMaster == null ? "" : uiMaster.OperatingMode.ToString().ToLowerInvariant());

        [ContextMenu("API/Self Check")]
        void ApiSelfCheck()
        {
            Debug.Assert(ApiUrl("/api/v1/jobs") == "http://127.0.0.1:8000/api/v1/jobs");
            Debug.Assert(MatchesJob(new Job { job_status = "PENDING" }, "QUEUE"));
            Debug.Assert(!MatchesJob(new Job { job_status = "COMPLETED" }, "QUEUE"));
        }
    }
}
