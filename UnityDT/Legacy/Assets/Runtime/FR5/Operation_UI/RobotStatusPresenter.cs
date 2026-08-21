// FR5 런타임 상태를 관제 HUD의 ROBOT STATUS 패널에 표시합니다.
// 값을 읽어 문자열로 옮기는 역할만 하고, 로봇 제어 판단은 기존 기능 계층에 맡깁니다.

using FR5Mvp.RobotControl;
using FR5Mvp.SafetyMonitoring;
using UnityEngine;
using UnityEngine.UIElements;

namespace FR5Mvp.OperationUI
{
    /// <summary>ROBOT STATUS 패널의 관절·그리퍼·상태 표시와 그리퍼 버튼을 연결합니다.</summary>
    [AddComponentMenu("Robotics/FR5/Operation UI/Robot Status Presenter")]
    [DisallowMultipleComponent]
    public sealed class RobotStatusPresenter : MonoBehaviour
    {
        const int JointCount = 6;
        const string Unavailable = "—";

        // SET HOME 고정 각도 수정 위치: 아래 배열을 J1부터 J6 순서로 변경합니다.
        static readonly float[] HomePoseDegrees = { 0f, -90f, 90f, -90f, -90f, 0f };

        [SerializeField] UIDocument document;
        [SerializeField] FR5SystemOrchestrator system;
        [SerializeField, Tooltip("Label shown next to the robot state badge.")]
        string robotId = "FR5-01";
        [SerializeField, Min(0.02f), Tooltip("Seconds between value refreshes.")]
        float refreshInterval = 0.1f;

        readonly Label[] jointValues = new Label[JointCount];
        readonly VisualElement[] jointFills = new VisualElement[JointCount];
        readonly Slider[] jogSliders = new Slider[JointCount];
        readonly Label[] jogActuals = new Label[JointCount];
        readonly Label[] jogTargets = new Label[JointCount];

        Label robotIdLabel;
        VisualElement robotDot;
        Label gripperValue;
        VisualElement gripperFill;
        Button gripperOpenButton;
        Button gripperCloseButton;
        Label watchdogStateLabel;
        Label watchdogTimingLabel;
        VisualElement watchdogDot;
        Label[] tcpValues;
        Label[] rpyValues;
        Button monitorTab;
        Button manualTab;
        Button homeButton;
        Button applyButton;
        VisualElement monitorPane;
        VisualElement manualPane;

        SafetyMonitor safetyMonitor;
        bool bound;
        float nextRefreshTime;

        void OnEnable()
        {
            ResolveReferences();
            nextRefreshTime = 0f;
        }

        void OnDisable() => Unbind();

        void Update()
        {
            if (!bound && !TryBind())
                return;
            if (Time.unscaledTime < nextRefreshTime)
                return;
            nextRefreshTime = Time.unscaledTime + refreshInterval;
            Refresh();
        }

        /// <summary>같은 오브젝트나 부모에서 UIDocument와 FR5 시스템을 찾아 채웁니다.</summary>
        void ResolveReferences()
        {
            if (document == null)
                document = GetComponent<UIDocument>();
            if (system == null)
                system = FindAnyObjectByType<FR5SystemOrchestrator>();
            // SafetyMonitor는 오케스트레이터가 공개하지 않으므로 직접 찾습니다.
            // RefreshReferences가 쓰는 것과 같은 탐색 방식입니다.
            if (safetyMonitor == null && system != null)
                safetyMonitor = system.GetComponentInChildren<SafetyMonitor>(true);
        }

