using MainUnity.Runtime.Robot.Assembly;
using MainUnity.Runtime.Robot.Interface;
using MainUnity.Runtime.Robot.Mock;
using MainUnity.Runtime.Robot.Real;
using MainUnity.Runtime.Robot.Status;
using MainUnity.Runtime.RobotGhost;
using UnityEngine;
using ScenarioController = global::MainUnity.Runtime.Scenario.Scenario;

namespace MainUnity.Runtime.Robot
{
    public enum RobotOperatingMode
    {
        Mock,
        Real
    }

    [DefaultExecutionOrder(-100)]
    [DisallowMultipleComponent]
    [RequireComponent(typeof(RobotStatusManager), typeof(GripperSubscriber))]
    [RequireComponent(typeof(RobotStatusMaster))]
    [RequireComponent(typeof(AssemblyProgressManager))]
    public sealed class RobotMaster : MonoBehaviour
    {
        [Header("Backend")]
        [Tooltip("Inspector와 HUD에서 활성화할 로봇 Backend")]
        [SerializeField] RobotOperatingMode operatingMode = RobotOperatingMode.Mock;
        [SerializeField] MockRobotMaster mock;
        [SerializeField] FairinoRealRobotMaster real;
        [SerializeField] RobotStatusMaster status;

        [Header("Ghost")]
        [SerializeField] GhostMaster ghost;
        [SerializeField] MockRobotGhostControl mockGhost;
        [SerializeField] RealRobotGhostControl realGhost;

        [Tooltip("비우면 자식에서 찾습니다. 조립 진행을 Backend 와 무관하게 보관합니다.")]
        [SerializeField] AssemblyProgressManager assemblyProgress;
        [SerializeField] ArticulationBody articulationRoot;
        [SerializeField] Transform tcp;
        [SerializeField] ScenarioController scenario;
        

        public RobotOperatingMode OperatingMode => operatingMode;

/// <summary>편집 상태에서 Mock 또는 Real Backend를 선택한다.</summary>
        public bool TrySetOperatingMode(RobotOperatingMode mode)
        {
            if (Application.isPlaying)
            {
                Debug.LogWarning("Robot operating mode can only be changed outside Play Mode.", this);
                return false;
            }

            operatingMode = mode;
            ApplyEditorBackendVisibility();
            return true;
        }
        /// <summary>Inspector Context Menu에서 Mock Backend를 편집 상태로 선택한다.</summary>
        [ContextMenu("Backend/Use Mock (Edit Mode)")]
        void UseMockInEditMode() => TrySetOperatingMode(RobotOperatingMode.Mock);

        /// <summary>Inspector Context Menu에서 Real Backend를 편집 상태로 선택한다.</summary>
        [ContextMenu("Backend/Use Real (Edit Mode)")]
        void UseRealInEditMode() => TrySetOperatingMode(RobotOperatingMode.Real);

        public IRobotControl Control { get; private set; }
        public IRobotGhostControl GhostControl { get; private set; }
        public Transform Tcp => tcp;

        /// <summary>선택된 Backend의 ScenarioControl을 주입받는 Scenario다. UI는 이 경로로 받는다.</summary>
        public ScenarioController Scenario => scenario;
        public RobotStatusMaster Status => status != null
            ? status
            : status = GetComponentInChildren<RobotStatusMaster>(true);

        /// <summary>조립 진행 상태다. UI는 Backend를 거치지 말고 이 경로로 받는다.</summary>
        public AssemblyProgressManager AssemblyProgress => assemblyProgress != null
            ? assemblyProgress
            : assemblyProgress = GetComponentInChildren<AssemblyProgressManager>(true);

        void OnEnable() => Initialize();
void OnValidate()
        {
            RefreshReferences();
            if (!Application.isPlaying)
                ApplyEditorBackendVisibility();
        }

        /// <summary>선택된 Mock 또는 FAIRINO 구현을 공통 Master에 주입한다.</summary>
        public bool Initialize()
        {
            RefreshReferences();
            IRobotBackend mockBackend = mock;
            IRobotBackend realBackend = real;
            RobotStatusManager statusManager = Status?.StatusManager;
            AssemblyProgressManager progress = AssemblyProgress;
            mockBackend?.Initialize(articulationRoot, statusManager, progress);
            realBackend?.Initialize(articulationRoot, statusManager, progress);

            // Backend 를 바꾸면 이전 작업의 진행은 더 이상 이 화면의 사실이 아니다.
            progress?.Clear();
            mockBackend?.SetActive(operatingMode == RobotOperatingMode.Mock);
            realBackend?.SetActive(operatingMode == RobotOperatingMode.Real);

            mockGhost?.Initialize(ghost);
            realGhost?.Initialize(ghost);
            // ROSConnection.Unsubscribe는 같은 토픽의 모든 callback을 지우므로
            // 둘 다 해제한 다음 선택된 Backend 하나만 구독한다.
            mockGhost?.SetActive(false);
            realGhost?.SetActive(false);
            GhostControl = operatingMode == RobotOperatingMode.Mock
                ? mockGhost
                : realGhost;
            GhostControl?.SetActive(true);

            IRobotBackend selectedBackend = operatingMode == RobotOperatingMode.Mock
                ? mockBackend
                : realBackend;
            IRobotStateSource stateSource = selectedBackend?.StateSource;
            Control = selectedBackend?.Control;
            scenario?.Initialize(selectedBackend?.ScenarioControl);

            if (stateSource == null || Status == null || GhostControl == null || ghost == null)
            {
                Debug.LogError($"{operatingMode} robot backend is incomplete.", this);
                return false;
            }

            if (Control == null || selectedBackend?.ScenarioControl == null)
                Debug.LogWarning($"{operatingMode} robot control is not configured.", this);

            Status.Initialize(stateSource);
            return true;
        }

        void ApplyEditorBackendVisibility()
        {
            if (mock == null || real == null || mock.gameObject == real.gameObject)
                return;

            mock.gameObject.SetActive(operatingMode == RobotOperatingMode.Mock);
            real.gameObject.SetActive(operatingMode == RobotOperatingMode.Real);
        }

        void RefreshReferences()
        {
            if (mock == null)
                mock = GetComponentInChildren<MockRobotMaster>(true);
            if (real == null)
                real = GetComponentInChildren<FairinoRealRobotMaster>(true);
            if (ghost == null)
                ghost = FindAnyObjectByType<GhostMaster>(FindObjectsInactive.Include);
            if (mockGhost == null && mock != null)
                mockGhost = mock.GetComponentInChildren<MockRobotGhostControl>(true);
            if (realGhost == null && real != null)
                realGhost = real.GetComponentInChildren<RealRobotGhostControl>(true);

            if (articulationRoot == null)
            {
                ArticulationBody[] bodies =
                    GetComponentsInChildren<ArticulationBody>(true);
                for (int i = 0; i < bodies.Length; i++)
                {
                    if (!bodies[i].isRoot)
                        continue;
                    articulationRoot = bodies[i];
                    break;
                }
            }

            if (tcp == null && articulationRoot != null)
            {
                foreach (Transform candidate in articulationRoot.GetComponentsInChildren<Transform>(true))
                {
                    if (candidate.name == "TCP")
                    {
                        tcp = candidate;
                        break;
                    }
                }
            }

            _ = Status;
            _ = AssemblyProgress;
        }
    }
}
