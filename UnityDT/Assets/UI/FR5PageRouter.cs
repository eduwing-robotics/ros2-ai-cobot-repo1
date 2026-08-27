// 역할: 페이지 5개를 UIDocument 단위로 전환한다.
//
// 페이지는 최상위 계층이므로 어느 패널에도 종속되지 않는다(Docs/UI.md 4절).
// 각 페이지는 자기 GameObject 에 UIDocument 하나 + 바인더를 갖고, 라우터는
// 활성 페이지의 UIDocument 만 켠다. 비활성 페이지는 Update 가 돌지 않는다.
//
// 각 페이지 UXML 은 nav-run / nav-monitor / nav-inspect / nav-manual / nav-quality / nav-setup
// 이라는 같은 이름의 버튼을 갖고 있으므로, 라우터가 모든 문서에서 한 번에 등록한다.

using System;
using MainUnity.Runtime.Robot.Assembly;
using UnityEngine;
using UnityEngine.UIElements;

namespace MainUnity.UI
{
    public enum FR5Page
    {
        Run,
        Inspect,
        Manual,
        Quality,
        Setup,
    }

    [DisallowMultipleComponent]
    public sealed class FR5PageRouter : MonoBehaviour
    {
        [Serializable]
        public sealed class PageEntry
        {
            public FR5Page page;

            [Tooltip("이 페이지의 UIDocument 입니다. 비우면 그 페이지는 없는 것으로 봅니다.")]
            public UIDocument document;

            [Tooltip("아직 화면이 없는 페이지는 꺼 둡니다. 레일에서 눌러도 넘어가지 않습니다.")]
            public bool available = true;
        }

        [Header("페이지")]
        [SerializeField] FR5Page startPage = FR5Page.Run;
        [SerializeField] PageEntry[] pages =
        {
            new PageEntry { page = FR5Page.Run },
            new PageEntry { page = FR5Page.Inspect },
            new PageEntry { page = FR5Page.Manual },
            new PageEntry { page = FR5Page.Quality },
            // SETUP 은 아직 UXML 이 없다. 화면이 생기면 available 을 켠다.
            new PageEntry { page = FR5Page.Setup, available = false },
        };

        static readonly (FR5Page Page, string Button)[] NavButtons =
        {
            (FR5Page.Run, "nav-run"),
            (FR5Page.Inspect, "nav-inspect"),
            (FR5Page.Manual, "nav-manual"),
            (FR5Page.Quality, "nav-quality"),
            (FR5Page.Setup, "nav-setup"),
        };

        readonly System.Collections.Generic.HashSet<UIDocument> wiredDocuments =
            new System.Collections.Generic.HashSet<UIDocument>();

        UIDocument requestDocument;
        AssemblyProgressManager assemblyProgress;
        bool progressSubscribed;
        bool monitorRequested;
        FR5Page current;

        /// <summary>현재 열린 페이지다.</summary>
        public FR5Page Current => current;

        void OnEnable()
        {
            wiredDocuments.Clear();
            current = startPage;

            // MONITOR 가 기본 화면이다. 이 화면을 켜는 이유는 셀을 지켜보기 위해서이지
            // 작업을 넣기 위해서가 아니다. 작업 요청은 RUN 탭을 눌러 들어간다.
            //
            // monitorRequested 를 여기서 정하지 않으면 이전 세션의 값이 남는다.
            // current 는 초기화하면서 이 값만 두면 화면이 무엇으로 열릴지 예측할 수 없다.
            monitorRequested = startPage == FR5Page.Run;

            ResolveRequestDocument();
            ResolveProgress();
            Apply();
        }

        void OnDisable()
        {
            if (progressSubscribed && assemblyProgress != null)
                assemblyProgress.ProgressChanged -= OnProgressChanged;
            progressSubscribed = false;
        }

        void Update()
        {
            if (ResolveProgress() && current == FR5Page.Run)
                Apply();
            // UIDocument 는 활성화된 뒤에야 rootVisualElement 를 만든다. 켜진 문서 중
            // 아직 등록하지 않은 것만 한 번씩 등록한다.
            //
            // 매 프레임 다시 등록하면 안 된다. Clickable 을 새로 갈아끼우면 PointerDown 을
            // 받은 인스턴스와 PointerUp 을 받는 인스턴스가 달라져 클릭이 완결되지 않는다.
            // (전환이 먹지 않던 원인이 이것이었다)
            foreach (PageEntry entry in pages)
                WireDocument(entry?.document);
            WireDocument(requestDocument);
        }

