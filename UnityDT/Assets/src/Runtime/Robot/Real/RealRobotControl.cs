// 역할: Real 로봇의 저수준 이동과 수동 제어 명령을 제공한다.

using System.Collections.Generic;
using System.Threading.Tasks;
using MainUnity.Runtime.Robot.Interface;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Real
{
    [DisallowMultipleComponent]
    public sealed class RealRobotControl : MonoBehaviour, IRobotControl
    {
        [SerializeField] RealGripperRequest gripperRequest;

        void Awake() => RefreshReferences();
        void OnValidate() => RefreshReferences();

        /// <summary>
        /// TODO: Real 작업 노드가 준비되면 MoveJ 티칭 포인트 요청을 발행하고,
        /// 노드의 완료·거부·타임아웃 결과로 Task를 완료한다.
        /// Unity 좌표와 카메라 좌표는 Real 작업 노드가 소유한다.
        /// </summary>
        public Task MoveJ(RobotPoint point) =>
            Task.FromException(new System.NotSupportedException(
                "REAL MoveJ requires a configured ROS work node."));

        /// <summary>
        /// 현재 FAIRINO 원격 서비스에는 관절 직접 명령 경로가 연결되어 있지 않다.
        /// TODO: SDK의 안전한 관절 명령 계약이 확정되면 여기에서 연결한다.
        /// </summary>
        public bool TrySetJointTarget(IReadOnlyList<float> jointDegrees) =>
            Reject("REAL joint control is not implemented.");

        public bool TryOpenGripper() => TrySetGripperOpeningPercent(100f);
        public bool TryCloseGripper() => TrySetGripperOpeningPercent(0f);

        public bool TrySetGripperOpeningPercent(float openingPercent) =>
            gripperRequest != null && gripperRequest.TryRequestOpeningPercent(openingPercent);

        bool Reject(string detail)
        {
            Debug.LogWarning(detail, this);
            return false;
        }

        void RefreshReferences()
        {
            gripperRequest = gripperRequest != null ? gripperRequest : GetComponentInChildren<RealGripperRequest>(true);
        }
    }
}
