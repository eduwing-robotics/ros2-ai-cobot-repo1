// 역할: INSPECT 페이지(FR5Inspect.uxml)의 카메라 상태와 판정 표시를 담당한다.
//
//   실연결 : 모드 · 비전 스트리밍 상태 · 프레임 경과 · 유닛 판정·불량·증거
//   미연결 : 항목별 검사 결과와 검출 좌표 — 계약이 생기기 전까지 지어내지 않는다.
//
// 카메라 텍스처 자체는 CamVisionReceiver 가 `camera-image` Image 요소에 직접 넣는다.
// 이 바인더는 "지금 영상이 살아 있는가"와 판정 표시만 맡는다.

using System;
using System.Collections;
using System.IO;
using MainUnity.Runtime.Camera;
using MainUnity.Runtime.Robot;
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
        }
        [Serializable] sealed class Defect { public string slot_code; public string defect_type; }

        [Header("데이터 소스")]
        [SerializeField] UIMaster uiMaster;
        [SerializeField] CamVisionReceiver vision;
        [SerializeField] string mainServerBaseUrl = "http://127.0.0.1:8000";

        [Tooltip("이 시간을 넘겨 프레임이 없으면 영상 없음으로 봅니다.")]
        [SerializeField] float staleSeconds = 2f;

        VisualElement cameraEmpty, detectBox, checkList, defectGrid, unitStrip;
        Image evidenceImage;
        Label cameraStats, cameraEmptyDesc, verdictTitle, verdictValue, verdictScore, defectSql, unitsSummary, jobSummary;
        bool cached, hasEvidence;
        Coroutine loadRoutine, evidenceRoutine;
        Texture2D evidenceTexture;
        string evidenceStats;
        string requestedJobId;

        void OnEnable() => cached = false;

        void OnDisable()
        {
            if (loadRoutine != null) StopCoroutine(loadRoutine);
            loadRoutine = null;
            StopEvidenceLoad();
            ClearEvidence();
        }

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
            evidenceImage = root.Q<Image>("evidence-image");
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
            BeginLoad();
        }

        /// <summary>판정은 검사 노드가 내린다. 화면이 PASS/FAIL 을 지어내면 그게 가장 위험하다.</summary>
        void BuildVerdict()
        {
            if (verdictTitle != null) verdictTitle.text = "INSPECTION RESULT";
            FR5EmptyState.Missing(verdictValue);
            FR5EmptyState.Dash(verdictScore);
            FR5EmptyState.Fill(checkList, "units.inspection_result 조회 필요 — 항목별 판정");
        }

        /// <summary>정상 슬롯은 행을 만들지 않는다는 DB 규칙을 화면도 따른다 — 불량만 색을 얻는다.</summary>
        void BuildDefects()
        {
            FR5EmptyState.Fill(defectGrid, "unit_defects 조회 필요 — 슬롯별 불량", 200f);
            FR5EmptyState.Detail(defectSql, "unit_defects(unit_id, slot_code, defect_type) 조회 경로 없음");
        }

        void BuildUnits()
        {
            FR5EmptyState.Fill(unitStrip, "units 조회 필요 — 대별 판정");
            FR5EmptyState.Dash(unitsSummary);
            FR5EmptyState.Missing(jobSummary);
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
            string jobId = requestedJobId;
            int unitId = 0;
            if (string.IsNullOrEmpty(jobId))
            {
                AssemblySnapshot snapshot = null;
                yield return Get("/api/v1/assemblies/current", json => snapshot = JsonUtility.FromJson<AssemblyResponse>(json)?.data);
                if (!isActiveAndEnabled) yield break;
                if (snapshot == null || string.IsNullOrEmpty(snapshot.job_id))
                {
                    ShowEmpty("활성 또는 최근 작업 없음");
                    loadRoutine = null;
                    yield break;
                }
                jobId = snapshot.job_id;
                unitId = snapshot.unit_id;
            }

            Unit[] units = null;
            yield return Get("/api/v1/jobs/" + jobId + "/units", json => units = JsonUtility.FromJson<UnitsResponse>(json)?.data ?? Array.Empty<Unit>());
            if (isActiveAndEnabled && units != null)
            {
                Unit selected = Array.Find(units, unit => unit.unit_id == unitId);
                if (selected == null && units.Length > 0) selected = units[units.Length - 1];
                if (selected == null) ShowEmpty("JOB #" + jobId + " 유닛 결과 없음");
                else ShowUnits(jobId, units, selected);
            }
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
            }
            else ShowEmpty("MainServer 조회 실패 · " + request.responseCode);
        }

        void ShowUnits(string jobId, Unit[] units, Unit selected)
        {
            FR5EmptyState.Present(jobSummary, "JOB #" + jobId + " · UNIT #" + selected.unit_id);
            if (unitsSummary != null) unitsSummary.text = units.Length + " UNIT";
            string result = string.IsNullOrEmpty(selected.inspection_result) ? "PENDING" : selected.inspection_result;
            if (verdictValue != null)
            {
                FR5EmptyState.Present(verdictValue, result);
                verdictValue.EnableInClassList("bad", result == "FAIL");
                verdictValue.EnableInClassList("warn", result == "PENDING");
            }
            FR5EmptyState.Detail(verdictScore, string.IsNullOrEmpty(selected.inspected_at) ? "검사 완료 대기" : selected.inspected_at);
            checkList?.Clear();
            // 실행 실패와 검사 불량은 다른 사실이지만, 둘 다 이상이므로 둘 다 색을 얻는다.
            // 색 없이 적으면 FAILED 가 정상 항목과 같은 무게로 보인다(Docs/ui-design.md의 색 역할).
            checkList?.Add(CheckLine("UNIT STATUS · " + selected.unit_status,
                selected.unit_status == "FAILED"));
            checkList?.Add(CheckLine("INSPECTION · " + result, result == "FAIL"));

            Defect[] defects = selected.defects ?? Array.Empty<Defect>();
            defectGrid?.Clear();
            if (defects.Length == 0) defectGrid?.Add(new Label("기록된 불량 없음"));
            foreach (Defect defect in defects)
            {
                var item = new Label(defect.slot_code + " · " + defect.defect_type);
                item.AddToClassList("slotchip");
                item.AddToClassList("slotchip--bad");
                defectGrid?.Add(item);
            }
            FR5EmptyState.Detail(defectSql, "unit_defects(unit_id=" + selected.unit_id + ") · " + defects.Length + " rows");

            unitStrip?.Clear();
            foreach (Unit unit in units)
            {
                string unitResult = string.IsNullOrEmpty(unit.inspection_result) ? "PENDING" : unit.inspection_result;
                Unit target = unit;
                var item = new Button();
                item.clicked += () => ShowUnits(jobId, units, target);
                item.AddToClassList("chip");
                // 글자는 .chip__text 자식이 맡는다. Button.text 로 직접 적으면 .chip 은
                // 상자만 꾸미고 글자는 기본값(15px · Normal · 자간 0 · 회색)으로 남아
                // 화면의 다른 칩과 규격이 어긋난다. 무엇보다 .chip--bad .chip__text 와
                // .chip--accent .chip__text 가 겨냥할 자식이 없어, FAIL 유닛의 글자가
                // 판정 색을 얻지 못하고 고른 유닛도 액센트를 얻지 못한다.
                var itemText = new Label("#" + unit.unit_sequence_in_job + "  " + unitResult);
                itemText.AddToClassList("chip__text");
                item.Add(itemText);
                // 선택은 "지금 여기"이므로 액센트다. 이전에는 chip--good(초록)이었는데,
                // 초록은 이 화면에서 합격을 뜻하므로 PENDING·FAIL 인 대를 골라도 합격처럼
                // 보였다. 판정은 판정 색으로만 말한다.
                if (unit.unit_id == selected.unit_id) item.AddToClassList("chip--accent");
                if (unit.inspection_result == "FAIL") item.AddToClassList("chip--bad");
                unitStrip?.Add(item);
            }

            ShowEvidence(selected.inspection_image_path);
        }

        void ShowEmpty(string message)
        {
            StopEvidenceLoad();
            ClearEvidence();
            FR5EmptyState.Missing(verdictValue);
            FR5EmptyState.Detail(verdictScore, message);
            FR5EmptyState.Fill(checkList, message);
            FR5EmptyState.Fill(defectGrid, message, 200f);
            FR5EmptyState.Fill(unitStrip, message);
            FR5EmptyState.Detail(defectSql, message);
            FR5EmptyState.Dash(unitsSummary);
            FR5EmptyState.Detail(jobSummary, message);
        }

        string ApiUrl(string path) => mainServerBaseUrl.TrimEnd('/') + path;

        void ShowEvidence(string path)
        {
            StopEvidenceLoad();
            ClearEvidence();
            if (evidenceImage == null || string.IsNullOrEmpty(path)) return;
            if (path != MockPassImagePath && path != MockInspectPassImagePath && path != MockFailImagePath)
            {
                Debug.LogWarning("거부된 검사 이미지 경로: " + path, this);
                return;
            }
            evidenceRoutine = StartCoroutine(LoadEvidence(path));
        }

        IEnumerator LoadEvidence(string path)
        {
            string filePath = Path.Combine(Application.streamingAssetsPath, path);
            using var request = UnityWebRequestTexture.GetTexture(new Uri(filePath).AbsoluteUri, true);
            request.timeout = 5;
            yield return request.SendWebRequest();
            if (!isActiveAndEnabled) yield break;
            if (request.result == UnityWebRequest.Result.Success)
            {
                evidenceTexture = DownloadHandlerTexture.GetContent(request);
                evidenceImage.image = evidenceTexture;
                evidenceImage.scaleMode = ScaleMode.ScaleToFit;
                evidenceImage.style.display = DisplayStyle.Flex;
                evidenceStats = "저장 캡처 · " + path;
                hasEvidence = true;
            }
            else Debug.LogWarning("검사 이미지 로드 실패: " + request.error, this);
            evidenceRoutine = null;
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
        }

        void RefreshVision()
        {
            bool received = vision != null && vision.HasReceivedImage;
            double age = vision != null ? Time.realtimeSinceStartupAsDouble - vision.LastReceiveTimeSeconds : -1;
            bool fresh = received && age >= 0 && age < staleSeconds;

            cameraEmpty?.EnableInClassList("empty", true);
            if (cameraEmpty != null)
                cameraEmpty.style.display = fresh || hasEvidence ? DisplayStyle.None : DisplayStyle.Flex;
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
                cameraStats.text = hasEvidence
                    ? evidenceStats
                    : fresh
                    ? $"수신 중 · 마지막 프레임 {age * 1000:0} ms 전"
                    : "수신 없음";
        }

        /// <summary>판정 목록의 한 줄이다. 이상일 때만 색을 얻는다.</summary>
        static Label CheckLine(string text, bool bad)
        {
            var line = new Label(text);
            if (bad) line.AddToClassList("bad");
            return line;
        }
    }
}
