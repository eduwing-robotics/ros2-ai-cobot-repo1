// 책임: FAIRINO SDK 상태 토픽을 공통 RobotStatusFrame으로 변환해 전달한다.
// 안전 판정·명령 완료 판단·ROS 명령 전송은 소유하지 않는다.

using System;
using MainUnity.Runtime.Robot.Interface;
using MainUnity.Runtime.Robot.Status;
using RosMessageTypes.Fairino;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Real
{
    [DisallowMultipleComponent]
    public sealed class RealStatusSubscriber : MonoBehaviour, IRobotStateSource
    {
        [SerializeField] string stateTopic = "/nonrt_state_data";
        [SerializeField] bool logReceivedState = true;
        [SerializeField, Min(0.1f)] float logIntervalSeconds = 1f;

        ROSConnection connection;
        bool subscribed;
        ulong receivedMessageCount;
        double nextLogTime;

        public event Action<RobotStatusFrame> StateReceived;
        public event Action<RobotErrorLabel, string> ErrorReceived;

        void OnDisable() => StopSubscription();

        public bool StartSubscription()
        {
            if (subscribed)
                return true;
            if (string.IsNullOrWhiteSpace(stateTopic))
            {
                ErrorReceived?.Invoke(RobotErrorLabel.InvalidData,
                    "FAIRINO state topic must not be empty.");
                return false;
            }

            try
            {
                connection ??= ROSConnection.GetOrCreateInstance();
                connection.Subscribe<RobotNonrtStateMsg>(stateTopic, ReceiveState);
                subscribed = true;
                Debug.Log($"[FAIRINO] Subscribed to {stateTopic}.", this);
                return true;
            }
            catch (Exception exception)
            {
                ErrorReceived?.Invoke(RobotErrorLabel.Connection, exception.Message);
                return false;
            }
        }

        public void StopSubscription()
        {
            if (!subscribed || connection == null)
                return;
            connection.Unsubscribe(stateTopic);
            subscribed = false;
            Debug.Log($"[FAIRINO] Unsubscribed from {stateTopic}.", this);
        }

        void ReceiveState(RobotNonrtStateMsg message)
        {
            try
            {
                if (message == null)
                    throw new ArgumentException("FAIRINO state message is null.");
                if (message.reconnect_flag != 0)
                {
                    ErrorReceived?.Invoke(RobotErrorLabel.Connection,
                        "FAIRINO SDK is disconnected from the robot controller.");
                    return;
                }

                double receiveTime = Time.realtimeSinceStartupAsDouble;
                RobotStatusFrame frame = ToStatusFrame(message, receiveTime);
                receivedMessageCount++;
                LogReceivedState(frame, receiveTime);
                StateReceived?.Invoke(frame);
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

        void LogReceivedState(RobotStatusFrame frame, double receiveTime)
        {
            if (!logReceivedState || receiveTime < nextLogTime)
                return;
            nextLogTime = receiveTime + Mathf.Max(0.1f, logIntervalSeconds);
            Debug.Log(
                $"[FAIRINO] RX #{receivedMessageCount} " +
                $"J=[{string.Join(", ", frame.JointDegrees)}] " +
                $"TCP=({frame.TcpPositionMillimeters.x:0.###}, " +
                $"{frame.TcpPositionMillimeters.y:0.###}, " +
                $"{frame.TcpPositionMillimeters.z:0.###}) mm " +
                $"motionDone={frame.RobotMotionDone} emg={frame.EmergencyStop} " +
                $"alarm={frame.Alarm} error={frame.MainErrorCode}:{frame.SubErrorCode}", this);
        }

        static RobotStatusFrame ToStatusFrame(
            RobotNonrtStateMsg message, double receiveTimeSeconds)
        {
            var joints = new[]
            {
                ToFiniteFloat(message.j1_cur_pos, "j1_cur_pos"),
                ToFiniteFloat(message.j2_cur_pos, "j2_cur_pos"),
                ToFiniteFloat(message.j3_cur_pos, "j3_cur_pos"),
                ToFiniteFloat(message.j4_cur_pos, "j4_cur_pos"),
                ToFiniteFloat(message.j5_cur_pos, "j5_cur_pos"),
                ToFiniteFloat(message.j6_cur_pos, "j6_cur_pos")
            };
            var tcpPosition = new Vector3(
                ToFiniteFloat(message.cart_x_cur_pos, "cart_x_cur_pos"),
                ToFiniteFloat(message.cart_y_cur_pos, "cart_y_cur_pos"),
                ToFiniteFloat(message.cart_z_cur_pos, "cart_z_cur_pos"));
            var tcpRotation = new Vector3(
                ToFiniteFloat(message.cart_a_cur_pos, "cart_a_cur_pos"),
                ToFiniteFloat(message.cart_b_cur_pos, "cart_b_cur_pos"),
                ToFiniteFloat(message.cart_c_cur_pos, "cart_c_cur_pos"));

            return new RobotStatusFrame(
                joints, tcpPosition, tcpRotation,
                message.robot_mode, message.prg_state, message.abnormal_stop,
                message.emg, message.alarm, message.robot_motion_done,
                message.grip_motion_done, message.gripperfaultnum,
                message.main_error_code, message.sub_error_code,
                message.timestamp, receiveTimeSeconds);
        }

        static float ToFiniteFloat(double value, string field)
        {
            if (!double.IsFinite(value) || value < -float.MaxValue || value > float.MaxValue)
                throw new ArgumentException($"{field} must be finite.");
            return (float)value;
        }

#if UNITY_EDITOR
        [ContextMenu("Self Check FAIRINO State Conversion")]
        void SelfCheckStateConversion()
        {
            var message = new RobotNonrtStateMsg
            {
                j1_cur_pos = 1d,
                cart_x_cur_pos = 100d,
                robot_motion_done = 1,
                timestamp = 2
            };
            RobotStatusFrame frame = ToStatusFrame(message, 3d);
            Debug.Assert(frame.JointDegrees[0] == 1f &&
                         frame.TcpPositionMillimeters.x == 100f &&
                         frame.RobotMotionDone == 1 && frame.SourceTimestamp == 2,
                "FAIRINO state conversion failed.", this);
        }
#endif
    }
}
