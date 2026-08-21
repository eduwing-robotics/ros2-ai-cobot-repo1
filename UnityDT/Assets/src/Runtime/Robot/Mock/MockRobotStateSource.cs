// 역할: MoveIt/FakeSystem의 joint_states를 공통 로봇 상태로 변환한다.

using System;
using MainUnity.Runtime.Robot.Interface;
using MainUnity.Runtime.Robot.Status;
using RosMessageTypes.Sensor;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Mock
{
    [DisallowMultipleComponent]
    public sealed class MockRobotStateSource : MonoBehaviour, IRobotStateSource
    {
        const int JointCount = 6;
        const string StateTopic = "/joint_states";

        ROSConnection connection;
        bool subscribed;

        public event Action<RobotStatusFrame> StateReceived;
        public event Action<RobotErrorLabel, string> ErrorReceived;

        // TODO: 공통 그리퍼 상태 계약이 생기면 RobotStatusFrame으로 통합한다.
        public event Action<float> GripperJointReceived;

        void Awake() => connection = ROSConnection.GetOrCreateInstance();

        void OnEnable()
        {
            if (!Application.isPlaying)
                return;
            StartSubscription();
        }

        void OnDisable() => StopSubscription();

        /// <summary>joint_states 구독을 시작한다.</summary>
        public bool StartSubscription()
        {
            if (subscribed)
                return true;
            try
            {
                connection ??= ROSConnection.GetOrCreateInstance();
                connection.Subscribe<JointStateMsg>(StateTopic, ReceiveState);
                subscribed = true;
                return true;
            }
            catch (Exception exception)
            {
                ErrorReceived?.Invoke(RobotErrorLabel.Connection, exception.Message);
                return false;
            }
        }

        /// <summary>현재 joint_states 구독을 해제한다.</summary>
        public void StopSubscription()
        {
            if (!subscribed || connection == null)
                return;

            connection.Unsubscribe(StateTopic);
            subscribed = false;
        }

        void ReceiveState(JointStateMsg message)
        {
            try
            {
                if (message?.name == null || message.position == null ||
                    message.name.Length != message.position.Length)
                    throw new ArgumentException("joint_states names and positions are invalid.");

                var joints = new float[JointCount];
                for (int jointIndex = 0; jointIndex < JointCount; jointIndex++)
                {
                    string expected = $"j{jointIndex + 1}";
                    int sourceIndex = Array.FindIndex(message.name,
                        name => string.Equals(name, expected, StringComparison.OrdinalIgnoreCase));
                    if (sourceIndex < 0)
                        throw new ArgumentException($"joint_states is missing {expected}.");
                    joints[jointIndex] = ToFiniteFloat(
                        message.position[sourceIndex] * Mathf.Rad2Deg, expected);
                }

                int gripperIndex = Array.FindIndex(message.name,
                    name => string.Equals(name, "finger_right_joint",
                        StringComparison.OrdinalIgnoreCase));
                if (gripperIndex >= 0)
                    GripperJointReceived?.Invoke(ToFiniteFloat(
                        message.position[gripperIndex], "finger_right_joint"));

                // ponytail: Mock에는 FAIRINO 안전 진단이 없으므로 수신 중이면 Idle로 취급한다.
                StateReceived?.Invoke(new RobotStatusFrame(
                    joints, Vector3.zero, Vector3.zero,
                    0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0,
                    Time.realtimeSinceStartupAsDouble));
            }
            catch (ArgumentException exception)
            {
                ErrorReceived?.Invoke(RobotErrorLabel.InvalidData, exception.Message);
            }
            catch (Exception exception)
            {
                ErrorReceived?.Invoke(RobotErrorLabel.Unknown, exception.Message);
            }
        }

        static float ToFiniteFloat(double value, string field)
        {
            if (!double.IsFinite(value) || value < -float.MaxValue || value > float.MaxValue)
                throw new ArgumentException($"{field} must be finite.");
            return (float)value;
        }
    }
}
