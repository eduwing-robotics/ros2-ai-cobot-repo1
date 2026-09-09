using System;
using System.Collections.Generic;
using System.Text;
using System.Threading.Tasks;
using MainUnity.Runtime.ConveyBelt;
using MainUnity.Runtime.Robot.Assembly;
using MainUnity.Runtime.Robot.Interface;
using MainUnity.Static;
using RosMessageTypes.Fairino;
using RosMessageTypes.Std;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;
using UnityEngine.Networking;

namespace MainUnity.Runtime.Robot.Mock
{
    /// <summary>Mock 조립 작업을 요청하고 callback을 씬 시각화에 반영한다.</summary>
    public sealed class MockAssemblyScenarioControl : MonoBehaviour, IRobotScenarioControl
    {
        const string ConveyorMoving = "CONVEYOR_MOVING";
        const string Started = "STARTED";
        const string Picked = "PICKED";
        const string Placed = "PLACED";
        const string AssemblyCompleted = "ASSEMBLY_COMPLETED";
        const string PcbPicked = "PCB_PICKED";
        const string PcbPlaced = "PCB_PLACED";
        const string Paused = "PAUSED";
        const string Completed = "COMPLETED";
        const string Failed = "FAILED";

        [Header("MainServer")]
        [SerializeField] string mainServerBaseUrl = "http://127.0.0.1:8000";

        [SerializeField] string productCode = "HBM-ACCELERATOR-PACKAGE-BOARD";
        [SerializeField] string productVersion = "hbm-pkg-r1";
        [SerializeField, Min(1)] int requestedQuantity = 1;
        [Header("ROS Feedback and Recovery")]
        [SerializeField] string startService = "/unity/assembly/start";
        [SerializeField] string feedbackTopic = "/unity/assembly/feedback";
        [SerializeField] string recipeVersion = "assembly-r1";
        [SerializeField, Min(1f)] float completionTimeoutSeconds = 1800f;

        [Header("Mock Conveyor")]
        [SerializeField] MockConveyor conveyor;

        [Header("Mock Visualization")]
        [SerializeField] ItemManager itemManager;
        [SerializeField] SimGripperCatcher gripperCatcher;
        [SerializeField] float resumeRotationOffsetDegrees = 90f;

        [Header("Assembled PCB Transfer")]
        Transform assembledPcb;
        [SerializeField] Transform assembledPcbAssemblyStopPoint;
        Transform assembledPcbPicker;
        [SerializeField] Transform assembledPcbDropPoint;

        readonly Dictionary<string, (string PartId, Transform Item, Transform Slot)> slotTargets =
            new(StringComparer.Ordinal);
        readonly HashSet<string> processedCallbacks = new(StringComparer.Ordinal);
        readonly List<AssemblyFeedback> bufferedFeedback = new();

        MockRobotControl control;
        AssemblyProgressManager progress;
        ROSConnection connection;
        TaskCompletionSource<string> terminal;
        readonly System.Diagnostics.Stopwatch executionClock = new();
        TaskCompletionSource<bool> executionStateChanged = new();
        bool awaitingExecution;

        Task recoveryTask = Task.CompletedTask;
        Transform heldItem;
        string activeJobId;
        long activeUnitId;
        string activeConveyorOperationId;
        string heldPartId;
        string heldSlotCode;
        int expectedStepCount;
        int heldStepOrder = -1;
        int lastPlacedStepOrder = -1;
        bool serviceRegistered;
        Vector3 assembledPcbPositionFromTcp;
        Quaternion assembledPcbRotationFromTcp = Quaternion.identity;
        bool assembledPcbHeld;
        bool assembledPcbTransferred;
        bool feedbackSubscribed;
        bool inspectionTransferStarted;
        bool assemblyConveyorStarted;
        bool recovering;
        int recoveryGeneration;

        public bool IsRunning => terminal != null && !terminal.Task.IsCompleted;

        [Serializable]
        sealed class JobRequest
        {
            public string command;
            public string job_id;
            public string product_code;
            public string product_version;
            public int requested_quantity;
            public string recipe_version;
        }

        [Serializable]
        sealed class ObservationRequest
        {
            public string command;
            public string job_id;
            public string recipe_version;
            public MockObservation[] observations;
        }

        [Serializable]
        sealed class TransferRequest
        {
            public string command;
            public string job_id;
            public long unit_id;
            public string operation_id;
            public AssembledPcbTransfer assembled_pcb;
        }

        [Serializable]
        sealed class ControlRequest
        {
            public string command;
            public string job_id;
        }

        [Serializable]
        sealed class ConveyorArrivalRequest
        {
            public string command;
            public string job_id;
            public long unit_id;
            public string operation_id;
        }

        [Serializable]
        sealed class ConveyorFailureRequest
        {
            public string command;
            public string job_id;
            public long unit_id;
            public string operation_id;
            public string message;
        }

        [Serializable]
        sealed class MockObservation
        {
            public int order;
            public string part_id;
            public string slot_code;
            public RosPoseRequest source;
            public RosPoseRequest target;
        }

        [Serializable]
        sealed class AssembledPcbTransfer
        {
            public RosPoseRequest source;
            public RosPoseRequest target;
        }

        [Serializable]
        sealed class RosPoseRequest
        {
            public float[] xyz_mm;
            public float[] xyzw;
        }

        [Serializable]
        sealed class StartResponse
        {
            public bool accepted;
            public string job_id;
            public string error_code;
            public string message;
        }

        [Serializable]
        sealed class StartApiResponse
        {
            public StartResponse data;
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
            public string operation_id;
            public string state;
            public int step_order;
            public string part_id;
            public string slot_code;
            public string error_code;
            public string message;
        }

        [Serializable]
        sealed class AssemblySnapshot
        {
            public bool available;
            public bool active;
            public string job_id;
            public long unit_id;
            public string operation_id;
            public string recipe_version;
            public string state;
            public int placed_count;
            public string runtime_mode;
            public string[] placed_slot_codes;
            public int expected_step_count;
            public int held_step_order;
            public string held_part_id;
            public string held_slot_code;
            public string error_code;
            public string message;
        }

        void Awake()
        {
            RefreshReferences();
            EnsureRosConnection();
        }

        void OnEnable()
        {
            RefreshReferences();
            EnsureRosConnection();
            recoveryTask = RecoverAsync(++recoveryGeneration);
        }

        void OnDisable()
        {
            recoveryGeneration++;
            recovering = false;
            bufferedFeedback.Clear();
            if (progress?.Latest?.State == AssemblyState.ConveyorMoving)
                _ = ReportConveyorFailureAsync(activeJobId, activeUnitId, activeConveyorOperationId,
                    "Mock assembly control was disabled during conveyor movement.");
            conveyor?.StopConveyor();
            FailActive("Mock assembly control was disabled.");
            if (feedbackSubscribed && connection != null)
            {
                connection.Unsubscribe(feedbackTopic);
                feedbackSubscribed = false;
            }
        }

        void OnValidate() => RefreshReferences();

