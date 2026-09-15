// 역할: 파레토 차트의 누적 기여 곡선과 80% 무릎을 그린다.
//
// 왜 곡선이 필요한가.
//   막대만 있으면 "PM-01 이 제일 많다"까지만 안다. 정작 필요한 답은
//   "어디까지 고치면 되는가"이고, 그건 누적선이 80% 선을 자르는 지점이다.
//   그 지점이 곧 작업 범위라서, 회의에서 결론이 나는 자리는 막대가 아니라 여기다.
//
// 막대는 왜 여기서 안 그리나.
//   막대는 눌러야 한다. Painter2D 로 그린 그림은 히트 테스트 대상이 아니라
//   클릭을 못 받는다. 그래서 막대는 바인더가 VisualElement 로 깔고,
//   이 요소는 그 위에 겹쳐 선만 그린다 (picking-mode 는 Ignore).
//
// 좌표계는 바인더와 공유한다 — 열 간격 pitch 는 양쪽이 같은 식으로 계산한다.
// 어긋나면 점이 막대 머리를 벗어나므로, 식을 고칠 때는 반드시 같이 고친다.

using System;
using UnityEngine;
using UnityEngine.UIElements;

namespace MainUnity.UI
{
    public sealed class ParetoCurve : VisualElement
    {
        // FR5Theme.uss 의 --c-ink / --c-ink-4 / --c-accent 와 같은 값이다.
        // USS 변수는 C# 에서 읽을 수 없어 여기 적는다. 테마를 바꾸면 같이 바꿔야 한다.
        static readonly Color Line = new(0.886f, 0.925f, 0.945f);
        static readonly Color Dim = new(0.392f, 0.439f, 0.478f);
        static readonly Color Accent = new(0.980f, 0.800f, 0.200f);

        float[] cumulative = Array.Empty<float>();
        int columns;

        /// <summary>80% 를 처음 넘는 항목의 번호. 없으면 -1.</summary>
        public int KneeIndex { get; private set; } = -1;

        public ParetoCurve()
        {
            pickingMode = PickingMode.Ignore;
            generateVisualContent += Draw;
        }

        /// <summary>
        /// 누적 비율(0~100)을 순서대로 넣는다. <paramref name="columnCount"/> 는 꼬리 칸까지
        /// 포함한 전체 열 수다 — 막대가 8개여도 "나머지 N 슬롯" 칸이 있으면 9다.
        /// 열 간격이 막대와 같아야 점이 막대 머리에 얹힌다.
        /// </summary>
        public void SetData(float[] cumulativePercent, int columnCount)
        {
            cumulative = cumulativePercent ?? Array.Empty<float>();
            columns = Mathf.Max(columnCount, cumulative.Length);

            KneeIndex = -1;
            for (int i = 0; i < cumulative.Length; i++)
            {
                if (cumulative[i] < 80f) continue;
                KneeIndex = i;
                break;
            }
            MarkDirtyRepaint();
        }

        public void ClearData()
        {
            cumulative = Array.Empty<float>();
            columns = 0;
            KneeIndex = -1;
            MarkDirtyRepaint();
        }

        /// <summary>열 i 의 가운데 x. 바인더의 막대 배치와 같은 식이어야 한다.</summary>
        public static float ColumnCenter(float width, int columnCount, int index)
        {
            if (columnCount <= 0) return 0f;
            float pitch = width / columnCount;
            return pitch * (index + 0.5f);
        }

        void Draw(MeshGenerationContext ctx)
        {
            Rect r = contentRect;
            if (cumulative.Length == 0 || r.width <= 1f || r.height <= 1f) return;

            var p = ctx.painter2D;

            // 80% 안내선을 먼저. 곡선 아래로 깔려야 교차점이 가려지지 않는다.
            float guideY = r.yMax - r.height * 0.80f;
            p.BeginPath();
            p.MoveTo(new Vector2(r.xMin, guideY));
            p.LineTo(new Vector2(r.xMax, guideY));
            p.strokeColor = Accent * new Color(1f, 1f, 1f, 0.45f);
            p.lineWidth = 1f;
            p.Stroke();

            // 누적선. 세로는 항상 0~100% 로 고정한다 — 표본에 맞춰 늘이면
            // 80% 선의 높이가 조회할 때마다 달라져 무릎을 눈으로 못 비빈다.
            p.BeginPath();
            for (int i = 0; i < cumulative.Length; i++)
            {
                var point = PointAt(r, i);
                if (i == 0) p.MoveTo(point);
                else p.LineTo(point);
            }
            p.strokeColor = Line * new Color(1f, 1f, 1f, 0.8f);
            p.lineWidth = 2f;
            p.lineJoin = LineJoin.Round;
            p.lineCap = LineCap.Round;
            p.Stroke();

            for (int i = 0; i < cumulative.Length; i++)
            {
                bool knee = i == KneeIndex;
                p.BeginPath();
                p.Arc(PointAt(r, i), knee ? 7f : 4f, 0f, 360f);
                p.fillColor = knee ? Accent : Line;
                p.Fill();
            }

            // 무릎에 테두리를 하나 더 둘러 "여기까지"를 못 놓치게 한다.
            if (KneeIndex >= 0)
            {
                p.BeginPath();
                p.Arc(PointAt(r, KneeIndex), 12f, 0f, 360f);
                p.strokeColor = Accent * new Color(1f, 1f, 1f, 0.45f);
                p.lineWidth = 1f;
                p.Stroke();
            }

            // 표본이 하나뿐이면 선이 점 하나로 남는다. 그때는 가로 눈금만 남겨 둔다.
            if (cumulative.Length != 1) return;
            p.BeginPath();
            p.MoveTo(new Vector2(r.xMin, PointAt(r, 0).y));
            p.LineTo(new Vector2(r.xMax, PointAt(r, 0).y));
            p.strokeColor = Dim;
            p.lineWidth = 1f;
            p.Stroke();
        }

        Vector2 PointAt(Rect r, int i) => new(
            r.xMin + ColumnCenter(r.width, columns, i),
            r.yMax - r.height * Mathf.Clamp01(cumulative[i] / 100f));
    }
}
