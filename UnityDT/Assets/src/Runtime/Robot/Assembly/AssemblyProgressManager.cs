// 역할: 조립 작업의 진행 상태를 Backend와 무관한 한 곳에 보관한다.
//
// RobotStatusManager 가 관절·TCP·안전 프레임을 보관하는 것과 같은 자리다.
// Mock 은 /unity/assembly/feedback 을, Real 은 조립 노드 계약이 생기면 그것을
// 여기에 쓴다. UI 는 어느 쪽이 썼는지 모른 채 Latest 만 읽는다.
//
// 이 클래스를 두는 이유는 하나다. UI 가 MockAssemblyScenarioControl 을 직접 참조하면
// Real 노드가 붙는 날 화면을 다시 써야 하고, "Mock 에서만 사는 화면" 이 하나 더
// 생긴다. 진행 표시는 Backend 선택과 무관해야 한다.

using UnityEngine;

namespace MainUnity.Runtime.Robot.Assembly
{
    /// <summary>조립 피드백의 상태 값이다. API.md 4.3 의 feedback.state 와 1:1 이다.</summary>
    public enum AssemblyState
    {
        /// <summary>작업이 없다. 시작 전이거나 종료 후 초기화된 상태다.</summary>
        Idle,
        Started,
        Picked,
        Placed,
        Completed,
        Failed,
    }

    /// <summary>
    /// 조립 진행 한 시점의 스냅샷이다. 필드는 피드백 JSON 과 1:1 로 둔다.
    /// 변환을 여기서 하지 않아야 계약이 바뀔 때 고칠 자리가 한 곳으로 남는다.
    /// </summary>
    public sealed class AssemblyProgressFrame
    {
        public AssemblyProgressFrame(string jobId, string recipeVersion, AssemblyState state,
            int stepOrder, int expectedStepCount, int placedCount,
            string partId, string slotCode, string errorCode, string message,
            double receiveTimeSeconds)
        {
            JobId = jobId ?? string.Empty;
            RecipeVersion = recipeVersion ?? string.Empty;
            State = state;
            StepOrder = stepOrder;
            ExpectedStepCount = expectedStepCount;
            PlacedCount = placedCount;
            PartId = partId ?? string.Empty;
            SlotCode = slotCode ?? string.Empty;
            ErrorCode = errorCode ?? string.Empty;
            Message = message ?? string.Empty;
            ReceiveTimeSeconds = receiveTimeSeconds;
        }

        public string JobId { get; }
        public string RecipeVersion { get; }
        public AssemblyState State { get; }

        /// <summary>레시피 스텝 번호(1부터). 스텝과 무관한 상태면 0 이다.</summary>
        public int StepOrder { get; }

        /// <summary>이 작업의 전체 스텝 수. Mock 기판은 25다.</summary>
        public int ExpectedStepCount { get; }

        /// <summary>지금까지 기판에 올라간 부품 수다.</summary>
        public int PlacedCount { get; }

        /// <summary>부품 종류다. 개체 식별자가 아니다 (예: HBM).</summary>
        public string PartId { get; }

        /// <summary>장착 위치 코드다 (예: HBM-03). DB·레시피·검사가 같은 값을 쓴다.</summary>
        public string SlotCode { get; }

        public string ErrorCode { get; }
        public string Message { get; }
        public double ReceiveTimeSeconds { get; }

        /// <summary>지금 부품을 쥐고 이동 중인지다. PICKED 와 PLACED 사이가 그 구간이다.</summary>
        public bool IsHolding => State == AssemblyState.Picked;

        /// <summary>작업이 끝났는지다. 완료와 실패를 모두 포함한다.</summary>
        public bool IsTerminal => State == AssemblyState.Completed || State == AssemblyState.Failed;

        /// <summary>0~1 진행률. 전체 스텝 수를 모르면 0 이다.</summary>
        public float PlacedRatio => ExpectedStepCount > 0
            ? Mathf.Clamp01((float)PlacedCount / ExpectedStepCount)
            : 0f;
    }

    /// <summary>
    /// 최신 조립 진행 프레임을 보관한다. 값을 만들지 않고 받은 것만 보관한다.
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class AssemblyProgressManager : MonoBehaviour
    {
        /// <summary>최신 프레임이다. 작업을 한 번도 시작하지 않았으면 null 이다.</summary>
        public AssemblyProgressFrame Latest { get; private set; }

        /// <summary>진행 프레임이 갱신될 때 발생한다.</summary>
        public event System.Action<AssemblyProgressFrame> ProgressChanged;

        /// <summary>Backend 가 받은 조립 피드백을 반영한다.</summary>
        public void Apply(AssemblyProgressFrame frame)
        {
            if (frame == null)
                return;
            Latest = frame;
            ProgressChanged?.Invoke(frame);
        }

        /// <summary>작업 추적을 초기화한다. Backend 가 바뀌거나 연결이 끊길 때 부른다.</summary>
        public void Clear()
        {
            if (Latest == null)
                return;
            Latest = null;
            ProgressChanged?.Invoke(null);
        }
    }
}