        bool TryBind()
        {
            ResolveReferences();
            VisualElement root = document != null ? document.rootVisualElement : null;
            if (root == null)
                return false;

            robotIdLabel = root.Q<Label>("robot-id");
            robotDot = root.Q<VisualElement>("robot-dot");
            gripperValue = root.Q<Label>("gripper-value");
            gripperFill = root.Q<VisualElement>("gripper-fill");
            gripperOpenButton = root.Q<Button>("gripper-open-button");
            gripperCloseButton = root.Q<Button>("gripper-close-button");
            watchdogStateLabel = root.Q<Label>("watchdog-state");
            watchdogTimingLabel = root.Q<Label>("watchdog-timing");
            watchdogDot = root.Q<VisualElement>("watchdog-dot");
            monitorTab = root.Q<Button>("tab-monitor");
            manualTab = root.Q<Button>("tab-manual");
            homeButton = root.Q<Button>("jog-home-button");
            applyButton = root.Q<Button>("jog-apply-button");
            monitorPane = root.Q<VisualElement>("pane-monitor");
            manualPane = root.Q<VisualElement>("pane-manual");

            tcpValues = new[]
            {
                root.Q<Label>("tcp-x-value"),
                root.Q<Label>("tcp-y-value"),
                root.Q<Label>("tcp-z-value")
            };
            rpyValues = new[]
            {
                root.Q<Label>("rpy-r-value"),
                root.Q<Label>("rpy-p-value"),
                root.Q<Label>("rpy-y-value")
            };

            for (int i = 0; i < JointCount; i++)
            {
                int number = i + 1;
                jointValues[i] = root.Q<Label>($"joint-{number}-value");
                jointFills[i] = root.Q<VisualElement>($"joint-{number}-fill");
                jogSliders[i] = root.Q<Slider>($"jog-{number}-slider");
                jogActuals[i] = root.Q<Label>($"jog-{number}-actual");
                jogTargets[i] = root.Q<Label>($"jog-{number}-target");
            }

            if (jointValues[0] == null)
                return false;

            ApplyJointLimits();
            BindCallbacks();
            DisableUnwiredActions(root);
            bound = true;
            Refresh();
            return true;
        }

        /// <summary>
        /// 조그 슬라이더 범위를 실제 관절 제한으로 맞춥니다.
        /// UXML에 적힌 값은 URDF를 다시 불러오면 어긋날 수 있으므로 런타임 값을 따릅니다.
        /// </summary>
        void ApplyJointLimits()
        {
            JointController[] joints = system?.RobotControl?.GetJoints();
            if (joints == null)
                return;

            for (int i = 0; i < JointCount && i < joints.Length; i++)
            {
                Slider slider = jogSliders[i];
                if (slider == null)
                    continue;
                // 범위를 먼저 넓힌 뒤 값을 넣어야 중간에 잘리지 않습니다.
                slider.lowValue = joints[i].LowerDegrees;
                slider.highValue = joints[i].UpperDegrees;
                slider.SetValueWithoutNotify(joints[i].ActualDegrees);
                SetText(jogTargets[i], FormatDegrees(joints[i].ActualDegrees));
            }
        }

        void BindCallbacks()
        {
            if (gripperOpenButton != null)
                gripperOpenButton.clicked += OpenGripper;
            if (gripperCloseButton != null)
                gripperCloseButton.clicked += CloseGripper;
            if (monitorTab != null)
                monitorTab.clicked += ShowMonitorPane;
            if (manualTab != null)
                manualTab.clicked += ShowManualPane;
            if (homeButton != null)
                homeButton.clicked += SetHomeTargets;
            if (applyButton != null)
                applyButton.clicked += ApplyManualPose;

            for (int i = 0; i < JointCount; i++)
            {
                Slider slider = jogSliders[i];
                if (slider == null)
                    continue;
                Label target = jogTargets[i];
                // 목표 표시만 갱신합니다. 실제 동작은 APPLY 배선 후에 붙습니다.
                slider.RegisterValueChangedCallback(
                    change => SetText(target, FormatDegrees(change.newValue)));
            }
        }

        void Unbind()
        {
            if (gripperOpenButton != null)
                gripperOpenButton.clicked -= OpenGripper;
            if (gripperCloseButton != null)
                gripperCloseButton.clicked -= CloseGripper;
            if (monitorTab != null)
                monitorTab.clicked -= ShowMonitorPane;
            if (manualTab != null)
                manualTab.clicked -= ShowManualPane;
            if (homeButton != null)
                homeButton.clicked -= SetHomeTargets;
            if (applyButton != null)
                applyButton.clicked -= ApplyManualPose;
            bound = false;
        }

