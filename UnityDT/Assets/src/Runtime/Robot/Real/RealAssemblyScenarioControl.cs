using System;
using System.Text;
using System.Threading.Tasks;
using MainUnity.Runtime.Robot.Assembly;
using MainUnity.Runtime.Robot.Interface;
using MainUnity.Static;
using RosMessageTypes.Fairino;
using RosMessageTypes.Std;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;
using UnityEngine.Networking;

namespace MainUnity.Runtime.Robot.Real
{
    /// <summary>Real 조립을 요청하고 설비 실행 및 DB 기록 완료까지 기다린다.</summary>
    public sealed class RealAssemblyScenarioControl : MonoBehaviour, IRobotScenarioControl
    {
        const string StartService = "/unity/assembly/start";
        const string FeedbackTopic = "/unity/assembly/feedback";
        const string RecipeVersion = "assembly-r1";
        const string MainServerBaseUrl = "http://127.0.0.1:8000";
        const double CompletionTimeoutSeconds = 1800d;
        const double ServiceTimeoutSeconds = 5d;

        [SerializeField] ItemManager itemManager;

        AssemblyProgressManager progress;
        ROSConnection connection;
        AssemblySnapshot latest;
        string activeJobId;
        string pendingJobId;
        bool serviceRegistered;
        bool feedbackSubscribed;
        bool executionPending;
        bool controlPending;
        string controlWaitLabel;
        double controlDeadline;
        AssemblySceneConfirmation pendingConfirmation;
        string confirmationJobId;
        bool refreshRequested;
        bool realStatusConfirmed;
        int generation;

        public bool IsRunning => executionPending || (latest != null && latest.active && latest.error_code != "SCENE_CONFIRMATION_REQUIRED");

        [Serializable]
        sealed class AssemblyRequest
        {
            public string command;
            public string job_id;
            public string recipe_version;
            public AssemblySceneConfirmation scene_confirmation;
        }

        [Serializable]
        sealed class ControlRequest
        {
            public string command;
            public string job_id;
        }

        [Serializable]
        sealed class JobRequest
        {
            public string command = "start";
            public string job_id;
            public string requested_by;
            public string product_code = "HBM-ACCELERATOR-PACKAGE-BOARD";
            public string product_version = "hbm-pkg-r1";
            public int requested_quantity = 1;
            public string recipe_version = RecipeVersion;
        }

        [Serializable]
        sealed class CommandResponse
        {
            public bool accepted;
            public string job_id;
            public string error_code;
            public string message;
        }

        [Serializable]
        sealed class ApiResponse
        {
            public CommandResponse data;
            public ApiError error;
        }

        [Serializable]
        sealed class ApiError
        {
            public string code;
            public string message;
        }

        [Serializable]
        sealed class AssemblyFeedback
        {
            public string job_id;
            public long unit_id;
            public string state;
        }

        [Serializable]
        sealed class AssemblySnapshot
        {
            public bool available;
            public bool active;
            public string job_id;
            public long unit_id;
            public string recipe_version;
            public string state;
            public int placed_count;
            public string runtime_mode;
            public int expected_step_count;
            public int held_step_order;
            public string held_part_id;
            public string held_slot_code;
            public string current_part_id;
            public string current_slot_code;
            public string current_action;
            public string current_phase;
            public string current_event;
            public string error_code;
            public string message;
            public bool controls_available;
            public bool force_cancel_available;
            public string pause_reason;
            public string resume_reason;
            public string cancel_reason;
            public bool control_pending;
            public string db_sync_state;
        }

        void OnEnable()
        {
            realStatusConfirmed = false;
            EnsureRosConnection();
            _ = RestoreProgressAsync(++generation);
        }

        void OnDisable()
        {
            generation++;
            realStatusConfirmed = false;
            if (feedbackSubscribed && connection != null)
            {
                connection.Unsubscribe(FeedbackTopic);
                feedbackSubscribed = false;
            }
        }

        internal void Initialize(AssemblyProgressManager assemblyProgress)
        {
            progress = assemblyProgress;
        }

        /// <summary>Backend가 확인한 Unit 투입을 공통 씬 객체 관리에 반영한다. 설비를 구동하지 않는다.</summary>
        public Transform BeginUnit(string jobId, long unitId)
        {
            if (itemManager == null)
                throw new InvalidOperationException("Assign the shared ItemManager.");
            return itemManager.BeginUnit(jobId, unitId);
        }

