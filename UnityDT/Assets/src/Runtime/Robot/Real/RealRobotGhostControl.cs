using MainUnity.Runtime.Robot.Interface;
using MainUnity.Runtime.Robot.Status;
using MainUnity.Runtime.RobotGhost;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Real
{
    [DisallowMultipleComponent]
    public sealed class RealRobotGhostControl : MonoBehaviour, IRobotGhostControl
    {
        [SerializeField] RealFairinoSdkGhostSolver fairinoSdkSolver;

        GhostMaster ghostMaster;
        RobotStatusManager statusManager;

        void OnDisable() => fairinoSdkSolver?.SetActive(false);
        void OnValidate() => RefreshReferences();

        public bool Initialize(GhostMaster destination)
        {
            ghostMaster = destination;
            RefreshReferences();
            if (ghostMaster != null)
                return InitializeSolver();
            Debug.LogError("Assign the common GhostMaster.", this);
            return false;
        }

        // 실제 상태는 기존 Real Backend 주입 경로를 사용한다.
        internal void InitializeReal(RobotStatusManager injectedStatusManager, RealRobotControl _)
        {
            statusManager = injectedStatusManager;
            RefreshReferences();
            InitializeSolver();
        }

        public void SetActive(bool value)
        {
            fairinoSdkSolver?.SetActive(value);
            enabled = value;
        }

        bool InitializeSolver() =>
            ghostMaster != null && fairinoSdkSolver != null &&
            fairinoSdkSolver.Initialize(ghostMaster, statusManager);

        void RefreshReferences()
        {
            if (fairinoSdkSolver == null)
                fairinoSdkSolver = GetComponent<RealFairinoSdkGhostSolver>();
        }
    }
}
