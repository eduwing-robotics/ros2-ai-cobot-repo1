using MainUnity.Runtime.Robot.Assembly;
using MainUnity.Runtime.Robot.Status;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Interface
{
    public interface IRobotModMatser
    {
        IRobotStateSource StateSource { get; }
        IRobotControl Control { get; }
        IRobotScenarioControl ScenarioControl { get; }

        // 진행 관리자는 상태 관리자와 같은 이유로 여기서 주입한다. Backend 가
        // 자기 것을 만들면 Mock/Real 이 서로 다른 곳에 쓰게 되고 UI 가 갈라진다.
        void Initialize(ArticulationBody articulationRoot, RobotStatusManager statusManager,
            AssemblyProgressManager assemblyProgress);
        void SetActive(bool active);
    }
}