        /// <summary>Backend가 확인한 Unit 완료를 반영하고 기판과 장착 부품을 보존한다.</summary>
        public void CompleteUnit(string jobId, long unitId)
        {
            if (itemManager == null)
                throw new InvalidOperationException("Assign the shared ItemManager.");
            itemManager.CompleteUnit(jobId, unitId);
        }

        public Task ExecuteAsync(Func<string, Task<AssemblySceneConfirmation>> confirmScene = null) => ExecuteCoreAsync(null, confirmScene);

        public Task ExecuteQueuedAsync(string jobId, Func<string, Task<AssemblySceneConfirmation>> confirmScene = null)
        {
            if (!Guid.TryParse(jobId, out Guid parsed))
                return Task.FromException(new ArgumentException("Job ID must be a UUID.", nameof(jobId)));
            return ExecuteCoreAsync(parsed.ToString(), confirmScene);
        }

        async Task ExecuteCoreAsync(string queuedJobId, Func<string, Task<AssemblySceneConfirmation>> confirmationProvider)
        {
            RequireEnabled(generation);
            if (executionPending)
                throw new InvalidOperationException("A Real assembly request is already running.");
            executionPending = true;
            int currentGeneration = generation;
            try
            {
                AssemblySnapshot snapshot = await ReadStatusAsync(currentGeneration);
                if (snapshot.active && !(snapshot.job_id == queuedJobId && snapshot.error_code == "SCENE_CONFIRMATION_REQUIRED"))
                    throw new InvalidOperationException("A Real assembly is already running.");
                if (itemManager == null)
                    throw new InvalidOperationException("Assign the shared ItemManager.");
                itemManager.ValidateConfiguration();
                var confirmScene = confirmationProvider ?? throw new InvalidOperationException("운영자의 현장 준비 확인이 필요합니다. JOBS 화면에서 실행하세요.");
                string requestedJobId = queuedJobId ?? (pendingJobId ??= Guid.NewGuid().ToString());
                if (pendingConfirmation != null && confirmationJobId != requestedJobId)
                    throw new InvalidOperationException("이전 실행 요청 상태를 먼저 확인하세요. 다른 Job에 현장 확인을 재사용할 수 없습니다.");
                if (pendingConfirmation == null)
                {
                    string executionId = Guid.NewGuid().ToString();
                    pendingConfirmation = await confirmScene(executionId);
                    confirmationJobId = requestedJobId;
                    if (pendingConfirmation == null || pendingConfirmation.execution_id != executionId ||
                        string.IsNullOrWhiteSpace(pendingConfirmation.operator_id) ||
                        pendingConfirmation.scope != "empty_gripper_empty_pcb_full_tray_fixed_fixture")
                        throw new InvalidOperationException("현장 준비 확인이 유효하지 않습니다.");
                }
                double age = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000d - pendingConfirmation.confirmed_unix;
                if (double.IsNaN(age) || double.IsInfinity(age) || age < 0 || age > 120)
                {
                    pendingConfirmation = null;
                    throw new InvalidOperationException("현장 준비 확인이 만료되었습니다. 다시 확인하세요.");
                }

                // Keep the same UUID after an uncertain HTTP/start response so a retry cannot add a second Job.
                string jobId = requestedJobId;
                activeJobId = jobId;
                if (queuedJobId == null)
                    await PostJobAsync(jobId, currentGeneration);
                await SendCommandAsync("start", jobId, currentGeneration);
                if (jobId == pendingJobId)
                    pendingJobId = null;
                pendingConfirmation = null;
                await MonitorAsync(jobId, currentGeneration, confirmScene);
            }
            finally
            {
                executionPending = false;
            }
        }

        double controlsReceivedAt = double.NegativeInfinity;

