// 역할: 공통 셸(FR5Shell.uxml)의 상단 바 값을 채운다. 모든 페이지에 하나씩 붙는다.
//
// 페이지마다 같은 코드를 복사하면 항목과 판정 기준이 갈라진다. 실제로 갈라져 있었다.
// 모드 · 로봇 상태 · 링크 · 알람은 페이지와 무관하므로 여기 한 곳에서만 다룬다.
//
//   실연결 : 모드 · RobotRunState · joint_states · board/image · MainServer · Sequencer 링크
//
// 작업(JOB)·사이클은 페이지가 아는 값이라 각 페이지 바인더가 채운다.

using System;
using System.Collections;
using MainUnity.Runtime.Camera;
using MainUnity.Runtime.Robot.Assembly;
using MainUnity.Runtime.Robot;
using MainUnity.Runtime.Robot.Status;
using UnityEngine;
using UnityEngine.Networking;
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

        [Header("서비스 상태")]
        [SerializeField] string mainServerBaseUrl = "http://127.0.0.1:8000";
        [SerializeField, Min(1f)] float servicePollSeconds = 5f;

        VisualElement modeMock, modeReal, robotChip, linkJointDot, linkImageDot,
            linkApiDot, linkSequencerDot, alarmBanner;
        VisualElement pageRoot;
        Button modeMockButton, modeRealButton, stopAllButton, viewFocusButton;
        VisualElement viewFocusRule;
        Label robotText, linkJointAge, linkImageAge, linkApiLabel, linkSequencerLabel,
            alarmLabel, alarmDetail, commandResult;
        Coroutine servicePolling;
        Label setupApi, setupSequencer;
        internal bool? ApiConnected { get; private set; }
        internal bool? SequencerConnected { get; private set; }
        internal string MainServerBaseUrl => mainServerBaseUrl;
        bool cached;
        bool stopRequestInFlight;
        bool hasAuxPanels;

        // 페이지마다 셸 인스턴스가 하나씩이라 인스턴스 필드로 두면 화면을 옮길 때마다
        // 집중이 풀린다. 접어 둔 것은 접어 둔 채로 있어야 하므로 static 이다.
        static bool focusMode;

        void OnEnable()
        {
            cached = false;
            ApiConnected = null;
            SequencerConnected = null;
            servicePolling = StartCoroutine(PollServiceLinks());
        }

        void OnDisable()
        {
            UnbindCommands();
            if (servicePolling != null) StopCoroutine(servicePolling);
            servicePolling = null;
        }

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
            if (commandResult != null)
                commandResult.style.display = string.IsNullOrEmpty(commandResult.text) ? DisplayStyle.None : DisplayStyle.Flex;
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
            linkApiDot = root.Q<VisualElement>("link-api-dot");
            linkApiLabel = root.Q<Label>("link-api-label");
            setupApi = root.Q<Label>("setup-api");
            setupSequencer = root.Q<Label>("setup-sequencer");
            linkSequencerDot = root.Q<VisualElement>("link-sequencer-dot");
            linkSequencerLabel = root.Q<Label>("link-sequencer-label");
            alarmBanner = root.Q<VisualElement>("alarm-banner");
            alarmLabel = root.Q<Label>("alarm-label");
            alarmDetail = root.Q<Label>("alarm-detail");
            commandResult = root.Q<Label>("command-result");
            viewFocusButton = root.Q<Button>("view-focus");
            viewFocusRule = root.Q<VisualElement>("view-focus-rule");
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
            if (stopAllButton != null) stopAllButton.clicked += TogglePause;
            if (viewFocusButton != null) viewFocusButton.clicked += ToggleFocus;
        }

        void UnbindCommands()
        {
            if (modeMockButton != null) modeMockButton.clicked -= SelectMockMode;
            if (modeRealButton != null) modeRealButton.clicked -= SelectRealMode;
            if (stopAllButton != null) stopAllButton.clicked -= TogglePause;
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
            // 위의 구분선도 같이 숨긴다. 그 선은 이 버튼을 페이지 탭 무리에서 떼어
            // 놓으려고 긋는 것이라, 버튼이 없으면 뗄 것이 없다. 남겨 두면 레일 맨
            // 아래에 아무것도 나누지 않는 선 하나가 화면 끝에 붙어 떠 있다.
            DisplayStyle focusDisplay = hasAuxPanels ? DisplayStyle.Flex : DisplayStyle.None;
            if (viewFocusButton != null) viewFocusButton.style.display = focusDisplay;
            if (viewFocusRule != null) viewFocusRule.style.display = focusDisplay;

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

            AssemblyProgressFrame frame = uiMaster?.AssemblyProgress?.Latest;
            bool paused = frame?.State == AssemblyState.Paused;
            bool conveyorMoving = frame?.State == AssemblyState.ConveyorMoving;
            bool pauseSupported = uiMaster?.IsSimulated == true;
            if (stopAllButton != null)
            {
                stopAllButton.text = !pauseSupported ? "일시정지 미지원" : stopRequestInFlight ? "처리 중…" : paused ? "▶ 재개" : "Ⅱ 일시정지";
                stopAllButton.SetEnabled(pauseSupported && !stopRequestInFlight && frame != null &&
                    !frame.IsTerminal && !conveyorMoving && uiMaster?.Scenario?.IsRunning == true);
                stopAllButton.tooltip = !pauseSupported
                    ? "Real 일시정지는 아직 지원하지 않습니다."
                    : conveyorMoving
                        ? "컨베이어 이동 중에는 일시정지할 수 없습니다."
                    : paused
                        ? "일시정지된 조립을 재개합니다."
                        : "현재 로봇 동작을 정지 확인 뒤 일시정지합니다.";
            }
        }

        async void TogglePause()
        {
            if (stopRequestInFlight || uiMaster?.Scenario == null) return;
            stopRequestInFlight = true;
            bool resume = uiMaster.AssemblyProgress?.Latest?.State == AssemblyState.Paused;
            if (commandResult != null) commandResult.text = "";
            try
            {
                if (resume)
                    await uiMaster.Scenario.ResumeAsync();
                else
                    await uiMaster.Scenario.PauseAsync();
            }
            catch (System.Exception exception)
            {
                string message = (resume ? "재개 실패" : "일시정지 실패") + " · " + exception.Message;
                if (commandResult != null) commandResult.text = message;
                uiMaster?.RecordEvent("조작", message, true);
                Debug.LogException(exception, this);
            }
            finally
            {
                stopRequestInFlight = false;
            }
        }

        /// <summary>액센트 색을 쓰는 유일한 곳이다. 여기가 흐려지면 실기/모의 구분이 사라진다.</summary>
        void RefreshMode()
        {
            bool known = uiMaster != null && uiMaster.RobotMaster != null;
            bool mock = known && uiMaster.IsSimulated;
            modeMock?.EnableInClassList("chip--accent", mock);
            modeReal?.EnableInClassList("chip--accent", known && !mock);

            // 페이지 뿌리의 fr5--mock 이 --c-accent 를 정한다. 이 줄이 없으면 UXML 에
            // 박아 둔 fr5--mock 이 그대로 남아, REAL 로 바꿔도 화면 전체 액센트가
            // 노란 채였다 — 모드에만 쓰기로 한 색이 모드를 안 따라가고 있었다.
            pageRoot?.EnableInClassList("fr5--mock", mock);
        }

        void RefreshState()
        {
            RobotRunState state = statusManager != null && statusManager.HasFreshState ? statusManager.State : RobotRunState.Disconnected;
            if (robotText != null) robotText.text = state switch
            {
                RobotRunState.Running => "이동 중",
                RobotRunState.Idle => "정지",
                RobotRunState.Error => "오류",
                _ => statusManager?.Latest == null ? "수신 대기" : "수신 중단"
            };

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
            bool jointLive = statusManager != null && statusManager.HasFreshState;
            // 링크가 살아 있는 것은 정상이므로 무채색(dot--ok)이다. 끊긴 것만 색을 얻는다.
            linkJointDot?.EnableInClassList("dot--ok", jointLive);
            linkJointDot?.EnableInClassList("dot--good", false);
            linkJointDot?.EnableInClassList("dot--bad", !jointLive);
            if (linkJointAge != null)
            {
                bool mock = uiMaster == null || uiMaster.IsSimulated;
                string topic = mock ? "joint_states" : "nonrt_state_data";
                linkJointAge.text = "ROS";
                linkJointAge.tooltip = jointLive ? topic + " 수신 중" : topic + " 수신 없음";
            }

            bool received = vision != null && vision.HasReceivedImage;
            double age = vision != null ? Time.realtimeSinceStartupAsDouble - vision.LastReceiveTimeSeconds : -1;
            bool fresh = received && age >= 0 && age < visionStaleSeconds;

            linkImageDot?.EnableInClassList("dot--ok", fresh);
            linkImageDot?.EnableInClassList("dot--good", false);
            linkImageDot?.EnableInClassList("dot--bad", received && !fresh);
            if (linkImageAge != null)
            {
                linkImageAge.text = "CAM";
                linkImageAge.tooltip = fresh
                    ? $"board/image · {age * 1000:0} ms"
                    : received ? "board/image 수신 지연" : "board/image 수신 없음";
            }
        }

        IEnumerator PollServiceLinks()
        {
            // UIDocument의 새 트리에 바인딩한 뒤에만 결과를 표시한다.
            while (!cached) yield return null;
            Resolve();
            while (true)
            {
                yield return RefreshServiceLinks();
                yield return new WaitForSecondsRealtime(Mathf.Max(1f, servicePollSeconds));
            }
        }

        [Serializable]
        sealed class HealthMode { public string runtime_mode; }
        [Serializable]
        sealed class HealthEnvelope { public HealthMode data; }

        IEnumerator RefreshServiceLinks()
        {
            string baseUrl = mainServerBaseUrl?.TrimEnd('/');
            if (!Uri.TryCreate(baseUrl, UriKind.Absolute, out Uri uri) ||
                uri.Scheme != Uri.UriSchemeHttp && uri.Scheme != Uri.UriSchemeHttps)
            {
                SetLinkState(linkApiDot, linkApiLabel, false, "MainServer URL이 올바르지 않습니다.");
                SetLinkState(linkSequencerDot, linkSequencerLabel, null,
                    "MainServer에 연결할 수 없어 확인하지 못했습니다.");
                yield break;
            }

            using (UnityWebRequest health = UnityWebRequest.Get(baseUrl + "/api/v1/health"))
            {
                health.timeout = 3;
                yield return health.SendWebRequest();
                if (health.result != UnityWebRequest.Result.Success)
                {
                    SetLinkState(linkApiDot, linkApiLabel, false,
                        "MainServer API·DB 응답 실패 · HTTP " + health.responseCode);
                    SetLinkState(linkSequencerDot, linkSequencerLabel, null,
                        "MainServer에 연결할 수 없어 확인하지 못했습니다.");
                    yield break;
                }
                string actual = null;
                try { actual = JsonUtility.FromJson<HealthEnvelope>(health.downloadHandler.text)?.data?.runtime_mode; }
                catch (ArgumentException) { }
                string expected = uiMaster == null ? null : uiMaster.OperatingMode.ToString().ToLowerInvariant();
                if (expected == null || actual != expected)
                {
                    string detail = $"환경 불일치 · 기대 {expected ?? "미설정"} / 서버 {actual ?? "미확인"}";
                    SetLinkState(linkApiDot, linkApiLabel, false, detail);
                    SetLinkState(linkSequencerDot, linkSequencerLabel, false, "환경 검증 실패로 조회 차단");
                    yield break;
                }
            }

            SetLinkState(linkApiDot, linkApiLabel, true, "MainServer API·DB 정상");
            using UnityWebRequest sequencer = UnityWebRequest.Get(
                baseUrl + "/api/v1/assemblies/current");
            sequencer.SetRequestHeader("X-Runtime-Mode", uiMaster == null ? "" : uiMaster.OperatingMode.ToString().ToLowerInvariant());
            sequencer.timeout = 3;
            yield return sequencer.SendWebRequest();
            SetLinkState(linkSequencerDot, linkSequencerLabel,
                sequencer.result == UnityWebRequest.Result.Success,
                sequencer.result == UnityWebRequest.Result.Success
                    ? "AssemblySequencer 응답 정상"
                    : "AssemblySequencer 응답 실패 · HTTP " + sequencer.responseCode);
        }

        void SetLinkState(VisualElement dot, Label label, bool? connected, string detail)
        {
            dot?.EnableInClassList("dot--ok", connected == true);
            dot?.EnableInClassList("dot--bad", connected == false);
            if (dot != null) dot.tooltip = detail;
            if (label != null) label.tooltip = detail;
            Label setup = null;
            if (label == linkApiLabel)
            {
                ApiConnected = connected;
                setup = setupApi;
            }
            else if (label == linkSequencerLabel)
            {
                SequencerConnected = connected;
                setup = setupSequencer;
            }
            if (setup != null)
            {
                setup.enableRichText = false;
                setup.text = detail + " · 확인 " + DateTime.Now.ToString("HH:mm:ss");
                setup.EnableInClassList("bad", connected == false);
            }
        }

        // 통신 흔들림은 0.6초 지속 후 표시하고 설비 알람은 즉시 표시한다.
        // 조건 해제 뒤 3초는 복구 안내로 전환한다. 현재 오류가 없다는 뜻이며
        // 설비 reset이나 작업 재개 완료를 뜻하지 않는다.
        const float AlarmShowDelaySeconds = 0.6f;
        const float AlarmHoldSeconds = 3f;
        double alarmSinceTime = -1d;
        double alarmShownUntil = -1d;
        string lastAlarmLabel;

        void RefreshAlarm()
        {
            if (alarmBanner == null) return;

            RobotRunState state = statusManager != null && statusManager.HasFreshState ? statusManager.State : RobotRunState.Disconnected;
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

            alarmBanner.EnableInClassList("alarm-banner--recovered", !condition);
            if (!condition)
            {
                if (alarmLabel != null) alarmLabel.text = "상태 복구";
                if (alarmDetail != null) alarmDetail.text = lastAlarmLabel + " · 수신 오류 신호 해소 · 설비 준비와 작업 재개는 별도 확인";
                return;
            }

            string label =
                statusManager == null || !statusManager.HasFreshState
                    ? frame == null ? "로봇 상태 수신 대기" : "로봇 상태 수신 중단" :
                emergency ? "비상정지 작동" :
                alarm ? "로봇 알람 발생" :
                abnormal ? "이상 정지" :
                state == RobotRunState.Disconnected
                    ? frame == null ? "로봇 상태 수신 대기" : "로봇 상태 수신 중단"
                    : "로봇 오류";
            lastAlarmLabel = label;
            if (alarmLabel != null) alarmLabel.text = label;

            string detail = state == RobotRunState.Disconnected
                ? "현재 자세를 확인할 수 없습니다 · 로봇 연결을 확인하세요"
                : "로봇 상태와 오류 코드를 확인하세요";
            if (frame != null && statusManager.HasFreshState && abnormal && !emergency && !alarm)
                detail = frame.MainErrorCode == 0 && frame.SubErrorCode == 0
                    ? $"abnormal_stop={frame.AbnormalStop} · 코드 0:0 · 상세 원인 미확인 · 컨트롤러 진단 확인"
                    : $"abnormal_stop={frame.AbnormalStop} · 컨트롤러 진단에서 코드 원인 확인";
            if (frame != null && !statusManager.HasFreshState)
                detail = $"마지막 수신 {Math.Max(0d, now - frame.ReceiveTimeSeconds):0.0}초 전 · E-STOP {frame.EmergencyStop} / ALARM {frame.Alarm} / 이상정지 {frame.AbnormalStop} · 현재 상태 미확인";
            if (frame != null && (frame.MainErrorCode != 0 || frame.SubErrorCode != 0))
                detail = $"error {frame.MainErrorCode}:{frame.SubErrorCode}   ·   {detail}";
            if (alarmDetail != null)
            {
                alarmDetail.text = detail;
                alarmDetail.tooltip = (statusManager?.ErrorDetail ?? "상태 수신 없음") +
                    (frame == null ? "" : $"\n/nonrt_state_data · 마지막 수신 {Math.Max(0d, now - frame.ReceiveTimeSeconds):0.0}초 전" +
                        $"\nabnormal_stop={frame.AbnormalStop}, emg={frame.EmergencyStop}, alarm={frame.Alarm}" +
                        $"\nmain={frame.MainErrorCode}, sub={frame.SubErrorCode}, robot_motion_done={frame.RobotMotionDone}" +
                        $"\nrobot_mode={frame.RobotMode}, prg_state={frame.ProgramState}" +
                        "\n동작 완료 신호와 이상정지 신호는 별도 값입니다. 동작 완료만으로 오류 해제를 판정하지 않습니다.");
            }

            // TODO(API): 해제 가능한 경고만 초기화하는 알람 확인·해제 경로가 없다.
            //            fairino_msgs 의 리셋 명령이 붙으면 여기에 해제 버튼을 단다.
        }
    }
}
