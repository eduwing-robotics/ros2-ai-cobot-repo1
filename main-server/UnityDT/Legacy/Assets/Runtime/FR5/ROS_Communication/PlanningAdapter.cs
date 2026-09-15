// Pick/Place 자세와 ROS 계획 메시지 사이의 변환과 전송만 담당합니다.

using System;
using FR5Mvp.RobotData;
using RosMessageTypes.Geometry;
using RosMessageTypes.Std;
using RosMessageTypes.Trajectory;
using Unity.Robotics.ROSTCPConnector;
using Unity.Robotics.ROSTCPConnector.ROSGeometry;
using UnityEngine;

namespace FR5Mvp.RosCommunication
{
    /// <summary>Pick/Place 자세와 ROS 계획 메시지 간 변환·전송 경계입니다.</summary>
    [AddComponentMenu("Robotics/FR5/ROS/Planning Adapter")]
    [DisallowMultipleComponent]
    public sealed class PlanningAdapter : MonoBehaviour
    {
        [SerializeField] Transform planningFrame;
        [SerializeField] string frameId = "base_link";
        [SerializeField] string requestTopic = "/fr5_unity/plan_request";
        [SerializeField] string resultTopic = "/fr5_unity/plan_result";
        [SerializeField] string statusTopic = "/fr5_unity/plan_status";
        [SerializeField] string cancelTopic = "/fr5_unity/plan_cancel";

        ROSConnection connection;

        public event Action<RobotTrajectory> PlanReceived;
        public event Action<string> PlanFailed;

        void Awake() => connection = ROSConnection.GetOrCreateInstance();

        void Start()
        {
            connection.RegisterPublisher<PoseArrayMsg>(requestTopic);
            connection.RegisterPublisher<EmptyMsg>(cancelTopic);
            connection.Subscribe<JointTrajectoryMsg>(resultTopic, ReceivePlan);
            connection.Subscribe<StringMsg>(statusTopic, ReceiveStatus);
        }

        void OnDestroy()
        {
            if (connection == null)
                return;
            connection.Unsubscribe(resultTopic);
            connection.Unsubscribe(statusTopic);
        }

        public void UsePlanningFrame(Transform value) => planningFrame = value;

        /// <summary>Unity 월드 자세를 계획 프레임의 ROS FLU 자세로 변환해 발행합니다.</summary>
        public void RequestPlan(Pose pickPose, Pose placePose)
        {
            connection.Publish(requestTopic, new PoseArrayMsg(
                new HeaderMsg { frame_id = frameId },
                new[] { ToRosPose(pickPose), ToRosPose(placePose) }));
        }

        public void CancelPlan() => connection.Publish(cancelTopic, new EmptyMsg());

        void ReceivePlan(JointTrajectoryMsg message)
        {
            if (message == null)
            {
                PlanFailed?.Invoke("Planner returned an empty trajectory.");
                return;
            }
            PlanReceived?.Invoke(FromRos(message));
        }

        void ReceiveStatus(StringMsg message)
        {
            if (message == null)
                return;
            const string prefix = "error:";
            if (message.data.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                PlanFailed?.Invoke(message.data.Substring(prefix.Length).Trim());
        }

        PoseMsg ToRosPose(Pose worldPose)
        {
            Vector3 position = planningFrame == null
                ? worldPose.position
                : planningFrame.InverseTransformPoint(worldPose.position);
            Quaternion rotation = planningFrame == null
                ? worldPose.rotation
                : Quaternion.Inverse(planningFrame.rotation) * worldPose.rotation;
            return new PoseMsg(position.To<FLU>(), rotation.To<FLU>());
        }

        /// <summary>ROS trajectory를 전송 계층과 독립적인 내부 경로로 변환합니다.</summary>
        public static RobotTrajectory FromRos(JointTrajectoryMsg message)
        {
            var points = new RobotTrajectoryPoint[message.points?.Length ?? 0];
            for (int i = 0; i < points.Length; i++)
            {
                JointTrajectoryPointMsg source = message.points[i];
                double seconds = source?.time_from_start == null
                    ? 0d
                    : source.time_from_start.sec + source.time_from_start.nanosec * 1e-9d;
                points[i] = new RobotTrajectoryPoint(
                    source?.positions,
                    source?.velocities,
                    source?.accelerations,
                    source?.effort,
                    seconds);
            }

            return new RobotTrajectory(
                message.header?.frame_id,
                message.header?.stamp?.sec ?? 0,
                message.header?.stamp?.nanosec ?? 0,
                message.joint_names,
                points);
        }
    }
}
