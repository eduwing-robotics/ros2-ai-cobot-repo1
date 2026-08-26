// 책임: Mock 명령을 ROS2 메시지로 변환·발행하고 Mock 완료 신호까지 대기한다.
// Unity 좌표 변환·Mock 상태 프로토콜은 여기에서만 소유한다.

using System;
using System.Collections;
using System.Collections.Generic;
using System.Threading.Tasks;
using MainUnity.Runtime.Robot.Interface;
using MainUnity.Runtime.Robot.Status;
using RosMessageTypes.Geometry;
using RosMessageTypes.Sensor;
using RosMessageTypes.Std;
using Unity.Robotics.ROSTCPConnector;
using Unity.Robotics.ROSTCPConnector.MessageGeneration;
using Unity.Robotics.ROSTCPConnector.ROSGeometry;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Mock
{
    [DisallowMultipleComponent]
    public sealed class MockRobotControl : MonoBehaviour, IRobotControl
    {
        static readonly string[] JointNames = { "j1", "j2", "j3", "j4", "j5", "j6" };
        // Mock 명령 Topic과 ROS 메시지 검증 설정이다.
        [Header("ROS2 Topics")]
        [SerializeField] string jointTargetTopic = "/unity/joint_target";
        [SerializeField] string moveJTargetTopic = "/unity/movej_target";
        [SerializeField] string tcpTargetTopic = "/unity/tcp_target";
        [SerializeField] string gripperTargetTopic = "/unity/gripper_target";
        [SerializeField] string tcpFrameId = "base_link";
        [SerializeField] string completionTopic = "/twin_visual/status";
        [SerializeField, Min(0.1f)] float completionTimeoutSeconds = 20f;

        [Header("Command Validation")]
        [SerializeField] RobotStatusManager statusManager;
        [SerializeField, Min(1f)] float maxAbsJointDegrees = 360f;
        [SerializeField, Min(1f)] float maxAbsTcpMillimeters = 10000f;

        [Header("Mock Teaching Points")]
        [SerializeField] Transform itemReadyPoint;
        [SerializeField] Transform assemblyReadyPoint;
        [SerializeField, Min(0f)] float homeToleranceDegrees = 0.1f;
        [SerializeField] float[] homeJointDegrees = { 0f, -90f, 90f, -90f, -90f, 0f };
        [SerializeField, Range(0, 100)] int openPositionPercent = 100;
        [SerializeField, Range(0, 100)] int closedPositionPercent;

        Transform robotBase;
        ROSConnection connection;
        bool publishersRegistered;
        bool completionSubscribed;
        bool waitingForCompletion;
        bool completionReceived;
        string expectedCompletion;
        string completionError;
        bool executing;

        public bool LastCommandSucceeded { get; private set; }

        void Awake() => RefreshReferences();
        void OnEnable() => SubscribeCompletion();
        void OnDisable() => UnsubscribeCompletion();
        void OnValidate() => RefreshReferences();

        public void Initialize(Transform baseLink, RobotStatusManager injectedStatusManager)
        {
            robotBase = baseLink;
            statusManager = injectedStatusManager != null ? injectedStatusManager : statusManager;
            RefreshReferences();
        }

        public Task MoveJ(RobotPoint point)
        {
            if (executing)
                return RejectExecution(RobotErrorLabel.CommandRejected,
                    "Mock robot is already executing a request.");

            IEnumerator motion;
            switch (point)
            {
                case RobotPoint.Home:
                    if (homeJointDegrees == null || homeJointDegrees.Length != 6)
                        return RejectExecution(RobotErrorLabel.InvalidData,
                            "Assign six Home joint angles.");
                    motion = MoveHome();
                    break;
                case RobotPoint.ItemReady:
                    if (itemReadyPoint == null)
                        return RejectExecution(RobotErrorLabel.InvalidData,
                            "Assign Item Ready Point.");
                    motion = MoveJTo(new Pose(itemReadyPoint.position, itemReadyPoint.rotation));
                    break;
                case RobotPoint.AssemblyReady:
                    if (assemblyReadyPoint == null)
                        return RejectExecution(RobotErrorLabel.InvalidData,
                            "Assign Assembly Ready Point.");
                    motion = MoveJTo(new Pose(assemblyReadyPoint.position, assemblyReadyPoint.rotation));
                    break;
                default:
                    return RejectExecution(RobotErrorLabel.InvalidData,
                        "Unknown robot teaching point.");
            }

            return ExecutePositionAsync(motion);
        }

        Task ExecutePositionAsync(IEnumerator motion)
        {
            if (executing)
                return RejectExecution(RobotErrorLabel.CommandRejected,
                    "Mock robot is already executing a request.");

            executing = true;
            var completion = new TaskCompletionSource<bool>();
            StartCoroutine(ExecutePosition(motion, completion));
            return completion.Task;
        }

        IEnumerator ExecutePosition(IEnumerator motion, TaskCompletionSource<bool> completion)
        {
            yield return motion;
            if (CompleteCommandFailure(completion))
                yield break;

            executing = false;
            completion.TrySetResult(true);
        }

        IEnumerator MoveHome()
        {
            float[] current = statusManager != null ? statusManager.Latest?.JointDegrees : null;
            if (current != null && current.Length == homeJointDegrees.Length)
            {
                bool atHome = true;
                for (int i = 0; i < current.Length; i++)
                    atHome &= Mathf.Abs(Mathf.DeltaAngle(current[i], homeJointDegrees[i])) <=
                        homeToleranceDegrees;
                if (atHome)
                {
                    LastCommandSucceeded = true;
                    yield break;
                }
            }

            yield return Execute(() => TrySetJointTarget(homeJointDegrees), "execution: complete");
        }

        bool CompleteCommandFailure(TaskCompletionSource<bool> completion)
        {
            if (LastCommandSucceeded)
                return false;

            string detail = statusManager != null && !string.IsNullOrWhiteSpace(statusManager.ErrorDetail)
                ? statusManager.ErrorDetail
                : "Mock command failed.";
            CompleteFailure(completion, detail);
            return true;
        }

        void CompleteFailure(TaskCompletionSource<bool> completion, string detail)
        {
            executing = false;
            completion.TrySetException(new InvalidOperationException(detail));
        }

        Task RejectExecution(RobotErrorLabel label, string detail) =>
            Task.FromException(RejectOperation(label, detail));

        internal InvalidOperationException RejectOperation(RobotErrorLabel label, string detail)
        {
            Reject(label, detail);
            return new InvalidOperationException(detail);
        }

        IEnumerator MoveJTo(Pose target) =>
            Execute(() => TryMoveJTo(target), "execution: complete");

        /// <summary>Mock 직선 이동 명령을 발행하고 완료 신호까지 기다린다.</summary>
        public IEnumerator MoveTo(Pose target) =>
            Execute(() => TryMoveTo(target), "execution: complete");

        /// <summary>수동 제어 UI의 관절 목표를 Mock ROS2 관절 명령으로 발행한다.</summary>
        public bool TrySetJointTarget(IReadOnlyList<float> jointDegrees)
        {
            if (!TryPrepare(out _))
                return false;
            if (jointDegrees == null || jointDegrees.Count != JointNames.Length)
                return Reject(RobotErrorLabel.InvalidData,
                    "Joint target requires exactly six joint angles.");

            var positions = new double[JointNames.Length];
            for (int i = 0; i < positions.Length; i++)
            {
                float value = jointDegrees[i];
                if (!IsFiniteInRange(value, maxAbsJointDegrees))
                    return Reject(RobotErrorLabel.InvalidData,
                        $"Joint {i + 1} must be finite and within ±{maxAbsJointDegrees} degrees.");
                positions[i] = value * Mathf.Deg2Rad;
            }

            return TryPublish(jointTargetTopic, new JointStateMsg(
                new HeaderMsg(), JointNames, positions, Array.Empty<double>(), Array.Empty<double>()));
        }

        bool TryMoveJTo(Pose target) => TryPublishPoseTarget(target, moveJTargetTopic);

        /// <summary>Unity TCP 목표를 base_link 기준으로 Mock ROS2에 발행한다.</summary>
        public bool TryMoveTo(Pose target) => TryPublishPoseTarget(target, tcpTargetTopic);

        bool TryPublishPoseTarget(Pose target, string targetTopic)
        {
            if (!TryGetRosTcpTarget(target, out Vector3 positionMillimeters,
                    out Quaternion rotation))
                return false;
            return TryPublishTcpTarget(targetTopic, positionMillimeters, rotation);
        }

        internal bool TryGetRosTcpTarget(Pose target, out Vector3 positionMillimeters,
            out Quaternion rotation)
        {
            positionMillimeters = default;
            rotation = default;
            RefreshReferences();
            if (robotBase == null)
                return Reject(RobotErrorLabel.InvalidData, "Robot base transform is unavailable.");

            Vector3 basePosition = robotBase.InverseTransformPoint(target.position);
            Quaternion baseRotation = Quaternion.Inverse(robotBase.rotation) * target.rotation;
            positionMillimeters = FLU.ConvertFromRUF(basePosition) * 1000f;
            rotation = FLU.ConvertFromRUF(baseRotation);
            return true;
        }

        public bool TryOpenGripper() => TrySetGripperOpeningPercent(openPositionPercent);
        public bool TryCloseGripper() => TrySetGripperOpeningPercent(closedPositionPercent);
        /// <summary>그리퍼 목표 열림 비율을 Mock ROS2 그리퍼 명령으로 발행한다.</summary>
        public bool TrySetGripperOpeningPercent(float openingPercent)
        {
            if (!TryPrepare(out _))
                return false;
            if (!IsFiniteInRange(openingPercent, 100f) || openingPercent < 0f)
                return Reject(RobotErrorLabel.InvalidData,
                    "Gripper target must be between 0 and 100 percent.");

            return TryPublish(gripperTargetTopic, new Float32Msg(openingPercent));
        }

        IEnumerator Execute(Func<bool> send, string completion)
        {
            if (!CanWaitForCompletion())
                yield break;

            BeginCompletionWait(completion);
            if (!send())
            {
                waitingForCompletion = false;
                LastCommandSucceeded = false;
                yield break;
            }

            yield return WaitForCompletion();
        }

        void BeginCompletionWait(string completion)
        {
            expectedCompletion = completion;
            completionReceived = false;
            completionError = null;
            waitingForCompletion = true;
        }

        IEnumerator WaitForCompletion()
        {
            double deadline = Time.realtimeSinceStartupAsDouble + completionTimeoutSeconds;
            while (!completionReceived && completionError == null &&
                   Time.realtimeSinceStartupAsDouble < deadline)
            {
                yield return null;
            }

            waitingForCompletion = false;
            if (completionReceived)
            {
                LastCommandSucceeded = true;
                yield break;
            }

            string detail = completionError;
            if (string.IsNullOrEmpty(detail))
                detail = string.Format(
                    "Mock command timed out after {0:0.###} seconds waiting for {1}.",
                    completionTimeoutSeconds, expectedCompletion);
            FailCompletion(CompletionFailureLabel(completionError), detail);
        }

        bool CanWaitForCompletion()
        {
            if (completionSubscribed && !string.IsNullOrWhiteSpace(completionTopic))
                return true;

            FailCompletion(RobotErrorLabel.InvalidData,
                "Mock completion topic is unavailable.");
            return false;
        }

        void FailCompletion(RobotErrorLabel label, string detail)
        {
            waitingForCompletion = false;
            LastCommandSucceeded = false;
            statusManager?.ReportError(label, detail);
        }

        static RobotErrorLabel CompletionFailureLabel(string error)
        {
            if (string.IsNullOrEmpty(error))
                return RobotErrorLabel.Timeout;
            return RobotErrorLabel.CommandRejected;
        }

        void SubscribeCompletion()
        {
            if (completionSubscribed || string.IsNullOrWhiteSpace(completionTopic))
                return;

            connection ??= ROSConnection.GetOrCreateInstance();
            connection.Subscribe<StringMsg>(completionTopic, ReceiveCompletion);
            completionSubscribed = true;
        }

        void UnsubscribeCompletion()
        {
            if (!completionSubscribed || connection == null)
                return;

            connection.Unsubscribe(completionTopic);
            completionSubscribed = false;
            waitingForCompletion = false;
        }

        void ReceiveCompletion(StringMsg message)
        {
            if (!waitingForCompletion || message == null)
                return;

            string status = message.data ?? string.Empty;
            if (status.StartsWith("error:", StringComparison.OrdinalIgnoreCase))
                completionError = status;
            else if (status == expectedCompletion)
                completionReceived = true;
        }

        bool TryPublishTcpTarget(string targetTopic, Vector3 positionMillimeters,
            Quaternion rotation)
        {
            if (!TryPrepare(out _))
                return false;
            float rotationLengthSquared = rotation.x * rotation.x + rotation.y * rotation.y +
                rotation.z * rotation.z + rotation.w * rotation.w;
            if (!IsFiniteInRange(positionMillimeters.x, maxAbsTcpMillimeters) ||
                !IsFiniteInRange(positionMillimeters.y, maxAbsTcpMillimeters) ||
                !IsFiniteInRange(positionMillimeters.z, maxAbsTcpMillimeters) ||
                !float.IsFinite(rotation.x) || !float.IsFinite(rotation.y) ||
                !float.IsFinite(rotation.z) || !float.IsFinite(rotation.w) ||
                !float.IsFinite(rotationLengthSquared) || rotationLengthSquared < 1e-12f)
            {
                return Reject(RobotErrorLabel.InvalidData,
                    "TCP target is outside the configured finite range.");
            }
            rotation = Quaternion.Normalize(rotation);

            var pose = new PoseMsg(
                new PointMsg(
                    positionMillimeters.x * 0.001,
                    positionMillimeters.y * 0.001,
                    positionMillimeters.z * 0.001),
                new QuaternionMsg(rotation.x, rotation.y, rotation.z, rotation.w));
            return TryPublish(targetTopic,
                new PoseStampedMsg(new HeaderMsg { frame_id = tcpFrameId }, pose));
        }

        bool TryPrepare(out string error)
        {
            if (string.IsNullOrWhiteSpace(jointTargetTopic) ||
                string.IsNullOrWhiteSpace(moveJTargetTopic) ||
                string.IsNullOrWhiteSpace(tcpTargetTopic) ||
                string.IsNullOrWhiteSpace(gripperTargetTopic))
            {
                error = "ROS2 target topics must not be empty.";
                return Reject(RobotErrorLabel.InvalidData, error);
            }

            if (jointTargetTopic == tcpTargetTopic ||
                jointTargetTopic == moveJTargetTopic ||
                jointTargetTopic == gripperTargetTopic ||
                moveJTargetTopic == tcpTargetTopic ||
                moveJTargetTopic == gripperTargetTopic ||
                tcpTargetTopic == gripperTargetTopic)
            {
                error = "ROS2 target topics must be unique.";
                return Reject(RobotErrorLabel.InvalidData, error);
            }

            if (statusManager == null)
            {
                error = "RobotStatusManager is not assigned.";
                return false;
            }
            if (!statusManager.CanAcceptCommand(out error))
                return false;

            connection ??= ROSConnection.GetOrCreateInstance();
            if (!publishersRegistered)
            {
                connection.RegisterPublisher<JointStateMsg>(jointTargetTopic);
                connection.RegisterPublisher<PoseStampedMsg>(moveJTargetTopic);
                connection.RegisterPublisher<PoseStampedMsg>(tcpTargetTopic);
                connection.RegisterPublisher<Float32Msg>(gripperTargetTopic);
                publishersRegistered = true;
            }

            return true;
        }

        bool TryPublish(string topic, Message message)
        {
            try
            {
                connection.Publish(topic, message);
                return true;
            }
            catch (Exception exception)
            {
                return Reject(RobotErrorLabel.Connection, exception.Message);
            }
        }

        bool Reject(RobotErrorLabel label, string detail)
        {
            statusManager?.ReportError(label, detail);
            return false;
        }

        static bool IsFiniteInRange(float value, float maxAbsolute) =>
            float.IsFinite(value) && Mathf.Abs(value) <= maxAbsolute;

#if UNITY_EDITOR
        [ContextMenu("Self Check Mock Command Conversion")]
        void SelfCheckCommandConversion()
        {
            Debug.Assert(CompletionFailureLabel(null) == RobotErrorLabel.Timeout &&
                         CompletionFailureLabel("error: rejected") == RobotErrorLabel.CommandRejected,
                "Mock completion failures must distinguish timeout from rejection.");

            Debug.Assert(itemReadyPoint != null && assemblyReadyPoint != null &&
                         homeJointDegrees?.Length == 6,
                "Mock MoveJ teaching points and Home joints must be assigned.");
        }
#endif

        void RefreshReferences()
        {
            if (statusManager == null)
                statusManager = FindAnyObjectByType<RobotStatusManager>();
        }
    }
}
