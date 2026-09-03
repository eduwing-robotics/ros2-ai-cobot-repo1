// 역할: HUD가 필요로 하는 런타임 참조를 한 곳에서 해석해 UI 컴포넌트에 중계한다.
//
// UI 컴포넌트(FR5RunBinder, ManualJointPanel 등)는 씬을 직접 뒤지지 않는다.
// 씬 스캔은 이 클래스에만 남겨 두고, 나머지는 RobotMaster가 주입한 경로를 따라간다.
//   RobotMaster ─ Status(RobotStatusMaster) ─ StatusManager / Gripper
//               ├ AssemblyProgress(AssemblyProgressManager)
//               └ Scenario
// 기판 슬롯 구성(ItemManager)은 로봇이 아니라 트윈 쪽 데이터라 여기서 따로 들고 있는다.
// Ghost는 RobotMaster 계층 밖의 시각화 전용이라 여기서만 별도로 들고 있는다.

using MainUnity.Runtime.Camera;
using MainUnity.Runtime.Robot.Assembly;
using MainUnity.Runtime.Robot;
using MainUnity.Runtime.Robot.Status;
using MainUnity.Runtime.RobotGhost;
using MainUnity.Static;
using UnityEngine;
using UnityEngine.UIElements;
using ScenarioController = MainUnity.Runtime.Scenario.Scenario;

namespace MainUnity.UI
{
    // 페이지별 UIDocument 는 자식 오브젝트로 갈라지고 UIMaster 는 그 부모에 하나만 둔다.
    // 그래서 UIDocument 를 강제하지 않는다.
    [DisallowMultipleComponent]
    public sealed class UIMaster : MonoBehaviour
    {
        [Header("런타임 참조")]
        [Tooltip("비우면 씬에서 찾습니다. HUD가 로봇 계층으로 들어가는 유일한 입구입니다.")]
        [SerializeField] RobotMaster robotMaster;

        [Tooltip("비우면 씬에서 찾습니다. RobotMaster 계층 밖의 시각화 전용 컴포넌트입니다.")]
        [SerializeField] GhostMaster ghostMaster;

        [Tooltip("비우면 같은 오브젝트에서 찾습니다. ROBOT 뷰포트에 실카메라 영상을 넣는 수신기입니다.")]
        [SerializeField] CamVisionReceiver visionImage;

        [Tooltip("비우면 씬에서 찾습니다. 기판 슬롯 구성을 들고 있는 트윈 쪽 데이터입니다.")]
        [SerializeField] ItemManager board;

        /// <summary>Mock/Real Backend를 선택해 주입하는 로봇 진입점이다.</summary>
        public RobotMaster RobotMaster => robotMaster != null
            ? robotMaster
            : robotMaster = FindAnyObjectByType<RobotMaster>();

        /// <summary>현재 선택된 Backend다. RobotMaster를 못 찾으면 실측으로 오인하지 않도록 Mock으로 본다.</summary>
        public RobotOperatingMode OperatingMode => RobotMaster != null
            ? RobotMaster.OperatingMode
            : RobotOperatingMode.Mock;

        /// <summary>Mock Backend는 일부 필드를 0으로 채워 보내므로 표시를 달리해야 한다.</summary>
        public bool IsSimulated => OperatingMode == RobotOperatingMode.Mock;

        /// <summary>Mock/Real과 무관하게 최신 상태를 보관하는 공통 관리자다.</summary>
        public RobotStatusManager StatusManager => RobotMaster != null
            ? RobotMaster.Status?.StatusManager
            : null;

        /// <summary>
        /// 조립 진행 상태다. Mock/Real 어느 Backend가 채웠는지 화면은 알 필요가 없다.
        /// </summary>
        public AssemblyProgressManager AssemblyProgress => RobotMaster != null
            ? RobotMaster.AssemblyProgress
            : null;

        /// <summary>
        /// 기판의 슬롯 구성이다. 타입별 슬롯 수와 실행 순서를 여기서만 읽는다.
        /// 진행 프레임은 "몇 번째까지 놓았는가"만 말하므로, "전부 몇 개인가"는 트윈이 답한다.
        /// Backend 와 무관한 씬 데이터라 Mock/Real 어느 쪽에서도 같은 값이다.
        /// TODO(API): 완성체 슬롯 조회가 생기면 그쪽으로 옮긴다 (DATA_STATION/DB/README.md의 Product Slot 계약).
        /// </summary>
        public ItemManager Board => board != null
            ? board
            : board = FindAnyObjectByType<ItemManager>();

        /// <summary>공통 그리퍼 상태 컴포넌트다.</summary>
        public GripperSubscriber Gripper => RobotMaster != null
            ? RobotMaster.Status?.Gripper
            : null;

        /// <summary>선택된 Backend의 ScenarioControl을 주입받은 Scenario다.</summary>
        public ScenarioController Scenario => RobotMaster != null
            ? RobotMaster.Scenario
            : null;

        /// <summary>관절 목표 미리보기를 담당하는 Ghost 진입점이다.</summary>
        public GhostMaster Ghost => ghostMaster != null
            ? ghostMaster
            : ghostMaster = FindAnyObjectByType<GhostMaster>();

        /// <summary>ROBOT 뷰포트의 실카메라 영상 수신기다. HUD와 같은 오브젝트에 붙어 있다.</summary>
        public CamVisionReceiver VisionImage => visionImage != null
            ? visionImage
            : visionImage = GetComponent<CamVisionReceiver>();

        void Awake() => RefreshReferences();

        void OnValidate() => RefreshReferences();

        /// <summary>Inspector가 비어 있는 참조만 씬에서 채운다.</summary>
        public void RefreshReferences()
        {
            _ = RobotMaster;
            _ = Ghost;
            _ = VisionImage;
            _ = Board;
        }
    }
}
