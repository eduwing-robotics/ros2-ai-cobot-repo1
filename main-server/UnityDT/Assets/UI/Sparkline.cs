// 역할: 값 하나의 최근 이력을 한 줄로 그린다.
//
// 왜 필요한가 (Docs/ui-design.md 3.1절).
//   값 하나만 보여 주면 운전자는 "지금 얼마인가"만 알고 "어느 쪽으로 가고 있는가"는
//   모른다. 그래서 이상을 알람이 뜬 뒤에야 알아챈다. 워치독이 12ms 인 것은 정상이지만,
//   4ms 에서 12ms 로 올라오는 중인 것은 곧 끊어진다는 뜻이다. 두 경우의 숫자는 같다.
//
// 색 규칙은 화면 전체와 같다 — 정상에는 색을 주지 않는다.
//   선은 항상 무채색이고, 한계선을 넘은 구간만 색을 얻는다.
//
// UXML 에 등록하지 않고 바인더가 C# 으로 만들어 붙인다. 관절 행 · TCP 행과 같은 방식이다.

using UnityEngine;
using UnityEngine.UIElements;

namespace MainUnity.UI
{
    public sealed class Sparkline : VisualElement
    {
        // FR5Theme.uss 의 --c-ok / --c-bad / --c-line 과 같은 값이다.
        // USS 변수는 C# 에서 읽을 수 없어 여기 적는다. 테마를 바꾸면 같이 바꿔야 한다.
        static readonly Color Normal = new(0.561f, 0.651f, 0.706f);
        static readonly Color Alert = new(0.941f, 0.278f, 0.353f);
        static readonly Color Guide = new(1f, 1f, 1f, 0.09f);

        readonly float[] samples;
        int count;
        int head;

        float rangeLow, rangeHigh;
        bool fixedRange;

        /// <summary>이 값을 넘은 최신 표본은 선 전체를 이상 색으로 바꾼다. NaN 이면 한계가 없다.</summary>
        public float Limit { get; set; } = float.NaN;

        public Sparkline(int capacity = 120)
        {
            samples = new float[Mathf.Max(8, capacity)];
            AddToClassList("spark");
            generateVisualContent += Draw;
        }

        /// <summary>세로 범위를 고정한다. 고정하지 않으면 표본의 최소·최대에 맞춘다.</summary>
        public void SetRange(float low, float high)
        {
            rangeLow = low;
            rangeHigh = high;
            fixedRange = high > low;
        }

        /// <summary>표본을 하나 넣는다. 갱신이 필요할 때만 다시 그린다.</summary>
        public void Push(float value)
        {
            if (float.IsNaN(value) || float.IsInfinity(value)) return;
            samples[head] = value;
            head = (head + 1) % samples.Length;
            if (count < samples.Length) count++;
            MarkDirtyRepaint();
        }

        /// <summary>
        /// 연결이 끊겼을 때다. 이력을 지운다 — 끊긴 구간을 평평한 선으로 그리면 거짓이다.
        /// 이름이 Clear 가 아닌 이유는 VisualElement.Clear() 가 자식을 지우는 메서드라
        /// 가려 놓으면 참조 타입에 따라 다른 일이 벌어지기 때문이다.
        /// </summary>
        public void ClearHistory()
        {
            count = 0;
            head = 0;
            MarkDirtyRepaint();
        }

        float SampleAt(int i)
        {
            // 가장 오래된 것이 0 번이 되도록 읽는다.
            int start = count < samples.Length ? 0 : head;
            return samples[(start + i) % samples.Length];
        }

        void Draw(MeshGenerationContext ctx)
        {
            Rect r = contentRect;
            if (count < 2 || r.width <= 1f || r.height <= 1f) return;

            float low = rangeLow, high = rangeHigh;
            if (!fixedRange)
            {
                low = float.MaxValue;
                high = float.MinValue;
                for (int i = 0; i < count; i++)
                {
                    float s = SampleAt(i);
                    if (s < low) low = s;
                    if (s > high) high = s;
                }
            }

            // 값이 전혀 변하지 않으면 범위가 0 이 되어 0 으로 나눈다. 그때는 가운데 직선이다.
            float span = high - low;
            if (span <= Mathf.Epsilon) { DrawFlat(ctx, r); return; }

            var p = ctx.painter2D;

            // 한계선 먼저. 선 아래로 깔려야 값이 가려지지 않는다.
            if (!float.IsNaN(Limit) && Limit > low && Limit < high)
            {
                float ly = r.yMax - (Limit - low) / span * r.height;
                p.BeginPath();
                p.MoveTo(new Vector2(r.xMin, ly));
                p.LineTo(new Vector2(r.xMax, ly));
                p.strokeColor = Guide;
                p.lineWidth = 1f;
                p.Stroke();
            }

            float latest = SampleAt(count - 1);
            bool over = !float.IsNaN(Limit) && latest > Limit;

            p.BeginPath();
            for (int i = 0; i < count; i++)
            {
                float x = r.xMin + r.width * i / (count - 1);
                float y = r.yMax - (SampleAt(i) - low) / span * r.height;
                if (i == 0) p.MoveTo(new Vector2(x, y));
                else p.LineTo(new Vector2(x, y));
            }
            p.strokeColor = over ? Alert : Normal;
            p.lineWidth = 1.5f;
            p.lineJoin = LineJoin.Round;
            p.lineCap = LineCap.Butt;
            p.Stroke();
        }

        void DrawFlat(MeshGenerationContext ctx, Rect r)
        {
            var p = ctx.painter2D;
            float y = r.center.y;
            p.BeginPath();
            p.MoveTo(new Vector2(r.xMin, y));
            p.LineTo(new Vector2(r.xMax, y));
            p.strokeColor = Normal;
            p.lineWidth = 1.5f;
            p.Stroke();
        }
    }
}
