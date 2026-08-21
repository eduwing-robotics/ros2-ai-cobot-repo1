// 역할: 로봇 데이터 없이 "보여주는 방식"만 바꾸는 HUD 조작을 담당한다.
//
//   - 우측 카메라 탭   GLOBAL / ROBOT / ERROR / ALL  → cam-stack 의 뷰포트 표시 전환
//   - 중앙 시점 프리셋 OVERVIEW / TOOL / TOP / FREE  → 메인 카메라를 앵커 위치로 이동
//   - 하단 이벤트 필터 ALL / WARN / ERROR           → event-list 행 숨김
//
// ROS 연결이나 RobotMaster 가 없어도 전부 동작합니다. 실데이터가 필요한 조작
// (SERVO / STOP ALL / SPEED / PROCESS / 카메라 도구)은 여기 두지 않았습니다.
//
// 조회하는 UXML name 과 프리셋 앵커는 Inspector 에서 지정합니다.
// 목록·개수도 Inspector 에서 늘리고 줄일 수 있습니다.

using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UIElements;

namespace MainUnity.UI
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(UIDocument))]
    public sealed class FR5ViewControls : MonoBehaviour
    {
        /// <summary>카메라 탭 한 개. viewport 를 비우면 "전부 보기" 탭이 된다.</summary>
        [Serializable]
        public sealed class CameraTab
        {
            [UxmlName("Button")] public string button;
            [Tooltip("이 탭이 보여줄 뷰포트. 비우면 모든 뷰포트를 함께 표시합니다(ALL).")]
            [UxmlName] public string viewport;
            [Tooltip("cam-active-mode 배지에 표시할 이름.")]
            public string label;
        }

        /// <summary>시점 프리셋 한 개.</summary>
        [Serializable]
        public sealed class ViewPreset
        {
            [UxmlName("Button")] public string button;
            [Tooltip("카메라를 옮길 위치. 비우면 시점을 건드리지 않습니다(FREE 처럼 자유 조작을 남길 때).")]
            public Transform anchor;
            [Tooltip("체크하면 매 프레임 앵커를 따라갑니다. TOOL 처럼 움직이는 대상에 붙일 때 씁니다.")]
            public bool follow;
        }

        /// <summary>이벤트 필터 한 개. 지정한 심각도 이상만 남긴다.</summary>
        [Serializable]
        public sealed class EventFilter
        {
            [UxmlName("Button")] public string button;
            [Tooltip("0 = 전부, 1 = 경고 이상, 2 = 오류만")]
            [Range(0, 2)] public int minSeverity;
        }

        static CameraTab[] MakeCameraTabs() => new[]
        {
            new CameraTab { button = "tab-global", viewport = "viewport-global", label = "GLOBAL" },
            new CameraTab { button = "tab-robot", viewport = "RealdepthCam", label = "ROBOT" },
            new CameraTab { button = "tab-error-check", viewport = "viewport-error-check", label = "ERROR" },
            new CameraTab { button = "tab-all", viewport = string.Empty, label = "ALL" },
        };

        static ViewPreset[] MakeViewPresets() => new[]
        {
            new ViewPreset { button = "view-preset-overview" },
            new ViewPreset { button = "view-preset-tool", follow = true },
            new ViewPreset { button = "view-preset-top" },
            new ViewPreset { button = "view-preset-free" },
        };

        static EventFilter[] MakeEventFilters() => new[]
        {
            new EventFilter { button = "event-filter-all", minSeverity = 0 },
            new EventFilter { button = "event-filter-warn", minSeverity = 1 },
            new EventFilter { button = "event-filter-error", minSeverity = 2 },
        };

        [Header("시점 프리셋이 움직일 카메라")]
        [Tooltip("비우면 MainCamera 를 찾아 씁니다.")]
        [SerializeField] Camera viewCamera;

        [Header("UI 요소 이름 (UXML)")]
        [SerializeField] CameraTab[] cameraTabs = MakeCameraTabs();
        [UxmlName("Label")]
        [SerializeField] string activeModeLabel = "cam-active-mode";
        [SerializeField] ViewPreset[] viewPresets = MakeViewPresets();
        [SerializeField] EventFilter[] eventFilters = MakeEventFilters();
        [UxmlName("ScrollView")]
        [SerializeField] string eventListName = "event-list";

        [Header("시작 선택")]
        [Tooltip("처음 켤 카메라 탭 / 시점 프리셋 / 이벤트 필터의 순번.")]
        [SerializeField] int startCameraTab = 3;
        [SerializeField] int startViewPreset = 0;
        [SerializeField] int startEventFilter = 0;

        readonly List<Action> unbind = new();

        Button[] cameraTabButtons;
        VisualElement[] cameraViewports;
        Label activeMode;
        Button[] presetButtons;
        Button[] filterButtons;
        ScrollView eventList;

        Transform followAnchor;
        int eventSeverityFloor;
        bool bound;

        void OnEnable() => Bind();
        void OnDisable() => Unbind();

        void LateUpdate()
        {
            // 로봇이 움직이는 동안 붙어 다니는 프리셋(TOOL 등)만 여기서 갱신한다.
            if (followAnchor == null || viewCamera == null)
                return;

            viewCamera.transform.SetPositionAndRotation(followAnchor.position, followAnchor.rotation);
        }

        void Bind()
        {
            VisualElement root = GetComponent<UIDocument>().rootVisualElement;
            if (viewCamera == null)
                viewCamera = Camera.main;

            activeMode = Find<Label>(root, activeModeLabel);
            eventList = Find<ScrollView>(root, eventListName);

            cameraTabButtons = new Button[cameraTabs.Length];
            cameraViewports = new VisualElement[cameraTabs.Length];
            for (int i = 0; i < cameraTabs.Length; i++)
            {
                cameraTabButtons[i] = Find<Button>(root, cameraTabs[i].button);
                cameraViewports[i] = Find<VisualElement>(root, cameraTabs[i].viewport);
                Bind(cameraTabButtons[i], i, SelectCameraTab);
            }

            presetButtons = new Button[viewPresets.Length];
            for (int i = 0; i < viewPresets.Length; i++)
            {
                presetButtons[i] = Find<Button>(root, viewPresets[i].button);
                Bind(presetButtons[i], i, SelectViewPreset);
            }

            filterButtons = new Button[eventFilters.Length];
            for (int i = 0; i < eventFilters.Length; i++)
            {
                filterButtons[i] = Find<Button>(root, eventFilters[i].button);
                Bind(filterButtons[i], i, SelectEventFilter);
            }

            bound = true;
            SelectCameraTab(startCameraTab);
            SelectViewPreset(startViewPreset);
            SelectEventFilter(startEventFilter);
        }

        void Unbind()
        {
            foreach (Action remove in unbind)
                remove();
            unbind.Clear();
            followAnchor = null;
            bound = false;
        }

        /// <summary>버튼에 순번을 실어 핸들러를 걸고, 해제하는 방법을 같이 적어 둔다.</summary>
        void Bind(Button button, int index, Action<int> handler)
        {
            if (button == null)
                return;

            Action click = () => handler(index);
            button.clicked += click;
            unbind.Add(() => button.clicked -= click);
        }

        // =========================== 카메라 탭 ===========================

        /// <summary>탭 하나를 고른다. viewport 가 빈 탭은 전체 표시로 취급한다.</summary>
        public void SelectCameraTab(int index)
        {
            if (!bound || index < 0 || index >= cameraTabs.Length)
                return;

            bool showAll = string.IsNullOrEmpty(cameraTabs[index].viewport);

            for (int i = 0; i < cameraTabs.Length; i++)
            {
                cameraTabButtons[i]?.EnableInClassList("hud-tab--active", i == index);

                if (cameraViewports[i] == null)
                    continue;

                bool visible = showAll || i == index;
                cameraViewports[i].style.display = visible ? DisplayStyle.Flex : DisplayStyle.None;
                // 한 대만 볼 때는 남은 뷰포트를 키워 빈자리를 메운다.
                cameraViewports[i].EnableInClassList("hud-cam__viewport--solo", visible && !showAll);
            }

            if (activeMode != null)
                activeMode.text = cameraTabs[index].label;
        }

        // ========================== 시점 프리셋 ==========================

        /// <summary>프리셋 하나를 고른다. 앵커가 없으면 강조만 옮기고 시점은 그대로 둔다.</summary>
        public void SelectViewPreset(int index)
        {
            if (!bound || index < 0 || index >= viewPresets.Length)
                return;

            for (int i = 0; i < viewPresets.Length; i++)
                presetButtons[i]?.EnableInClassList("hud-button--active", i == index);

            ViewPreset preset = viewPresets[index];
            followAnchor = preset.follow ? preset.anchor : null;

            if (preset.anchor == null || viewCamera == null)
                return;

            viewCamera.transform.SetPositionAndRotation(preset.anchor.position, preset.anchor.rotation);
        }

        // ========================== 이벤트 필터 ==========================

        /// <summary>필터 하나를 고른다.</summary>
        public void SelectEventFilter(int index)
        {
            if (!bound || index < 0 || index >= eventFilters.Length)
                return;

            for (int i = 0; i < eventFilters.Length; i++)
                filterButtons[i]?.EnableInClassList("hud-button--active", i == index);

            eventSeverityFloor = eventFilters[index].minSeverity;
            ApplyEventFilter();
        }

        /// <summary>현재 필터를 목록 전체에 다시 적용한다. 행을 추가한 쪽에서 호출한다.</summary>
        public void ApplyEventFilter()
        {
            if (eventList == null)
                return;

            foreach (VisualElement row in eventList.Children())
                row.style.display = Severity(row) >= eventSeverityFloor
                    ? DisplayStyle.Flex
                    : DisplayStyle.None;
        }

        /// <summary>행에 붙은 수식자 클래스로 심각도를 읽는다. 0 정보 / 1 경고 / 2 오류.</summary>
        static int Severity(VisualElement row)
        {
            if (row.ClassListContains("hud-event--error"))
                return 2;
            return row.ClassListContains("hud-event--warn") ? 1 : 0;
        }

        // ============================= 공통 =============================

        T Find<T>(VisualElement root, string elementName) where T : VisualElement
        {
            if (string.IsNullOrEmpty(elementName))
                return null;

            var element = root.Q<T>(elementName);
            if (element == null)
                Debug.LogWarning($"UXML 에서 {typeof(T).Name} \"{elementName}\" 을 찾지 못했습니다.", this);
            return element;
        }
    }
}
