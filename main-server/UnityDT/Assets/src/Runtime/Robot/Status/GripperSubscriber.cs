// 역할: 로봇 상태 스냅샷에서 그리퍼 완료·고장·열림 피드백을 분리해 제공한다.

using UnityEngine;

namespace MainUnity.Runtime.Robot.Status
{
    [DisallowMultipleComponent]
    public sealed class GripperSubscriber : MonoBehaviour
    {
        public bool IsMotionDone { get; private set; }
        public ushort FaultGripperId { get; private set; }
        public byte Position { get; private set; }
        public bool IsPositionValid { get; private set; }

        /// <summary>최신 로봇 상태에서 그리퍼 완료·고장·열림 피드백을 반영한다.</summary>
        public void ApplyState(RobotStatusFrame frame)
        {
            if (frame == null)
                return;
            IsMotionDone = frame.GripperMotionDone != 0;
            FaultGripperId = frame.GripperFaultId;
            Position = frame.GripperPosition;
            IsPositionValid = frame.GripperFeedbackValid;
        }

        /// <summary>유효한 현재 그리퍼 열림 정도(0~100%)를 반환한다.</summary>
        public bool TryGetOpeningPercent(out float openingPercent)
        {
            openingPercent = Position;
            return IsPositionValid;
        }
    }
}
