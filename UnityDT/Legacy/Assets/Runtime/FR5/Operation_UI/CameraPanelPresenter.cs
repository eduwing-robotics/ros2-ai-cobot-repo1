// 관제 HUD의 카메라 패널에서 어떤 카메라를 볼지 선택합니다.
// 표시 전환만 담당하고 카메라 자체의 렌더 설정은 씬 구성에 맡깁니다.

using UnityEngine;
using UnityEngine.UIElements;

namespace FR5Mvp.OperationUI
{
    /// <summary>카메라 탭을 선택해 뷰포트 표시와 소스 상태 행을 전환합니다.</summary>
    [AddComponentMenu("Robotics/FR5/Operation UI/Camera Panel Presenter")]
    [DisallowMultipleComponent]
    public sealed class CameraPanelPresenter : MonoBehaviour
    {
        public enum CameraView
        {
            Global,
            Robot,
            ErrorCheck,
            All
        }

        const string HiddenClass = "hud-cam__viewport--hidden";
        const string SplitClass = "hud-cam__viewport--split";
        const string ActiveTabClass = "hud-tab--active";
        const string Unavailable = "—";

        // 탭과 뷰포트는 같은 순서로 짝지어 둡니다. All은 뷰포트가 없어 탭만 있습니다.
        static readonly string[] TabNames =
            { "tab-global", "tab-robot", "tab-error-check", "tab-all" };
        static readonly string[] ViewportNames =
            { "viewport-global", "viewport-robot", "viewport-error-check" };

        [SerializeField] UIDocument document;
        [SerializeField, Tooltip("View selected when the panel first appears.")]
        CameraView defaultView = CameraView.All;
        [SerializeField, Min(0.1f), Tooltip("Seconds between stream stat refreshes.")]
        float refreshInterval = 0.5f;

        readonly Button[] tabs = new Button[TabNames.Length];
        readonly Image[] viewports = new Image[ViewportNames.Length];
        readonly VisualElement[] viewportSources = new VisualElement[ViewportNames.Length];
        readonly Label[] viewportSourceTexts = new Label[ViewportNames.Length];

        VisualElement statusSource;
        Label statusSourceText;
        Label statusSourceName;
        Label statusStream;

        CameraView currentView;
        bool bound;
        float nextRefreshTime;

        public CameraView CurrentView => currentView;

        void OnEnable()
        {
            currentView = defaultView;
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
            // 해상도와 프레임률은 실제 텍스처와 렌더 주기에서 읽으므로 주기적으로 갱신합니다.
            RefreshStatusRow();
        }

        bool TryBind()
        {
            if (document == null)
                document = GetComponent<UIDocument>();
            VisualElement root = document != null ? document.rootVisualElement : null;
            if (root == null)
                return false;

            for (int i = 0; i < TabNames.Length; i++)
                tabs[i] = root.Q<Button>(TabNames[i]);
            for (int i = 0; i < ViewportNames.Length; i++)
            {
                viewports[i] = root.Q<Image>(ViewportNames[i]);
                viewportSources[i] = root.Q<VisualElement>($"{ViewportNames[i]}-source");
                viewportSourceTexts[i] = root.Q<Label>($"{ViewportNames[i]}-source-text");
            }

            statusSource = root.Q<VisualElement>("cam-source");
            statusSourceText = root.Q<Label>("cam-source-text");
            statusSourceName = root.Q<Label>("cam-source-name");
            statusStream = root.Q<Label>("cam-stream-value");

            if (tabs[0] == null || viewports[0] == null)
                return false;

            BindCallbacks();
            bound = true;
            Select(currentView);
            return true;
        }

        void BindCallbacks()
        {
            if (tabs[0] != null)
                tabs[0].clicked += SelectGlobal;
            if (tabs[1] != null)
                tabs[1].clicked += SelectRobot;
            if (tabs[2] != null)
                tabs[2].clicked += SelectErrorCheck;
            if (tabs[3] != null)
                tabs[3].clicked += SelectAll;
        }

