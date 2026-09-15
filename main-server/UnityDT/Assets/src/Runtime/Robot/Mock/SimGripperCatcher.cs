// 역할: Mock 및 시각화 환경에서 파지한 부품을 그리퍼 자식으로 유지하고 해제 시 원래 부모로 복원한다.

using UnityEngine;

namespace MainUnity.Runtime.Robot.Mock
{
    /// <summary>
    /// 그리퍼가 파지한 부품의 부모를 임시로 변경해 로봇 이동을 따라가게 한다.
    /// 물리 설정을 변경하지 않고 Transform 부모 관계만 사용한다.
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class SimGripperCatcher : MonoBehaviour
    {
        Transform caughtPart;
        Transform originalParent;

        public bool TryCatch(Transform part)
        {
            if (part == null || caughtPart != null)
                return false;

            caughtPart = part;
            originalParent = part.parent;
            part.SetParent(transform, true);
            return true;
        }

        public void Release()
        {
            if (caughtPart == null)
                return;

            caughtPart.SetParent(originalParent, true);
            caughtPart = null;
            originalParent = null;
        }
    }
}
