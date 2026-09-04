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

        // 기존 Real Backend 초기화 호출 계약은 유지한다. Ghost에는 로봇이 계산한 관절값만 필요하다.
        internal void InitializeReal(RobotStatusManager _, RealRobotControl __)
        {
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
            fairinoSdkSolver.Initialize(ghostMaster);

        void RefreshReferences()
        {
            if (fairinoSdkSolver == null)
                fairinoSdkSolver = GetComponent<RealFairinoSdkGhostSolver>();
        }
    }
}
