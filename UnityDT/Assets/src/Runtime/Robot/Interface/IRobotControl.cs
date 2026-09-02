// 역할: Scenario 명령과 저수준 로봇 제어 계약을 정의한다.

using System.Collections.Generic;
using System.Threading.Tasks;

namespace MainUnity.Runtime.Robot.Interface
{
    public enum RobotPoint
    {
        Home,
        ItemReady,
        AssemblyReady
    }

    /// <summary>Scenario가 요청하는 자동 조립 작업의 공통 계약이다.</summary>
    public interface IRobotScenarioControl
    {
        /// <summary>조립 작업이 실제로 완료되거나 실패할 때까지 기다린다.</summary>
        Task ExecuteAsync();
        /// <summary>현재 자동 조립을 안전한 동작 경계에서 일시정지한다.</summary>
        Task PauseAsync();
        /// <summary>일시정지된 자동 조립을 재개한다.</summary>
        Task ResumeAsync();
    }

    /// <summary>Backend의 저수준 이동 및 수동 제어 명령을 정의한다.</summary>
    public interface IRobotControl
    {
        /// <summary>지정된 티칭 포인트로 이동하고 완료될 때까지 기다린다.</summary>
        Task MoveJ(RobotPoint point);
        bool TrySetJointTarget(IReadOnlyList<float> jointDegrees);
        bool TryOpenGripper();
        bool TryCloseGripper();
    }
}