        public void Initialize(MockRobotControl selectedControl,
            AssemblyProgressManager assemblyProgress)
        {
            control = selectedControl != null ? selectedControl : control;
            progress = assemblyProgress != null ? assemblyProgress : progress;
            RefreshReferences();
        }

        public Task ExecuteAsync() => ExecuteCoreAsync(null);

        public Task ExecuteQueuedAsync(string jobId)
        {
            if (!Guid.TryParse(jobId, out _))
                return Task.FromException(new ArgumentException("Job ID must be a UUID.", nameof(jobId)));
            return ExecuteCoreAsync(jobId);
        }

        async Task ExecuteCoreAsync(string queuedJobId)
        {
            await recoveryTask;
            ValidateExecution();
            EnsureRosConnection();
            MockObservation[] observations = BuildObservations(true);

            var current = new TaskCompletionSource<string>();
            terminal = current;
            bool queuedJob = !string.IsNullOrEmpty(queuedJobId);
            if (queuedJob)
                activeJobId = queuedJobId;
            else if (string.IsNullOrEmpty(activeJobId))
                activeJobId = Guid.NewGuid().ToString();
            activeUnitId = 0;
            processedCallbacks.Clear();
            expectedStepCount = observations.Length;
            heldStepOrder = -1;
            lastPlacedStepOrder = 0;
            assembledPcbHeld = false;
            assembledPcbTransferred = false;
            inspectionTransferStarted = false;
            assemblyConveyorStarted = false;

            awaitingExecution = true;
            executionClock.Restart();
            bool accepted = false;
            try
            {
                string observationsJson = JsonUtility.ToJson(new ObservationRequest
                {
                    command = "observations",
                    job_id = activeJobId,
                    recipe_version = recipeVersion,
                    observations = observations
                });
                if (!queuedJob)
                {
                    string jobJson = JsonUtility.ToJson(new JobRequest
                    {
                        command = "start",
                        job_id = activeJobId,
                        product_code = productCode,
                        product_version = productVersion,
                        requested_quantity = requestedQuantity,
                        recipe_version = recipeVersion
                    });
                    await PostJobAsync(jobJson);
                }
                await SendMockAsync(observationsJson, "observations");
                accepted = true;

                await WaitForCompletionAsync(current.Task);

                string failure = await current.Task;
                if (!string.IsNullOrEmpty(failure))
                    throw new InvalidOperationException(failure);
            }
            finally
            {
                awaitingExecution = false;
                executionClock.Stop();
                // A caller timeout does not stop equipment. Retain tracking until terminal feedback.
                if (!accepted || current.Task.IsCompleted)
                {
                    if (ReferenceEquals(terminal, current))
                        terminal = null;
                    if (accepted)
                        activeJobId = string.Empty;
                    processedCallbacks.Clear();
                }
            }
        }

        async Task WaitForCompletionAsync(Task completion)
        {
            while (!completion.IsCompleted)
            {
                Task stateChanged = executionStateChanged.Task;
                if (!executionClock.IsRunning)
                {
                    await Task.WhenAny(completion, stateChanged);
                    continue;
                }
                double remaining = completionTimeoutSeconds - executionClock.Elapsed.TotalSeconds;
                if (remaining <= 0)
                    throw new TimeoutException(
                        $"Mock assembly timed out after {completionTimeoutSeconds:0.###} active seconds.");
                using var cancellation = new System.Threading.CancellationTokenSource();
                Task timeout = Task.Delay(TimeSpan.FromSeconds(remaining), cancellation.Token);
                await Task.WhenAny(completion, stateChanged, timeout);
                cancellation.Cancel();
            }
        }

        public async Task PauseAsync()
        {
            ValidateControl(false);
            await SendControlAsync("pause");
            await WaitForPausedStateAsync(true);
        }

        public async Task ResumeAsync()
        {
            ValidateControl(true);
            await SendControlAsync("resume");
            await WaitForPausedStateAsync(false);
        }

        async Task RecoverAsync(int generation)
        {
            if (!Application.isPlaying)
                return;

            recovering = true;
            bufferedFeedback.Clear();
            try
            {
                RefreshReferences();
                if (control == null || conveyor == null || itemManager == null ||
                    gripperCatcher == null)
                    throw new InvalidOperationException(
                        "Assign MockRobotControl, MockConveyor, ItemManager and SimGripperCatcher.");

                Task<RemoteCmdInterfaceResponse> request = connection
                    .SendServiceMessage<RemoteCmdInterfaceResponse>(startService,
                        new RemoteCmdInterfaceRequest("{\"command\":\"status\"}"));
                if (await Task.WhenAny(request, Task.Delay(TimeSpan.FromSeconds(5))) != request)
                    throw new TimeoutException("Mock assembly status service timed out.");
                if (generation != recoveryGeneration || !isActiveAndEnabled)
                    return;

                RemoteCmdInterfaceResponse message = await request;
                if (message == null || string.IsNullOrWhiteSpace(message.cmd_res))
                    throw new InvalidOperationException(
                        "Mock assembly status returned an empty response.");

                AssemblySnapshot snapshot;
                try
                {
                    snapshot = JsonUtility.FromJson<AssemblySnapshot>(message.cmd_res);
                    if (snapshot?.runtime_mode != "mock")
                        throw new InvalidOperationException("MODE_REJECTED expected=mock stage=assembly_status");
                }
                catch (Exception exception)
                {
                    throw new InvalidOperationException(
                        "Mock assembly status returned invalid JSON.", exception);
                }

                if (snapshot == null || !snapshot.available)
                    return;

                MockObservation[] preview = BuildObservations(true);
                ValidateSnapshot(snapshot, preview);
                activeJobId = snapshot.job_id;
                activeUnitId = snapshot.unit_id;
                if (itemManager.IsUnitCompleted(activeJobId, activeUnitId))
                {
                    expectedStepCount = snapshot.expected_step_count;
                    lastPlacedStepOrder = snapshot.placed_count;
                    assembledPcbTransferred = true;
                    terminal = snapshot.active ? new TaskCompletionSource<string>() : null;
                    Report(snapshot.active ? AssemblyState.Placed : AssemblyState.Completed, null);
                    recovering = false;
                    foreach (AssemblyFeedback feedback in bufferedFeedback.ToArray())
                        HandleFeedback(feedback);
                    return;
                }
                ResetVisualization(snapshot.state != ConveyorMoving);
                MockObservation[] observations = BuildObservations();
                _ = BuildAssembledPcbTransfer();
                RestoreSnapshot(snapshot, observations);
                recovering = false;
                Report(snapshot.state switch
                {
                    ConveyorMoving => AssemblyState.ConveyorMoving,
                    Started => AssemblyState.Started,
                    Picked => AssemblyState.Picked,
                    Placed => AssemblyState.Placed,
                    AssemblyCompleted => AssemblyState.Placed,
                    PcbPicked => AssemblyState.Placed,
                    PcbPlaced => AssemblyState.Placed,
                    Paused => AssemblyState.Paused,
                    Completed => AssemblyState.Completed,
                    Failed => AssemblyState.Failed,
                    _ => throw new InvalidOperationException("Unknown Mock assembly state.")
                }, null, snapshot.state == Failed ? snapshot.message : null);
                if (snapshot.state == ConveyorMoving)
                    _ = MoveToAssemblyAndConfirmAsync(snapshot.operation_id);
                else if (snapshot.state == AssemblyCompleted)
                    _ = MoveToInspectionAndRequestTransferAsync(snapshot.operation_id);
                if (!snapshot.active)
                    activeJobId = string.Empty;
                foreach (AssemblyFeedback feedback in bufferedFeedback.ToArray())
                    HandleFeedback(feedback);
            }
            catch (Exception exception)
            {
                if (generation == recoveryGeneration && isActiveAndEnabled)
                    Debug.LogWarning(
                        "Mock assembly progress could not be restored: " + exception.Message, this);
            }
            finally
            {
                if (generation == recoveryGeneration)
                {
                    recovering = false;
                    bufferedFeedback.Clear();
                }
            }
        }