        void ResolveRequestDocument()
        {
            if (requestDocument != null) return;

            FR5RequestBinder binder = GetComponentInChildren<FR5RequestBinder>(true);
            requestDocument = binder != null ? binder.GetComponent<UIDocument>() : null;
        }

        bool ResolveProgress()
        {
            AssemblyProgressManager next = GetComponent<UIMaster>()?.AssemblyProgress;
            if (next == assemblyProgress)
            {
                if (!progressSubscribed && assemblyProgress != null)
                {
                    assemblyProgress.ProgressChanged += OnProgressChanged;
                    progressSubscribed = true;
                }
                return false;
            }

            if (progressSubscribed && assemblyProgress != null)
                assemblyProgress.ProgressChanged -= OnProgressChanged;
            assemblyProgress = next;
            progressSubscribed = false;
            if (assemblyProgress != null)
            {
                assemblyProgress.ProgressChanged += OnProgressChanged;
                progressSubscribed = true;
            }
            return true;
        }

        void OnProgressChanged(AssemblyProgressFrame frame)
        {
            if (current == FR5Page.Run)
                Apply();
        }

        void WireDocument(UIDocument document)
        {
            if (document == null || wiredDocuments.Contains(document)) return;

            VisualElement root = document.rootVisualElement;
            if (root == null) return;

            Wire(root);
            wiredDocuments.Add(document);
        }

        /// <summary>한 문서의 nav 버튼을 한 번만 등록한다.</summary>
void Wire(VisualElement root)
        {
            Button monitor = root.Q<Button>("nav-monitor");
            if (monitor != null)
                monitor.clicked += OpenMonitor;

            foreach ((FR5Page target, string buttonName) in NavButtons)
            {
                Button button = root.Q<Button>(buttonName);
                if (button == null) continue;

                FR5Page captured = target;
                button.clicked += () => Go(captured);
                button.SetEnabled(IsAvailable(target));
            }

            RefreshNavigationVisuals(root);
        }

        public void Go(FR5Page page)
        {
            if (!IsAvailable(page)) return;
            monitorRequested = false;
            current = page;
            Apply();
        }

        /// <summary>진행 상태와 무관하게 실행 모니터 화면을 연다.</summary>
        public void OpenMonitor()
        {
            if (!IsAvailable(FR5Page.Run)) return;
            monitorRequested = true;
            current = FR5Page.Run;
            Apply();
        }

        bool IsAvailable(FR5Page page)
        {
            foreach (PageEntry e in pages)
                if (e != null && e.page == page)
                    return e.available && e.document != null;
            return false;
        }

        /// <summary>활성 페이지 하나만 켠다. 나머지는 꺼서 Update 비용을 없앤다.</summary>
void Apply()
        {
            UIDocument selected = DocumentFor(current);
            foreach (PageEntry entry in pages)
            {
                // 파괴 중인 문서를 만날 수 있다. gameObject 까지 확인한다.
                if (entry?.document == null || entry.document.gameObject == null) continue;
                SetDocumentActive(entry.document, entry.document == selected);
            }
            SetDocumentActive(requestDocument, requestDocument == selected);
            RefreshNavigationVisuals();
        }
        void RefreshNavigationVisuals()
        {
            foreach (PageEntry entry in pages)
                RefreshNavigationVisuals(entry?.document?.rootVisualElement);
            RefreshNavigationVisuals(requestDocument?.rootVisualElement);
        }

        void RefreshNavigationVisuals(VisualElement root)
        {
            if (root == null) return;

            bool monitorActive = monitorRequested && current == FR5Page.Run;
            root.Q<Button>("nav-monitor")?.EnableInClassList("tab--on", monitorActive);
            foreach ((FR5Page target, string buttonName) in NavButtons)
                root.Q<Button>(buttonName)?.EnableInClassList("tab--on",
                    !monitorActive && target == current);
        }



        UIDocument DocumentFor(FR5Page page)
        {
            if (page == FR5Page.Run && !monitorRequested && requestDocument != null &&
                (assemblyProgress?.Latest == null || assemblyProgress.Latest.IsTerminal))
                return requestDocument;

            foreach (PageEntry entry in pages)
                if (entry != null && entry.page == page)
                    return entry.document;
            return null;
        }

        void SetDocumentActive(UIDocument document, bool on)
        {
            if (document == null || document.gameObject == null) return;

            // 꺼지는 문서는 비주얼 트리가 사라지므로 등록 기록도 지운다.
            // 다시 켜질 때 Update 가 새 트리에 한 번 등록한다.
            if (!on) wiredDocuments.Remove(document);

            if (document.gameObject.activeSelf != on)
                document.gameObject.SetActive(on);
            if (document.enabled != on)
                document.enabled = on;
        }
    }
}
