// 역할: MANUAL 페이지(FR5Manual.uxml)에서 ManualJointPanel 이 다루지 않는 표시값만 담당한다.
//
// 조그 · 그리퍼 명령 · Ghost 미리보기는 ManualJointPanel 이 이미 검증된 상태로 소유한다.
// (jog-N-slider / -actual / -target, jog-apply/cancel/home, gripper-open/close-button)
// 여기서 다시 구현하면 같은 상태를 두 곳이 쓰게 되므로 건드리지 않는다.
//
// TODO(API·Real): Real 의 수동 관절 제어는 연결되어 있지 않다 (API.md 2절 각주).
//                 IRobotControl.MoveJ 와 TrySetJointTarget 이 Real 에서 비어 있어
//                 지금은 Mock 에서만 조그가 의미를 갖는다. 화면은 양쪽 모두 같다.
//
//   이 바인더가 맡는 것 : TCP · RPY 표시 · 그리퍼 폭 표시
//   ManualJointPanel     : 조그 슬라이더 · APPLY/CANCEL/HOME · 그리퍼 OPEN/CLOSE · Ghost
//
// 수동 조작은 작업 흐름 밖이라 jobs·units 를 만들지 않는다 (Architecture.md).

using MainUnity.Runtime.Robot.Status;
using UnityEngine;
using UnityEngine.UIElements;

namespace MainUnity.UI
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(UIDocument))]
    public sealed class FR5ManualBinder : MonoBehaviour
    {
        static readonly string[] TcpAxes = { "X", "Y", "Z", "R", "P", "Y" };

        [Header("데이터 소스")]
        [Tooltip("비우면 부모에서 찾습니다. 로봇 계층으로 들어가는 단일 입구입니다.")]
        [SerializeField] UIMaster uiMaster;
        [SerializeField] RobotStatusManager statusManager;
        [SerializeField] GripperSubscriber gripper;

        [SerializeField] float gripperStrokeMillimeters = 40f;

        readonly Label[] tcpLabels = new Label[6];

        Label gripperText, gripperValue;
        VisualElement gripperChip, gripperFill;
        bool cached;

        void OnEnable() => cached = false;

        void Update()
        {
            // UIDocument 는 활성화된 뒤에야 rootVisualElement 를 만든다.
            if (!cached) { Build(); if (!cached) return; }
            ResolveReferences();
            RefreshTcp();
            RefreshGripper();
        }

        void ResolveReferences()
        {
            if (uiMaster == null) uiMaster = GetComponentInParent<UIMaster>();
            if (uiMaster == null) return;
            if (statusManager == null) statusManager = uiMaster.StatusManager;
            if (gripper == null) gripper = uiMaster.Gripper;
        }

        /// <summary>TCP 행은 코드로 만든다. UXML 에는 빈 컨테이너만 둔다.</summary>
        void Build()
        {
            VisualElement root = GetComponent<UIDocument>().rootVisualElement;
            if (root == null) return;

            VisualElement tcpList = root.Q<VisualElement>("tcp-list");
            if (tcpList != null)
            {
                tcpList.Clear();
                for (int i = 0; i < TcpAxes.Length; i++)
                    tcpList.Add(BuildTcpRow(i));
            }

            gripperChip = root.Q<VisualElement>("gripper-state-chip");
            gripperText = root.Q<Label>("gripper-state-text");
            gripperValue = root.Q<Label>("gripper-value");
            gripperFill = root.Q<VisualElement>("gripper-fill");
            cached = true;
        }

        VisualElement BuildTcpRow(int i)
        {
            var row = new VisualElement();
            row.AddToClassList("row");
            row.style.height = 74;
            row.style.borderBottomWidth = 1;
            row.style.borderBottomColor = new Color(1f, 1f, 1f, 0.055f);

            var axis = new Label(TcpAxes[i]);
            axis.AddToClassList("value");
            axis.style.width = 60;
            row.Add(axis);

            var value = new Label("—");
            value.style.color = new Color(0.886f, 0.925f, 0.945f);
            value.style.fontSize = 22;
            value.style.unityFontStyleAndWeight = FontStyle.Bold;
            value.style.width = 200;
            value.style.unityTextAlign = TextAnchor.MiddleRight;
            tcpLabels[i] = value;
            row.Add(value);

            var spacer = new VisualElement();
            spacer.AddToClassList("spacer");
            row.Add(spacer);

            var unit = new Label(i < 3 ? "mm" : "deg");
            unit.AddToClassList("muted");
            unit.style.fontSize = 12;
            row.Add(unit);
            return row;
        }

        void RefreshTcp()
        {
            RobotStatusFrame frame = statusManager != null ? statusManager.Latest : null;
            if (frame == null)
            {
                foreach (Label l in tcpLabels) if (l != null) l.text = "—";
                return;
            }

            Vector3 p = frame.TcpPositionMillimeters;
            Vector3 r = frame.TcpRotationDegrees;
            SetTcp(0, p.x); SetTcp(1, p.y); SetTcp(2, p.z);
            SetTcp(3, r.x); SetTcp(4, r.y); SetTcp(5, r.z);
        }

        /// <summary>Mock Backend 는 TCP/RPY 를 채우지 않는다. 0 을 실측으로 오인하지 않게 비운다.</summary>
        void SetTcp(int i, float v)
        {
            if (tcpLabels[i] == null) return;
            bool blank = uiMaster != null && uiMaster.IsSimulated && Mathf.Approximately(v, 0f);
            tcpLabels[i].text = blank ? "—" : v.ToString("0.0");
        }

        void RefreshGripper()
        {
            if (gripper == null || !gripper.TryGetOpeningPercent(out float percent))
            {
                if (gripperValue != null) gripperValue.text = "—";
                if (gripperText != null) gripperText.text = "—";
                if (gripperFill != null) gripperFill.style.width = Length.Percent(0f);
                gripperChip?.EnableInClassList("chip--accent", false);
                return;
            }

            float mm = gripperStrokeMillimeters * percent * 0.01f;
            if (gripperValue != null) gripperValue.text = $"{mm:0.0} / {gripperStrokeMillimeters:0}";
            if (gripperFill != null) gripperFill.style.width = Length.Percent(percent);

            bool holding = percent < 95f;
            if (gripperText != null) gripperText.text = holding ? "HOLDING" : "OPEN";
            gripperChip?.EnableInClassList("chip--accent", holding);
        }

    }
}