        void RestoreSnapshot(AssemblySnapshot snapshot, MockObservation[] observations)
        {
            ValidateSnapshot(snapshot, observations);

            gripperCatcher.Release();
            processedCallbacks.Clear();
            activeConveyorOperationId = null;
            heldItem = null;
            heldPartId = string.Empty;
            heldSlotCode = string.Empty;
            heldStepOrder = -1;
            lastPlacedStepOrder = 0;
            activeJobId = snapshot.job_id;
            activeUnitId = snapshot.unit_id;
            assembledPcbHeld = false;
            assembledPcbTransferred = false;
            inspectionTransferStarted = false;
            expectedStepCount = snapshot.expected_step_count;

            // Rebuild only confirmed placements; scene array order is not recipe order.
            for (int index = 0; index < snapshot.placed_slot_codes.Length; index++)
            {
                string slotCode = snapshot.placed_slot_codes[index];
                var target = slotTargets[slotCode];
                ApplyPicked(new AssemblyFeedback
                {
                    job_id = snapshot.job_id,
                    state = Picked,
                    step_order = index + 1,
                    part_id = target.PartId,
                    slot_code = slotCode
                }, true);
                ApplyPlaced(new AssemblyFeedback
                {
                    job_id = snapshot.job_id,
                    state = Placed,
                    step_order = index + 1,
                    part_id = target.PartId,
                    slot_code = slotCode
                }, true);
            }
            if (snapshot.active)
            {
                if (snapshot.held_step_order > 0)
                {
                    ApplyPicked(new AssemblyFeedback
                    {
                        job_id = snapshot.job_id,
                        state = Picked,
                        step_order = snapshot.held_step_order,
                        part_id = snapshot.held_part_id,
                        slot_code = snapshot.held_slot_code
                    }, true);
                }
                if (snapshot.state == PcbPicked)
                    ApplyAssembledPcbPicked();
                else if (snapshot.state == PcbPlaced)
                {
                    ApplyAssembledPcbPicked();
                    ApplyAssembledPcbPlaced();
                }
            }
            else
            {
                lastPlacedStepOrder = snapshot.placed_count;
                if (snapshot.state == Completed)
                {
                    ApplyAssembledPcbPicked();
                    ApplyAssembledPcbPlaced();
                }
            }

            terminal = snapshot.active ? new TaskCompletionSource<string>() : null;
            string summary = $"Mock assembly restored: {snapshot.state}, " +
                $"{snapshot.placed_count}/{snapshot.expected_step_count} placed.";
            if (snapshot.state == Failed)
                Debug.LogError(summary + " " + snapshot.error_code + ": " + snapshot.message, this);
            else
                Debug.Log(summary, this);
        }

        void ValidateSnapshot(AssemblySnapshot snapshot, MockObservation[] observations)
        {
            if ((snapshot.state == ConveyorMoving || snapshot.state == AssemblyCompleted) &&
                !Guid.TryParse(snapshot.operation_id, out _))
                throw new InvalidOperationException("Conveyor status requires an operation UUID.");
            bool activeState = snapshot.state == ConveyorMoving || snapshot.state == Started || snapshot.state == Picked ||
                snapshot.state == Placed || snapshot.state == AssemblyCompleted ||
                snapshot.state == PcbPicked || snapshot.state == Paused ||
                snapshot.state == PcbPlaced;
            bool terminalState = snapshot.state == Completed || snapshot.state == Failed;
            if (!activeState && !terminalState)
                throw new InvalidOperationException(
                    "Mock assembly status contains an unknown state.");
            if (snapshot.active != activeState)
                throw new InvalidOperationException(
                    "Mock assembly status active flag does not match its state.");
            if (!Guid.TryParse(snapshot.job_id, out _) || snapshot.unit_id <= 0)
                throw new InvalidOperationException(
                    "Mock assembly status job_id must be a UUID.");
            if (snapshot.recipe_version != recipeVersion)
                throw new InvalidOperationException(
                    "Mock assembly status recipe_version did not match.");
            if (!float.IsFinite(resumeRotationOffsetDegrees))
                throw new InvalidOperationException(
                    "Mock resume rotation offset must be finite.");
            if (snapshot.expected_step_count != observations.Length)
                throw new InvalidOperationException(
                    "Mock assembly status step count did not match the scene.");
            if (snapshot.placed_count < 0 ||
                snapshot.placed_count > snapshot.expected_step_count)
                throw new InvalidOperationException(
                    "Mock assembly status placed_count is out of range.");
            if (snapshot.placed_slot_codes == null ||
                snapshot.placed_slot_codes.Length != snapshot.placed_count)
                throw new InvalidOperationException(
                    "Mock assembly status must identify every placed slot.");
            var placedSlots = new HashSet<string>(StringComparer.Ordinal);
            foreach (string slotCode in snapshot.placed_slot_codes)
            {
                if (string.IsNullOrWhiteSpace(slotCode) || !placedSlots.Add(slotCode) ||
                    !slotTargets.ContainsKey(slotCode))
                    throw new InvalidOperationException(
                        "Mock assembly status contains a duplicate or unknown placed slot.");
            }
            if (snapshot.held_step_order < 0 ||
                snapshot.held_step_order > snapshot.expected_step_count ||
                snapshot.held_step_order != 0 &&
                snapshot.held_step_order != snapshot.placed_count + 1)
                throw new InvalidOperationException(
                    "Mock assembly status held_step_order is out of sequence.");
            if (snapshot.held_step_order > 0)
            {
                if (string.IsNullOrWhiteSpace(snapshot.held_slot_code) ||
                    placedSlots.Contains(snapshot.held_slot_code) ||
                    !slotTargets.TryGetValue(snapshot.held_slot_code, out var held) ||
                    snapshot.held_part_id != held.PartId)
                    throw new InvalidOperationException(
                        "Mock assembly status held item did not match the scene.");
            }
            if (snapshot.state == Picked && snapshot.held_step_order == 0 ||
                snapshot.state != Picked && snapshot.state != Paused &&
                snapshot.state != Failed &&
                snapshot.held_step_order != 0)
                throw new InvalidOperationException(
                    "Mock assembly status held item did not match its state.");
            if (snapshot.state == Started && snapshot.placed_count != 0 ||
                snapshot.state == Placed && snapshot.placed_count == 0 ||
                snapshot.state == AssemblyCompleted &&
                snapshot.placed_count != snapshot.expected_step_count ||
                (snapshot.state == PcbPicked || snapshot.state == PcbPlaced) &&
                snapshot.placed_count != snapshot.expected_step_count ||
                snapshot.state == Completed &&
                snapshot.placed_count != snapshot.expected_step_count)
                throw new InvalidOperationException(
                    "Mock assembly status placed_count did not match its state.");
        }