        public string GetControlBlockReason(string action)
        {
            if (controlPending) return "제어 요청의 실제 결과를 확인 중입니다.";
            if (action == "force_cancel")
                return latest != null && latest.force_cancel_available && Time.realtimeSinceStartupAsDouble - controlsReceivedAt <= 3d
                    ? "" : "서버의 강제 취소 지원 또는 활성 Job을 확인하지 못했습니다.";
            if (latest == null || !latest.controls_available || !latest.available ||
                Time.realtimeSinceStartupAsDouble - controlsReceivedAt > 3d)
                return "최신 조작 가능 상태를 확인 중입니다.";
            return action switch
            {
                "pause" => latest.pause_reason ?? "서버 판정 누락",
                "resume" => latest.resume_reason ?? "서버 판정 누락",
                "cancel" => latest.cancel_reason ?? "서버 판정 누락",
                _ => "지원하지 않는 조작입니다."
            };
        }

        public Task PauseAsync() => SendControlAsync("pause");
        public Task ResumeAsync() => SendControlAsync("resume");
        public Task CancelAsync() => SendControlAsync("cancel");

        public async Task ForceCancelAsync(string jobId)
        {
            RequireEnabled(generation);
            if (!Guid.TryParse(jobId, out _)) throw new ArgumentException("Job ID must be a UUID.");
            if (controlPending) throw new InvalidOperationException("기존 제어 요청의 결과 확인 중입니다.");
            controlPending = true;
            int currentGeneration = generation;
            try
            {
                try { await SendCommandAsync("force_cancel", jobId, currentGeneration); }
                catch (TimeoutException) { /* Reconcile the same Job without repeating the command. */ }
                controlDeadline = Time.realtimeSinceStartupAsDouble + 60d;
                controlWaitLabel = "생산 기록 강제 취소 확인 중 · 설비 정지 미확인";
                while (Time.realtimeSinceStartupAsDouble < controlDeadline)
                {
                    AssemblySnapshot snapshot;
                    try { snapshot = await ReadStatusAsync(currentGeneration); }
                    catch (TimeoutException) { await Task.Delay(100); continue; }
                    if (snapshot.job_id != jobId) throw new InvalidOperationException("강제 취소 대상 Job의 결과를 확인할 수 없습니다.");
                    ApplySnapshot(snapshot);
                    if (!snapshot.active && snapshot.error_code == "EXECUTION_FORCE_CANCELLED" && snapshot.db_sync_state == "SYNCED") return;
                    if (snapshot.db_sync_state == "FAILED") throw Failure(snapshot.error_code, snapshot.message);
                    await Task.Delay(100);
                }
                throw new TimeoutException("강제 취소의 DB 반영 미확인 · 현재 기록을 다시 확인하세요.");
            }
            finally
            {
                controlPending = false;
                controlWaitLabel = null;
                if (progress?.Latest != null) progress.Latest.PendingRequest = null;
            }
        }

        async Task SendControlAsync(string action)
        {
            RequireEnabled(generation);
            if (controlPending)
                throw new InvalidOperationException("제어 요청의 실제 결과를 확인 중입니다.");
            controlPending = true;
            string expectedJobId = activeJobId;
            int currentGeneration = generation;
            try
            {
                AssemblySnapshot snapshot = await ReadStatusAsync(currentGeneration);
                if (!snapshot.available || !snapshot.active || snapshot.job_id != expectedJobId)
                    throw new InvalidOperationException("일치하는 실행 중 작업이 없습니다.");
                string jobId = snapshot.job_id;
                string previousError = snapshot.error_code;
                try { await SendCommandAsync(action, jobId, currentGeneration); }
                catch (TimeoutException)
                {
                    // An absent acknowledgement cannot prove rejection. Observe without resending control.
                }
                double deadline = Time.realtimeSinceStartupAsDouble + 60d;
                controlDeadline = deadline;
                controlWaitLabel = action == "cancel" ? "취소 · 설비 정지 및 DB 반영 확인 중" :
                    action == "pause" ? "일시정지 확인 대기 중" : "재개 확인 대기 중";
                while (Time.realtimeSinceStartupAsDouble < deadline)
                {
                    try { snapshot = await ReadStatusAsync(currentGeneration); }
                    catch (TimeoutException)
                    {
                        await Task.Delay(100);
                        continue;
                    }
                    if (!snapshot.available || snapshot.job_id != jobId)
                        throw new InvalidOperationException("제어 확인 중 작업 상태를 잃었습니다.");
                    ApplySnapshot(snapshot);
                    if (action == "cancel" && snapshot.error_code == "EXECUTION_CANCELLED" &&
                        !snapshot.active && snapshot.db_sync_state == "SYNCED")
                        return;
                    if (action == "resume" && snapshot.state == "PAUSED" && snapshot.error_code == "SCENE_CONFIRMATION_REQUIRED")
                        return;
                    if (action == "cancel" && snapshot.active && snapshot.db_sync_state != "FAILED" &&
                        (string.IsNullOrEmpty(snapshot.error_code) || snapshot.error_code == previousError ||
                         snapshot.error_code == "EXECUTION_CANCELLED"))
                    {
                        await Task.Delay(100);
                        continue;
                    }
                    if (snapshot.state == "FAILED" || !string.IsNullOrEmpty(snapshot.error_code))
                        throw Failure(snapshot.error_code, snapshot.message);
                    if (!snapshot.active)
                        throw new InvalidOperationException("제어 확인 전에 작업이 종료되었습니다.");
                    if (!snapshot.control_pending && (action == "pause" && snapshot.state == "PAUSED" ||
                        action == "resume" && (snapshot.state == "STARTED" || snapshot.state == "PLACED")))
                        return;
                    await Task.Delay(100);
                }
                throw new TimeoutException("제어 결과가 확인되지 않았습니다. 현재 상태를 확인하세요.");
            }
            finally
            {
                controlPending = false;
                controlWaitLabel = null;
                if (progress?.Latest != null) progress.Latest.PendingRequest = null;
            }
        }