        /// <summary>아직 연결하지 않은 버튼은 눌러도 아무 일이 없으므로 비활성으로 둡니다.</summary>
        static void DisableUnwiredActions(VisualElement root)
        {
            root.Q<Button>("jog-cancel-button")?.SetEnabled(false);
        }

        void OpenGripper() => system?.OpenGripper();
        void CloseGripper() => system?.CloseGripper();

        void SetHomeTargets()
        {
            for (int i = 0; i < JointCount; i++)
            {
                float target = HomePoseDegrees[i];
                jogSliders[i]?.SetValueWithoutNotify(target);
                SetText(jogTargets[i], FormatDegrees(target));
            }
        }

        void ApplyManualPose()
        {
            var targets = new float[JointCount];
            for (int i = 0; i < JointCount; i++)
                targets[i] = jogSliders[i]?.value ?? 0f;
            system?.ApplyManualPose(targets);
        }

        void ShowMonitorPane() => SelectPane(true);
        void ShowManualPane() => SelectPane(false);

        void SelectPane(bool monitor)
        {
            monitorPane?.EnableInClassList("hud-pane--hidden", !monitor);
            manualPane?.EnableInClassList("hud-pane--hidden", monitor);
            monitorTab?.EnableInClassList("hud-tab--active", monitor);
            manualTab?.EnableInClassList("hud-tab--active", !monitor);
            if (!monitor)
                ApplyJointLimits();
        }

        void Refresh()
        {
            RefreshRobotBadge();
            RefreshJoints();
            RefreshGripper();
            RefreshTcp();
            RefreshWatchdog();
        }

        void RefreshRobotBadge()
        {
            FR5SystemOrchestrator.SystemState state = system != null
                ? system.State
                : FR5SystemOrchestrator.SystemState.Unconfigured;
            SetText(robotIdLabel, $"{robotId} · {state.ToString().ToUpperInvariant()}");
            SetDot(robotDot, ResolveDotTone(state));
        }

        static string ResolveDotTone(FR5SystemOrchestrator.SystemState state) => state switch
        {
            FR5SystemOrchestrator.SystemState.Ready => "ok",
            FR5SystemOrchestrator.SystemState.Working => "ok",
            FR5SystemOrchestrator.SystemState.WaitingForRos => "warn",
            FR5SystemOrchestrator.SystemState.Stopped => "warn",
            FR5SystemOrchestrator.SystemState.Faulted => "fault",
            _ => "idle"
        };

        void RefreshJoints()
        {
            JointController[] joints = system?.RobotControl?.GetJoints();
            for (int i = 0; i < JointCount; i++)
            {
                if (joints == null || i >= joints.Length)
                {
                    SetText(jointValues[i], Unavailable);
                    SetWidth(jointFills[i], 0f);
                    continue;
                }

                JointController joint = joints[i];
                float actual = joint.ActualDegrees;
                SetText(jointValues[i], FormatDegrees(actual, withUnit: false));
                SetWidth(jointFills[i], Normalize(actual, joint.LowerDegrees, joint.UpperDegrees));
                SetText(jogActuals[i], FormatDegrees(actual));
            }
        }

        void RefreshGripper()
        {
            GripperController gripper = system?.RobotControl?.Gripper;
            if (gripper == null || !gripper.IsBound)
            {
                SetText(gripperValue, Unavailable);
                SetWidth(gripperFill, 0f);
                return;
            }

            float openMillimeters = gripper.OpeningMeters * 1000f;
            float maxMillimeters = gripper.UpperMeters * 1000f;
            SetText(gripperValue, $"{openMillimeters:F1} / {maxMillimeters:F1}");
            SetWidth(gripperFill, Normalize(
                gripper.OpeningMeters, gripper.LowerMeters, gripper.UpperMeters));
        }

