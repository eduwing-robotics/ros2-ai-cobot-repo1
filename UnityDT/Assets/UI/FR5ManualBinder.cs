// 역할: MANUAL의 TCP·그리퍼 관측값과 로봇 카메라 표시 영역을 소유한다.
// 목표·경로 미리보기와 이동 요청의 판정은 ManualJointPanel / Ghost가 담당한다.

using System.Collections;
using MainUnity.Runtime.Robot.Status;
using UnityEngine;
using UnityEngine.UIElements;

namespace MainUnity.UI
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(UIDocument))]
    public sealed class FR5ManualBinder : MonoBehaviour
    {
        static readonly string[] TcpAxes = { "X", "Y", "Z", "ROLL", "PITCH", "YAW" };

        [Header("데이터 소스")]
        [Tooltip("비우면 부모에서 찾습니다. 로봇 계층으로 들어가는 단일 입구입니다.")]
        [SerializeField] UIMaster uiMaster;
        [SerializeField] RobotStatusManager statusManager;
        [SerializeField] GripperSubscriber gripper;

        // 기존 씬 직렬화 호환용으로 보존한다. 실측 거리로 환산하는 데 사용하지 않는다.
        [SerializeField] float gripperStrokeMillimeters = 40f;

        [Header("로봇 표시 영역")]
        [Tooltip("MANUAL에서만 표시 영역을 조정할 카메라입니다. 위치와 회전은 변경하지 않습니다.")]
        [SerializeField] Camera previewCamera;

        readonly Label[] tcpLabels = new Label[6];

        Label gripperText, gripperValue;
        VisualElement gripperChip, gripperFill;
        bool cached;
        VisualElement documentRoot, viewport;
        Coroutine bindRoutine;
        Rect previousCameraRect;
        bool cameraRectChanged;

        void OnEnable()
        {
            cached = false;
            if (uiMaster == null) uiMaster = GetComponentInParent<UIMaster>();
            ResolveReferences();
            bindRoutine = StartCoroutine(BindDocument());
        }

        void OnDisable()
        {
            if (bindRoutine != null) StopCoroutine(bindRoutine);
            bindRoutine = null;
            documentRoot?.UnregisterCallback<GeometryChangedEvent>(OnViewportGeometryChanged);
            viewport?.UnregisterCallback<GeometryChangedEvent>(OnViewportGeometryChanged);
            if (cameraRectChanged && previewCamera != null)
                previewCamera.rect = previousCameraRect;
            cameraRectChanged = false;
            documentRoot = null;
            viewport = null;
            cached = false;
        }

        IEnumerator BindDocument()
        {
            // UIDocument가 활성화 과정에서 시각 트리를 만든 뒤 연결한다.
            yield return null;
            while (!cached)
            {
                Build();
                if (!cached) yield return null;
            }
            bindRoutine = null;
        }

        void Update()
        {
            if (!cached) return;
            ResolveReferences();
            RefreshTcp();
            RefreshGripper();
        }

        void ResolveReferences()
        {
            if (uiMaster == null) return;
            if (statusManager == null) statusManager = uiMaster.StatusManager;
            if (gripper == null) gripper = uiMaster.Gripper;
        }

        void Build()
        {
            VisualElement root = GetComponent<UIDocument>().rootVisualElement;
            if (root == null) return;

            VisualElement tcpList = root.Q<VisualElement>("tcp-list");
            VisualElement previewViewport = root.Q<VisualElement>("manual-viewport");
            if (tcpList == null || previewViewport == null) return;

            tcpList.Clear();
            for (int i = 0; i < TcpAxes.Length; i++)
                tcpList.Add(BuildTcpRow(i));

            documentRoot = root;
            viewport = previewViewport;
            documentRoot.RegisterCallback<GeometryChangedEvent>(OnViewportGeometryChanged);
            viewport.RegisterCallback<GeometryChangedEvent>(OnViewportGeometryChanged);
            UpdateCameraViewport();

            gripperChip = root.Q<VisualElement>("gripper-state-chip");
            gripperText = root.Q<Label>("gripper-state-text");
            gripperValue = root.Q<Label>("gripper-value");
            gripperFill = root.Q<VisualElement>("gripper-fill");
            cached = true;
        }

        void OnViewportGeometryChanged(GeometryChangedEvent _) => UpdateCameraViewport();

        void UpdateCameraViewport()
        {
            if (previewCamera == null || documentRoot == null || viewport == null) return;
            Rect rootBounds = documentRoot.worldBound;
            Rect viewportBounds = viewport.worldBound;
            if (!(rootBounds.width > 0f && rootBounds.height > 0f &&
                  viewportBounds.width > 0f && viewportBounds.height > 0f)) return;

            float left = Mathf.Clamp01((viewportBounds.xMin - rootBounds.xMin) / rootBounds.width);
            float right = Mathf.Clamp01((viewportBounds.xMax - rootBounds.xMin) / rootBounds.width);
            // UI Toolkit은 좌상단, Camera.rect는 좌하단 원점이며 단위는 화면 대비 비율이다.
            float bottom = Mathf.Clamp01(1f - (viewportBounds.yMax - rootBounds.yMin) / rootBounds.height);
            float top = Mathf.Clamp01(1f - (viewportBounds.yMin - rootBounds.yMin) / rootBounds.height);
            if (!(right > left && top > bottom)) return;

            if (!cameraRectChanged)
            {
                previousCameraRect = previewCamera.rect;
                cameraRectChanged = true;
            }
            previewCamera.rect = Rect.MinMaxRect(left, bottom, right, top);
        }

        VisualElement BuildTcpRow(int i)
        {
            var row = new VisualElement();
            row.AddToClassList("row");
            row.AddToClassList("manual-tcp-row");

            var axis = new Label(TcpAxes[i]);
            axis.AddToClassList("manual-tcp-axis");
            row.Add(axis);

            var value = new Label("—");
            value.AddToClassList("manual-tcp-value");
            tcpLabels[i] = value;
            row.Add(value);

            var unit = new Label(i < 3 ? "mm" : "deg");
            unit.AddToClassList("muted");
            unit.AddToClassList("manual-tcp-unit");
            row.Add(unit);
            return row;
        }

        void RefreshTcp()
        {
            RobotStatusFrame frame = statusManager != null ? statusManager.Latest : null;
            if (frame == null || !statusManager.HasFreshState)
            {
                foreach (Label l in tcpLabels) if (l != null) l.text = "—";
                return;
            }

            Vector3 p = frame.TcpPositionMillimeters;
            Vector3 r = frame.TcpRotationDegrees;
            SetTcp(0, p.x); SetTcp(1, p.y); SetTcp(2, p.z);
            SetTcp(3, r.x); SetTcp(4, r.y); SetTcp(5, r.z);
        }

        // Mock Backend는 TCP/RPY를 채우지 않으므로 0을 실측으로 오인하지 않게 비운다.
        void SetTcp(int i, float v)
        {
            if (tcpLabels[i] == null) return;
            bool blank = uiMaster != null && uiMaster.IsSimulated && Mathf.Approximately(v, 0f);
            tcpLabels[i].text = blank ? "—" : v.ToString("0.0");
        }

        void RefreshGripper()
        {
            if (statusManager == null || !statusManager.HasFreshState || gripper == null || !gripper.TryGetOpeningPercent(out float percent))
            {
                if (gripperValue != null) gripperValue.text = "—";
                if (gripperText != null) gripperText.text = "—";
                if (gripperFill != null) gripperFill.style.width = Length.Percent(0f);
                gripperChip?.EnableInClassList("chip--accent", false);
                return;
            }

            if (gripperValue != null) gripperValue.text = $"{percent:0}";
            if (gripperFill != null) gripperFill.style.width = Length.Percent(percent);

            if (gripperText != null) gripperText.text = "파지 미확인";
            gripperChip?.EnableInClassList("chip--accent", false);
        }

    }
}
