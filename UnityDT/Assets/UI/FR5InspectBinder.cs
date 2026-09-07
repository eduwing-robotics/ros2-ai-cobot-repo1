// 역할: INSPECT 페이지(FR5Inspect.uxml)의 카메라 상태와 판정 표시를 담당한다.
//
//   실연결 : 모드 · 비전 스트리밍 상태 · 프레임 경과 · 유닛 판정·불량·증거
//   항목별 결과는 MainServer의 보관 JSON을 읽으며 의심 항목은 확정 불량과 구분한다.
//
// 카메라 텍스처 자체는 CamVisionReceiver 가 `camera-image` Image 요소에 직접 넣는다.
// 이 바인더는 "지금 영상이 살아 있는가"와 판정 표시만 맡는다.

using System;
using System.Collections;
using System.IO;
using System.Globalization;
using MainUnity.Runtime.Camera;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UIElements;

namespace MainUnity.UI
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(UIDocument))]
    public sealed class FR5InspectBinder : MonoBehaviour
    {
        const string MockPassImagePath = "InspectionSamples/mock-pass.jpg";
        const string MockInspectPassImagePath = "InspectionSamples/mock-inspect-pass-board-1.png";
        const string MockFailImagePath = "InspectionSamples/mock-fail.jpg";

        [Serializable] sealed class AssemblyResponse { public AssemblySnapshot data; }
        [Serializable] sealed class UnitsResponse { public Unit[] data; }
        [Serializable] sealed class AssemblySnapshot { public string job_id; public int unit_id; }
        [Serializable] sealed class Unit
        {
            public int unit_id;
            public int unit_sequence_in_job;
            public string unit_status;
            public string inspection_result;
            public string inspection_image_path;
            public string inspected_at;
            public Defect[] defects;
            public Inspection inspection;
            public string inspection_error;
            public string inspection_image_url;
        }
        [Serializable] sealed class Defect { public string slot_code; public string defect_type; }
        [Serializable] sealed class Inspection { public InspectionResult result; }
        [Serializable] sealed class InspectionResult { public Slot[] slots; public Finding[] findings; }
        [Serializable] sealed class Slot { public string slot_code; public string part_name; public string decision; }
        [Serializable] sealed class Finding
        {
            public string slot_code;
            public string primary_defect_name_ko;
            public string[] details;
            public string authority;
            public bool confirmed_defect;
        }

        [Header("데이터 소스")]
        [SerializeField] UIMaster uiMaster;
        [SerializeField] CamVisionReceiver vision;
        [SerializeField] string mainServerBaseUrl = "http://127.0.0.1:8000";

        [Tooltip("이 시간을 넘겨 프레임이 없으면 영상 없음으로 봅니다.")]
        [SerializeField] float staleSeconds = 2f;

        VisualElement cameraEmpty, checkList, defectGrid, unitStrip;
        Image evidenceImage, liveImage;
        Label cameraStats, cameraEmptyDesc, cameraEmptyTitle, cameraSource, cameraNote;
        Label verdictValue, verdictScore, defectSql, unitsSummary, jobSummary, inspectionContext, inspectionMessage;
        Button refreshButton, liveButton, evidenceButton;
        bool cached, hasEvidence, queryFailed, hasSelection;
        bool showLiveVideo = true;
        double nextVisionRefresh;
        Coroutine loadRoutine, evidenceRoutine;
        Texture2D evidenceTexture;
        string evidenceStats;
        string evidenceMessage;
        string requestedJobId;

        void OnEnable() => cached = false;

        void OnDisable()
        {
            if (loadRoutine != null) StopCoroutine(loadRoutine);
            loadRoutine = null;
            StopEvidenceLoad();
            ClearEvidence();
            if (refreshButton != null) refreshButton.clicked -= BeginLoad;
            if (liveButton != null) liveButton.clicked -= SelectLive;
            if (evidenceButton != null) evidenceButton.clicked -= SelectEvidence;
        }

        void Update()
        {
            // UIDocument 는 활성화된 뒤에야 rootVisualElement 를 만든다.
            if (!cached) { Build(); if (!cached) return; }
            ResolveReferences();
            if (Time.realtimeSinceStartupAsDouble < nextVisionRefresh) return;
            nextVisionRefresh = Time.realtimeSinceStartupAsDouble + 0.25d;
            RefreshVision();
        }

        void ResolveReferences()
        {
            if (uiMaster == null) uiMaster = GetComponentInParent<UIMaster>();
            if (vision == null && uiMaster != null) vision = uiMaster.VisionImage;
            // 페이지 재진입으로 재생성된 Image에 기존 수신기를 다시 연결한다.
            vision?.SetTargetImage(liveImage);
        }

        void Build()
        {
            VisualElement root = GetComponent<UIDocument>().rootVisualElement;
            if (root == null) return;

            cameraEmpty = root.Q<VisualElement>("camera-empty");
            evidenceImage = root.Q<Image>("evidence-image");
            cameraEmptyDesc = root.Q<Label>("camera-empty-desc");
            liveImage = root.Q<Image>("camera-image");
            cameraEmptyTitle = root.Q<Label>("camera-empty-title");
            cameraSource = root.Q<Label>("camera-source");
            cameraNote = root.Q<Label>("camera-note");
            inspectionContext = root.Q<Label>("inspection-context");
            inspectionMessage = root.Q<Label>("inspection-message");
            refreshButton = root.Q<Button>("inspect-refresh");
            liveButton = root.Q<Button>("camera-live");
            evidenceButton = root.Q<Button>("camera-evidence");
            if (refreshButton != null) refreshButton.clicked += BeginLoad;
            if (liveButton != null) liveButton.clicked += SelectLive;
            if (evidenceButton != null) evidenceButton.clicked += SelectEvidence;
            cameraStats = root.Q<Label>("camera-stats");
            checkList = root.Q<VisualElement>("check-list");
            defectGrid = root.Q<VisualElement>("defect-grid");
            unitStrip = root.Q<VisualElement>("unit-strip");
            verdictValue = root.Q<Label>("verdict-value");
            verdictScore = root.Q<Label>("verdict-score");
            defectSql = root.Q<Label>("defect-sql");
            unitsSummary = root.Q<Label>("units-summary");
            jobSummary = root.Q<Label>("job-id");

            if (inspectionContext != null) inspectionContext.enableRichText = false;
            if (inspectionMessage != null) inspectionMessage.enableRichText = false;
            cached = true;
            nextVisionRefresh = 0d;
            BeginLoad();
        }

        void BeginLoad()
        {
            if (loadRoutine == null && isActiveAndEnabled) loadRoutine = StartCoroutine(Load());
        }

        internal void ShowJob(string jobId)
        {
            if (string.IsNullOrEmpty(jobId)) return;
            requestedJobId = jobId;
            if (loadRoutine != null) StopCoroutine(loadRoutine);
            loadRoutine = null;
            if (cached) BeginLoad();
        }

        IEnumerator Load()
        {
            queryFailed = false;
            ShowState("조회 중", "검사 기록을 불러오고 있습니다.");
            refreshButton?.SetEnabled(false);
            try
            {
                string jobId = requestedJobId;
                int unitId = 0;
                if (string.IsNullOrEmpty(jobId))
                {
                    AssemblySnapshot snapshot = null;
                    yield return Get("/api/v1/assemblies/current", json => snapshot = JsonUtility.FromJson<AssemblyResponse>(json)?.data);
                    // 실패는 Get 경계에서 표시했다. 빈 성공 응답으로 덮어쓰지 않는다.
                    if (!isActiveAndEnabled || queryFailed) yield break;
                    if (snapshot == null || string.IsNullOrEmpty(snapshot.job_id))
                    {
                        ShowState("작업 없음", "현재 조회할 작업이 없습니다. 작업 화면에서 검사할 작업을 선택하세요.");
                        yield break;
                    }
                    jobId = snapshot.job_id;
                    unitId = snapshot.unit_id;
                }

                Unit[] units = null;
                yield return Get("/api/v1/jobs/" + Uri.EscapeDataString(jobId) + "/units",
                    json =>
                    {
                        units = JsonUtility.FromJson<UnitsResponse>(json)?.data;
                        if (units == null || Array.Exists(units, unit => unit == null ||
                            (unit.defects != null && Array.Exists(unit.defects, defect => defect == null))))
                            throw new FormatException("Invalid inspection units.");
                    });
                if (!isActiveAndEnabled || queryFailed) yield break;
                Unit selected = Array.Find(units, unit => unit.unit_id == unitId);
                if (selected == null && units.Length > 0) selected = units[units.Length - 1];
                if (selected == null)
                    ShowState("생산 기록 없음", "선택한 작업에 아직 생산 시도가 없습니다. 실행 후 새로고침하세요.");
                else ShowUnits(jobId, units, selected);
            }
            finally
            {
                loadRoutine = null;
                refreshButton?.SetEnabled(true);
            }
        }

        IEnumerator Get(string path, Action<string> onSuccess)
        {
            using var request = UnityWebRequest.Get(ApiUrl(path));
            request.SetRequestHeader("X-Runtime-Mode", uiMaster == null ? "" : uiMaster.OperatingMode.ToString().ToLowerInvariant());
            request.timeout = 5;
            yield return request.SendWebRequest();
            if (!isActiveAndEnabled) yield break;
            if (request.result == UnityWebRequest.Result.Success)
            {
                try { onSuccess(request.downloadHandler.text); }
                catch (Exception)
                {
                    queryFailed = true;
                    ShowState("조회 실패", "검사 기록의 응답 형식을 확인할 수 없습니다. 새로고침 후에도 반복되면 서버를 확인하세요.", true);
                }
            }
            else
            {
                queryFailed = true;
                ShowState("조회 실패", request.responseCode == 0
                    ? "서버에 연결할 수 없습니다. 연결 상태를 확인한 뒤 새로고침하세요."
                    : "검사 기록을 불러오지 못했습니다. 잠시 후 새로고침하세요.", true);
                if (inspectionMessage != null)
                    inspectionMessage.tooltip = "HTTP " + request.responseCode + " · " + request.error;
            }
        }

        void ShowUnits(string jobId, Unit[] units, Unit selected)
        {
            hasSelection = true;
            showLiveVideo = false;
            FR5EmptyState.Present(jobSummary, "생산 시도 #" + selected.unit_sequence_in_job);
            if (jobSummary != null) jobSummary.tooltip = "Job " + jobId + " · Unit " + selected.unit_id;
            if (inspectionContext != null)
            {
                inspectionContext.text = "선택한 생산 시도 #" + selected.unit_sequence_in_job;
                inspectionContext.tooltip = "Job " + jobId + " · Unit " + selected.unit_id;
            }
            if (unitsSummary != null)
                unitsSummary.text = "총 " + units.Length + "회 · 선택 #" + selected.unit_sequence_in_job + " · 좌우로 이동해 선택";
            string result = string.IsNullOrEmpty(selected.inspection_result) ? "PENDING" : selected.inspection_result;
            bool pending = result == "PENDING";
            string verdict = pending ? (selected.unit_status == "FAILED" ? "검사 미완료" : "검사 대기") : result;
            SetVerdict(result == "UNKNOWN" ? "판정 보류" : verdict, result == "FAIL", pending || result == "UNKNOWN");
            if (inspectionMessage != null)
            {
                inspectionMessage.text = result switch
                {
                    "PASS" => "검사 합격 · 기록된 판정입니다.",
                    "FAIL" => "검사 불합격 · 아래 불량 위치를 확인하세요.",
                    "UNKNOWN" => "검사 완료 · 판정 보류. 의심 항목은 확정 불량이 아닙니다.",
                    _ => selected.unit_status == "FAILED" ? "실행이 실패하여 검사 판정이 기록되지 않았습니다." :
                        "아직 검사 판정이 기록되지 않았습니다. 완료 후 새로고침하세요."
                };
                inspectionMessage.tooltip = "";
            }
            string inspectedAt = "—";
            if (DateTimeOffset.TryParse(selected.inspected_at, CultureInfo.InvariantCulture,
                DateTimeStyles.AssumeUniversal, out var time))
                inspectedAt = time.ToLocalTime().ToString("yyyy-MM-dd HH:mm:ss");
            FR5EmptyState.Detail(verdictScore, inspectedAt);
            if (verdictScore != null) verdictScore.tooltip = selected.inspected_at ?? "검사 시각 기록 없음";
            checkList?.Clear();
            string execution = selected.unit_status switch
            {
                "RUNNING" => "실행 중", "COMPLETED" => "실행 완료", "FAILED" => "실행 실패", _ => "상태 확인 필요"
            };
            checkList?.Add(CheckLine("생산 시도 상태 · " + execution, selected.unit_status == "FAILED"));

            Defect[] defects = selected.defects ?? Array.Empty<Defect>();
            defectGrid?.Clear();
            if (defects.Length == 0)
                defectGrid?.Add(CheckLine(pending ? "검사 완료 후 불량 내역을 확인할 수 있습니다." :
                    result == "FAIL" ? "불합격 판정이지만 상세 불량 내역은 없습니다." : "기록된 불량이 없습니다.", false));
            foreach (Defect defect in defects)
            {
                if (selected.inspection?.result?.findings != null) continue;
                var item = new Label(defect.slot_code + " · " + defect.defect_type) { enableRichText = false };
                item.tooltip = item.text;
                item.AddToClassList("slotchip");
                item.AddToClassList("slotchip--bad");
                defectGrid?.Add(item);
            }
            InspectionResult detail = selected.inspection?.result;
            if (detail?.slots != null)
            {
                foreach (Slot slot in detail.slots)
                {
                    if (slot == null) continue;
                    checkList?.Add(CheckLine(slot.slot_code + " · " + slot.part_name + " · " + slot.decision, false));
                }
            }
            if (detail?.findings != null)
            {
                foreach (Finding finding in detail.findings)
                {
                    if (finding == null) continue;
                    var item = new Label(finding.slot_code + " · " + finding.primary_defect_name_ko
                        + (finding.confirmed_defect ? " · 확정" : " · 의심")) { enableRichText = false };
                    item.tooltip = finding.authority + "\n" + string.Join("\n", finding.details ?? Array.Empty<string>());
                    item.AddToClassList("slotchip");
                    if (finding.confirmed_defect) item.AddToClassList("slotchip--bad");
                    defectGrid?.Add(item);
                }
            }
            if (!string.IsNullOrEmpty(selected.inspection_error))
                checkList?.Add(CheckLine("상세 검사 자료를 읽지 못했습니다. 새로고침하세요.", true));
            FR5EmptyState.Detail(defectSql, "확정 불량 " + defects.Length + "건");

            unitStrip?.Clear();
            foreach (Unit unit in units)
            {
                string unitResult = string.IsNullOrEmpty(unit.inspection_result) || unit.inspection_result == "PENDING"
                    ? (unit.unit_status == "FAILED" ? "미완료" : "검사 대기") : unit.inspection_result;
                Unit target = unit;
                var item = new Button(() => ShowUnits(jobId, units, target));
                item.AddToClassList("chip");
                var itemText = new Label("#" + unit.unit_sequence_in_job + "  " + unitResult) { enableRichText = false };
                itemText.AddToClassList("chip__text");
                item.Add(itemText);
                if (unit.unit_id == selected.unit_id) item.AddToClassList("chip--accent");
                if (unit.inspection_result == "FAIL") item.AddToClassList("chip--bad");
                unitStrip?.Add(item);
            }
            ShowEvidence(selected.inspection_image_path, selected.inspection_image_url, selected.unit_id);
            RefreshVision();
        }

        void SetVerdict(string text, bool error, bool pending = false)
        {
            if (verdictValue == null) return;
            FR5EmptyState.Present(verdictValue, text);
            verdictValue.EnableInClassList("inspect-verdict--status", text != "PASS" && text != "FAIL");
            verdictValue.EnableInClassList("bad", error);
            verdictValue.EnableInClassList("warn", pending);
        }

        void ShowState(string title, string message, bool error = false)
        {
            StopEvidenceLoad();
            ClearEvidence();
            hasSelection = false;
            showLiveVideo = true;
            SetVerdict(title, error);
            if (inspectionContext != null) { inspectionContext.text = "검사 기록"; inspectionContext.tooltip = ""; }
            if (inspectionMessage != null) { inspectionMessage.text = message; inspectionMessage.tooltip = ""; }
            FR5EmptyState.Dash(verdictScore);
            if (verdictScore != null) verdictScore.tooltip = "검사 시각 기록 없음";
            checkList?.Clear();
            defectGrid?.Clear();
            defectGrid?.Add(CheckLine("검사 기록을 선택하면 불량 위치가 표시됩니다.", false));
            unitStrip?.Clear();
            unitStrip?.Add(CheckLine("표시할 생산 시도 이력이 없습니다.", false));
            FR5EmptyState.Dash(defectSql);
            FR5EmptyState.Detail(unitsSummary, "기록 선택 전");
            FR5EmptyState.Dash(jobSummary);
            if (jobSummary != null) jobSummary.tooltip = "";
            RefreshVision();
        }

        string ApiUrl(string path) => mainServerBaseUrl.TrimEnd('/') + path;

        void ShowEvidence(string path, string imageUrl, int unitId)
        {
            StopEvidenceLoad();
            ClearEvidence();
            if (evidenceButton != null) evidenceButton.tooltip = "";
            evidenceMessage = "이 생산 시도에 저장된 검사 이미지가 없습니다.";
            if (evidenceImage == null) return;
            if (imageUrl == "/api/v1/units/" + unitId + "/inspection/image")
            {
                evidenceMessage = "검사 기록 이미지를 불러오고 있습니다.";
                evidenceRoutine = StartCoroutine(LoadEvidence(imageUrl, true));
                return;
            }
            if (string.IsNullOrEmpty(path)) return;
            if (path != MockPassImagePath && path != MockInspectPassImagePath && path != MockFailImagePath)
            {
                evidenceMessage = "현재 화면에서 열 수 없는 검사 이미지입니다.";
                if (evidenceButton != null) evidenceButton.tooltip = path;
                Debug.LogWarning("거부된 검사 이미지 경로: " + path, this);
                return;
            }
            evidenceMessage = "검사 기록 이미지를 불러오고 있습니다.";
            if (evidenceButton != null) evidenceButton.tooltip = path;
            evidenceRoutine = StartCoroutine(LoadEvidence(path));
        }

        IEnumerator LoadEvidence(string path, bool remote = false)
        {
            string filePath = Path.Combine(Application.streamingAssetsPath, path);
            using var request = UnityWebRequestTexture.GetTexture(remote ? ApiUrl(path) : new Uri(filePath).AbsoluteUri, true);
            if (remote)
                request.SetRequestHeader("X-Runtime-Mode", uiMaster == null ? "" : uiMaster.OperatingMode.ToString().ToLowerInvariant());
            request.timeout = 5;
            yield return request.SendWebRequest();
            if (!isActiveAndEnabled) yield break;
            if (request.result == UnityWebRequest.Result.Success)
            {
                evidenceTexture = DownloadHandlerTexture.GetContent(request);
                evidenceImage.image = evidenceTexture;
                evidenceImage.scaleMode = ScaleMode.ScaleToFit;
                evidenceImage.style.display = showLiveVideo ? DisplayStyle.None : DisplayStyle.Flex;
                evidenceStats = remote ? "보관된 검사 결과 이미지" : "기록에 연결된 샘플 이미지 · 실제 촬영 이미지 아님";
                hasEvidence = true;
            }
            else
            {
                evidenceMessage = "검사 이미지를 불러오지 못했습니다. 새로고침으로 다시 시도하세요.";
                Debug.LogWarning("검사 이미지 로드 실패: " + request.error, this);
            }
            evidenceRoutine = null;
            RefreshVision();
        }

        void StopEvidenceLoad()
        {
            if (evidenceRoutine != null) StopCoroutine(evidenceRoutine);
            evidenceRoutine = null;
        }

        void ClearEvidence()
        {
            if (evidenceImage != null)
            {
                evidenceImage.image = null;
                evidenceImage.style.display = DisplayStyle.None;
            }
            if (evidenceTexture != null) Destroy(evidenceTexture);
            evidenceTexture = null;
            evidenceStats = null;
            hasEvidence = false;
            evidenceMessage = null;
        }

        void SelectLive() { showLiveVideo = true; RefreshVision(); }
        void SelectEvidence() { showLiveVideo = false; RefreshVision(); }

        void RefreshVision()
        {
            bool received = vision != null && vision.HasReceivedImage;
            double age = received ? Math.Max(0d, Time.realtimeSinceStartupAsDouble - vision.LastReceiveTimeSeconds) : -1d;
            bool fresh = received && vision.isActiveAndEnabled && age < staleSeconds;
            bool visible = showLiveVideo ? fresh : hasEvidence;
            if (liveImage != null) liveImage.style.display = showLiveVideo ? DisplayStyle.Flex : DisplayStyle.None;
            if (evidenceImage != null) evidenceImage.style.display = !showLiveVideo && hasEvidence ? DisplayStyle.Flex : DisplayStyle.None;
            if (cameraEmpty != null) cameraEmpty.style.display = visible ? DisplayStyle.None : DisplayStyle.Flex;
            liveButton?.EnableInClassList("inspect-tab--on", showLiveVideo);
            evidenceButton?.EnableInClassList("inspect-tab--on", !showLiveVideo);
            evidenceButton?.SetEnabled(hasSelection);
            if (cameraSource != null)
                cameraSource.text = showLiveVideo ? "현재 영상 · LIVE" : hasEvidence ? "검사 기록 · SAMPLE" : "검사 기록 이미지";
            if (cameraEmptyTitle != null)
                cameraEmptyTitle.text = showLiveVideo ? (received ? "영상 수신 중단" : "영상 수신 대기") : "검사 기록 이미지";
            if (cameraEmptyDesc != null)
                cameraEmptyDesc.text = showLiveVideo ? "카메라 연결과 영상 수신 상태를 확인하세요." : evidenceMessage;
            if (cameraStats != null)
                cameraStats.text = showLiveVideo ? (received ? $"마지막 프레임 {age:0.0}초 전" : "수신 기록 없음") :
                    hasEvidence ? evidenceStats : "기록 이미지 표시 안 됨";
            if (cameraNote != null)
                cameraNote.text = showLiveVideo ? "현재 영상은 선택한 생산 시도의 검사 기록과 다를 수 있습니다." :
                    "선택한 생산 시도에 연결된 이미지입니다. 판정은 오른쪽 기록을 기준으로 확인하세요.";
        }

        /// <summary>판정 목록의 한 줄이다. 이상일 때만 색을 얻는다.</summary>
        static Label CheckLine(string text, bool bad)
        {
            var line = new Label(text) { enableRichText = false };
            if (bad) line.AddToClassList("bad");
            return line;
        }
    }
}