        /// <summary>
        /// TCP 자세를 robot_base 기준으로 표시합니다.
        /// GripperController의 Tcp Transform이 비어 있으면 값을 만들어내지 않고 비웁니다.
        /// 이 값은 Unity 좌표계 기준이며 ROS TF 변환은 별도 과제입니다.
        /// </summary>
        void RefreshTcp()
        {
            Transform tcp = system?.RobotControl?.Gripper?.Tcp;
            Transform baseFrame = system?.ModelRoot;
            if (tcp == null || baseFrame == null)
            {
                for (int i = 0; i < 3; i++)
                {
                    SetText(tcpValues?[i], Unavailable);
                    SetText(rpyValues?[i], Unavailable);
                }
                return;
            }

            Vector3 local = baseFrame.InverseTransformPoint(tcp.position) * 1000f;
            SetText(tcpValues[0], local.x.ToString("F2"));
            SetText(tcpValues[1], local.y.ToString("F2"));
            SetText(tcpValues[2], local.z.ToString("F2"));

            Vector3 euler = (Quaternion.Inverse(baseFrame.rotation) * tcp.rotation).eulerAngles;
            SetText(rpyValues[0], Wrap180(euler.x).ToString("F1"));
            SetText(rpyValues[1], Wrap180(euler.y).ToString("F1"));
            SetText(rpyValues[2], Wrap180(euler.z).ToString("F1"));
        }

        void RefreshWatchdog()
        {
            if (safetyMonitor == null)
            {
                SetText(watchdogStateLabel, Unavailable);
                SetText(watchdogTimingLabel, Unavailable);
                SetWatchdogTone("idle");
                return;
            }

            string state;
            string tone;
            if (safetyMonitor.IsTimedOut)
            {
                state = "TIMEOUT";
                tone = "fault";
            }
            else if (safetyMonitor.IsHealthy)
            {
                state = "HEALTHY";
                tone = "ok";
            }
            else
            {
                // 아직 유효한 관절 상태를 한 번도 받지 못한 상태입니다.
                state = "NO SIGNAL";
                tone = "idle";
            }

            SetText(watchdogStateLabel, state);
            SetText(watchdogTimingLabel,
                $"{safetyMonitor.TimeoutSeconds * 1000f:F0} / " +
                $"{safetyMonitor.InterpolationSeconds * 1000f:F0} ms");
            SetWatchdogTone(tone);
        }

        void SetWatchdogTone(string tone)
        {
            if (watchdogStateLabel != null)
            {
                watchdogStateLabel.EnableInClassList("hud-watchdog__state--fault", tone == "fault");
                watchdogStateLabel.EnableInClassList("hud-watchdog__state--idle", tone == "idle");
            }
            SetDot(watchdogDot, tone);
        }

        static void SetDot(VisualElement dot, string tone)
        {
            if (dot == null)
                return;
            dot.EnableInClassList("hud-dot--ok", tone == "ok");
            dot.EnableInClassList("hud-dot--warn", tone == "warn");
            dot.EnableInClassList("hud-dot--fault", tone == "fault");
        }

        static void SetText(Label label, string value)
        {
            // 값이 그대로면 문자열 갱신을 건너뛰어 불필요한 레이아웃 작업을 막습니다.
            if (label != null && label.text != value)
                label.text = value;
        }

        static void SetWidth(VisualElement element, float percent)
        {
            if (element == null)
                return;
            var width = Length.Percent(Mathf.Clamp(percent, 0f, 100f));
            if (element.style.width != new StyleLength(width))
                element.style.width = width;
        }

        static float Normalize(float value, float lower, float upper) =>
            Mathf.Approximately(upper, lower)
                ? 0f
                : Mathf.Clamp01((value - lower) / (upper - lower)) * 100f;

        static string FormatDegrees(float degrees, bool withUnit = true) =>
            withUnit ? $"{degrees:F1}°" : degrees.ToString("F1");

        static float Wrap180(float degrees)
        {
            degrees %= 360f;
            if (degrees > 180f)
                degrees -= 360f;
            else if (degrees < -180f)
                degrees += 360f;
            return degrees;
        }
    }
}
