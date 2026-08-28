using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using MainUnity.Runtime.Robot.Assembly;
using MainUnity.Runtime.Robot.Interface;
using MainUnity.Static;
using RosMessageTypes.Fairino;
using RosMessageTypes.Std;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Mock
{
    /// <summary>Mock 조립 작업을 요청하고 callback을 씬 시각화에 반영한다.</summary>
    public sealed class MockAssemblyScenarioControl : MonoBehaviour, IRobotScenarioControl
    {
        const string Started = "STARTED";
        const string Picked = "PICKED";
        const string Placed = "PLACED";
        const string Completed = "COMPLETED";
        const string Failed = "FAILED";

        [Header("ROS Assembly")]
        [SerializeField] string startService = "/unity/assembly/start";
        [SerializeField] string feedbackTopic = "/unity/assembly/feedback";
        [SerializeField] string recipeVersion = "mock-r1";
        [SerializeField, Min(1f)] float completionTimeoutSeconds = 1800f;

        [Header("Mock Visualization")]
        [SerializeField] ItemManager itemManager;
        [SerializeField] SimGripperCatcher gripperCatcher;
        [SerializeField] float resumeRotationOffsetDegrees = 90f;

        readonly Dictionary<string, int> nextItemIndices = new(StringComparer.Ordinal);
        readonly Dictionary<string, int> nextSlotIndices = new(StringComparer.Ordinal);
        readonly HashSet<string> processedCallbacks = new(StringComparer.Ordinal);
        readonly List<AssemblyFeedback> bufferedFeedback = new();

        MockRobotControl control;
        AssemblyProgressManager progress;
        ROSConnection connection;
        TaskCompletionSource<string> terminal;
        Task recoveryTask = Task.CompletedTask;
        Transform heldItem;
        string activeRequestId;
        string heldPartId;
        string heldSlotCode;
        int expectedStepCount;
        int heldStepOrder = -1;
        int lastPlacedStepOrder = -1;
        bool serviceRegistered;
        bool feedbackSubscribed;
        bool assemblyRequested;
        bool recovering;
        int recoveryGeneration;

        [Serializable]
        sealed class StartRequest
        {
            public string command;
            public string request_id;
            public string recipe_version;
            public MockObservation[] observations;
        }

        [Serializable]
        sealed class MockObservation
        {
            public int order;
            public string part_id;
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
            public string request_id;
            public string error_code;
            public string message;
        }

        [Serializable]
        sealed class AssemblyFeedback
        {
            public string request_id;
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
            public string request_id;
            public string recipe_version;
            public string state;
            public int placed_count;
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
            EnsureRosConnection();
            recoveryTask = RecoverAsync(++recoveryGeneration);
        }

        void OnDisable()
        {
            recoveryGeneration++;
            recovering = false;
            bufferedFeedback.Clear();
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

        public async Task ExecuteAsync()
        {
            await recoveryTask;
            ValidateExecution();
            EnsureRosConnection();
            MockObservation[] observations = BuildObservations();

            var current = new TaskCompletionSource<string>();
            terminal = current;
            assemblyRequested = true;
            activeRequestId = Guid.NewGuid().ToString("N");
            processedCallbacks.Clear();
            expectedStepCount = observations.Length;
            heldStepOrder = -1;
            lastPlacedStepOrder = 0;

            Task timeout = Task.Delay(TimeSpan.FromSeconds(completionTimeoutSeconds));
            try
            {
                string json = JsonUtility.ToJson(new StartRequest
                {
                    command = "start",
                    request_id = activeRequestId,
                    recipe_version = recipeVersion,
                    observations = observations
                });
                Task<RemoteCmdInterfaceResponse> request = connection
                    .SendServiceMessage<RemoteCmdInterfaceResponse>(startService,
                        new RemoteCmdInterfaceRequest(json));

                if (await Task.WhenAny(request, timeout) != request)
                    throw new TimeoutException("Mock assembly start service timed out.");

                ValidateStartResponse(await request);
                Report(AssemblyState.Started, null);

                if (await Task.WhenAny(current.Task, timeout) != current.Task)
                    throw new TimeoutException(
                        $"Mock assembly timed out after {completionTimeoutSeconds:0.###} seconds.");

                string failure = await current.Task;
                if (!string.IsNullOrEmpty(failure))
                    throw new InvalidOperationException(failure);
            }
            finally
            {
                if (ReferenceEquals(terminal, current))
                {
                    terminal = null;
                    activeRequestId = string.Empty;
                    processedCallbacks.Clear();
                }
            }
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
                if (control == null || itemManager == null || gripperCatcher == null)
                    throw new InvalidOperationException(
                        "Assign MockRobotControl, ItemManager and SimGripperCatcher.");

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
                }
                catch (Exception exception)
                {
                    throw new InvalidOperationException(
                        "Mock assembly status returned invalid JSON.", exception);
                }

                if (snapshot == null || !snapshot.available)
                    return;

                MockObservation[] observations = BuildObservations();
                RestoreSnapshot(snapshot, observations);
                recovering = false;
                Report(snapshot.state switch
                {
                    Started => AssemblyState.Started,
                    Picked => AssemblyState.Picked,
                    Placed => AssemblyState.Placed,
                    Completed => AssemblyState.Completed,
                    Failed => AssemblyState.Failed,
                    _ => throw new InvalidOperationException("Unknown Mock assembly state.")
                }, null, snapshot.state == Failed ? snapshot.message : null);
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
            nextItemIndices.Clear();
            nextSlotIndices.Clear();
            processedCallbacks.Clear();
            heldItem = null;
            heldPartId = string.Empty;
            heldSlotCode = string.Empty;
            heldStepOrder = -1;
            lastPlacedStepOrder = 0;
            activeRequestId = snapshot.request_id;
            expectedStepCount = snapshot.expected_step_count;

            if (snapshot.active)
            {
                for (int index = 0; index < snapshot.placed_count; index++)
                {
                    MockObservation observation = observations[index];
                    if (!itemManager.TryGetSlotGroup(observation.part_id,
                            out ItemManager.AssemblySlot group))
                        throw new InvalidOperationException(
                            "No Mock slot group for: " + observation.part_id);
                    int slotIndex = nextSlotIndices.TryGetValue(observation.part_id,
                        out int next) ? next : 0;
                    Transform[] slots = group.Slots;
                    if (slots == null || slotIndex >= slots.Length || slots[slotIndex] == null)
                        throw new InvalidOperationException(
                            "No remaining Mock slot for: " + observation.part_id);
                    string recoveredSlot = slots[slotIndex].name;
                    ApplyPicked(new AssemblyFeedback
                    {
                        request_id = snapshot.request_id,
                        state = Picked,
                        step_order = observation.order,
                        part_id = observation.part_id,
                        slot_code = recoveredSlot
                    }, true);
                    ApplyPlaced(new AssemblyFeedback
                    {
                        request_id = snapshot.request_id,
                        state = Placed,
                        step_order = observation.order,
                        part_id = observation.part_id,
                        slot_code = recoveredSlot
                    }, true);
                }

                if (snapshot.held_step_order > 0)
                {
                    MockObservation observation = observations[snapshot.held_step_order - 1];
                    ApplyPicked(new AssemblyFeedback
                    {
                        request_id = snapshot.request_id,
                        state = Picked,
                        step_order = observation.order,
                        part_id = snapshot.held_part_id,
                        slot_code = snapshot.held_slot_code
                    }, true);
                }
            }
            else
            {
                lastPlacedStepOrder = snapshot.placed_count;
            }

            assemblyRequested = snapshot.active;
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
            bool activeState = snapshot.state == Started || snapshot.state == Picked ||
                snapshot.state == Placed;
            bool terminalState = snapshot.state == Completed || snapshot.state == Failed;
            if (!activeState && !terminalState)
                throw new InvalidOperationException(
                    "Mock assembly status contains an unknown state.");
            if (snapshot.active != activeState)
                throw new InvalidOperationException(
                    "Mock assembly status active flag does not match its state.");
            if (!Guid.TryParse(snapshot.request_id, out _))
                throw new InvalidOperationException(
                    "Mock assembly status request_id must be a UUID.");
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
            if (snapshot.held_step_order < 0 ||
                snapshot.held_step_order > snapshot.expected_step_count ||
                snapshot.held_step_order != 0 &&
                snapshot.held_step_order != snapshot.placed_count + 1)
                throw new InvalidOperationException(
                    "Mock assembly status held_step_order is out of sequence.");
            if (snapshot.held_step_order > 0)
            {
                MockObservation held = observations[snapshot.held_step_order - 1];
                if (snapshot.held_part_id != held.part_id ||
                    string.IsNullOrWhiteSpace(snapshot.held_slot_code))
                    throw new InvalidOperationException(
                        "Mock assembly status held item did not match the scene.");
            }
            if (snapshot.state == Picked && snapshot.held_step_order == 0 ||
                snapshot.state != Picked && snapshot.state != Failed &&
                snapshot.held_step_order != 0)
                throw new InvalidOperationException(
                    "Mock assembly status held item did not match its state.");
            if (snapshot.state == Started && snapshot.placed_count != 0 ||
                snapshot.state == Placed && snapshot.placed_count == 0 ||
                snapshot.state == Completed &&
                snapshot.placed_count != snapshot.expected_step_count)
                throw new InvalidOperationException(
                    "Mock assembly status placed_count did not match its state.");
        }

        void ValidateExecution()
        {
            RefreshReferences();
            if (!Application.isPlaying || !isActiveAndEnabled)
                throw new InvalidOperationException("Mock assembly requires an active component in Play Mode.");
            if (terminal != null)
                throw new InvalidOperationException("A Mock assembly request is already running.");
            if (control == null || itemManager == null || gripperCatcher == null)
                throw new InvalidOperationException(
                    "Assign MockRobotControl, ItemManager and SimGripperCatcher.");
            if (string.IsNullOrWhiteSpace(startService) || string.IsNullOrWhiteSpace(feedbackTopic) ||
                string.IsNullOrWhiteSpace(recipeVersion))
                throw new InvalidOperationException("Mock assembly ROS names and recipe version are required.");
            if (!float.IsFinite(completionTimeoutSeconds) || completionTimeoutSeconds <= 0f)
                throw new InvalidOperationException("Mock assembly timeout must be positive and finite.");
            if (assemblyRequested)
                throw new InvalidOperationException("Reload the Mock scene before starting another assembly.");
        }

        void ValidateStartResponse(RemoteCmdInterfaceResponse message)
        {
            if (message == null || string.IsNullOrWhiteSpace(message.cmd_res))
                throw new InvalidOperationException("Mock assembly start returned an empty response.");

            StartResponse response;
            try
            {
                response = JsonUtility.FromJson<StartResponse>(message.cmd_res);
            }
            catch (Exception exception)
            {
                throw new InvalidOperationException("Mock assembly start returned invalid JSON.", exception);
            }

            if (response == null || response.request_id != activeRequestId)
                throw new InvalidOperationException("Mock assembly start response request_id did not match.");
            if (response.accepted)
                return;

            string reason = string.IsNullOrWhiteSpace(response.message)
                ? "Mock assembly request was rejected."
                : response.message;
            assemblyRequested = false;
            throw new InvalidOperationException(string.IsNullOrWhiteSpace(response.error_code)
                ? reason
                : $"{response.error_code}: {reason}");
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
                feedback.request_id != activeRequestId)
                return;

            try
            {
                ValidateFeedback(feedback);
                if ((feedback.state == Picked || feedback.state == Placed) &&
                    feedback.step_order <= lastPlacedStepOrder)
                    return;
                if (feedback.state == Picked && heldItem != null &&
                    feedback.step_order == heldStepOrder && feedback.part_id == heldPartId &&
                    feedback.slot_code == heldSlotCode)
                    return;

                string key = string.Concat(feedback.state, "|", feedback.step_order, "|",
                    feedback.part_id, "|", feedback.slot_code);
                if (!processedCallbacks.Add(key))
                    return;

                switch (feedback.state)
                {
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
                    case Completed:
                        if (heldItem != null)
                            throw new InvalidOperationException("COMPLETED arrived while an item was held.");
                        if (lastPlacedStepOrder != expectedStepCount)
                            throw new InvalidOperationException(
                                "COMPLETED arrived before all Mock observations were placed.");
                        Report(AssemblyState.Completed, feedback);
                        terminal.TrySetResult(string.Empty);
                        break;
                    case Failed:
                        string reason = string.IsNullOrWhiteSpace(feedback.message)
                            ? "Mock assembly failed."
                            : feedback.message;
                        Report(AssemblyState.Failed, feedback);
                        terminal.TrySetResult(string.IsNullOrWhiteSpace(feedback.error_code)
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

        static void ValidateFeedback(AssemblyFeedback feedback)
        {
            if (feedback.step_order < 0)
                throw new InvalidOperationException("Assembly feedback step_order must not be negative.");
            if ((feedback.state == Picked || feedback.state == Placed) &&
                (string.IsNullOrWhiteSpace(feedback.part_id) ||
                 string.IsNullOrWhiteSpace(feedback.slot_code)))
                throw new InvalidOperationException(
                    "PICKED and PLACED feedback require part_id and slot_code.");
        }

        void ApplyPicked(AssemblyFeedback feedback, bool restoreRotation = false)
        {
            if (heldItem != null || feedback.step_order != lastPlacedStepOrder + 1)
                throw new InvalidOperationException("PICKED feedback arrived out of order.");
            if (!itemManager.TryGetItemGroup(feedback.part_id, out ItemManager.ItemGroup group))
                throw new InvalidOperationException("Unknown Mock part_id: " + feedback.part_id);

            int index = nextItemIndices.TryGetValue(feedback.part_id, out int next) ? next : 0;
            if (group.Items == null || index >= group.Items.Length || group.Items[index] == null)
                throw new InvalidOperationException("No remaining Mock item for: " + feedback.part_id);

            Transform item = group.Items[index];
            if (!gripperCatcher.TryCatch(item))
                throw new InvalidOperationException("Mock gripper could not catch: " + feedback.part_id);

            // ponytail: Remove this snap when mock-r1 recipe poses and frames are calibrated.
            item.position = gripperCatcher.transform.position;
            if (restoreRotation)
                item.rotation = gripperCatcher.transform.rotation *
                    Quaternion.Euler(0f, resumeRotationOffsetDegrees, 0f);
            heldItem = item;
            heldPartId = feedback.part_id;
            heldSlotCode = feedback.slot_code;
            heldStepOrder = feedback.step_order;
            nextItemIndices[feedback.part_id] = index + 1;
        }

        void ApplyPlaced(AssemblyFeedback feedback, bool restoreRotation = false)
        {
            if (heldItem == null || feedback.step_order != heldStepOrder ||
                feedback.part_id != heldPartId || feedback.slot_code != heldSlotCode)
                throw new InvalidOperationException("PLACED did not match the held Mock item.");
            if (!itemManager.TryGetSlotGroup(feedback.part_id, out ItemManager.AssemblySlot group))
                throw new InvalidOperationException("No Mock slot group for: " + feedback.part_id);

            int index = nextSlotIndices.TryGetValue(feedback.part_id, out int next) ? next : 0;
            Transform[] slots = group.Slots;
            if (index >= slots.Length || slots[index] == null)
                throw new InvalidOperationException("No remaining Mock slot for: " + feedback.part_id);

            Transform slot = slots[index];
            // 씬 슬롯 이름이 곧 slot_code 다. ROS 는 실행 전에 part_id 만 대조하므로
            // (mock_sim.resolve_observations) 같은 타입 안의 순서가 어긋나도 조립은 통과하고
            // 기록만 틀어진다. 로봇은 Unity 가 준 좌표로 가므로 동작은 옳고 이름만 틀리며,
            // 그 결과 unit_defects 가 엉뚱한 물리 슬롯을 가리킨다. 이 비교가 유일한 방어선이다.
            if (!string.Equals(slot.name, feedback.slot_code, StringComparison.Ordinal))
                Debug.LogError(
                    $"Slot code mismatch at step {feedback.step_order}: recipe '{feedback.slot_code}' " +
                    $"vs scene '{slot.name}'. Inspection records will name the wrong slot.", this);

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
            nextSlotIndices[feedback.part_id] = index + 1;
            lastPlacedStepOrder = feedback.step_order;
            heldItem = null;
            heldPartId = string.Empty;
            heldSlotCode = string.Empty;
            heldStepOrder = -1;
        }

        MockObservation[] BuildObservations()
        {
            ItemManager.AssemblySlot[] slotGroups = itemManager.AssemblySlots;
            if (slotGroups == null || slotGroups.Length == 0)
                throw new InvalidOperationException("Mock assembly requires at least one slot group.");

            var itemIndices = new Dictionary<string, int>(StringComparer.Ordinal);
            var observations = new List<MockObservation>();
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
                Transform[] items = itemGroup.Items;
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
                    Pose placement = new(slot.position + slot.rotation * gripOffset,
                        slot.rotation);

                    observations.Add(new MockObservation
                    {
                        // Correlation only; the loaded recipe owns execution order validation.
                        order = observations.Count + 1,
                        part_id = slotGroup.RequiredItemType,
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
            if (terminal == null || !terminal.TrySetResult(error))
                return;
            Debug.LogError("Mock assembly failed: " + error, this);
            Report(AssemblyState.Failed, null, error);
        }

        /// <summary>
        /// 진행 상태를 공용 관리자에 넘긴다. 값을 만들지 않고 지금 아는 것만 옮긴다.
        /// lastPlacedStepOrder 가 곧 배치 수다 — PICKED 가 순번을 강제하므로 둘은 같다.
        /// </summary>
        void Report(AssemblyState state, AssemblyFeedback feedback, string error = null)
        {
            if (progress == null)
                return;
            progress.Apply(new AssemblyProgressFrame(
                activeRequestId,
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
            if (itemManager == null)
                itemManager = FindAnyObjectByType<ItemManager>();
            if (gripperCatcher == null)
                gripperCatcher = FindAnyObjectByType<SimGripperCatcher>();
        }
    }
}
