// 역할: 페이지 5개를 UIDocument 단위로 전환한다.
//
// 페이지는 최상위 계층이므로 어느 패널에도 종속되지 않는다(Docs/UI.md 4절).
// 각 페이지는 자기 GameObject 에 UIDocument 하나 + 바인더를 갖고, 라우터는
// 활성 페이지의 UIDocument 만 켠다. 비활성 페이지는 Update 가 돌지 않는다.
//
// 각 페이지 UXML 은 nav-run / nav-inspect / nav-manual / nav-quality / nav-setup
// 이라는 같은 이름의 버튼을 갖고 있으므로, 라우터가 모든 문서에서 한 번에 등록한다.

using System;
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

        FR5Page current;

        /// <summary>현재 열린 페이지다.</summary>
        public FR5Page Current => current;

        void OnEnable()
        {
            wiredDocuments.Clear();
            current = startPage;
            Apply();
        }

        void Update()
        {
            // UIDocument 는 활성화된 뒤에야 rootVisualElement 를 만든다. 켜진 문서 중
            // 아직 등록하지 않은 것만 한 번씩 등록한다.
            //
            // 매 프레임 다시 등록하면 안 된다. Clickable 을 새로 갈아끼우면 PointerDown 을
            // 받은 인스턴스와 PointerUp 을 받는 인스턴스가 달라져 클릭이 완결되지 않는다.
            // (전환이 먹지 않던 원인이 이것이었다)
            foreach (PageEntry entry in pages)
            {
                if (entry?.document == null) continue;
                if (wiredDocuments.Contains(entry.document)) continue;

                VisualElement root = entry.document.rootVisualElement;
                if (root == null) continue;

                Wire(root);
                wiredDocuments.Add(entry.document);
            }
        }

        /// <summary>한 문서의 nav 버튼을 한 번만 등록한다.</summary>
        void Wire(VisualElement root)
        {
            foreach ((FR5Page target, string buttonName) in NavButtons)
            {
                Button button = root.Q<Button>(buttonName);
                if (button == null) continue;

                FR5Page captured = target;
                button.clicked += () => Go(captured);
                button.SetEnabled(IsAvailable(target));
                // 활성 표시는 라우터가 붙인다. 페이지 UXML 에 박아 두면 셸을 공유할 수 없다.
                button.EnableInClassList("tab--on", target == current);
            }
        }

        public void Go(FR5Page page)
        {
            if (!IsAvailable(page)) return;
            current = page;
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
            foreach (PageEntry entry in pages)
            {
                // 파괴 중인 문서를 만날 수 있다. gameObject 까지 확인한다.
                if (entry?.document == null || entry.document.gameObject == null) continue;
                bool on = entry.page == current;

                // 꺼지는 문서는 비주얼 트리가 사라지므로 등록 기록도 지운다.
                // 다시 켜질 때 Update 가 새 트리에 한 번 등록한다.
                if (!on) wiredDocuments.Remove(entry.document);

                if (entry.document.gameObject.activeSelf != on)
                    entry.document.gameObject.SetActive(on);
                if (entry.document.enabled != on)
                    entry.document.enabled = on;
            }
        }
    }
}
