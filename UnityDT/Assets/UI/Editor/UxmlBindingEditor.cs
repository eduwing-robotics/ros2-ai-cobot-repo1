// 역할: FR5Hud 프리팹에 붙은 컴포넌트들의 Inspector 하단에 "UXML 바인딩 검사" 버튼을 붙인다.
//
// 버튼을 누르면 [UxmlName] 필드 값이 실제 .uxml 에 있는지 전부 대조해서
// 없는 이름과 비워둔 이름을 콘솔에 정리해 보여줍니다.
// 재생 없이 확인할 수 있으므로 UXML 이름을 바꾼 직후에 눌러보면 됩니다.

using System.Collections.Generic;
using System.Text;
using MainUnity.Runtime.Camera;
using UnityEditor;
using UnityEngine;
using UnityEngine.UIElements;

namespace MainUnity.UI.EditorTools
{
    public abstract class UxmlBindingEditor : Editor
    {
        public override void OnInspectorGUI()
        {
            DrawDefaultInspector();

            VisualTreeAsset source = UxmlNameCatalog.FindSourceAsset(target);
            EditorGUILayout.Space();

            if (source == null)
            {
                EditorGUILayout.HelpBox(
                    "UIDocument 또는 Source Asset(.uxml) 이 없어 이름 드롭다운을 채울 수 없습니다.",
                    MessageType.Warning);
                return;
            }

            EditorGUILayout.LabelField("UXML", source.name, EditorStyles.miniLabel);
            if (GUILayout.Button("UXML 바인딩 검사"))
                Validate(target, source);
        }

        static void Validate(Object target, VisualTreeAsset source)
        {
            IReadOnlyList<UxmlElementInfo> elements = UxmlNameCatalog.GetElements(source);
            var names = new HashSet<string>();
            var tags = new Dictionary<string, string>();
            foreach (UxmlElementInfo element in elements)
            {
                names.Add(element.Name);
                tags[element.Name] = element.Tag;
            }

            var missing = new List<string>();
            var mismatched = new List<string>();
            int emptyCount = 0;
            int okCount = 0;

            foreach (UxmlNameBinding binding in UxmlNameCatalog.CollectBindings(target))
            {
                if (string.IsNullOrEmpty(binding.Value))
                {
                    emptyCount++;
                    continue;
                }

                if (!names.Contains(binding.Value))
                {
                    missing.Add($"  {binding.FieldPath} → \"{binding.Value}\"");
                    continue;
                }

                if (!string.IsNullOrEmpty(binding.ElementTag) && tags[binding.Value] != binding.ElementTag)
                    mismatched.Add($"  {binding.FieldPath} → \"{binding.Value}\" 는 " +
                                   $"{tags[binding.Value]} 인데 {binding.ElementTag} 로 조회합니다");

                okCount++;
            }

            var report = new StringBuilder();
            report.Append($"[{target.GetType().Name}] UXML 바인딩 검사 — ");
            report.Append($"정상 {okCount} · 없음 {missing.Count} · 타입 불일치 {mismatched.Count} · 비움 {emptyCount}");

            if (missing.Count > 0)
                report.Append("\n\nUXML 에 없는 이름:\n").Append(string.Join("\n", missing));
            if (mismatched.Count > 0)
                report.Append("\n\n요소 타입이 다릅니다:\n").Append(string.Join("\n", mismatched));

            if (missing.Count > 0)
                Debug.LogError(report.ToString(), target);
            else if (mismatched.Count > 0)
                Debug.LogWarning(report.ToString(), target);
            else
                Debug.Log(report.ToString(), target);
        }
    }

    [CustomEditor(typeof(ManualJointPanel))]
    public sealed class ManualJointPanelEditor : UxmlBindingEditor { }

    [CustomEditor(typeof(FR5ViewControls))]
    public sealed class FR5ViewControlsEditor : UxmlBindingEditor { }

    [CustomEditor(typeof(CamVisionReceiver))]
    public sealed class CamVisionReceiverEditor : UxmlBindingEditor { }
}
