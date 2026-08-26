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
        Button modeMockButton, modeRealButton, stopAllButton;
        Label robotText, linkJointAge, linkImageAge, alarmLabel, alarmDetail;
        bool cached;

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
        }

        void UnbindCommands()
        {
            if (modeMockButton != null) modeMockButton.clicked -= SelectMockMode;
            if (modeRealButton != null) modeRealButton.clicked -= SelectRealMode;
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
        }

        void RefreshState()
        {
            RobotRunState state = statusManager != null ? statusManager.State : RobotRunState.Disconnected;
            if (robotText != null) robotText.text = state.ToString().ToUpperInvariant();

            bool bad = state == RobotRunState.Disconnected || state == RobotRunState.Error;
            robotChip?.EnableInClassList("chip--bad", bad);
            robotChip?.EnableInClassList("chip--good", state == RobotRunState.Running);
        }

        void RefreshLinks()
        {
            bool jointLive = statusManager != null && statusManager.Latest != null;
            linkJointDot?.EnableInClassList("dot--good", jointLive);
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

            linkImageDot?.EnableInClassList("dot--good", fresh);
            linkImageDot?.EnableInClassList("dot--bad", received && !fresh);
            if (linkImageAge != null)
                linkImageAge.text = fresh ? $"{age * 1000:0} ms" : "board/image";
        }

        /// <summary>
        /// 알람 띠. 평상시에는 높이 0 이고 Error / Disconnected 일 때만 나타난다.
        /// Real 백엔드는 비상정지·알람·에러코드를 프레임에 실어 보내므로 그 값을 우선한다.
        /// </summary>
        void RefreshAlarm()
        {
            if (alarmBanner == null) return;

            RobotRunState state = statusManager != null ? statusManager.State : RobotRunState.Disconnected;
            RobotStatusFrame frame = statusManager != null ? statusManager.Latest : null;

            bool emergency = frame != null && frame.EmergencyStop != 0;
            bool alarm = frame != null && frame.Alarm != 0;
            bool abnormal = frame != null && frame.AbnormalStop != 0;
            bool show = state == RobotRunState.Error || state == RobotRunState.Disconnected
                        || emergency || alarm || abnormal;

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