        void ValidateExecution()
        {
            RefreshReferences();
            itemManager?.ValidateConfiguration();
            if (!Application.isPlaying || !isActiveAndEnabled)
                throw new InvalidOperationException("Mock assembly requires an active component in Play Mode.");
            if (terminal != null)
                throw new InvalidOperationException("A Mock assembly request is already running.");
            if (control == null || conveyor == null || itemManager == null ||
                gripperCatcher == null)
                throw new InvalidOperationException(
                    "Assign MockRobotControl, MockConveyor, ItemManager and SimGripperCatcher.");
            if (string.IsNullOrWhiteSpace(startService) || string.IsNullOrWhiteSpace(feedbackTopic) ||
                string.IsNullOrWhiteSpace(recipeVersion) ||
                string.IsNullOrWhiteSpace(productCode) ||
                string.IsNullOrWhiteSpace(productVersion))
                throw new InvalidOperationException(
                    "Mock ROS names, product identity and recipe version are required.");
            if (requestedQuantity <= 0)
                throw new InvalidOperationException(
                    "Mock requested quantity must be a positive integer.");
            if (!Uri.TryCreate(mainServerBaseUrl, UriKind.Absolute, out Uri mainServerUri) ||
                mainServerUri.Scheme != Uri.UriSchemeHttp &&
                mainServerUri.Scheme != Uri.UriSchemeHttps)
                throw new InvalidOperationException("Mock MainServer URL must use HTTP or HTTPS.");
            if (!float.IsFinite(completionTimeoutSeconds) || completionTimeoutSeconds <= 0f)
                throw new InvalidOperationException("Mock assembly timeout must be positive and finite.");
        }

        async Task SendMockAsync(string json, string operation)
        {
            Task<RemoteCmdInterfaceResponse> request = connection
                .SendServiceMessage<RemoteCmdInterfaceResponse>(startService,
                    new RemoteCmdInterfaceRequest("mock\n" + json));
            if (await Task.WhenAny(request, Task.Delay(TimeSpan.FromSeconds(5))) != request)
                throw new TimeoutException($"Mock assembly {operation} service timed out.");

            RemoteCmdInterfaceResponse message = await request;
            if (message == null || string.IsNullOrWhiteSpace(message.cmd_res))
                throw new InvalidOperationException(
                    $"Mock assembly {operation} returned an empty response.");
            StartResponse response;
            try
            {
                response = JsonUtility.FromJson<StartResponse>(message.cmd_res);
            }
            catch (Exception exception)
            {
                throw new InvalidOperationException(
                    $"Mock assembly {operation} returned invalid JSON.", exception);
            }
            if (response == null || response.job_id != activeJobId)
                throw new InvalidOperationException(
                    $"Mock assembly {operation} response job_id did not match.");
            if (!response.accepted)
            {
                string reason = string.IsNullOrWhiteSpace(response.message)
                    ? $"Mock assembly {operation} was rejected."
                    : response.message;
                throw new InvalidOperationException(
                    string.IsNullOrWhiteSpace(response.error_code)
                        ? reason
                        : response.error_code + ": " + reason);
            }
        }

        void ValidateControl(bool resume)
        {
            AssemblyProgressFrame latest = progress != null ? progress.Latest : null;
            if (!Application.isPlaying || !isActiveAndEnabled || terminal == null ||
                terminal.Task.IsCompleted || string.IsNullOrEmpty(activeJobId))
                throw new InvalidOperationException("No Mock assembly is running.");
            if (resume != (latest != null && latest.State == AssemblyState.Paused))
                throw new InvalidOperationException(resume
                    ? "Mock assembly is not paused."
                    : "Mock assembly is already paused.");
            if (!resume && latest?.State == AssemblyState.ConveyorMoving)
                throw new InvalidOperationException(
                    "Mock assembly cannot pause while the conveyor is moving.");
        }

        Task SendControlAsync(string command) => SendMockAsync(JsonUtility.ToJson(
            new ControlRequest { command = command, job_id = activeJobId }), command);

        async Task WaitForPausedStateAsync(bool paused)
        {
            double deadline = Time.realtimeSinceStartupAsDouble + 60d;
            while (isActiveAndEnabled && terminal != null && !terminal.Task.IsCompleted &&
                   Time.realtimeSinceStartupAsDouble < deadline)
            {
                if ((progress?.Latest?.State == AssemblyState.Paused) == paused)
                    return;
                await Task.Yield();
            }
            throw new TimeoutException(paused
                ? "Mock assembly pause was not confirmed."
                : "Mock assembly resume was not confirmed.");
        }

        async Task PostJobAsync(string json)
        {
            using var request = new UnityWebRequest(
                mainServerBaseUrl.TrimEnd('/') + "/api/v1/assemblies",
                UnityWebRequest.kHttpVerbPOST);
            request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json));
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            request.SetRequestHeader("X-Runtime-Mode", "mock");
            request.timeout = 5;
            UnityWebRequestAsyncOperation operation = request.SendWebRequest();
            while (!operation.isDone)
                await Task.Yield();

            StartApiResponse response = null;
            try
            {
                if (!string.IsNullOrWhiteSpace(request.downloadHandler.text))
                    response = JsonUtility.FromJson<StartApiResponse>(
                        request.downloadHandler.text);
            }
            catch (Exception exception)
            {
                throw new InvalidOperationException(
                    "MainServer returned invalid assembly JSON.", exception);
            }

            if (request.result != UnityWebRequest.Result.Success)
            {
                string message = response?.error?.message;
                string code = response?.error?.code;
                string reason = string.IsNullOrWhiteSpace(message)
                    ? $"MainServer assembly request failed ({request.responseCode})."
                    : message;
                throw new InvalidOperationException(string.IsNullOrWhiteSpace(code)
                    ? reason
                    : $"{code}: {reason}");
            }
            if (response?.data == null || response.data.job_id != activeJobId)
                throw new InvalidOperationException(
                    "MainServer assembly response job_id did not match.");
            if (response.data.accepted)
                return;

