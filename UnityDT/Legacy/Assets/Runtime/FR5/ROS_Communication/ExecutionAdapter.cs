// 내부 관절 경로와 ROS 실행 메시지 사이의 변환과 전송만 담당합니다.

using System;
using FR5Mvp.RobotData;
using RosMessageTypes.BuiltinInterfaces;
using RosMessageTypes.Std;
using RosMessageTypes.Trajectory;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

namespace FR5Mvp.RosCommunication
{
    /// <summary>내부 관절 경로와 ROS 실행 메시지 간 변환·전송 경계입니다.</summary>
    [AddComponentMenu("Robotics/FR5/ROS/Execution Adapter")]
    [DisallowMultipleComponent]
    public sealed class ExecutionAdapter : MonoBehaviour
    {
        [SerializeField] string requestTopic = "/fr5_unity/execution_request";
        [SerializeField] string statusTopic = "/fr5_unity/execution_status";
        [SerializeField] string cancelTopic = "/fr5_unity/execution_cancel";

        ROSConnection connection;

        public event Action ExecutionCompleted;
        public event Action<string> ExecutionFailed;

        void Awake() => connection = ROSConnection.GetOrCreateInstance();

        void Start()
        {
            connection.RegisterPublisher<JointTrajectoryMsg>(requestTopic);
            connection.RegisterPublisher<EmptyMsg>(cancelTopic);
            connection.Subscribe<StringMsg>(statusTopic, ReceiveStatus);
        }

        void OnDestroy()
        {
            if (connection != null)
                connection.Unsubscribe(statusTopic);
        }

        /// <summary>내부 경로를 ROS JointTrajectory로 변환해 실행기에 발행합니다.</summary>
        public void Execute(RobotTrajectory trajectory) =>
            connection.Publish(requestTopic, ToRos(trajectory));

        public void Cancel() => connection.Publish(cancelTopic, new EmptyMsg());

        void ReceiveStatus(StringMsg message)
        {
            if (message == null)
                return;
            if (message.data.Equals("completed", StringComparison.OrdinalIgnoreCase))
            {
                ExecutionCompleted?.Invoke();
                return;
            }
            const string prefix = "error:";
            if (message.data.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                ExecutionFailed?.Invoke(message.data.Substring(prefix.Length).Trim());
        }

        /// <summary>내부 경로를 ROS JointTrajectory 메시지로 변환합니다.</summary>
        public static JointTrajectoryMsg ToRos(RobotTrajectory trajectory)
        {
            if (trajectory == null)
                throw new ArgumentNullException(nameof(trajectory));

            var points = new JointTrajectoryPointMsg[trajectory.Points.Length];
            for (int i = 0; i < points.Length; i++)
            {
                RobotTrajectoryPoint source = trajectory.Points[i];
                SplitSeconds(source.TimeFromStartSeconds, out int seconds, out uint nanoseconds);
                points[i] = new JointTrajectoryPointMsg(
                    source.Positions,
                    source.Velocities,
                    source.Accelerations,
                    source.Effort,
                    new DurationMsg(seconds, nanoseconds));
            }

            return new JointTrajectoryMsg(
                new HeaderMsg
                {
                    frame_id = trajectory.FrameId,
                    stamp = new TimeMsg(
                        trajectory.StampSeconds,
                        trajectory.StampNanoseconds)
                },
                trajectory.JointNames,
                points);
        }

        static void SplitSeconds(double value, out int seconds, out uint nanoseconds)
        {
            seconds = (int)Math.Floor(value);
            nanoseconds = (uint)Math.Round((value - seconds) * 1_000_000_000d);
            if (nanoseconds < 1_000_000_000)
                return;
            seconds++;
            nanoseconds = 0;
        }
    }
}