        async Task RestoreProgressAsync(int currentGeneration)
        {
            // Keep permission/status observation alive after a workflow wait has failed.
            while (Application.isPlaying && isActiveAndEnabled && currentGeneration == generation)
            {
                if (!executionPending && !controlPending)
                {
                    try
                    {
                        AssemblySnapshot snapshot = await ReadStatusAsync(currentGeneration);
                        activeJobId = snapshot.job_id;
                        if (snapshot.available && snapshot.state != "IDLE") ApplySnapshot(snapshot);
                        else
                        {
                            latest = snapshot;
                            controlsReceivedAt = Time.realtimeSinceStartupAsDouble;
                            if (!snapshot.active && snapshot.state == "IDLE")
                                progress?.Apply(new AssemblyProgressFrame("", RecipeVersion, AssemblyState.Idle,
                                    0, 0, 0, "", "", snapshot.error_code,
                                    string.IsNullOrEmpty(snapshot.message) ? "작업 요청 대기" : snapshot.message,
                                    controlsReceivedAt));
                        }
                    }
                    catch (Exception)
                    {
                        controlsReceivedAt = double.NegativeInfinity;
                    }
                }
                await Task.Delay(1000);
            }
        }

        async Task MonitorAsync(string jobId, int currentGeneration, Func<string, Task<AssemblySceneConfirmation>> confirmScene = null)
        {
            double deadline = Time.realtimeSinceStartupAsDouble + CompletionTimeoutSeconds;
            bool observed = false;
            long confirmedAfterUnit = 0;
            double qualityPausedAt = -1d;
            while (qualityPausedAt >= 0d || Time.realtimeSinceStartupAsDouble < deadline)
            {
                refreshRequested = false;
                AssemblySnapshot snapshot = await ReadStatusAsync(currentGeneration);
                if (snapshot.available && snapshot.job_id == jobId)
                {
                    observed = true;
                    ApplySnapshot(snapshot);
                    if (snapshot.state == "PAUSED" && snapshot.error_code == "QUALITY_HOLD")
                    {
                        if (qualityPausedAt < 0d) qualityPausedAt = Time.realtimeSinceStartupAsDouble;
                        await Task.Delay(100);
                        continue;
                    }
                    if (qualityPausedAt >= 0d)
                    {
                        deadline += Time.realtimeSinceStartupAsDouble - qualityPausedAt;
                        qualityPausedAt = -1d;
                    }
                    if (snapshot.state == "PAUSED" && !string.IsNullOrEmpty(snapshot.error_code))
                    {
                        if (snapshot.error_code != "SCENE_CONFIRMATION_REQUIRED" || confirmScene == null)
                            throw Failure(snapshot.error_code, snapshot.message);
                        if (confirmedAfterUnit != snapshot.unit_id)
                        {
                            string executionId = Guid.NewGuid().ToString();
                            pendingConfirmation = await confirmScene(executionId);
                            confirmationJobId = jobId;
                            RequireEnabled(currentGeneration);
                            if (pendingConfirmation == null || pendingConfirmation.execution_id != executionId)
                                throw new InvalidOperationException("다음 Unit의 현장 확인이 취소되었거나 유효하지 않습니다.");
                            await SendCommandAsync("start", jobId, currentGeneration);
                            pendingConfirmation = null;
                            confirmedAfterUnit = snapshot.unit_id;
                        }
                    }
                    if ((snapshot.error_code == "EXECUTION_CANCELLED" || snapshot.error_code == "EXECUTION_FORCE_CANCELLED") && !snapshot.active && snapshot.db_sync_state == "SYNCED")
                        throw new OperationCanceledException("작업 취소 완료");
                    if (snapshot.state == "FAILED" || snapshot.db_sync_state == "FAILED")
                        throw Failure(snapshot.error_code, snapshot.message);
                    // A feedback message or accepted response is not completion. The authoritative status must
                    // confirm the requested Job ended successfully and its terminal DB writes are durable.
                    if (snapshot.state == "COMPLETED" && !snapshot.active && snapshot.db_sync_state == "SYNCED")
                        return;
                }
                else if (observed)
                    throw new InvalidOperationException("Real assembly status lost the requested Job.");
                // Request acceptance alone is not completion; wait for the matching Unit status.
                double nextPoll = Time.realtimeSinceStartupAsDouble + 1d;
                do
                {
                    RequireEnabled(currentGeneration);
                    await Task.Delay(100);
                }
                while (!refreshRequested && Time.realtimeSinceStartupAsDouble < nextPoll);
            }
            throw new TimeoutException($"Real assembly completion was not confirmed within {CompletionTimeoutSeconds:0} seconds.");
        }

