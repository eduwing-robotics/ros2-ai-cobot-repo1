// 책임: Real Backend의 의존성을 주입하고 활성 상태에 따른 이벤트 연결만 제어한다.
// 명령 검증·ROS 서비스 호출·상태 판정은 하위 컴포넌트가 소유한다.

using MainUnity.Runtime.Robot.Assembly;
using MainUnity.Runtime.Robot.Interface;
using MainUnity.Runtime.Robot.Status;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Real
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(RealShadowing))]
    public sealed class FairinoRealRobotMaster : MonoBehaviour, IRobotBackend
    {
        [SerializeField] RealStatusSubscriber stateSource;
        [SerializeField] RealShadowing shadowing;
        [SerializeField] RealGripperRequest gripperRequest;
        [SerializeField] RealRobotControl control;
        [SerializeField] RealAssemblyScenarioControl assemblyControl;
        [SerializeField] RealRobotGhostControl ghostControl;

        public IRobotStateSource StateSource => stateSource;
        public IRobotControl Control => control;
        public IRobotScenarioControl ScenarioControl => assemblyControl;

        void Awake() => RefreshReferences();
        void OnDisable() => Unbind();
        void OnValidate() => RefreshReferences();

        // TODO(API·Real): 조립 노드 계약이 생기면 assemblyControl 이 assemblyProgress 에 쓴다.
        //                 Mock 과 같은 곳에 쓰면 UI 는 바뀌지 않는다.
        public void Initialize(ArticulationBody articulationRoot, RobotStatusManager statusManager,
            AssemblyProgressManager assemblyProgress)
        {
            RefreshReferences();
            control?.Initialize(articulationRoot, statusManager);
            ghostControl?.InitializeReal(statusManager, control);
            gripperRequest?.Initialize(statusManager);

            shadowing?.Initialize(articulationRoot);
        }

        public void SetActive(bool active)
        {
            RefreshReferences();
            if (active)
                Bind();
            else
                Unbind();
            if (stateSource != null)
                stateSource.enabled = active;
            if (shadowing != null)
                shadowing.enabled = active;
            if (gripperRequest != null)
                gripperRequest.enabled = active;

            if (control != null)
                control.enabled = active;
            if (assemblyControl != null)
                assemblyControl.enabled = active;
        }

        void RefreshReferences()
        {
            if (stateSource == null)
                stateSource = GetComponentInChildren<RealStatusSubscriber>(true);
            if (shadowing == null)
                shadowing = GetComponentInChildren<RealShadowing>(true);
            if (gripperRequest == null)
                gripperRequest = GetComponentInChildren<RealGripperRequest>(true);
            if (control == null)
                control = GetComponentInChildren<RealRobotControl>(true);
            if (assemblyControl == null)
                assemblyControl = GetComponentInChildren<RealAssemblyScenarioControl>(true);
            if (ghostControl == null)
                ghostControl = GetComponentInChildren<RealRobotGhostControl>(true);
        }

        void Bind()
        {
            if (stateSource == null || shadowing == null)
                return;
            stateSource.StateReceived -= shadowing.ApplyState;
            stateSource.StateReceived += shadowing.ApplyState;
        }

        void Unbind()
        {
            if (stateSource != null && shadowing != null)
                stateSource.StateReceived -= shadowing.ApplyState;
        }
    }
}
