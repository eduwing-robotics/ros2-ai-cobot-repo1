// ROS 연결, joint-state 단일 구독과 전송 Adapter 라우팅을 조정합니다.

using System;
using System.Collections.Generic;
using FR5Mvp.RobotData;
using RosMessageTypes.Sensor;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;
using UnityEngine.Serialization;

namespace FR5Mvp.RosCommunication
{
    /// <summary>ROS 연결, 단일 joint-state 구독과 전송 adapter 라우팅을 조정합니다.</summary>
    [AddComponentMenu("Robotics/FR5/ROS Communication Orchestrator")]
    [DisallowMultipleComponent]
    public sealed class RosCommunicationOrchestrator : MonoBehaviour
    {
        static readonly string[] JointNames = { "j1", "j2", "j3", "j4", "j5", "j6" };

        [SerializeField] string rosIpAddress = "127.0.0.1";
        [SerializeField, Range(1, 65535)] int rosPort = 10000;
        [FormerlySerializedAs("topicName")]
        [SerializeField] string jointStateTopic = "/joint_states";
        [SerializeField] string gripperJointName = "finger_right_joint";
        [SerializeField] PlanningAdapter planningAdapter;
        [SerializeField] ExecutionAdapter executionAdapter;
        [SerializeField] GripperCommandAdapter gripperCommandAdapter;

        readonly float[] degrees = new float[JointNames.Length];
        ROSConnection connection;
        bool childEventsBound;
        bool jointStateSubscribed;

        public bool IsConfigured =>
            planningAdapter != null &&
            executionAdapter != null &&
            gripperCommandAdapter != null &&
            !string.IsNullOrWhiteSpace(jointStateTopic);
        public string LastError { get; private set; } = string.Empty;
        public string GripperStatus =>
            gripperCommandAdapter != null ? gripperCommandAdapter.LastStatus : "unconfigured";

        public event Action<IReadOnlyList<string>, IReadOnlyList<float>, double>
            JointStateReceived;
        public event Action<float> GripperStateReceived;
        public event Action<RobotTrajectory> PlanReceived;
        public event Action<string> PlanFailed;
        public event Action ExecutionCompleted;
        public event Action<string> ExecutionFailed;

        void Awake()
        {
            connection = ROSConnection.GetOrCreateInstance();
            connection.RosIPAddress = rosIpAddress;
            connection.RosPort = rosPort;
            connection.ConnectOnStart = true;
            RefreshAdapters(transform.root);
        }

        void OnEnable()
        {
            BindChildEvents();
            SubscribeJointState();
        }

        void Start() => SubscribeJointState();

        void OnDisable()
        {
            UnsubscribeJointState();
            UnbindChildEvents();
        }

        /// <summary>현재 FR5 계층에서 ROS 전송 Adapter를 찾아 이 기능 아래에 연결합니다.</summary>
        public void RefreshAdapters(Transform root)
        {
            UnbindChildEvents();
            Transform scope = root != null ? root : transform.root;
            if (planningAdapter == null)
                planningAdapter = scope.GetComponentInChildren<PlanningAdapter>(true);
            if (executionAdapter == null)
                executionAdapter = scope.GetComponentInChildren<ExecutionAdapter>(true);
            if (gripperCommandAdapter == null)
                gripperCommandAdapter = scope.GetComponentInChildren<GripperCommandAdapter>(true);
            BindChildEvents();
        }

        public void UsePlanningFrame(Transform value) =>
            planningAdapter?.UsePlanningFrame(value);

        public void RequestPlan(Pose pickPose, Pose placePose) =>
            planningAdapter?.RequestPlan(pickPose, placePose);

        public void CancelPlan() => planningAdapter?.CancelPlan();

        public void Execute(RobotTrajectory trajectory) =>
            executionAdapter?.Execute(trajectory);

        public void CancelExecution() => executionAdapter?.Cancel();
        public void StopExecution() => executionAdapter?.Cancel();
        public void SendGripperCommand(float meters) =>
            gripperCommandAdapter?.SendCommand(meters);

        void SubscribeJointState()
        {
            if (jointStateSubscribed || connection == null || !Application.isPlaying)
                return;
            if (string.IsNullOrWhiteSpace(jointStateTopic))
            {
                LastError = "Joint-state topic must not be empty.";
                return;
            }
            connection.Subscribe<JointStateMsg>(jointStateTopic, ReceiveJointState);
            jointStateSubscribed = true;
        }