        async Task<AssemblySnapshot> ReadStatusAsync(int currentGeneration)
        {
            string json = await SendServiceAsync("{\"command\":\"status\"}", currentGeneration);
            AssemblySnapshot snapshot = JsonUtility.FromJson<AssemblySnapshot>(json);
            realStatusConfirmed = snapshot != null && snapshot.runtime_mode == "real";
            if (!realStatusConfirmed)
                throw new InvalidOperationException("MODE_REJECTED expected=real stage=assembly_status");
            if (!snapshot.available)
                return snapshot;
            if (!snapshot.active && snapshot.state == "IDLE" && string.IsNullOrEmpty(snapshot.job_id) && snapshot.unit_id == 0)
                return snapshot;
            AssemblyState state = ToState(snapshot.state);
            if (!Guid.TryParse(snapshot.job_id, out _) || snapshot.unit_id <= 0 ||
                snapshot.recipe_version != RecipeVersion || snapshot.expected_step_count <= 0 ||
                snapshot.placed_count < 0 || snapshot.placed_count > snapshot.expected_step_count ||
                snapshot.held_step_order < 0 || snapshot.held_step_order > snapshot.expected_step_count ||
                snapshot.active == (state == AssemblyState.Completed || state == AssemblyState.Failed))
                throw new InvalidOperationException("Real assembly status contains invalid Job, Unit or progress data.");
            if (state == AssemblyState.Completed &&
                (snapshot.placed_count != snapshot.expected_step_count || snapshot.held_step_order != 0))
                throw new InvalidOperationException("Real assembly completed with unfinished placements.");
            return snapshot;
        }

