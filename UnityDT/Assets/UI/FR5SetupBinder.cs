// 역할: SETUP에서 주입된 운전·보정 상태와 마지막 관측 Job의 설정 근거를 표시한다.
using System;
using System.Collections;
using MainUnity.Runtime.Camera;
using MainUnity.Runtime.Robot.Status;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UIElements;

namespace MainUnity.UI
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(UIDocument))]
    public sealed class FR5SetupBinder : MonoBehaviour
    {
        [SerializeField] UIMaster uiMaster;
        [Serializable] sealed class JobResponse { public Job data; }
        [Serializable] sealed class Job
        {
            public string job_id;
            public string product_code;
            public string product_version;
            public string recipe_version;
        }

        FR5ShellBinder shell;
        Label summary, reasons, mode, robot, gripper, cameraStatus, tray, board, recipe, product, slots;
        Label jobId, jobNote;
        Button refresh;
        Coroutine observations;
        UnityWebRequest jobRequest;
        string loadedJobId;
        Job loadedJob;
        string jobError;
        double nextJobQuery;

        void OnEnable() => observations = StartCoroutine(Observe());

        void OnDisable()
        {
            if (observations != null) StopCoroutine(observations);
            observations = null;
            if (jobRequest != null)
            {
                jobRequest.Abort();
                jobRequest.Dispose();
                jobRequest = null;
            }
            if (refresh != null) refresh.clicked -= RefreshJob;
            loadedJob = null;
            loadedJobId = null;
            jobError = null;
        }

        IEnumerator Observe()
        {
            var document = GetComponent<UIDocument>();
            while (document.rootVisualElement == null) yield return null;
            var root = document.rootVisualElement;
            if (uiMaster == null) uiMaster = GetComponentInParent<UIMaster>();
            shell = GetComponent<FR5ShellBinder>();
            summary = root.Q<Label>("setup-summary");
            reasons = root.Q<Label>("setup-reasons");
            mode = root.Q<Label>("setup-mode");
            robot = root.Q<Label>("setup-robot");
            gripper = root.Q<Label>("setup-gripper");
            cameraStatus = root.Q<Label>("setup-camera");
            tray = root.Q<Label>("setup-tray");
            board = root.Q<Label>("setup-board");
            recipe = root.Q<Label>("setup-recipe");
            product = root.Q<Label>("setup-product");
            slots = root.Q<Label>("setup-slots");
            jobId = root.Q<Label>("setup-job");
            jobNote = root.Q<Label>("setup-job-note");
            root.Query<Label>().ForEach(label => label.enableRichText = false);
            refresh = root.Q<Button>("setup-refresh");
            if (refresh != null) refresh.clicked += RefreshJob;
            nextJobQuery = 0d;
            var interval = new WaitForSecondsRealtime(0.25f);
            while (true)
            {
                RefreshObservations();
                RefreshJobQuery();
                yield return interval;
            }
        }

        void RefreshJob() => nextJobQuery = 0d;

        void RefreshObservations()
        {
            var status = uiMaster != null ? uiMaster.StatusManager : null;
            var frame = status != null ? status.Latest : null;
            bool fresh = status != null && status.HasFreshState;
            bool mock = uiMaster != null && uiMaster.IsSimulated;
            mode.text = uiMaster?.RobotMaster == null ? "미확인 · 로봇 연결 참조 없음" :
                (mock ? "MOCK · 시뮬레이션" : "REAL · 실제 설비") + "\n운전 중 모드 변경 불가";
            robot.text = !fresh ? "미확인 · 최신 로봇 상태 없음" :
                status.CanAcceptCommand(out string reason) ? "로봇 명령 수신 가능 · 셀 전체 준비 판정 아님" : "명령 수신 불가 · " + reason;
            robot.text += frame == null ? "" : "\n마지막 수신 " + Age(frame.ReceiveTimeSeconds);
            gripper.text = !fresh || !frame.GripperFeedbackValid ? "미확인 · 유효한 그리퍼 피드백 없음" :
                "오류 코드 " + frame.GripperFaultId + " · 동작 완료 값 " + frame.GripperMotionDone;
            if (mock) gripper.text += "\n시뮬레이션 피드백 · 실설비 확인 아님";
            var vision = uiMaster != null ? uiMaster.VisionImage : null;
            cameraStatus.text = vision == null ? "미확인 · 영상 수신기 연결 없음" :
                !vision.isActiveAndEnabled ? "현재 페이지에서 수신기 비활성 · INSPECT에서 확인" :
                !vision.HasReceivedImage ? "영상 수신 대기" :
                (vision.IsStreaming ? "영상 수신 중" : "영상 수신 지연") + " · " + Age(vision.LastReceiveTimeSeconds);

            var traySource = uiMaster != null ? uiMaster.Calibration : null;
            var boardSource = uiMaster != null ? uiMaster.BoardCalibration : null;
            tray.text = mock ? "사용 안 함 · 시뮬레이션 배치 사용" : traySource == null ? "미확인 · 트레이 좌표 수신기 없음" :
                (traySource.isActiveAndEnabled ? "" : "수신 비활성 · ") + traySource.ProgressDetail +
                "\n수신 " + Age(traySource.LastReceiveTime) + " · 반영 " + Age(traySource.LastAppliedTime);
            board.text = mock ? "사용 안 함 · 시뮬레이션 배치 사용" : boardSource == null ? "미확인 · 기판 좌표 수신기 없음" :
                (boardSource.isActiveAndEnabled ? "" : "수신 비활성 · ") + boardSource.ProgressDetail +
                "\n수신 " + Age(boardSource.LastReceiveTime) + " · 반영 " + Age(boardSource.LastAppliedTime) +
                "\n보정 ID " + (string.IsNullOrEmpty(boardSource.CalibrationId) ? "미확인" : boardSource.CalibrationId);

            bool calibrationError = !mock &&
                (traySource != null && (traySource.Progress == TrayPartCalibrator.ProgressState.Rejected ||
                    traySource.Progress == TrayPartCalibrator.ProgressState.ConfigurationError) ||
                 boardSource != null && (boardSource.Progress == BoardPartCalibrator.ProgressState.Rejected ||
                    boardSource.Progress == BoardPartCalibrator.ProgressState.ConfigurationError));
            bool serviceError = shell != null && (shell.ApiConnected == false || shell.SequencerConnected == false);
            bool robotError = status != null && status.State == RobotRunState.Error;
            bool blocked = robotError || calibrationError || serviceError;
            summary.text = blocked ? "준비 필요" : "확인 불가 · 미확인 항목 있음";
            summary.EnableInClassList("bad", blocked);
            // 연결·배치 반영 성공만으로 설비 reset과 안전 준비를 보장할 수 없다.
            reasons.text = (robotError ? "로봇 오류를 확인하세요. " : "") +
                (calibrationError ? "보정 결과를 확인하세요. " : "") +
                (serviceError ? "서비스 연결을 확인하세요. " : "") +
                "설비 전체 준비·reset 완료와 레시피 사전 검증 결과는 미확인입니다. 실제 실행 가능 여부는 실행 시 설비에서 확인합니다.";

            var progress = uiMaster != null ? uiMaster.AssemblyProgress?.Latest : null;
            string observedJob = progress?.JobId;
            bool matching = loadedJob != null && loadedJob.job_id == observedJob && shell?.ApiConnected == true;
            jobId.text = string.IsNullOrEmpty(observedJob) ? "관측 Job 없음" : observedJob;
            recipe.text = matching ? loadedJob.recipe_version : string.IsNullOrEmpty(progress?.RecipeVersion) ?
                "미확인 · 조립 진행 정보 없음" : progress.RecipeVersion + " · 마지막 실행 피드백";
            product.text = matching ? loadedJob.product_code + " · " + loadedJob.product_version : "미확인 · " +
                (string.IsNullOrEmpty(observedJob) ? "작업은 JOBS에서 등록·선택" : jobError ?? "작업 정보 조회 대기");
            jobNote.text = "마지막 관측 Job 기준 · 다음 작업의 적용 설정을 보장하지 않습니다." +
                (progress == null ? "" : "\n진행 수신 " + Age(progress.ReceiveTimeSeconds));
            var slotGroups = uiMaster != null ? uiMaster.Board?.AssemblySlots : null;
            int count = 0;
            if (slotGroups != null)
                foreach (var group in slotGroups)
                    if (group != null && group.Slots != null) count += group.Slots.Length;
            slots.text = slotGroups == null ? "미확인 · 트윈 기판 구성 없음" :
                "트윈 구성 " + slotGroups.Length + "종 · " + count + "개 슬롯 · 제품 레시피와 일치 검증 전";
        }

        void RefreshJobQuery()
        {
            string currentJob = uiMaster != null ? uiMaster.AssemblyProgress?.Latest?.JobId : null;
            if (currentJob != loadedJobId || shell?.ApiConnected != true)
            {
                loadedJob = null;
                jobError = null;
                nextJobQuery = 0d;
                loadedJobId = currentJob;
                if (jobRequest != null)
                {
                    jobRequest.Abort();
                    jobRequest.Dispose();
                    jobRequest = null;
                }
            }
            if (shell?.ApiConnected != true || string.IsNullOrEmpty(currentJob)) return;
            if (jobRequest != null)
            {
                if (!jobRequest.isDone) return;
                try
                {
                    loadedJob = jobRequest.result == UnityWebRequest.Result.Success
                        ? JsonUtility.FromJson<JobResponse>(jobRequest.downloadHandler.text)?.data : null;
                    if (loadedJob == null || loadedJob.job_id != currentJob)
                    {
                        loadedJob = null;
                        jobError = "조회 실패 · HTTP " + jobRequest.responseCode;
                    }
                    else jobError = null;
                }
                catch (ArgumentException) { loadedJob = null; jobError = "응답 형식 확인 필요"; }
                finally { jobRequest.Dispose(); jobRequest = null; }
                nextJobQuery = Time.realtimeSinceStartupAsDouble + 5d;
            }
            if (Time.realtimeSinceStartupAsDouble < nextJobQuery) return;
            jobRequest = UnityWebRequest.Get(shell.MainServerBaseUrl.TrimEnd('/') + "/api/v1/jobs/" + Uri.EscapeDataString(currentJob));
            jobRequest.timeout = 3;
            jobRequest.SetRequestHeader("X-Runtime-Mode", uiMaster.OperatingMode.ToString().ToLowerInvariant());
            jobRequest.SendWebRequest();
        }

        static string Age(double time) => time < 0d ? "기록 없음" :
            Math.Max(0d, Time.realtimeSinceStartupAsDouble - time).ToString("0.0") + "초 전";
    }
}
