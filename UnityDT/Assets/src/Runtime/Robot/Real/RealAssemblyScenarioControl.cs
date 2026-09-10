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

        [SerializeField] ItemManager itemManager;

        AssemblyProgressManager progress;
        ROSConnection connection;
        AssemblySnapshot latest;
        Task recoveryTask = Task.CompletedTask;
        string activeJobId;
        string pendingJobId;
        bool serviceRegistered;
        bool feedbackSubscribed;
        bool executionPending;
        bool controlPending;
        AssemblySceneConfirmation pendingConfirmation;
        string confirmationJobId;
        bool refreshRequested;
        bool realStatusConfirmed;
        int generation;

        public bool IsRunning => executionPending || (latest != null && latest.active);

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
            public string error_code;
            public string message;
            public string db_sync_state;
        }

        void OnEnable()
        {
            realStatusConfirmed = false;
            EnsureRosConnection();
            recoveryTask = RestoreProgressAsync(++generation);
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
                await recoveryTask;
                AssemblySnapshot snapshot = await ReadStatusAsync(currentGeneration);
                if (snapshot.active)
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
                await MonitorAsync(jobId, currentGeneration);
                pendingConfirmation = null;
            }
            finally
            {
                executionPending = false;
            }
        }

        public Task PauseAsync() => SetPausedAsync(true);
        public Task ResumeAsync() => Task.FromException(new InvalidOperationException(
            "Real robot pause cancels the operation; retained resume is unavailable. Physical reconciliation is required."));

        async Task SetPausedAsync(bool paused)
        {
            RequireEnabled(generation);
            if (controlPending)
                throw new InvalidOperationException("A Real pause or resume request is already pending.");
            controlPending = true;
            int currentGeneration = generation;
            try
            {
                AssemblySnapshot snapshot = await ReadStatusAsync(currentGeneration);
                if (!snapshot.available || !snapshot.active || snapshot.job_id != activeJobId)
                    throw new InvalidOperationException("No matching Real assembly is running.");
                if ((snapshot.state == "PAUSED") == paused)
                    throw new InvalidOperationException(paused
                        ? "Real assembly is already paused." : "Real assembly is not paused.");
                string jobId = snapshot.job_id;
                await SendCommandAsync(paused ? "pause" : "resume", jobId, currentGeneration);
                double deadline = Time.realtimeSinceStartupAsDouble + 60d;
                while (Time.realtimeSinceStartupAsDouble < deadline)
                {
                    snapshot = await ReadStatusAsync(currentGeneration);
                    if (!snapshot.available || snapshot.job_id != jobId)
                        throw new InvalidOperationException("Real assembly changed while confirming pause or resume.");
                    ApplySnapshot(snapshot);
                    if (snapshot.state == "FAILED")
                        throw Failure(snapshot.error_code, snapshot.message);
                    if (!snapshot.active)
                        throw new InvalidOperationException("Real assembly ended before pause or resume was confirmed.");
                    if ((snapshot.state == "PAUSED") == paused)
                        return;
                    await Task.Delay(100);
                }
                throw new TimeoutException(paused
                    ? "Real assembly pause was not confirmed." : "Real assembly resume was not confirmed.");
            }
            finally
            {
                controlPending = false;
            }
        }

        async Task RestoreProgressAsync(int currentGeneration)
        {
            if (!Application.isPlaying)
                return;
            try
            {
                AssemblySnapshot snapshot = await ReadStatusAsync(currentGeneration);
                if (!snapshot.available)
                    return;
                activeJobId = snapshot.job_id;
                ApplySnapshot(snapshot);
                if (snapshot.active)
                    _ = ObserveExistingAsync(snapshot.job_id, currentGeneration);
            }
            catch (Exception exception)
            {
                if (currentGeneration == generation && isActiveAndEnabled)
                    Debug.LogWarning("Real assembly progress could not be restored: " + exception.Message, this);
            }
        }

        async Task ObserveExistingAsync(string jobId, int currentGeneration)
        {
            try
            {
                await MonitorAsync(jobId, currentGeneration);
            }
            catch (Exception exception)
            {
                if (currentGeneration == generation && isActiveAndEnabled)
                    Debug.LogWarning("Real assembly observation stopped: " + exception.Message, this);
            }
        }

        async Task MonitorAsync(string jobId, int currentGeneration)
        {
            double deadline = Time.realtimeSinceStartupAsDouble + CompletionTimeoutSeconds;
            bool observed = false;
            while (Time.realtimeSinceStartupAsDouble < deadline)
            {
                refreshRequested = false;
                AssemblySnapshot snapshot = await ReadStatusAsync(currentGeneration);
                if (snapshot.available && snapshot.job_id == jobId)
                {
                    observed = true;
                    ApplySnapshot(snapshot);
                    if (snapshot.state == "FAILED" || snapshot.db_sync_state == "FAILED")
                        throw Failure(snapshot.error_code, snapshot.message);
                    // A feedback message or accepted response is not completion. The authoritative status must
                    // confirm the requested Job ended successfully and its terminal DB writes are durable.
                    if (snapshot.state == "COMPLETED" && !snapshot.active && snapshot.db_sync_state == "SYNCED")
                        return;
                }
                else if (observed)
                    throw new InvalidOperationException("Real assembly status lost the requested Job.");
                // Accepted Jobs are claimed by the Sequencer queue timer. Until then status can still
                // describe the previous Job; wait for this UUID without treating acceptance as execution.
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
                    snapshot.state == "COMPLETED" && snapshot.db_sync_state == "SYNCED")
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
                Time.realtimeSinceStartupAsDouble));
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
            if (await Task.WhenAny(request, Task.Delay(TimeSpan.FromSeconds(5))) != request)
                throw new TimeoutException("Real assembly service timed out; execution state is unconfirmed.");
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
                JsonUtility.ToJson(new JobRequest { job_id = jobId })));
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