        void UnsubscribeJointState()
        {
            if (!jointStateSubscribed || connection == null)
                return;
            connection.Unsubscribe(jointStateTopic);
            jointStateSubscribed = false;
        }

        void ReceiveJointState(JointStateMsg message)
        {
            bool armValid = TryConvertArmState(
                message,
                Time.realtimeSinceStartupAsDouble,
                degrees,
                out double timestamp,
                out string error);
            if (armValid)
            {
                LastError = string.Empty;
                JointStateReceived?.Invoke(JointNames, degrees, timestamp);
            }
            else
            {
                LastError = error;
                Debug.LogWarning($"Ignored {jointStateTopic}: {error}", this);
            }

            if (TryReadGripperPosition(message, gripperJointName, out float meters))
                GripperStateReceived?.Invoke(meters);
        }

        void BindChildEvents()
        {
            if (childEventsBound || !isActiveAndEnabled)
                return;
            if (planningAdapter != null)
            {
                planningAdapter.PlanReceived += ForwardPlan;
                planningAdapter.PlanFailed += ForwardPlanFailure;
            }
            if (executionAdapter != null)
            {
                executionAdapter.ExecutionCompleted += ForwardExecutionCompleted;
                executionAdapter.ExecutionFailed += ForwardExecutionFailure;
            }
            childEventsBound = true;
        }

        void UnbindChildEvents()
        {
            if (!childEventsBound)
                return;
            if (planningAdapter != null)
            {
                planningAdapter.PlanReceived -= ForwardPlan;
                planningAdapter.PlanFailed -= ForwardPlanFailure;
            }
            if (executionAdapter != null)
            {
                executionAdapter.ExecutionCompleted -= ForwardExecutionCompleted;
                executionAdapter.ExecutionFailed -= ForwardExecutionFailure;
            }
            childEventsBound = false;
        }

        void ForwardPlan(RobotTrajectory value) => PlanReceived?.Invoke(value);
        void ForwardPlanFailure(string error) => PlanFailed?.Invoke(error);
        void ForwardExecutionCompleted() => ExecutionCompleted?.Invoke();
        void ForwardExecutionFailure(string error) => ExecutionFailed?.Invoke(error);

        /// <summary>ROS joint-state를 FR5 관절 순서의 degree 값으로 검증·변환합니다.</summary>
        public static bool TryConvertArmState(
            JointStateMsg message,
            double receiveTimeSeconds,
            float[] outputDegrees,
            out double timestamp,
            out string error)
        {
            timestamp = receiveTimeSeconds;
            error = string.Empty;
            if (message?.name == null || message.position == null ||
                message.name.Length != message.position.Length)
            {
                error = "Joint names and positions must have matching lengths.";
                return false;
            }
            if (outputDegrees == null || outputDegrees.Length != JointNames.Length)
            {
                error = $"Expected an output buffer for {JointNames.Length} joints.";
                return false;
            }

            if (message.header?.stamp != null)
            {
                if (message.header.stamp.nanosec >= 1_000_000_000)
                {
                    error = "Joint-state timestamp nanoseconds are invalid.";
                    return false;
                }
                if (message.header.stamp.sec != 0 || message.header.stamp.nanosec != 0)
                    timestamp = message.header.stamp.sec +
                        message.header.stamp.nanosec * 1e-9d;
            }

            for (int i = 0; i < JointNames.Length; i++)
            {
                int index = Array.IndexOf(message.name, JointNames[i]);
                if (index < 0 || Array.LastIndexOf(message.name, JointNames[i]) != index)
                {
                    error = $"Joint '{JointNames[i]}' must appear exactly once.";
                    return false;
                }
                double radians = message.position[index];
                if (!double.IsFinite(radians))
                {
                    error = $"Joint '{JointNames[i]}' position must be finite.";
                    return false;
                }
                outputDegrees[i] = (float)(radians * Mathf.Rad2Deg);
            }
            return true;
        }

        /// <summary>ROS joint-state에서 중복되지 않은 유효 그리퍼 관절 위치를 읽습니다.</summary>
        public static bool TryReadGripperPosition(
            JointStateMsg message,
            string expectedJoint,
            out float meters)
        {
            meters = 0f;
            if (message?.name == null || message.position == null ||
                message.name.Length != message.position.Length)
                return false;
            int index = Array.IndexOf(message.name, expectedJoint);
            if (index < 0 || Array.LastIndexOf(message.name, expectedJoint) != index)
                return false;
            double position = message.position[index];
            if (!double.IsFinite(position))
                return false;
            meters = (float)position;
            return true;
        }
    }
}
