using System;
using FR5Mvp.RobotData;
using FR5Mvp.RosCommunication;
using RosMessageTypes.Geometry;
using RosMessageTypes.Std;
using RosMessageTypes.Trajectory;
using Unity.Robotics.ROSTCPConnector;
using Unity.Robotics.ROSTCPConnector.ROSGeometry;
using UnityEngine;

namespace TWINMVP
{
    [AddComponentMenu("Robotics/TWIN MVP/MoveIt Adapter")]
    [DisallowMultipleComponent]
    public sealed class TwinMvpMoveItAdapter : MonoBehaviour
    {
        [SerializeField] Transform planningFrame;
        [SerializeField] string frameId = "base_link";
        [SerializeField] string planRequestTopic = "/twin_mvp/plan_request";
        [SerializeField] string planResultTopic = "/twin_mvp/plan_result";
        [SerializeField] string planStatusTopic = "/twin_mvp/plan_status";
        [SerializeField] string executionRequestTopic = "/twin_mvp/execution_request";
        [SerializeField] string executionStatusTopic = "/twin_mvp/execution_status";

        ROSConnection connection;

        public event Action<RobotTrajectory> PlanReceived;
        public event Action<string> PlanFailed;
        public event Action ExecutionCompleted;
        public event Action<string> ExecutionFailed;

        void Awake() => connection = ROSConnection.GetOrCreateInstance();

        void Start()
        {
            connection.RegisterPublisher<PoseStampedMsg>(planRequestTopic);
            connection.RegisterPublisher<JointTrajectoryMsg>(executionRequestTopic);
            connection.Subscribe<JointTrajectoryMsg>(planResultTopic,
                message => PlanReceived?.Invoke(PlanningAdapter.FromRos(message)));
            connection.Subscribe<StringMsg>(planStatusTopic, ReceivePlanStatus);
            connection.Subscribe<StringMsg>(executionStatusTopic, ReceiveExecutionStatus);
        }

        void OnDestroy()
        {
            if (connection == null)
                return;
            connection.Unsubscribe(planResultTopic);
            connection.Unsubscribe(planStatusTopic);
            connection.Unsubscribe(executionStatusTopic);
        }

        public void UsePlanningFrame(Transform value) => planningFrame = value;

        public void RequestPlan(Pose worldPose)
        {
            Vector3 position = planningFrame == null
                ? worldPose.position
                : planningFrame.InverseTransformPoint(worldPose.position);
            Quaternion rotation = planningFrame == null
                ? worldPose.rotation
                : Quaternion.Inverse(planningFrame.rotation) * worldPose.rotation;
            connection.Publish(planRequestTopic, new PoseStampedMsg(
                new HeaderMsg { frame_id = frameId },
                new PoseMsg(position.To<FLU>(), rotation.To<FLU>())));
        }

        public void Execute(RobotTrajectory trajectory) =>
            connection.Publish(executionRequestTopic, ExecutionAdapter.ToRos(trajectory));

        void ReceivePlanStatus(StringMsg message)
        {
            if (TryReadError(message, out string error))
                PlanFailed?.Invoke(error);
        }

        void ReceiveExecutionStatus(StringMsg message)
        {
            if (message?.data.Equals("completed", StringComparison.OrdinalIgnoreCase) == true)
                ExecutionCompleted?.Invoke();
            else if (TryReadError(message, out string error))
                ExecutionFailed?.Invoke(error);
        }

        static bool TryReadError(StringMsg message, out string error)
        {
            const string prefix = "error:";
            error = string.Empty;
            if (message?.data.StartsWith(prefix, StringComparison.OrdinalIgnoreCase) != true)
                return false;
            error = message.data.Substring(prefix.Length).Trim();
            return true;
        }

        [ContextMenu("TWIN MVP/Validate MoveIt Adapter")]
        void ValidateAdapter() =>
            Debug.Assert(planningFrame != null, "Assign the FR5 planning frame.", this);
    }
}
