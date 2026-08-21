// 책임: 검증된 최신 로봇 상태를 단일 원본으로 보관하고 공통 안전 상태를 판정한다.
// 명령 전송·완료 대기·ROS 메시지 변환은 소유하지 않는다.

using System;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Status
{
    public enum RobotRunState
    {
        Disconnected,
        Idle,
        Running,
        Error
    }

    public enum RobotErrorLabel
    {
        None,
        Connection,
        Timeout,
        InvalidData,
        EmergencyStop,
        RobotAlarm,
        ServiceMismatch,
        CommandRejected,
        Unknown
    }

    public sealed class RobotStatusFrame
    {
        internal RobotStatusFrame(
            float[] jointDegrees,
            Vector3 tcpPositionMillimeters,
            Vector3 tcpRotationDegrees,
            byte robotMode,
            byte programState,
            byte abnormalStop,
            byte emergencyStop,
            byte alarm,
            byte robotMotionDone,
            byte gripperMotionDone,
            ushort gripperFaultId,
            uint mainErrorCode,
            uint subErrorCode,
            ulong sourceTimestamp,
            double receiveTimeSeconds)
        {
            JointDegrees = jointDegrees;
            TcpPositionMillimeters = tcpPositionMillimeters;
            TcpRotationDegrees = tcpRotationDegrees;
            RobotMode = robotMode;
            ProgramState = programState;
            AbnormalStop = abnormalStop;
            EmergencyStop = emergencyStop;
            Alarm = alarm;
            RobotMotionDone = robotMotionDone;
            GripperMotionDone = gripperMotionDone;
            GripperFaultId = gripperFaultId;
            MainErrorCode = mainErrorCode;
            SubErrorCode = subErrorCode;
            SourceTimestamp = sourceTimestamp;
            ReceiveTimeSeconds = receiveTimeSeconds;
        }

        public float[] JointDegrees { get; }
        public Vector3 TcpPositionMillimeters { get; }
        public Vector3 TcpRotationDegrees { get; }
        public byte RobotMode { get; }
        public byte ProgramState { get; }
        public byte AbnormalStop { get; }
        public byte EmergencyStop { get; }
        public byte Alarm { get; }
        public byte RobotMotionDone { get; }
        public byte GripperMotionDone { get; }
        public ushort GripperFaultId { get; }
        public uint MainErrorCode { get; }
        public uint SubErrorCode { get; }
        public ulong SourceTimestamp { get; }
        public double ReceiveTimeSeconds { get; }
    }

    [DisallowMultipleComponent]
    public sealed class RobotStatusManager : MonoBehaviour
    {
        [SerializeField, Min(0.05f)] float staleAfterSeconds = 0.5f;

        double lastReceiveTimeSeconds = -1d;

        public RobotRunState State { get; private set; } = RobotRunState.Disconnected;
        public RobotErrorLabel ErrorLabel { get; private set; } = RobotErrorLabel.Connection;
        public string ErrorDetail { get; private set; } = "Robot state has not been received.";
        public RobotStatusFrame Latest { get; private set; }

        public event Action<RobotRunState, RobotErrorLabel, string> StatusChanged;

        void Update()
        {
            if (lastReceiveTimeSeconds < 0d ||
                Time.realtimeSinceStartupAsDouble - lastReceiveTimeSeconds <= staleAfterSeconds)
                return;

            if (State != RobotRunState.Disconnected || ErrorLabel != RobotErrorLabel.Timeout)
                SetStatus(RobotRunState.Disconnected, RobotErrorLabel.Timeout,
                    $"Robot state is older than {staleAfterSeconds:0.###} seconds.");
        }

        /// <summary>검증된 최신 로봇 상태를 저장하고 운전 상태와 오류 라벨을 갱신한다.</summary>
        public void ApplyState(RobotStatusFrame frame)
        {
            if (frame == null || frame.JointDegrees == null || frame.JointDegrees.Length != 6)
            {
                ReportError(RobotErrorLabel.InvalidData, "Robot state must contain six joints.");
                return;
            }

            Latest = frame;
            lastReceiveTimeSeconds = frame.ReceiveTimeSeconds;

            if (frame.EmergencyStop != 0)
                SetStatus(RobotRunState.Error, RobotErrorLabel.EmergencyStop,
                    "Robot emergency stop is active.");
            else if (frame.AbnormalStop != 0 || frame.Alarm != 0 ||
                     frame.MainErrorCode != 0 || frame.SubErrorCode != 0)
                SetStatus(RobotRunState.Error, RobotErrorLabel.RobotAlarm,
                    $"Robot alarm: main={frame.MainErrorCode}, sub={frame.SubErrorCode}.");
            else
                SetStatus(frame.RobotMotionDone == 0 ? RobotRunState.Running : RobotRunState.Idle,
                    RobotErrorLabel.None, string.Empty);
        }

        /// <summary>현재 상태에서 새 제어 명령을 안전하게 받을 수 있는지 확인한다.</summary>
        public bool CanAcceptCommand(out string reason)
        {
            if (State == RobotRunState.Idle && ErrorLabel == RobotErrorLabel.None)
            {
                reason = string.Empty;
                return true;
            }

            reason = string.IsNullOrEmpty(ErrorDetail)
                ? $"Robot state is {State}."
                : ErrorDetail;
            return false;
        }

        /// <summary>통신·파싱·명령 계층에서 구분한 오류를 상태에 반영한다.</summary>
        public void ReportError(RobotErrorLabel label, string detail)
        {
            SetStatus(RobotRunState.Error, label,
                string.IsNullOrWhiteSpace(detail) ? label.ToString() : detail);
        }

        void SetStatus(RobotRunState state, RobotErrorLabel label, string detail)
        {
            bool changed = State != state || ErrorLabel != label || ErrorDetail != detail;
            State = state;
            ErrorLabel = label;
            ErrorDetail = detail;
            if (changed)
                StatusChanged?.Invoke(state, label, detail);
        }
    }
}
