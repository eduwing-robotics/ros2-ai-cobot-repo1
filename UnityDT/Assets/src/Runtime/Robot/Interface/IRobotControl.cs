// 역할: Scenario 명령과 저수준 로봇 제어 계약을 정의한다.

using System;
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

    /// <summary>운영자가 해당 실행에 대해 직접 확인한 현장 준비 정보다. 자동 생성한 확인으로 대체하지 않는다.</summary>
    [Serializable]
    public sealed class AssemblySceneConfirmation
    {
        public string operator_id;
        public string execution_id;
        public double confirmed_unix;
        public string scope = "empty_gripper_empty_pcb_full_tray_fixed_fixture";
    }

    /// <summary>Scenario가 요청하는 자동 조립 작업의 공통 계약이다.</summary>
    public interface IRobotScenarioControl
    {
        /// <summary>호출자의 대기가 끝난 뒤에도 추적 중인 작업이 있으면 true다.</summary>
        bool IsRunning { get; }

        /// <summary>조립 작업이 실제로 완료되거나 실패할 때까지 기다린다.</summary>
        Task ExecuteAsync(Func<string, Task<AssemblySceneConfirmation>> confirmScene = null);
        /// <summary>이미 등록된 PENDING Job을 같은 ID로 실행한다.</summary>
        Task ExecuteQueuedAsync(string jobId, Func<string, Task<AssemblySceneConfirmation>> confirmScene = null);
        /// <summary>현재 자동 조립을 실제 정지 확인 뒤 일시정지한다.</summary>
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
