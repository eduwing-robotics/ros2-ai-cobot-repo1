// 역할: MoveIt/FakeSystem용 상태 수신과 제어 구현을 하나의 Mock Backend로 제공한다.

using MainUnity.Runtime.Robot.Assembly;
using MainUnity.Runtime.Robot.Interface;
using MainUnity.Runtime.Robot.Status;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Mock
{
    [DisallowMultipleComponent]
    public sealed class MockRobotMaster : MonoBehaviour, IRobotBackend
    {
        [SerializeField] MockRobotStateSource stateSource;
        [SerializeField] MockRobotShadowing shadowing;
        [SerializeField] MockRobotControl control;
        [SerializeField] MockAssemblyScenarioControl assemblyControl;

        public IRobotStateSource StateSource => stateSource;
        public IRobotControl Control => control;
        public IRobotScenarioControl ScenarioControl => assemblyControl;

        void OnDisable() => Unbind();
        void OnValidate() => RefreshReferences();

        public void Initialize(ArticulationBody articulationRoot, RobotStatusManager statusManager,
            AssemblyProgressManager assemblyProgress)
        {
            RefreshReferences();
            shadowing?.Initialize(articulationRoot);
            control?.Initialize(articulationRoot != null ? articulationRoot.transform : null, statusManager);
            assemblyControl?.Initialize(control, assemblyProgress);
        }

        public void SetActive(bool active)
        {
            if (active)
                Bind();
            else
                Unbind();
            if (stateSource != null)
                stateSource.enabled = active;
            if (shadowing != null)
                shadowing.enabled = active;
            if (control != null)
                control.enabled = active;
            if (assemblyControl != null)
                assemblyControl.enabled = active;
        }

        void RefreshReferences()
        {
            if (stateSource == null)
                stateSource = GetComponentInChildren<MockRobotStateSource>(true);
            if (shadowing == null)
                shadowing = GetComponentInChildren<MockRobotShadowing>(true);
            if (control == null)
                control = GetComponentInChildren<MockRobotControl>(true);
            if (assemblyControl == null)
                assemblyControl = GetComponentInChildren<MockAssemblyScenarioControl>(true);
        }
        void Bind()
        {
            if (stateSource == null || shadowing == null)
                return;
            stateSource.StateReceived -= shadowing.ApplyState;
            stateSource.StateReceived += shadowing.ApplyState;
            stateSource.GripperJointReceived -= shadowing.ApplyGripperJointPosition;
            stateSource.GripperJointReceived += shadowing.ApplyGripperJointPosition;
        }

        void Unbind()
        {
            if (stateSource == null || shadowing == null)
                return;
            stateSource.StateReceived -= shadowing.ApplyState;
            stateSource.GripperJointReceived -= shadowing.ApplyGripperJointPosition;
        }
    }
}
