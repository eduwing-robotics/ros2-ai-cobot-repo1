// 역할: FR5 MANUAL 페이지의 Ghost 조그 미리보기와 안전 안내를 담당한다.
//   - J1~J6 목표 자세를 Ghost에 표시
//   - APPLY · 그리퍼는 실제 로봇 명령을 발행하지 않음
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
            float[] joints = statusManager?.Latest?.JointDegrees;
            if (joints == null || joints.Length != JointCount)
                return;

            for (int i = 0; i < JointCount; i++)
                actualLabels[i].text = $"{joints[i]:0.0}°";
        }

        /// <summary>APPLY는 현재 실동작을 차단하고 Ghost 미리보기만 유지한다.</summary>
        public bool TryApplyJointTargets()
        {
            SetHint("실동작 차단 중 — 목표만 미리보기로 표시합니다.");
            return false;
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
                sliders[i].RegisterValueChangedCallback(OnSliderChanged);
            }

            if (gripperOpenButton != null)
                gripperOpenButton.clicked += OpenGripper;
            if (gripperCloseButton != null)
                gripperCloseButton.clicked += CloseGripper;
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

            if (statusManager == null)
                statusManager = uiMaster.StatusManager;
            if (ghostMaster == null)
                ghostMaster = uiMaster.Ghost;
        }
    }
}