        void ApplySnapshot(AssemblySnapshot snapshot)
        {
            if (latest != null && latest.job_id == snapshot.job_id && snapshot.unit_id < latest.unit_id)
                return;
            latest = snapshot;
            controlsReceivedAt = Time.realtimeSinceStartupAsDouble;
            // Unit lifecycle is mirrored only from the backend's confirmed state. No Mock conveyor,
            // attachment or pose simulation is used to acknowledge physical completion.
            if (itemManager != null && !itemManager.IsUnitCompleted(snapshot.job_id, snapshot.unit_id) &&
                snapshot.state != "FAILED")
            {
                if (itemManager.CurrentBoard != null &&
                    (itemManager.JobId != snapshot.job_id || itemManager.UnitId != snapshot.unit_id))
                    itemManager.DiscardCurrentUnit();
                BeginUnit(snapshot.job_id, snapshot.unit_id);
                if (snapshot.state == "PCB_PLACED" ||
                    (snapshot.state == "COMPLETED" || snapshot.error_code == "SCENE_CONFIRMATION_REQUIRED") && snapshot.db_sync_state == "SYNCED")
                    CompleteUnit(snapshot.job_id, snapshot.unit_id);
            }
            AssemblyState state = ToState(snapshot.state);
            // Do not display success while terminal DB synchronization is still pending.
            if (state == AssemblyState.Completed && snapshot.db_sync_state != "SYNCED")
                state = snapshot.db_sync_state == "FAILED" ? AssemblyState.Failed : AssemblyState.Placed;
            progress?.Apply(new AssemblyProgressFrame(
                snapshot.job_id, snapshot.recipe_version, state, snapshot.held_step_order,
                snapshot.expected_step_count, snapshot.placed_count,
                snapshot.held_part_id, snapshot.held_slot_code, snapshot.error_code, snapshot.message,
                Time.realtimeSinceStartupAsDouble)
            {
                CancellationConfirmed = !snapshot.active && snapshot.error_code == "EXECUTION_CANCELLED" && snapshot.db_sync_state == "SYNCED",
                PendingRequest = controlWaitLabel,
                RequestDeadline = controlDeadline,
                CurrentPartId = snapshot.current_part_id,
                CurrentSlotCode = snapshot.current_slot_code,
                CurrentAction = snapshot.current_action,
                CurrentPhase = snapshot.current_phase,
                CurrentEvent = snapshot.current_event
            });
        }

        void ReceiveFeedback(StringMsg message)
        {
            if (!isActiveAndEnabled || !realStatusConfirmed || string.IsNullOrEmpty(activeJobId) ||
                message == null || string.IsNullOrWhiteSpace(message.data))
                return;
            try
            {
                AssemblyFeedback feedback = JsonUtility.FromJson<AssemblyFeedback>(message.data);
                if (feedback == null || feedback.job_id != activeJobId)
                    return;
                refreshRequested = true;
                // The next Unit may start before the status poll. Preserve an existing board when
                // its matching transfer completion arrives; Job success still requires status + DB sync.
                if (feedback.state == "PCB_PLACED" && feedback.unit_id > 0 && itemManager != null &&
                    itemManager.CurrentBoard != null && itemManager.JobId == feedback.job_id &&
                    itemManager.UnitId == feedback.unit_id)
                    CompleteUnit(feedback.job_id, feedback.unit_id);
            }
            catch (Exception exception)
            {
                Debug.LogWarning("Ignored invalid Real assembly feedback: " + exception.Message, this);
            }
        }

        async Task SendCommandAsync(string command, string jobId, int currentGeneration)
        {
            string json = command == "start"
                ? JsonUtility.ToJson(new AssemblyRequest
                {
                    command = command, job_id = jobId, recipe_version = RecipeVersion, scene_confirmation = pendingConfirmation
                })
                : JsonUtility.ToJson(new ControlRequest { command = command, job_id = jobId });
            if (progress != null && progress.Latest?.JobId != jobId)
                progress.Apply(new AssemblyProgressFrame(jobId, RecipeVersion, AssemblyState.Idle,
                    0, 0, 0, "", "", "", "실행 요청 중 · 설비 상태 확인 대기", double.NegativeInfinity));
            string responseJson = await SendServiceAsync("real\n" + json, currentGeneration);
            CommandResponse response = JsonUtility.FromJson<CommandResponse>(responseJson);
            if (response == null || response.job_id != jobId)
                throw new InvalidOperationException($"Real assembly {command} response job_id did not match.");
            if (!response.accepted)
            {
                // A definitive rejection permits a new operator confirmation;
                // an uncertain transport result retains the original identity.
                pendingConfirmation = null;
                confirmationJobId = null;
                throw Failure(response.error_code, response.message);
            }
        }

