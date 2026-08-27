// 역할: 공통 셸(FR5Shell.uxml)의 상단 바 값을 채운다. 모든 페이지에 하나씩 붙는다.
//
// 페이지마다 같은 코드를 복사하면 항목과 판정 기준이 갈라진다. 실제로 갈라져 있었다.
// 모드 · 로봇 상태 · 링크 · 속도는 페이지와 무관하므로 여기 한 곳에서만 다룬다.
//
//   실연결 : 모드 · RobotRunState · joint_states 링크 · board/image 링크
//   샘플   : 속도 오버라이드  [TODO(API): 속도 지령 경로가 없다]
//
// 작업(JOB)·사이클은 페이지가 아는 값이라 각 페이지 바인더가 채운다.

using MainUnity.Runtime.Camera;
using MainUnity.Runtime.Robot;
using MainUnity.Runtime.Robot.Status;
using UnityEngine;
using UnityEngine.UIElements;

namespace MainUnity.UI
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(UIDocument))]
    public sealed class FR5ShellBinder : MonoBehaviour
    {
        [Header("데이터 소스")]
        [SerializeField] UIMaster uiMaster;
        [SerializeField] RobotStatusManager statusManager;
        [SerializeField] CamVisionReceiver vision;

        [Tooltip("이 시간을 넘겨 프레임이 없으면 영상 링크를 끊긴 것으로 봅니다.")]
        [SerializeField] float visionStaleSeconds = 2f;

        VisualElement modeMock, modeReal, robotChip, linkJointDot, linkImageDot, alarmBanner;
        VisualElement pageRoot;
        Button modeMockButton, modeRealButton, stopAllButton, viewFocusButton;
        Label robotText, linkJointAge, linkImageAge, alarmLabel, alarmDetail;
        bool cached;
        bool hasAuxPanels;

        // 페이지마다 셸 인스턴스가 하나씩이라 인스턴스 필드로 두면 화면을 옮길 때마다
        // 집중이 풀린다. 접어 둔 것은 접어 둔 채로 있어야 하므로 static 이다.
        static bool focusMode;

        void OnEnable() => cached = false;

        void OnDisable() => UnbindCommands();

        void Update()
        {
            if (!cached) { Build(); if (!cached) return; }
            Resolve();
            RefreshCommandAvailability();
            RefreshMode();
            RefreshState();
            RefreshLinks();
            RefreshAlarm();
            RefreshFocus();
        }

        void Build()
        {
            VisualElement root = GetComponent<UIDocument>().rootVisualElement;
            if (root == null) return;

            modeMock = root.Q<VisualElement>("mode-mock");
            modeReal = root.Q<VisualElement>("mode-real");
            modeMockButton = root.Q<Button>("mode-mock");
            modeRealButton = root.Q<Button>("mode-real");
            stopAllButton = root.Q<Button>("stop-all-button");
            robotChip = root.Q<VisualElement>("robot-state-chip");
            robotText = root.Q<Label>("robot-state-text");
            linkJointDot = root.Q<VisualElement>("link-joint-dot");
            linkJointAge = root.Q<Label>("link-joint-age");
            linkImageDot = root.Q<VisualElement>("link-image-dot");
            linkImageAge = root.Q<Label>("link-image-age");
            alarmBanner = root.Q<VisualElement>("alarm-banner");
            alarmLabel = root.Q<Label>("alarm-label");
            alarmDetail = root.Q<Label>("alarm-detail");
            viewFocusButton = root.Q<Button>("view-focus");
            pageRoot = root.Q<VisualElement>(className: "page");
            hasAuxPanels = pageRoot != null && pageRoot.Q<VisualElement>(className: "panel--aux") != null;

            // 셸이 없는 문서에 붙었을 수 있다. 그 경우 조용히 아무것도 하지 않는다.
            cached = modeMock != null || robotChip != null || linkJointDot != null;
            BindCommands();
        }

        void Resolve()
        {
            if (uiMaster == null) uiMaster = GetComponentInParent<UIMaster>();
            if (uiMaster == null) return;
            if (statusManager == null) statusManager = uiMaster.StatusManager;
            if (vision == null) vision = uiMaster.VisionImage;
        }
        void BindCommands()
        {
            if (modeMockButton != null) modeMockButton.clicked += SelectMockMode;
            if (modeRealButton != null) modeRealButton.clicked += SelectRealMode;
            if (viewFocusButton != null) viewFocusButton.clicked += ToggleFocus;
        }

        void UnbindCommands()
        {
            if (modeMockButton != null) modeMockButton.clicked -= SelectMockMode;
            if (modeRealButton != null) modeRealButton.clicked -= SelectRealMode;
            if (viewFocusButton != null) viewFocusButton.clicked -= ToggleFocus;
        }

        static void ToggleFocus() => focusMode = !focusMode;

        /// <summary>
        /// 트윈 집중. 보조 패널(.panel--aux)만 접어 3D 를 드러낸다.
        /// 상단 바 · 페이지 레일 · 알람 띠는 건드리지 않는다 — 알람이 접기로 사라지면
        /// 접기가 위험이 된다.
        /// </summary>
        void RefreshFocus()
        {
            // 접을 것이 없는 화면(검사 · 품질 · 요청)에서는 버튼 자체를 숨긴다.
            // 눌러도 아무 일도 없는 버튼은 고장으로 보인다.
            if (viewFocusButton != null)
                viewFocusButton.style.display = hasAuxPanels ? DisplayStyle.Flex : DisplayStyle.None;

            bool on = focusMode && hasAuxPanels;
            pageRoot?.EnableInClassList("page--focus", on);
            viewFocusButton?.EnableInClassList("tab--on", on);
        }

        void SelectMockMode() => SelectMode(RobotOperatingMode.Mock);
        void SelectRealMode() => SelectMode(RobotOperatingMode.Real);

        void SelectMode(RobotOperatingMode mode)
        {
            uiMaster?.RobotMaster?.TrySetOperatingMode(mode);
        }

        void RefreshCommandAvailability()
        {
            bool canChangeMode = uiMaster?.RobotMaster != null && !Application.isPlaying;
            modeMockButton?.SetEnabled(canChangeMode);
            modeRealButton?.SetEnabled(canChangeMode);
            if (modeMockButton != null)
                modeMockButton.tooltip = canChangeMode ? "Mock Backend 선택" : "운전 중에는 모드를 바꿀 수 없습니다.";
            if (modeRealButton != null)
                modeRealButton.tooltip = canChangeMode ? "Real Backend 선택" : "운전 중에는 모드를 바꿀 수 없습니다.";

            // IRobotControl에는 정지 계약이 없다. Ghost 정지만 호출하면 실제 로봇은 계속
            // 움직일 수 있으므로 STOP으로 연결하지 않는다.
            stopAllButton?.SetEnabled(false);
            if (stopAllButton != null)
                stopAllButton.tooltip = "STOP 제어 계약이 아직 없습니다.";
        }



        /// <summary>액센트 색을 쓰는 유일한 곳이다. 여기가 흐려지면 실기/모의 구분이 사라진다.</summary>
        void RefreshMode()
        {
            bool mock = uiMaster == null || uiMaster.IsSimulated;
            modeMock?.EnableInClassList("chip--accent", mock);
            modeReal?.EnableInClassList("chip--accent", !mock);

            // 페이지 뿌리의 fr5--mock 이 --c-accent 를 정한다. 이 줄이 없으면 UXML 에
            // 박아 둔 fr5--mock 이 그대로 남아, REAL 로 바꿔도 화면 전체 액센트가
            // 노란 채였다 — 모드에만 쓰기로 한 색이 모드를 안 따라가고 있었다.
            pageRoot?.EnableInClassList("fr5--mock", mock);
        }

        void RefreshState()
        {
            RobotRunState state = statusManager != null ? statusManager.State : RobotRunState.Disconnected;
            if (robotText != null) robotText.text = state.ToString().ToUpperInvariant();

            // 정상에는 색을 주지 않는다 (Docs/ui-design.md 1절).
            // RUNNING 에 초록을 주면 "정상이라는 신호"가 화면에서 가장 눈에 띄는 것이 되고,
            // 그러면 이상이 났을 때 달라지는 것이 색 하나뿐이라 알아채기 어려워진다.
            // 상태는 chip 안의 글자(RUNNING / IDLE / ERROR)가 이미 말한다.
            bool bad = state == RobotRunState.Disconnected || state == RobotRunState.Error;
            robotChip?.EnableInClassList("chip--bad", bad);
            robotChip?.EnableInClassList("chip--good", false);
        }

        void RefreshLinks()
        {
            bool jointLive = statusManager != null && statusManager.Latest != null;
            // 링크가 살아 있는 것은 정상이므로 무채색(dot--ok)이다. 끊긴 것만 색을 얻는다.
            linkJointDot?.EnableInClassList("dot--ok", jointLive);
            linkJointDot?.EnableInClassList("dot--good", false);
            linkJointDot?.EnableInClassList("dot--bad", !jointLive);
            if (linkJointAge != null)
            {
                bool mock = uiMaster == null || uiMaster.IsSimulated;
                string topic = mock ? "joint_states" : "nonrt_state_data";
                linkJointAge.text = jointLive ? topic : "수신 없음";
            }

            bool received = vision != null && vision.HasReceivedImage;
            double age = vision != null ? Time.realtimeSinceStartupAsDouble - vision.LastReceiveTimeSeconds : -1;
            bool fresh = received && age >= 0 && age < visionStaleSeconds;

            linkImageDot?.EnableInClassList("dot--ok", fresh);
            linkImageDot?.EnableInClassList("dot--good", false);
            linkImageDot?.EnableInClassList("dot--bad", received && !fresh);
            if (linkImageAge != null)
                linkImageAge.text = fresh ? $"{age * 1000:0} ms" : "board/image";
        }

        /// <summary>
        /// 알람 띠. 평상시에는 높이 0 이고 Error / Disconnected 일 때만 나타난다.
        /// Real 백엔드는 비상정지·알람·에러코드를 프레임에 실어 보내므로 그 값을 우선한다.
        /// </summary>
        /// <summary>
        /// 알람은 채터링하면 안 된다 (EEMUA 191 · IEC 62682).
        /// 링크 지터나 메인 스레드 정체로 상태가 한두 프레임 뒤집히는 것까지 띠로 알리면
        /// 화면이 깜빡이고, 그러면 진짜 알람도 같은 깜빡임으로 보여 무시하게 된다.
        ///
        /// 그래서 두 방향에 각각 시간을 건다.
        ///   켤 때  조건이 ShowDelay 만큼 이어져야 켠다.
        ///   끌 때  한 번 켜지면 HoldSeconds 동안은 조건이 사라져도 유지한다.
        /// 비상정지 · 알람 · 이상정지는 지연 없이 즉시 켠다. 늦으면 안 되는 것들이다.
        /// </summary>
        const float AlarmShowDelaySeconds = 0.6f;
        const float AlarmHoldSeconds = 3f;
        double alarmSinceTime = -1d;
        double alarmShownUntil = -1d;

        void RefreshAlarm()
        {
            if (alarmBanner == null) return;

            RobotRunState state = statusManager != null ? statusManager.State : RobotRunState.Disconnected;
            RobotStatusFrame frame = statusManager != null ? statusManager.Latest : null;

            bool emergency = frame != null && frame.EmergencyStop != 0;
            bool alarm = frame != null && frame.Alarm != 0;
            bool abnormal = frame != null && frame.AbnormalStop != 0;
            bool hard = emergency || alarm || abnormal;
            bool condition = hard || state == RobotRunState.Error || state == RobotRunState.Disconnected;

            double now = Time.realtimeSinceStartupAsDouble;
            if (!condition) alarmSinceTime = -1d;
            else if (alarmSinceTime < 0d) alarmSinceTime = now;

            // 하드 알람은 즉시, 링크 계열은 조건이 이어진 뒤에 켠다.
            bool arm = condition && (hard || now - alarmSinceTime >= AlarmShowDelaySeconds);
            if (arm) alarmShownUntil = now + AlarmHoldSeconds;

            bool show = arm || now < alarmShownUntil;
            alarmBanner.style.display = show ? DisplayStyle.Flex : DisplayStyle.None;
            if (!show) return;

            string label =
                emergency ? "EMERGENCY STOP" :
                alarm ? "ROBOT ALARM" :
                abnormal ? "ABNORMAL STOP" :
                statusManager != null ? statusManager.ErrorLabel.ToString().ToUpperInvariant() : "DISCONNECTED";
            if (alarmLabel != null) alarmLabel.text = label;

            string detail = statusManager != null ? statusManager.ErrorDetail : "상태 수신 없음";
            if (frame != null && (frame.MainErrorCode != 0 || frame.SubErrorCode != 0))
                detail = $"error {frame.MainErrorCode}:{frame.SubErrorCode}   ·   {detail}";
            if (alarmDetail != null) alarmDetail.text = detail;

            // TODO(API): 해제 가능한 경고만 초기화하는 알람 확인·해제 경로가 없다.
            //            fairino_msgs 의 리셋 명령이 붙으면 여기에 해제 버튼을 단다.
        }
    }
}
