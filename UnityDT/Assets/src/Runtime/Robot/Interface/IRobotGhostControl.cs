using MainUnity.Runtime.RobotGhost;

namespace MainUnity.Runtime.Robot.Interface
{
    /// <summary>선택된 Backend의 최종 관절 자세를 공통 Ghost에 표시하는 계약이다.</summary>
    public interface IRobotGhostControl
    {
        bool Initialize(GhostMaster ghostMaster);
        void SetActive(bool active);
    }
}
