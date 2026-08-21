// 역할: 로봇 상태 스냅샷에서 그리퍼 완료·고장 대상 ID만 분리해 제공한다.

using UnityEngine;

namespace MainUnity.Runtime.Robot.Status
{
    [DisallowMultipleComponent]
    public sealed class GripperSubscriber : MonoBehaviour
    {
        public bool IsMotionDone { get; private set; }
        public ushort FaultGripperId { get; private set; }

        /// <summary>최신 로봇 상태에서 그리퍼 완료 여부와 고장 대상 ID를 반영한다.</summary>
        public void ApplyState(RobotStatusFrame frame)
        {
            if (frame == null)
                return;
            IsMotionDone = frame.GripperMotionDone != 0;
            FaultGripperId = frame.GripperFaultId;
        }

        /// <summary>현재 그리퍼 열림 정도를 반환한다. 상태 메시지가 값을 제공하면 구현한다.</summary>
        public bool TryGetOpeningPercent(out float openingPercent)
        {
            // Skeleton: RobotNonrtState에는 현재 그리퍼 열림 정도가 없어 아직 채울 수 없다.
            openingPercent = 0f;
            return false;
        }
    }
}
