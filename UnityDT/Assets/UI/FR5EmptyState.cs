// 역할: 데이터 출처가 아직 없는 자리에 "무엇이 없는지"를 적는다.
//
// 규칙 셋.
//   1. 값을 지어내지 않는다. 샘플 상수는 화면을 실측으로 오인하게 만든다.
//   2. 빈 칸도 남기지 않는다. 빈 칸은 "미구현"인지 "데이터가 0"인지 구분되지 않는다.
//   3. 어떤 조회가 붙으면 채워지는지 이름을 적는다 (`jobs 조회`, `GET /alerts` …).
//      그래야 화면이 곧 남은 작업 목록이 된다.
//
// 색은 `--c-warn` 이다. 붉은색(`--c-bad`)은 불량·비상정지에 남겨 둔다 — 연결이 없는 것은
// 이상이지만 위험은 아니고, 화면 전체가 붉어지면 진짜 이상이 묻힌다 (Docs/UI.md 6절).

using UnityEngine.UIElements;

namespace MainUnity.UI
{
    /// <summary>조회 경로가 없는 자리를 표시하는 공용 빈 상태다.</summary>
    static class FR5EmptyState
    {
        /// <summary>모든 미연결 자리가 같은 낱말을 쓴다. 화면마다 다른 말을 하면 못 알아본다.</summary>
        public const string Title = "연결 없음";

        /// <summary>목록·격자 자리를 통째로 비우고 사유를 적는다.</summary>
        public static void Fill(VisualElement host, string source, float height = 0f)
        {
            if (host == null) return;
            host.Clear();
            host.Add(Block(source, height));
        }

        /// <summary>빈 상태 블록 하나를 만든다.</summary>
        public static VisualElement Block(string source, float height = 0f)
        {
            var box = new VisualElement();
            box.AddToClassList("empty");
            if (height > 0f) box.style.height = height;

            var title = new Label(Title);
            title.AddToClassList("empty__title");
            title.AddToClassList("empty__title--miss");
            box.Add(title);

            if (!string.IsNullOrEmpty(source))
            {
                var desc = new Label(source);
                desc.AddToClassList("empty__desc");
                box.Add(desc);
            }
            return box;
        }

        /// <summary>값 한 칸짜리 자리다. 이름·판정처럼 글자가 들어갈 곳에 쓴다.</summary>
        public static void Missing(Label label)
        {
            if (label == null) return;
            label.text = Title;
            label.EnableInClassList("warn", true);
        }

        /// <summary>값 밑에 붙는 사유 줄이다. 어떤 조회가 필요한지만 적는다.</summary>
        public static void Detail(Label label, string source)
        {
            if (label == null) return;
            label.text = source;
        }

        /// <summary>수치 자리다. 숫자를 지어내느니 줄표를 둔다.</summary>
        public static void Dash(Label label)
        {
            if (label == null) return;
            label.text = "—";
        }
    }
}
