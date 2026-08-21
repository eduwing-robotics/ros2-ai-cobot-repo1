using MainUnity.Runtime.Robot.Status;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Interface
{
    public interface IRobotShadowing
    {
        /// <summary>Articulation 루트를 초기화한다.</summary>
        void Initialize(ArticulationBody articulationRoot);
        /// <summary>선형 위치·거리 mm, 회전 deg 단위의 상태를 Unity 모델에 반영한다.</summary>
        void ApplyState(RobotStatusFrame frame);
    }
}
