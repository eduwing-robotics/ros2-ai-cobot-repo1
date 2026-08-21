// 역할: FR5 Dashboard 좌측 ROBOT STATUS 패널을 담당한다.
//   - 탭 전환 MONITOR / MANUAL / PLANNING / I/O
//   - MANUAL 탭에서 J1~J6 목표를 입력하고 IRobotControl로 전달
//   - MONITOR 탭의 그리퍼 OPEN / CLOSE
//   - 상단 MOCK / REAL 모드 전환
//
// 조회하는 UXML name 은 [UxmlName] 필드로 노출되어 있어 Inspector 에서 드롭다운으로 고릅니다.
// 목록은 같은 GameObject 의 UIDocument 가 물고 있는 .uxml 에서 읽어오고,
// Inspector 하단 "UXML 바인딩 검사" 버튼으로 재생 없이 이름을 대조할 수 있습니다.

using System;
using MainUnity.Runtime.Robot;
using MainUnity.Runtime.RobotGhost;
using MainUnity.Runtime.Robot.Status;
using UnityEngine;
using UnityEngine.UIElements;

namespace MainUnity.UI
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(UIDocument))]
    public sealed class ManualJointPanel : MonoBehaviour
    {
        const int JointCount = 6;

        /// <summary>MANUAL 탭 조그 한 줄.</summary>
        [Serializable]
        public sealed class JogRowNames
        {
            [UxmlName("Slider")] public string slider;
            [UxmlName("Label")] public string actual;
            [UxmlName("Label")] public string target;
        }

        [Serializable]
        public sealed class PanelNames
        {
            [UxmlName] public string hudRoot = "";          // 페이지마다 루트 이름이 다르다
            [UxmlName] public string monitorPane = "pane-monitor";
            [UxmlName] public string manualPane = "pane-manual";
            [UxmlName] public string planningPane = "pane-planning";
            [UxmlName("ScrollView")] public string planningList = "planning-list";
            [UxmlName] public string ioPane = "pane-io";
            [UxmlName("Button")] public string monitorTab = "tab-monitor";
            [UxmlName("Button")] public string manualTab = "tab-manual";
            [UxmlName("Button")] public string planningTab = "tab-planning";
            [UxmlName("Button")] public string ioTab = "tab-io";
            [UxmlName("Button")] public string gripperOpenButton = "gripper-open-button";
            [UxmlName("Button")] public string gripperCloseButton = "gripper-close-button";
            [UxmlName("Button")] public string mockModeButton = "mode-mock";
            [UxmlName("Button")] public string realModeButton = "mode-real";
            [UxmlName("Button")] public string applyButton = "jog-apply-button";
            [UxmlName("Button")] public string cancelButton = "jog-cancel-button";
            [UxmlName("Button")] public string homeButton = "jog-home-button";
            [UxmlName("Label")] public string hint = "ghost-hint";
            public JogRowNames[] jogRows = MakeJogRows();
        }

        static JogRowNames[] MakeJogRows()
        {
            var rows = new JogRowNames[JointCount];
            for (int i = 0; i < JointCount; i++)
            {
                int n = i + 1;
                rows[i] = new JogRowNames
                {
                    slider = $"jog-{n}-slider",
                    actual = $"jog-{n}-actual",
                    target = $"jog-{n}-target",
                };
            }
            return rows;
        }

        [Header("데이터 소스")]
        [Tooltip("비우면 같은 오브젝트에서 찾습니다. 로봇·Ghost 참조를 받는 단일 진입점입니다.")]
        [SerializeField] UIMaster uiMaster;
        [SerializeField] RobotMaster robotMaster;
        [SerializeField] RobotStatusManager statusManager;
        [SerializeField] GhostMaster ghostMaster;

        [Header("UI 요소 이름 (UXML)")]
        [SerializeField] PanelNames names = new();

        readonly Slider[] sliders = new Slider[JointCount];
        readonly Label[] actualLabels = new Label[JointCount];
        readonly Label[] targetLabels = new Label[JointCount];
        readonly float[] initialTargets = new float[JointCount];

        VisualElement monitorPane;
        VisualElement hudRoot;
        VisualElement planningPane;
        ScrollView planningList;
        VisualElement manualPane;
        VisualElement ioPane;
        Button monitorTab;
        Button planningTab;
        Button manualTab;
        Button ioTab;
        Button gripperOpenButton;
        Button gripperCloseButton;

        // 탭과 페인을 짝지어 들고 다닌다. I/O 처럼 나중에 늘어나도 ShowPane 은 그대로 둔다.
        VisualElement[] panes;
        Button[] tabs;

        Button mockModeButton;
        Button realModeButton;
        Button applyButton;
        Button cancelButton;
        Button homeButton;
        Label hint;
        bool bound;

        void OnEnable() => Bind();
        void OnDisable() => Unbind();

        void Update()
        {
            // 페이지가 런타임에 켜지면 OnEnable 시점에 rootVisualElement 가 아직 없다.
            // 될 때까지 재시도한다.
            if (!bound)
            {
                Bind();
                if (!bound)
                    return;
            }

            RefreshReferences();
            RefreshModeUI();
            float[] joints = statusManager?.Latest?.JointDegrees;
            if (joints == null || joints.Length != JointCount)
                return;

            for (int i = 0; i < JointCount; i++)
                actualLabels[i].text = $"{joints[i]:0.0}°";
        }

        /// <summary>현재 Slider의 J1~J6 목표값을 ROS2로 전달한다.</summary>
        public bool TryApplyJointTargets()
        {
            RefreshReferences();
            if (robotMaster?.Control == null)
            {
                SetHint("RobotMaster Control을 찾을 수 없습니다.");
                return false;
            }

            var targets = new float[JointCount];
            for (int i = 0; i < JointCount; i++)
                targets[i] = sliders[i].value;

            // ─────────────────────────────────────────────────────────
            // [실동작 차단] MANUAL 페이지는 지금 화면만 만든 단계다.
            // 슬라이더와 Ghost 미리보기는 그대로 두고 로봇으로 나가는 명령만 막는다.
            // 풀 때는 아래 두 줄의 주석을 벗기고 그 아래 차단 블록을 지우면 된다.
            //
            // bool accepted = robotMaster.Control.TrySetJointTarget(targets);
            // SetHint(accepted ? "관절 목표 자세를 전달했습니다." : "관절 목표 자세가 거부되었습니다.");
            // return accepted;
            SetHint("실동작 차단 중 — 목표만 미리보기로 표시합니다.");
            return false;
            // ─────────────────────────────────────────────────────────
        }

        /// <summary>현재 Slider의 J1~J6 목표 자세를 Ghost에만 표시한다.</summary>
        public bool TryPreviewJointTargets()
        {
            RefreshReferences();
            if (!bound || ghostMaster == null)
                return false;

            var targets = new float[JointCount];
            for (int i = 0; i < JointCount; i++)
                targets[i] = sliders[i].value;
            return ghostMaster.PreviewJoints(targets);
        }


        /// <summary>이름이 비어 있으면 조회를 건너뛴다. Q() 는 null 이름에 예외를 던진다.</summary>
        static T Find<T>(VisualElement root, string name) where T : VisualElement =>
            string.IsNullOrEmpty(name) ? null : root.Q<T>(name);

        void Bind()
        {
            VisualElement root = GetComponent<UIDocument>().rootVisualElement;
            hudRoot = Find<VisualElement>(root, names.hudRoot);
            monitorPane = Find<VisualElement>(root, names.monitorPane);
            manualPane = Find<VisualElement>(root, names.manualPane);
            planningPane = Find<VisualElement>(root, names.planningPane);
            planningList = Find<ScrollView>(root, names.planningList);
            ioPane = Find<VisualElement>(root, names.ioPane);
            monitorTab = Find<Button>(root, names.monitorTab);
            manualTab = Find<Button>(root, names.manualTab);
            planningTab = Find<Button>(root, names.planningTab);
            ioTab = Find<Button>(root, names.ioTab);
            gripperOpenButton = Find<Button>(root, names.gripperOpenButton);
            gripperCloseButton = Find<Button>(root, names.gripperCloseButton);
            mockModeButton = Find<Button>(root, names.mockModeButton);
            realModeButton = Find<Button>(root, names.realModeButton);
            applyButton = Find<Button>(root, names.applyButton);
            cancelButton = Find<Button>(root, names.cancelButton);
            homeButton = Find<Button>(root, names.homeButton);
            hint = Find<Label>(root, names.hint);

            // 탭·페인·PLANNING 은 4탭 시절 구조다. 페이지가 분리된 뒤로는 없는 화면이 많아
            // 필수로 두지 않는다. MANUAL 이 실제로 쓰는 것(조그·APPLY·CANCEL·HOME)만 요구한다.
            if (applyButton == null || cancelButton == null || homeButton == null)
            {
                Debug.LogError("MANUAL 필수 요소(APPLY/CANCEL/HOME)를 찾을 수 없습니다. " +
                               "Inspector 의 UI 요소 이름과 UXML 을 대조하세요.", this);
                return;
            }

            for (int i = 0; i < JointCount; i++)
            {
                int jointNumber = i + 1;
                JogRowNames row = names.jogRows != null && i < names.jogRows.Length ? names.jogRows[i] : null;
                if (row != null)
                {
                    sliders[i] = Find<Slider>(root, row.slider);
                    actualLabels[i] = Find<Label>(root, row.actual);
                    targetLabels[i] = Find<Label>(root, row.target);
                }
                if (sliders[i] == null || actualLabels[i] == null || targetLabels[i] == null)
                {
                    Debug.LogError($"MANUAL J{jointNumber} UI 요소를 찾을 수 없습니다.", this);
                    return;
                }
                initialTargets[i] = sliders[i].value;
                sliders[i].RegisterValueChangedCallback(OnSliderChanged);
            }

            // I/O 는 목업 단계에 없던 4번째 탭이라 아직 UXML 에 없을 수 있습니다. 있을 때만 엮습니다.
            panes = new[] { monitorPane, manualPane, planningPane, ioPane };
            tabs = new[] { monitorTab, manualTab, planningTab, ioTab };

            if (monitorTab != null) monitorTab.clicked += ShowMonitor;
            if (manualTab != null) manualTab.clicked += ShowManual;
            if (planningTab != null) planningTab.clicked += ShowPlanning;
            if (ioTab != null && ioPane != null)
                ioTab.clicked += ShowIo;
            if (gripperOpenButton != null)
                gripperOpenButton.clicked += OpenGripper;
            if (gripperCloseButton != null)
                gripperCloseButton.clicked += CloseGripper;
            if (mockModeButton != null) mockModeButton.clicked += SetMockMode;
            if (realModeButton != null) realModeButton.clicked += SetRealMode;
            applyButton.clicked += Apply;
            cancelButton.clicked += Cancel;
            homeButton.clicked += SetHome;
            bound = true;
            RefreshReferences();
            RefreshModeUI();
        }

        void Unbind()
        {
            if (!bound)
                return;
            for (int i = 0; i < JointCount; i++)
                sliders[i].UnregisterValueChangedCallback(OnSliderChanged);
            if (monitorTab != null) monitorTab.clicked -= ShowMonitor;
            if (manualTab != null) manualTab.clicked -= ShowManual;
            if (planningTab != null) planningTab.clicked -= ShowPlanning;
            if (ioTab != null && ioPane != null)
                ioTab.clicked -= ShowIo;
            if (gripperOpenButton != null)
                gripperOpenButton.clicked -= OpenGripper;
            if (gripperCloseButton != null)
                gripperCloseButton.clicked -= CloseGripper;
            if (mockModeButton != null) mockModeButton.clicked -= SetMockMode;
            if (realModeButton != null) realModeButton.clicked -= SetRealMode;
            applyButton.clicked -= Apply;
            cancelButton.clicked -= Cancel;
            homeButton.clicked -= SetHome;
            bound = false;
        }

        void ShowMonitor() => ShowPane(monitorPane);
        void ShowManual() => ShowPane(manualPane);
        void ShowPlanning() => ShowPane(planningPane);
        void ShowIo() => ShowPane(ioPane);
        void SetMockMode() => SetOperatingMode(RobotOperatingMode.Mock);
        void SetRealMode() => SetOperatingMode(RobotOperatingMode.Real);

        /// <summary>그리퍼를 설정된 열림 위치로 보낸다.</summary>
        void OpenGripper() => SendGripper(true);

        /// <summary>그리퍼를 설정된 닫힘 위치로 보낸다.</summary>
        void CloseGripper() => SendGripper(false);

        void SendGripper(bool open)
        {
            RefreshReferences();
            if (robotMaster?.Control == null)
            {
                SetHint("RobotMaster Control을 찾을 수 없습니다.");
                return;
            }

            string action = open ? "열기" : "닫기";

            // [실동작 차단] 위 [실동작 차단] 주석과 같은 이유다.
            // bool accepted = open
            //     ? robotMaster.Control.TryOpenGripper()
            //     : robotMaster.Control.TryCloseGripper();
            // SetHint(accepted ? $"그리퍼 {action} 명령을 전달했습니다." : $"그리퍼 {action} 명령이 거부되었습니다.");
            SetHint($"실동작 차단 중 — 그리퍼 {action} 명령을 보내지 않았습니다.");
        }

        void SetOperatingMode(RobotOperatingMode mode)
        {
            RefreshReferences();

            // [실동작 차단] 모드 전환은 REAL 로 넘어가는 순간 실기에 명령이 나갈 수 있는
            // 경로다. 화면만 만든 단계에서는 막아 둔다.
            // if (robotMaster == null || !robotMaster.TrySetOperatingMode(mode))
            //     Debug.LogError(mode + " robot backend activation failed.", this);
            SetHint($"실동작 차단 중 — 모드({mode}) 전환을 적용하지 않았습니다.");

            RefreshModeUI();
        }

        void RefreshModeUI()
        {
            if (robotMaster == null || mockModeButton == null || realModeButton == null)
                return;
            bool isMock = robotMaster.OperatingMode == RobotOperatingMode.Mock;
            hudRoot?.EnableInClassList("hud--mock", isMock);
            mockModeButton.EnableInClassList("hud-mode__btn--active-mock", isMock);
            realModeButton.EnableInClassList("hud-mode__btn--active-real", !isMock);
        }
        void Apply() => TryApplyJointTargets();

        void Cancel()
        {
            float[] joints = statusManager?.Latest?.JointDegrees;
            SetTargets(joints != null && joints.Length == JointCount ? joints : initialTargets);
        }

        void SetHome() => SetTargets(initialTargets);

        void SetTargets(float[] targets)
        {
            if (targets == null || targets.Length != JointCount)
                return;
            for (int i = 0; i < JointCount; i++)
            {
                sliders[i].SetValueWithoutNotify(targets[i]);
                targetLabels[i].text = targets[i].ToString("0.0") + "°";
            }
            TryPreviewJointTargets();
        }

        void OnSliderChanged(ChangeEvent<float> change)
        {
            for (int i = 0; i < JointCount; i++)
                if (ReferenceEquals(change.target, sliders[i]))
                {
                    targetLabels[i].text = $"{change.newValue:0.0}°";
                    TryPreviewJointTargets();
                    return;
                }
        }

        /// <summary>페인 하나만 남기고 숨긴다. 탭 밑줄도 같이 옮긴다.</summary>
        void ShowPane(VisualElement pane)
        {
            for (int i = 0; i < panes.Length; i++)
            {
                bool selected = panes[i] != null && panes[i] == pane;
                panes[i]?.EnableInClassList("hud-pane--hidden", !selected);
                tabs[i]?.EnableInClassList("hud-tab--active", selected);
            }
        }

        void SetHint(string message)
        {
            if (hint != null)
                hint.text = message;
        }

        // 참조는 전부 UIMaster 를 통해서만 받는다. 여기서 씬을 뒤지지 않는다.
        // Inspector 에 직접 꽂아둔 값이 있으면 그쪽이 우선한다.
        void RefreshReferences()
        {
            // UIMaster 는 페이지들의 부모(FR5 UI)에 하나만 둔다.
            if (uiMaster == null)
                uiMaster = GetComponentInParent<UIMaster>();
            if (uiMaster == null)
                return;

            if (robotMaster == null)
                robotMaster = uiMaster.RobotMaster;
            if (statusManager == null)
                statusManager = uiMaster.StatusManager;
            if (ghostMaster == null)
                ghostMaster = uiMaster.Ghost;
        }
    }
}