        void Unbind()
        {
            if (tabs[0] != null)
                tabs[0].clicked -= SelectGlobal;
            if (tabs[1] != null)
                tabs[1].clicked -= SelectRobot;
            if (tabs[2] != null)
                tabs[2].clicked -= SelectErrorCheck;
            if (tabs[3] != null)
                tabs[3].clicked -= SelectAll;
            bound = false;
        }

        void SelectGlobal() => Select(CameraView.Global);
        void SelectRobot() => Select(CameraView.Robot);
        void SelectErrorCheck() => Select(CameraView.ErrorCheck);
        void SelectAll() => Select(CameraView.All);

        /// <summary>선택한 보기로 탭 강조와 뷰포트 표시를 맞춥니다.</summary>
        public void Select(CameraView view)
        {
            currentView = view;
            if (!bound)
                return;

            for (int i = 0; i < tabs.Length; i++)
                tabs[i]?.EnableInClassList(ActiveTabClass, (int)view == i);

            bool showAll = view == CameraView.All;
            for (int i = 0; i < viewports.Length; i++)
            {
                bool visible = showAll || (int)view == i;
                viewports[i]?.EnableInClassList(HiddenClass, !visible);
                // ALL에서는 셋을 나눠 담고, 단일 선택에서는 하나가 전체 높이를 씁니다.
                viewports[i]?.EnableInClassList(SplitClass, showAll);
            }

            RefreshStatusRow();
        }

        /// <summary>
        /// 상태 행을 선택된 카메라 기준으로 채웁니다.
        /// 소스 구분은 뷰포트 배지에서, 해상도는 실제 텍스처에서 가져와
        /// 나중에 ROS 영상으로 바꿔도 따라오게 합니다.
        /// </summary>
        void RefreshStatusRow()
        {
            if (currentView == CameraView.All)
            {
                CopySourceTone(-1);
                SetText(statusSourceName, $"{CountLiveSources()} sources · RenderTexture");
                SetText(statusStream, $"{Mathf.RoundToInt(CurrentFramesPerSecond())} FPS");
                return;
            }

            int index = (int)currentView;
            Image viewport = index < viewports.Length ? viewports[index] : null;
            Texture texture = viewport?.image;

            CopySourceTone(index);
            SetText(statusSourceName, texture == null
                ? Unavailable
                : $"{texture.name} · RenderTexture");
            SetText(statusStream, texture == null
                ? Unavailable
                : $"{texture.width}×{texture.height} · " +
                  $"{Mathf.RoundToInt(CurrentFramesPerSecond())} FPS");
        }

        /// <summary>뷰포트 배지의 ROS/SIM 구분을 상태 행에 그대로 옮깁니다.</summary>
        void CopySourceTone(int index)
        {
            if (statusSource == null)
                return;

            bool ros = false;
            string text = "SIM";
            if (index >= 0 && index < viewportSources.Length && viewportSources[index] != null)
            {
                ros = viewportSources[index].ClassListContains("hud-source--ros");
                text = viewportSourceTexts[index] != null
                    ? viewportSourceTexts[index].text
                    : (ros ? "ROS" : "SIM");
            }
            else if (index < 0)
            {
                // ALL에서는 하나라도 실기 영상이면 실기 톤으로 올려 오인을 막습니다.
                for (int i = 0; i < viewportSources.Length; i++)
                {
                    if (viewportSources[i] != null &&
                        viewportSources[i].ClassListContains("hud-source--ros"))
                    {
                        ros = true;
                        break;
                    }
                }
                text = ros ? "ROS" : "SIM";
            }

            statusSource.EnableInClassList("hud-source--ros", ros);
            statusSource.EnableInClassList("hud-source--sim", !ros);
            SetText(statusSourceText, text);
        }

        int CountLiveSources()
        {
            int count = 0;
            for (int i = 0; i < viewports.Length; i++)
            {
                if (viewports[i]?.image != null)
                    count++;
            }
            return count;
        }

        // RenderTexture 카메라는 렌더 주기가 곧 프레임률이므로 그대로 씁니다.
        static float CurrentFramesPerSecond() =>
            Time.smoothDeltaTime > 0f ? 1f / Time.smoothDeltaTime : 0f;

        static void SetText(Label label, string value)
        {
            if (label != null && label.text != value)
                label.text = value;
        }
    }
}