            string rejected = string.IsNullOrWhiteSpace(response.data.message)
                ? "MainServer assembly request was rejected."
                : response.data.message;
            throw new InvalidOperationException(string.IsNullOrWhiteSpace(response.data.error_code)
                ? rejected
                : $"{response.data.error_code}: {rejected}");
        }

        async Task MoveToAssemblyAndConfirmAsync(string operationId)
        {
            if (assemblyConveyorStarted)
                return;

            assemblyConveyorStarted = true;
            activeConveyorOperationId = operationId;
            string jobId = activeJobId;
            long unitId = activeUnitId;
            try
            {
                if (itemManager.CurrentBoard == null)
                {
                    assembledPcb = itemManager.BeginUnit(jobId, unitId);
                    assembledPcbPicker = itemManager.CurrentPicker;
                    itemManager.PrepareSupply();
                    _ = BuildObservations();
                }
                conveyor.SetBoard(assembledPcb);
                await conveyor.MoveBoardToAssemblyAsync();
                if (!isActiveAndEnabled || terminal == null || terminal.Task.IsCompleted ||
                    jobId != activeJobId || unitId != activeUnitId || operationId != activeConveyorOperationId)
                    return;

                await SendMockAsync(JsonUtility.ToJson(new ConveyorArrivalRequest
                {
                    command = "conveyor_arrived",
                    job_id = jobId,
                    unit_id = unitId,
                    operation_id = operationId
                }), "conveyor arrival");
            }
            catch (Exception exception)
            {
                if (jobId != activeJobId || unitId != activeUnitId || operationId != activeConveyorOperationId) return;
                if (isActiveAndEnabled)
                    await ReportConveyorFailureAsync(jobId, unitId, operationId, exception.Message);
                if (jobId == activeJobId && unitId == activeUnitId && operationId == activeConveyorOperationId)
                    FailActive(exception.Message);
            }
        }

        async Task ReportConveyorFailureAsync(string jobId, long unitId, string operationId, string message)
        {
            if (string.IsNullOrEmpty(activeJobId))
                return;

            try
            {
                await SendMockAsync(JsonUtility.ToJson(new ConveyorFailureRequest
                {
                    command = "conveyor_failed",
                    job_id = jobId,
                    unit_id = unitId,
                    operation_id = operationId,
                    message = string.IsNullOrWhiteSpace(message)
                        ? "Mock conveyor movement failed."
                        : message
                }), "conveyor failure");
            }
            catch (Exception exception)
            {
                Debug.LogWarning(
                    "Mock conveyor failure could not be reported: " + exception.Message, this);
            }
        }

        async Task MoveToInspectionAndRequestTransferAsync(string operationId)
        {
            if (inspectionTransferStarted)
                return;
            inspectionTransferStarted = true;
            activeConveyorOperationId = operationId;
            Report(AssemblyState.ConveyorMoving, null);
            bool conveyorArrived = false;
            string jobId = activeJobId;
            long unitId = activeUnitId;

            try
            {
                await conveyor.MoveBoardToInspectionAsync();
                conveyorArrived = true;
                if (!isActiveAndEnabled || terminal == null || terminal.Task.IsCompleted ||
                    jobId != activeJobId || unitId != activeUnitId || operationId != activeConveyorOperationId)
                    return;

                EnsureRosConnection();
                string json = JsonUtility.ToJson(new TransferRequest
                {
                    command = "transfer_assembled_pcb",
                    job_id = jobId,
                    unit_id = unitId,
                    operation_id = operationId,
                    assembled_pcb = BuildAssembledPcbTransfer()
                });
                Task<RemoteCmdInterfaceResponse> request = connection
                    .SendServiceMessage<RemoteCmdInterfaceResponse>(startService,
                        new RemoteCmdInterfaceRequest("mock\n" + json));
                if (await Task.WhenAny(request, Task.Delay(TimeSpan.FromSeconds(5))) != request)
                    throw new TimeoutException("Mock PCB transfer request timed out.");

                RemoteCmdInterfaceResponse message = await request;
                if (message == null || string.IsNullOrWhiteSpace(message.cmd_res))
                    throw new InvalidOperationException(
                        "Mock PCB transfer returned an empty response.");

                StartResponse response;
                try
                {
                    response = JsonUtility.FromJson<StartResponse>(message.cmd_res);
                }
                catch (Exception exception)
                {
                    throw new InvalidOperationException(
                        "Mock PCB transfer returned invalid JSON.", exception);
                }

                if (response == null || response.job_id != activeJobId)
                    throw new InvalidOperationException(
                        "Mock PCB transfer response job_id did not match.");
                if (!response.accepted)
                {
                    string reason = string.IsNullOrWhiteSpace(response.message)
                        ? "Mock PCB transfer request was rejected."
                        : response.message;
                    throw new InvalidOperationException(
                        string.IsNullOrWhiteSpace(response.error_code)
                            ? reason
                            : response.error_code + ": " + reason);
                }
            }
            catch (Exception exception)
            {
                if (jobId != activeJobId || unitId != activeUnitId || operationId != activeConveyorOperationId) return;
                if (!conveyorArrived && isActiveAndEnabled)
                    await ReportConveyorFailureAsync(jobId, unitId, operationId, exception.Message);
                if (jobId == activeJobId && unitId == activeUnitId && operationId == activeConveyorOperationId)
                    FailActive(exception.Message);
            }
        }

        void ReceiveFeedback(StringMsg message)
        {
            if (message == null || string.IsNullOrWhiteSpace(message.data))
                return;

            AssemblyFeedback feedback;
            try
            {
                feedback = JsonUtility.FromJson<AssemblyFeedback>(message.data);
            }
            catch (Exception exception)
            {
                Debug.LogWarning("Ignored invalid assembly feedback JSON: " + exception.Message, this);
                return;
            }
            if (feedback == null)
                return;
            if (recovering)
            {
                bufferedFeedback.Add(feedback);
                return;
            }

            HandleFeedback(feedback);
        }

        void HandleFeedback(AssemblyFeedback feedback)
        {
            if (terminal == null || terminal.Task.IsCompleted ||
                feedback.job_id != activeJobId)
                return;

            try
            {
                ValidateFeedback(feedback);
                if (feedback.state == Failed && feedback.unit_id > 0 && activeUnitId > 0 &&
                    feedback.unit_id != activeUnitId)
                    return;
                if (feedback.state != Failed && feedback.unit_id <= 0)
                    throw new InvalidOperationException("Assembly feedback requires a positive Unit ID.");
                if (feedback.state != Completed && itemManager.IsUnitCompleted(feedback.job_id, feedback.unit_id))
                    return;
                if (feedback.unit_id != activeUnitId && feedback.state != Failed)
                {
                    if (feedback.state != ConveyorMoving || feedback.unit_id < activeUnitId)
                        return;
                    if (activeUnitId != 0 && !assembledPcbTransferred)
                        throw new InvalidOperationException("The previous Unit has not finished PCB transfer.");
                    gripperCatcher.Release();
                    itemManager.DiscardCurrentUnit();
                    assembledPcb = null;
                    activeUnitId = feedback.unit_id;
                    ResetProgress();
                }
                bool wasPaused = progress?.Latest?.State == AssemblyState.Paused;
                if (feedback.state == Paused)
                {
                    Report(AssemblyState.Paused, null);
                    return;
                }
                if (wasPaused)
                {
                    Report(feedback.state switch
                    {
                        ConveyorMoving => AssemblyState.ConveyorMoving,
                        Started => AssemblyState.Started,
                        Picked => AssemblyState.Picked,
                        Placed => AssemblyState.Placed,
                        AssemblyCompleted => AssemblyState.Placed,
                        PcbPicked => AssemblyState.Placed,
                        PcbPlaced => AssemblyState.Placed,
                        Completed => AssemblyState.Completed,
                        Failed => AssemblyState.Failed,
                        _ => throw new InvalidOperationException(
                            "Unknown resumed assembly state: " + feedback.state)
                    }, feedback.state == Picked || feedback.state == Placed
                        ? feedback
                        : null);
                    return;
                }
                if ((feedback.state == Picked || feedback.state == Placed) &&
                    feedback.step_order <= lastPlacedStepOrder)
                    return;
                if (feedback.state == Picked && heldItem != null &&
                    feedback.step_order == heldStepOrder && feedback.part_id == heldPartId &&
                    feedback.slot_code == heldSlotCode)
                    return;

                string key = string.Concat(feedback.unit_id, "|", feedback.state, "|", feedback.step_order, "|",
                    feedback.part_id, "|", feedback.slot_code);
                if (!processedCallbacks.Add(key))
                    return;

                switch (feedback.state)
                {
                    case ConveyorMoving:
                        assemblyConveyorStarted = false;
                        Report(AssemblyState.ConveyorMoving, feedback);
                        _ = MoveToAssemblyAndConfirmAsync(feedback.operation_id);
                        break;
                    case Started:
                        Report(AssemblyState.Started, feedback);
                        break;
                    case Picked:
                        ApplyPicked(feedback);
                        Report(AssemblyState.Picked, feedback);
                        break;
                    case Placed:
                        ApplyPlaced(feedback);
                        Report(AssemblyState.Placed, feedback);
                        break;
                    case AssemblyCompleted:
                        if (heldItem != null || heldStepOrder > 0)
                            throw new InvalidOperationException(
                                "ASSEMBLY_COMPLETED arrived while a component was held.");
                        if (lastPlacedStepOrder != expectedStepCount)
                            throw new InvalidOperationException(
                                "ASSEMBLY_COMPLETED arrived before all Mock observations were placed.");
                        _ = MoveToInspectionAndRequestTransferAsync(feedback.operation_id);
                        break;
                    case PcbPicked:
                        ApplyAssembledPcbPicked();
                        Report(AssemblyState.Placed, feedback);
                        break;
                    case PcbPlaced:
                        ApplyAssembledPcbPlaced();
                        Report(AssemblyState.Placed, feedback);
                        break;
                    case Completed:
                        if (heldItem != null || assembledPcbHeld)
                            throw new InvalidOperationException("COMPLETED arrived while an object was held.");
                        if (lastPlacedStepOrder != expectedStepCount)
                            throw new InvalidOperationException(
                                "COMPLETED arrived before all Mock observations were placed.");
                        if (!assembledPcbTransferred)
                            throw new InvalidOperationException(
                                "COMPLETED arrived before the assembled PCB was transferred.");
                        Report(AssemblyState.Completed, feedback);
                        CompleteActive(string.Empty);
                        break;
                    case Failed:
                        string reason = string.IsNullOrWhiteSpace(feedback.message)
                            ? "Mock assembly failed."
                            : feedback.message;
                        Report(AssemblyState.Failed, feedback);
                        CompleteActive(string.IsNullOrWhiteSpace(feedback.error_code)
                            ? reason
                            : $"{feedback.error_code}: {reason}");
                        break;
                    default:
                        throw new InvalidOperationException(
                            "Unknown assembly feedback state: " + feedback.state);
                }
            }
            catch (Exception exception)
            {
                FailActive(exception.Message);
            }
        }

        void ResetVisualization(bool boardAtAssembly)
        {
            gripperCatcher.Release();
            itemManager.DiscardCurrentUnit();
            assembledPcb = itemManager.BeginUnit(activeJobId, activeUnitId);
            assembledPcbPicker = itemManager.CurrentPicker;
            itemManager.PrepareSupply();
            conveyor.SetBoard(assembledPcb);
            if (boardAtAssembly)
                RestoreAssembledPcbAtAssembly();
            ResetProgress();
        }

        void ResetProgress()
        {
            processedCallbacks.Clear();
            activeConveyorOperationId = null;
            heldItem = null;
            heldPartId = string.Empty;
            heldSlotCode = string.Empty;
            heldStepOrder = -1;
            lastPlacedStepOrder = 0;
            assembledPcbHeld = false;
            assembledPcbTransferred = false;
            inspectionTransferStarted = false;
            assemblyConveyorStarted = false;
        }

        static void ValidateFeedback(AssemblyFeedback feedback)
        {
            if ((feedback.state == ConveyorMoving || feedback.state == AssemblyCompleted) &&
                !Guid.TryParse(feedback.operation_id, out _))
                throw new InvalidOperationException("Conveyor feedback requires an operation UUID.");
            if (feedback.step_order < 0)
                throw new InvalidOperationException("Assembly feedback step_order must not be negative.");
            if ((feedback.state == Picked || feedback.state == Placed) &&
                (string.IsNullOrWhiteSpace(feedback.part_id) ||
                 string.IsNullOrWhiteSpace(feedback.slot_code)))
                throw new InvalidOperationException(
                    "PICKED and PLACED feedback require part_id and slot_code.");
            if ((feedback.state == ConveyorMoving || feedback.state == AssemblyCompleted || feedback.state == PcbPicked ||
                    feedback.state == PcbPlaced || feedback.state == Paused) &&
                (feedback.step_order != 0 || !string.IsNullOrWhiteSpace(feedback.part_id) ||
                 !string.IsNullOrWhiteSpace(feedback.slot_code)))
                throw new InvalidOperationException(
                    "Assembly phase feedback must not contain component step data.");
        }

        void ApplyPicked(AssemblyFeedback feedback, bool restoreRotation = false)
        {
            if (heldItem != null || feedback.step_order != lastPlacedStepOrder + 1)
                throw new InvalidOperationException("PICKED feedback arrived out of order.");
            if (!slotTargets.TryGetValue(feedback.slot_code, out var target) ||
                target.PartId != feedback.part_id || target.Item == null || target.Slot == null)
                throw new InvalidOperationException("Unknown Mock part or slot: " + feedback.slot_code);

            // Keep the item paired with the source pose sent for this slot, even
            // when YAML executes slots in a different order than the Inspector.
            Transform item = target.Item;
            if (!gripperCatcher.TryCatch(item))
                throw new InvalidOperationException("Mock gripper could not catch: " + feedback.part_id);

            // This snap represents confirmed pickup, not a measured part pose.
            item.position = gripperCatcher.transform.position;
            if (restoreRotation)
                item.rotation = gripperCatcher.transform.rotation *
                    Quaternion.Euler(0f, resumeRotationOffsetDegrees, 0f);
            heldItem = item;
            heldPartId = feedback.part_id;
            heldSlotCode = feedback.slot_code;
            heldStepOrder = feedback.step_order;
        }

        void ApplyPlaced(AssemblyFeedback feedback, bool restoreRotation = false)
        {
            if (heldItem == null || feedback.step_order != heldStepOrder ||
                feedback.part_id != heldPartId || feedback.slot_code != heldSlotCode)
                throw new InvalidOperationException("PLACED did not match the held Mock item.");
            if (!slotTargets.TryGetValue(feedback.slot_code, out var target) ||
                target.PartId != feedback.part_id || target.Slot == null || target.Item != heldItem)
                throw new InvalidOperationException("Unknown Mock part or slot: " + feedback.slot_code);

            Transform slot = target.Slot;

            Transform board = slot.parent;
            if (board == null)
                throw new InvalidOperationException(
                    "Assembly slots must be children of a PCB slot container.");

            Transform item = heldItem;
            gripperCatcher.Release();
            item.SetParent(board, true);
            item.position = slot.position;
            if (restoreRotation)
                item.rotation = slot.rotation *
                    Quaternion.Euler(0f, resumeRotationOffsetDegrees, 0f);
            lastPlacedStepOrder = feedback.step_order;
            heldItem = null;
            heldPartId = string.Empty;
            heldSlotCode = string.Empty;
            heldStepOrder = -1;
        }

        void RestoreAssembledPcbAtAssembly()
        {
            if (assembledPcb == null || assembledPcbAssemblyStopPoint == null)
                throw new InvalidOperationException(
                    "Assign assembled PCB and its assembly stop point.");

            Vector3 position = assembledPcb.position;
            position.z = assembledPcbAssemblyStopPoint.position.z;
            assembledPcb.position = position;
        }

        AssembledPcbTransfer BuildAssembledPcbTransfer()
        {
            if (assembledPcb == null || assembledPcbPicker == null ||
                assembledPcbDropPoint == null)
                throw new InvalidOperationException(
                    "Assign assembled PCB, Picker and DropPoint Transforms.");
            if (assembledPcbPicker == assembledPcb ||
                !assembledPcbPicker.IsChildOf(assembledPcb))
                throw new InvalidOperationException(
                    "The assembled PCB Picker must be a child of the assembled PCB.");
            if (assembledPcbDropPoint == assembledPcb ||
                assembledPcbDropPoint.IsChildOf(assembledPcb))
                throw new InvalidOperationException(
                    "The assembled PCB DropPoint must not be a child of the assembled PCB.");

            ValidateFiniteTransform(assembledPcb, "assembled PCB", assembledPcb.name);
            ValidateFiniteTransform(assembledPcbPicker, "assembled PCB Picker", assembledPcb.name);
            ValidateFiniteTransform(assembledPcbDropPoint, "assembled PCB DropPoint",
                assembledPcb.name);
            Quaternion sourceTcpRotation =
                DownwardTcpRotation(assembledPcbPicker.rotation);
            assembledPcbPositionFromTcp = Quaternion.Inverse(sourceTcpRotation) *
                (assembledPcb.position - assembledPcbPicker.position);
            assembledPcbRotationFromTcp = Quaternion.Inverse(sourceTcpRotation) *
                assembledPcb.rotation;

            return new AssembledPcbTransfer
            {
                source = ToRosPoseRequest(
                    new Pose(assembledPcbPicker.position, assembledPcbPicker.rotation),
                    "assembled PCB source"),
                target = ToRosPoseRequest(
                    new Pose(assembledPcbDropPoint.position, assembledPcbDropPoint.rotation),
                    "assembled PCB target")
            };
        }

        void ApplyAssembledPcbPicked()
        {
            if (assembledPcbHeld || assembledPcbTransferred || heldItem != null ||
                lastPlacedStepOrder != expectedStepCount)
                throw new InvalidOperationException("PCB_PICKED feedback arrived out of order.");

            MoveAssembledPcbToTcp(
                gripperCatcher.transform.position,
                gripperCatcher.transform.rotation);
            if (!gripperCatcher.TryCatch(assembledPcb))
                throw new InvalidOperationException(
                    "Mock gripper could not catch the assembled PCB.");
            assembledPcbHeld = true;
        }

        void ApplyAssembledPcbPlaced()
        {
            if (!assembledPcbHeld || assembledPcbTransferred)
                throw new InvalidOperationException("PCB_PLACED feedback arrived out of order.");

            gripperCatcher.Release();
            MoveAssembledPcbToTcp(assembledPcbDropPoint.position,
                DownwardTcpRotation(assembledPcbDropPoint.rotation));
            assembledPcbHeld = false;
            assembledPcbTransferred = true;
            itemManager.CompleteUnit(activeJobId, activeUnitId);
        }

        void MoveAssembledPcbToTcp(Vector3 tcpPosition, Quaternion tcpRotation)
        {
            assembledPcb.position =
                tcpPosition + tcpRotation * assembledPcbPositionFromTcp;
            assembledPcb.rotation = tcpRotation * assembledPcbRotationFromTcp;
        }

        MockObservation[] BuildObservations(bool preview = false)
        {
            if (assembledPcbAssemblyStopPoint == null)
                throw new InvalidOperationException("Assign the PCB assembly stop point.");
            // Unit 생성 전 좌표 등록은 프리팹·고정 공급점으로 계산해 이전 완료품을 참조하지 않는다.
            Vector3 boardPosition = preview ? itemManager.IncomingBoardPosition : assembledPcb.position;
            Vector3 assemblyOffset = Vector3.forward *
                (assembledPcbAssemblyStopPoint.position.z - boardPosition.z);
            ItemManager.AssemblySlot[] slotGroups = preview ? itemManager.PrefabSlots : itemManager.AssemblySlots;
            if (slotGroups == null || slotGroups.Length == 0)
                throw new InvalidOperationException("Mock assembly requires at least one slot group.");

            var itemIndices = new Dictionary<string, int>(StringComparer.Ordinal);
            var observations = new List<MockObservation>();
            slotTargets.Clear();
            foreach (ItemManager.AssemblySlot slotGroup in slotGroups)
            {
                if (slotGroup == null || string.IsNullOrWhiteSpace(slotGroup.RequiredItemType))
                    throw new InvalidOperationException("Mock slot group requires an item type.");
                if (!itemManager.TryGetItemGroup(slotGroup.RequiredItemType,
                        out ItemManager.ItemGroup itemGroup))
                    throw new InvalidOperationException(
                        "No Mock item group for: " + slotGroup.RequiredItemType);

                Transform[] slots = slotGroup.Slots;
                if (slots == null || slots.Length == 0)
                    throw new InvalidOperationException(
                        "No Mock assembly slots for: " + slotGroup.RequiredItemType);

                int itemIndex = itemIndices.TryGetValue(slotGroup.RequiredItemType, out int next)
                    ? next
                    : 0;
                Transform[] items = preview ? itemGroup.SupplyPoints : itemGroup.Items;
                if (items == null || items.Length - itemIndex < slots.Length)
                    throw new InvalidOperationException(
                        $"Mock part count for {slotGroup.RequiredItemType} must cover " +
                        $"all {slots.Length} assembly slots.");

                for (int slotIndex = 0; slotIndex < slots.Length; slotIndex++, itemIndex++)
                {
                    Transform item = items[itemIndex];
                    Transform slot = slots[slotIndex];
                    if (item == null || slot == null)
                        throw new InvalidOperationException(
                            "Mock observation part and slot Transforms are required.");
                    if (string.IsNullOrWhiteSpace(slot.name) ||
                        !slotTargets.TryAdd(slot.name, (slotGroup.RequiredItemType, item, slot)))
                        throw new InvalidOperationException(
                            "Mock slot names must be non-empty and unique: " + slot.name);
                    ValidateFiniteTransform(item, "part", slotGroup.RequiredItemType);
                    ValidateFiniteTransform(slot, "slot", slotGroup.RequiredItemType);
                    if (!float.IsFinite(itemGroup.PickupOffsetXZ.x) ||
                        !float.IsFinite(itemGroup.PickupOffsetXZ.y))
                        throw new InvalidOperationException(
                            "Mock pickup offset must be finite for: " + slotGroup.RequiredItemType);

                    Quaternion pickupRotation = item.rotation * Quaternion.Euler(0f,
                        itemGroup.PickVertically ? 90f : 0f, 0f);
                    Pose pickup = new(item.position + new Vector3(itemGroup.PickupOffsetXZ.x,
                        0f, itemGroup.PickupOffsetXZ.y), pickupRotation);
                    Vector3 gripOffset = Quaternion.Inverse(item.rotation) *
                        (pickup.position - item.position);
                    Pose slotPose = itemManager.GetSlotPose(slot);
                    Pose placement = new(slotPose.position + assemblyOffset +
                        slotPose.rotation * gripOffset,
                        slotPose.rotation);

                    observations.Add(new MockObservation
                    {
                        // Observation numbering only; YAML owns execution order.
                        order = observations.Count + 1,
                        part_id = slotGroup.RequiredItemType,
                        slot_code = slot.name,
                        source = ToRosPoseRequest(pickup, "source"),
                        target = ToRosPoseRequest(placement, "target")
                    });
                }
                itemIndices[slotGroup.RequiredItemType] = itemIndex;
            }

            return observations.ToArray();
        }

        static void ValidateFiniteTransform(Transform value, string kind, string partId)
        {
            Vector3 position = value.position;
            Quaternion rotation = value.rotation;
            if (!IsFinite(position) || !IsFinite(rotation))
                throw new InvalidOperationException(
                    $"Mock {kind} Transform must have a finite pose for: {partId}");
        }

        static bool IsFinite(Vector3 value) =>
            float.IsFinite(value.x) && float.IsFinite(value.y) && float.IsFinite(value.z);

        static bool IsFinite(Quaternion value) =>
            float.IsFinite(value.x) && float.IsFinite(value.y) && float.IsFinite(value.z) &&
            float.IsFinite(value.w) && Quaternion.Dot(value, value) > 0f;

        RosPoseRequest ToRosPoseRequest(Pose tcpTarget, string targetName)
        {
            tcpTarget.rotation = DownwardTcpRotation(tcpTarget.rotation);
            if (!control.TryGetRosTcpTarget(tcpTarget, out Vector3 positionMillimeters,
                    out Quaternion rotation))
                throw new InvalidOperationException(
                    "Could not convert Mock " + targetName + " TCP pose to base_link.");
            if (!IsFinite(positionMillimeters) || !IsFinite(rotation))
                throw new InvalidOperationException(
                    "Converted Mock " + targetName + " TCP pose must be finite.");

            return new RosPoseRequest
            {
                xyz_mm = new[]
                {
                    positionMillimeters.x, positionMillimeters.y, positionMillimeters.z
                },
                xyzw = new[] { rotation.x, rotation.y, rotation.z, rotation.w }
            };
        }

        static Quaternion DownwardTcpRotation(Quaternion unityTargetRotation) =>
            Quaternion.AngleAxis(-unityTargetRotation.eulerAngles.y, Vector3.up) *
            Quaternion.AngleAxis(180f, Vector3.forward);

        void FailActive(string error)
        {
            if (assembledPcbHeld)
            {
                gripperCatcher.Release();
                assembledPcbHeld = false;
            }
            if (!IsRunning)
                return;
            Debug.LogError("Mock assembly failed: " + error, this);
            Report(AssemblyState.Failed, null, error);
            CompleteActive(error);
        }

        bool CompleteActive(string failure)
        {
            assemblyConveyorStarted = false;
            TaskCompletionSource<string> current = terminal;
            if (current == null || !current.TrySetResult(failure))
                return false;
            if (ReferenceEquals(terminal, current))
            {
                terminal = null;
                processedCallbacks.Clear();
                if (!awaitingExecution)
                    activeJobId = string.Empty;
            }
            return true;
        }

        /// <summary>
        /// 진행 상태를 공용 관리자에 넘긴다. 값을 만들지 않고 지금 아는 것만 옮긴다.
        /// lastPlacedStepOrder 가 곧 배치 수다 — PICKED 가 순번을 강제하므로 둘은 같다.
        /// </summary>
        void Report(AssemblyState state, AssemblyFeedback feedback, string error = null)
        {
            // Only confirmed PAUSED time is excluded; resume retains the remaining budget.
            if (awaitingExecution)
            {
                if (state == AssemblyState.Paused)
                    executionClock.Stop();
                else
                    executionClock.Start();
                TaskCompletionSource<bool> changed = executionStateChanged;
                executionStateChanged = new TaskCompletionSource<bool>();
                changed.TrySetResult(true);
            }
            if (progress == null)
                return;
            progress.Apply(new AssemblyProgressFrame(
                activeJobId,
                recipeVersion,
                state,
                feedback != null ? feedback.step_order : heldStepOrder > 0 ? heldStepOrder : 0,
                expectedStepCount,
                lastPlacedStepOrder,
                feedback != null ? feedback.part_id : heldPartId,
                feedback != null ? feedback.slot_code : heldSlotCode,
                feedback != null ? feedback.error_code : string.Empty,
                feedback != null ? feedback.message : error,
                Time.realtimeSinceStartupAsDouble));
        }

        void EnsureRosConnection()
        {
            if (string.IsNullOrWhiteSpace(startService) || string.IsNullOrWhiteSpace(feedbackTopic))
                return;

            connection ??= ROSConnection.GetOrCreateInstance();
            if (!serviceRegistered)
            {
                connection.RegisterRosService<RemoteCmdInterfaceRequest,
                    RemoteCmdInterfaceResponse>(startService);
                serviceRegistered = true;
            }
            if (!feedbackSubscribed && isActiveAndEnabled)
            {
                connection.Subscribe<StringMsg>(feedbackTopic, ReceiveFeedback);
                feedbackSubscribed = true;
            }
        }

        void RefreshReferences()
        {
            if (control == null)
                control = GetComponentInChildren<MockRobotControl>(true);

        }
    }
}