        async Task<string> SendServiceAsync(string payload, int currentGeneration)
        {
            RequireEnabled(currentGeneration);
            EnsureRosConnection();
            Task<RemoteCmdInterfaceResponse> request = connection
                .SendServiceMessage<RemoteCmdInterfaceResponse>(StartService, new RemoteCmdInterfaceRequest(payload));
            var frame = progress?.Latest;
            bool command = payload.StartsWith("real\n", StringComparison.Ordinal);
            if (command && frame != null)
            {
                frame.PendingRequest = "작업 명령 요청 대기 중";
                frame.RequestDeadline = Time.realtimeSinceStartupAsDouble + ServiceTimeoutSeconds;
            }
            try
            {
                if (await Task.WhenAny(request, Task.Delay(TimeSpan.FromSeconds(ServiceTimeoutSeconds))) != request)
                    throw new TimeoutException("요청 응답 시간 초과 · 실제 실행 결과는 상태 재조회로 확인해야 합니다.");
            }
            finally
            {
                if (command && frame != null)
                {
                    frame.PendingRequest = null;
                    if (progress?.Latest != null) progress.Latest.PendingRequest = null;
                }
            }
            RequireEnabled(currentGeneration);
            RemoteCmdInterfaceResponse response = await request;
            if (response == null || string.IsNullOrWhiteSpace(response.cmd_res))
                throw new InvalidOperationException("Real assembly service returned an empty response.");
            return response.cmd_res;
        }

        async Task PostJobAsync(string jobId, int currentGeneration)
        {
            RequireEnabled(currentGeneration);
            using var request = new UnityWebRequest(MainServerBaseUrl + "/api/v1/assemblies", UnityWebRequest.kHttpVerbPOST);
            request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(
                JsonUtility.ToJson(new JobRequest { job_id = jobId, requested_by = pendingConfirmation.operator_id })));
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            request.SetRequestHeader("X-Runtime-Mode", "real");
            request.timeout = 5;
            UnityWebRequestAsyncOperation operation = request.SendWebRequest();
            while (!operation.isDone)
            {
                RequireEnabled(currentGeneration);
                await Task.Yield();
            }
            RequireEnabled(currentGeneration);
            ApiResponse response = string.IsNullOrWhiteSpace(request.downloadHandler.text)
                ? null : JsonUtility.FromJson<ApiResponse>(request.downloadHandler.text);
            if (request.result != UnityWebRequest.Result.Success)
                throw Failure(response?.error?.code, response?.error?.message ??
                    $"MainServer assembly request failed ({request.responseCode}).");
            if (response?.data == null || response.data.job_id != jobId)
                throw new InvalidOperationException("MainServer assembly response job_id did not match.");
            if (!response.data.accepted)
                throw Failure(response.data.error_code, response.data.message);
        }

        void RequireEnabled(int currentGeneration)
        {
            if (!Application.isPlaying || !isActiveAndEnabled || currentGeneration != generation)
                throw new InvalidOperationException("Real assembly control is disabled; physical execution status is unconfirmed.");
        }

        void EnsureRosConnection()
        {
            connection ??= ROSConnection.GetOrCreateInstance();
            if (!serviceRegistered)
            {
                connection.RegisterRosService<RemoteCmdInterfaceRequest, RemoteCmdInterfaceResponse>(StartService);
                serviceRegistered = true;
            }
            if (!feedbackSubscribed && isActiveAndEnabled)
            {
                connection.Subscribe<StringMsg>(FeedbackTopic, ReceiveFeedback);
                feedbackSubscribed = true;
            }
        }

        static AssemblyState ToState(string state) => state switch
        {
            "CONVEYOR_MOVING" => AssemblyState.ConveyorMoving,
            "STARTED" => AssemblyState.Started,
            "PICKED" => AssemblyState.Picked,
            "PLACED" or "ASSEMBLY_COMPLETED" or "PCB_PICKED" or "PCB_PLACED" => AssemblyState.Placed,
            "PAUSED" => AssemblyState.Paused,
            "COMPLETED" => AssemblyState.Completed,
            "FAILED" => AssemblyState.Failed,
            _ => throw new InvalidOperationException("Unknown Real assembly state: " + state)
        };

        static InvalidOperationException Failure(string code, string message)
        {
            string reason = string.IsNullOrWhiteSpace(message) ? "Real assembly request failed." : message;
            return new InvalidOperationException(string.IsNullOrWhiteSpace(code) ? reason : code + ": " + reason);
        }
    }
}
