// 역할: MANUAL 목표 경로를 Ghost로 검사하고 주입된 수동 제어 계약에 요청한다.
// 그리퍼 명령은 연결하지 않으며, 요청 수락을 작업 완료로 표시하지 않는다.
//
// 조회하는 UXML name 은 Inspector 직렬화 필드로 지정합니다.

using System;
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
            public string slider;
            public string actual;
            public string target;
        }

        [Serializable]
        public sealed class PanelNames
        {
            public string gripperOpenButton = "gripper-open-button";
            public string gripperCloseButton = "gripper-close-button";
            public string applyButton = "jog-apply-button";
            public string cancelButton = "jog-cancel-button";
            public string homeButton = "jog-home-button";
            public string hint = "ghost-hint";
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
        [SerializeField] RobotStatusManager statusManager;
        [SerializeField] GhostMaster ghostMaster;

        [Header("UI 요소 이름 (UXML)")]
        [SerializeField] PanelNames names = new();

        readonly Slider[] sliders = new Slider[JointCount];
        readonly Label[] actualLabels = new Label[JointCount];
        readonly Label[] targetLabels = new Label[JointCount];
        readonly float[] initialTargets = new float[JointCount];

        Button gripperOpenButton;
        Button gripperCloseButton;

        Button applyButton;
        Button cancelButton;
        Button homeButton;
        Label hint;
        bool bound;
        bool initializedTargets;
        bool requestSubmitted;
        double nextRefresh;
        readonly float[] previewStart = new float[JointCount];
        readonly float[] requestedTargets = new float[JointCount];
        string lastHint;
        bool lastHintError;

        void OnEnable()
        {
            initializedTargets = false;
            requestSubmitted = false;
            nextRefresh = 0d;
            lastHint = null;
            Bind();
        }
        void OnDisable()
        {
            ghostMaster?.EndManualPreview();
            Unbind();
        }

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

            if (Time.realtimeSinceStartupAsDouble < nextRefresh) return;
            nextRefresh = Time.realtimeSinceStartupAsDouble + 0.1d;
            RefreshReferences();
            float[] joints = statusManager?.Latest?.JointDegrees;
            bool fresh = statusManager != null && statusManager.HasFreshState && joints?.Length == JointCount;
            for (int i = 0; i < JointCount; i++) actualLabels[i].text = fresh ? $"{joints[i]:0.0}°" : "—";
            if (fresh && !initializedTargets)
            {
                initializedTargets = true;
                SetTargets(joints);
            }
            bool canRequest = CanRequest(out string reason);
            applyButton.SetEnabled(canRequest);
            applyButton.tooltip = reason;
            if (requestSubmitted) SetHint("요청 접수 · 실행 완료 아님 · 진행 상태를 확인하세요.");
            else if (!fresh) SetHint("요청 거부 · 최신 로봇 자세를 확인할 수 없습니다.", true);
            else
            {
                string preview = ghostMaster != null ? ghostMaster.ManualStatus : "Ghost 연결 없음";
                SetHint(preview + (uiMaster?.IsSimulated == false ? "\nREAL 임의 관절 이동 미지원 · 요청 차단" : ""),
                    ghostMaster?.ManualCollision == true);
            }
        }

        /// <summary>검사한 목표를 수동 제어 계약에 전달한다. true는 요청 수락이며 실제 완료가 아니다.</summary>
        public bool TryApplyJointTargets()
        {
            RefreshReferences();
            if (!CanRequest(out string reason))
            {
                SetHint("요청 거부 · " + reason, true);
                return false;
            }
            bool accepted = uiMaster.RobotMaster.Control.TrySetJointTarget(requestedTargets);
            if (!accepted)
            {
                SetHint("요청 거부 · " + (statusManager?.ErrorDetail ?? "수동 제어가 요청을 수락하지 않았습니다."), true);
                return false;
            }
            requestSubmitted = true;
            applyButton.SetEnabled(false);
            SetHint("요청 접수 · 실행 완료 아님 · 진행 상태를 확인하세요.");
            return true;
        }

        bool CanRequest(out string reason)
        {
            reason = "최신 로봇 자세가 필요합니다.";
            if (!bound || !initializedTargets || statusManager == null || !statusManager.HasFreshState) return false;
            if (uiMaster?.RobotMaster?.Control == null) { reason = "수동 제어 연결 없음"; return false; }
            if (uiMaster.Scenario?.IsRunning == true) { reason = "자동 조립 실행 중"; return false; }
            if (requestSubmitted) { reason = "이미 요청한 목표입니다."; return false; }
            if (!statusManager.CanAcceptCommand(out reason)) return false;
            if (ghostMaster == null || !ghostMaster.ManualPathReady)
            { reason = ghostMaster != null ? ghostMaster.ManualStatus : "Ghost 경로 검사 없음"; return false; }
            float[] current = statusManager.Latest?.JointDegrees;
            if (current == null || current.Length != JointCount) { reason = "현재 자세 미확인"; return false; }
            for (int i = 0; i < JointCount; i++)
            {
                if (!float.IsFinite(current[i]) || Mathf.Abs(current[i] - previewStart[i]) > 0.2f ||
                    sliders[i].value != requestedTargets[i])
                { reason = "검사 후 현재 자세 또는 목표가 바뀌었습니다. 목표를 다시 확인하세요."; return false; }
            }
            if (!uiMaster.IsSimulated) { reason = "REAL 임의 관절 이동 미지원"; return false; }
            reason = "검사한 관절 목표 요청 · 실제 계획 및 완료는 실행 설비에서 확인";
            return true;
        }

        /// <summary>현재 자세에서 Slider 목표까지 Ghost 관절 보간 경로 검사를 시작한다.</summary>
        public bool TryPreviewJointTargets()
        {
            RefreshReferences();
            if (!bound || ghostMaster == null || statusManager == null || !statusManager.HasFreshState ||
                statusManager.Latest?.JointDegrees?.Length != JointCount)
            {
                ghostMaster?.EndManualPreview();
                SetHint("요청 거부 · 최신 현재 자세 또는 Ghost 연결 없음", true);
                return false;
            }
            requestSubmitted = false;
            for (int i = 0; i < JointCount; i++)
            {
                previewStart[i] = statusManager.Latest.JointDegrees[i];
                requestedTargets[i] = sliders[i].value;
            }
            applyButton.SetEnabled(false);
            return ghostMaster.PreviewManualPath(previewStart, requestedTargets);
        }


        /// <summary>이름이 비어 있으면 조회를 건너뛴다. Q() 는 null 이름에 예외를 던진다.</summary>
        static T Find<T>(VisualElement root, string name) where T : VisualElement =>
            string.IsNullOrEmpty(name) ? null : UnityEngine.UIElements.UQueryExtensions.Q<T>(root, name, System.Array.Empty<string>());

        void Bind()
        {
            VisualElement root = GetComponent<UIDocument>().rootVisualElement;
            if (root == null)
                return;
            gripperOpenButton = Find<Button>(root, names.gripperOpenButton);
            gripperCloseButton = Find<Button>(root, names.gripperCloseButton);
            applyButton = Find<Button>(root, names.applyButton);
            cancelButton = Find<Button>(root, names.cancelButton);
            homeButton = Find<Button>(root, names.homeButton);
            hint = Find<Label>(root, names.hint);

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
                targetLabels[i].text = sliders[i].value.ToString("0.0") + "°";
                sliders[i].RegisterValueChangedCallback(OnSliderChanged);
            }

            if (gripperOpenButton != null)
            {
                gripperOpenButton.SetEnabled(false);
                gripperOpenButton.tooltip = "실동작 그리퍼 명령은 연결되어 있지 않습니다.";
                gripperOpenButton.clicked += OpenGripper;
            }
            if (gripperCloseButton != null)
            {
                gripperCloseButton.SetEnabled(false);
                gripperCloseButton.tooltip = "실동작 그리퍼 명령은 연결되어 있지 않습니다.";
                gripperCloseButton.clicked += CloseGripper;
            }
            applyButton.SetEnabled(false);
            applyButton.tooltip = "현재 자세와 목표 경로 검사 후 요청할 수 있습니다.";
            applyButton.clicked += Apply;
            cancelButton.clicked += Cancel;
            homeButton.clicked += SetHome;
            bound = true;
            RefreshReferences();
        }

        void Unbind()
        {
            if (!bound)
                return;
            for (int i = 0; i < JointCount; i++)
                sliders[i].UnregisterValueChangedCallback(OnSliderChanged);
            if (gripperOpenButton != null)
                gripperOpenButton.clicked -= OpenGripper;
            if (gripperCloseButton != null)
                gripperCloseButton.clicked -= CloseGripper;
            applyButton.clicked -= Apply;
            cancelButton.clicked -= Cancel;
            homeButton.clicked -= SetHome;
            bound = false;
        }

        void OpenGripper() => SetHint("실동작 차단 중 — 그리퍼 열기 명령을 보내지 않았습니다.");

        void CloseGripper() => SetHint("실동작 차단 중 — 그리퍼 닫기 명령을 보내지 않았습니다.");

        void Apply() => TryApplyJointTargets();

        void Cancel()
        {
            float[] joints = statusManager?.Latest?.JointDegrees;
            // 최신 수신이 없으면 이전 자세나 기본값을 현재 자세처럼 목표에 복사하지 않는다.
            if (statusManager != null && statusManager.HasFreshState && joints?.Length == JointCount)
                SetTargets(joints);
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

        void SetHint(string message, bool error = false)
        {
            if (hint == null || message == lastHint && error == lastHintError) return;
            lastHint = message;
            lastHintError = error;
            hint.enableRichText = false;
            hint.text = message;
            hint.EnableInClassList("bad", error);
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

            if (statusManager == null)
                statusManager = uiMaster.StatusManager;
            if (ghostMaster == null)
                ghostMaster = uiMaster.Ghost;
        }
    }
}
