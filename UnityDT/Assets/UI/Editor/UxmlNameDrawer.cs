// 역할: [UxmlName] 이 붙은 string 필드를 UXML 요소 이름 드롭다운으로 그린다.
//
// 드롭다운은 이름의 첫 구간(link-, joint-, cam- …)으로 묶여서 나옵니다.
// UXML 에 없는 이름이면 라벨이 빨갛게 바뀌고 뒤에 (없음) 이 붙습니다.
// 목록에서 고르는 대신 직접 치고 싶으면 우측 연필 토글로 텍스트 입력으로 바꿉니다.

using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using UnityEngine.UIElements;

namespace MainUnity.UI.EditorTools
{
    [CustomPropertyDrawer(typeof(UxmlNameAttribute))]
    public sealed class UxmlNameDrawer : PropertyDrawer
    {
        const string EmptyLabel = "(비움 — 바인딩 안 함)";
        const float ToggleWidth = 22f;

        static readonly HashSet<string> ManualEntry = new();
        static GUIContent manualIcon;

        /// <summary>직접 입력 토글 아이콘. 에디터 스킨에 아이콘이 없으면 글자로 대체한다.</summary>
        static GUIContent ManualIcon
        {
            get
            {
                if (manualIcon == null)
                {
                    GUIContent icon = EditorGUIUtility.IconContent("editicon.sml");
                    manualIcon = icon != null && icon.image != null
                        ? new GUIContent(icon.image, "이름을 직접 입력")
                        : new GUIContent("✎", "이름을 직접 입력");
                }
                return manualIcon;
            }
        }

        public override void OnGUI(Rect position, SerializedProperty property, GUIContent label)
        {
            if (property.propertyType != SerializedPropertyType.String)
            {
                EditorGUI.PropertyField(position, property, label);
                return;
            }

            var attribute = (UxmlNameAttribute)base.attribute;
            VisualTreeAsset source = UxmlNameCatalog.FindSourceAsset(property.serializedObject.targetObject);
            IReadOnlyList<UxmlElementInfo> elements = UxmlNameCatalog.GetElements(source);

            var fieldRect = new Rect(position.x, position.y, position.width - ToggleWidth - 2f, position.height);
            var toggleRect = new Rect(position.xMax - ToggleWidth, position.y, ToggleWidth, position.height);

            string key = property.serializedObject.targetObject.GetInstanceID() + property.propertyPath;
            bool manual = ManualEntry.Contains(key) || elements.Count == 0;

            if (manual)
                EditorGUI.PropertyField(fieldRect, property, label);
            else
                DrawDropdown(fieldRect, property, label, elements, attribute.ElementTag);

            bool wantManual = GUI.Toggle(toggleRect, manual, ManualIcon, EditorStyles.miniButton);
            if (wantManual != manual && elements.Count > 0)
            {
                if (wantManual)
                    ManualEntry.Add(key);
                else
                    ManualEntry.Remove(key);
            }
        }

        static void DrawDropdown(Rect rect, SerializedProperty property, GUIContent label,
            IReadOnlyList<UxmlElementInfo> elements, string elementTag)
        {
            string current = property.stringValue;
            bool empty = string.IsNullOrEmpty(current);
            bool exists = empty || Contains(elements, current);

            Color previous = GUI.color;
            if (!exists)
                GUI.color = new Color(1f, 0.55f, 0.55f);

            Rect content = EditorGUI.PrefixLabel(rect, label);
            var button = new GUIContent(empty ? EmptyLabel : exists ? current : current + "  (없음)");

            if (EditorGUI.DropdownButton(content, button, FocusType.Keyboard, EditorStyles.popup))
                ShowMenu(property, elements, elementTag);

            GUI.color = previous;
        }

        static void ShowMenu(SerializedProperty property, IReadOnlyList<UxmlElementInfo> elements, string elementTag)
        {
            // 메뉴가 뜨는 동안 property 가 무효화될 수 있으므로 복사본으로 잡아둔다.
            SerializedProperty target = property.Copy();
            var menu = new GenericMenu();

            menu.AddItem(new GUIContent(EmptyLabel), string.IsNullOrEmpty(target.stringValue),
                () => Apply(target, string.Empty));
            menu.AddSeparator(string.Empty);

            bool filtered = !string.IsNullOrEmpty(elementTag);
            int shown = 0;
            foreach (UxmlElementInfo element in elements)
            {
                if (filtered && element.Tag != elementTag)
                    continue;

                shown++;
                string entry = $"{Group(element.Name)}/{element.Name}  ({element.Tag})";
                string captured = element.Name;
                menu.AddItem(new GUIContent(entry), element.Name == target.stringValue,
                    () => Apply(target, captured));
            }

            // 태그 필터로 다 걸러졌으면(커스텀 컨트롤 등) 전체 목록을 따로 열어준다.
            if (filtered && shown == 0)
                foreach (UxmlElementInfo element in elements)
                {
                    string captured = element.Name;
                    menu.AddItem(new GUIContent($"전체/{Group(element.Name)}/{element.Name}  ({element.Tag})"),
                        element.Name == target.stringValue, () => Apply(target, captured));
                }

            menu.ShowAsContext();
        }

        static void Apply(SerializedProperty property, string value)
        {
            property.stringValue = value;
            property.serializedObject.ApplyModifiedProperties();
        }

        /// <summary>이름의 첫 구간을 메뉴 그룹으로 쓴다. link-joint-dot → link</summary>
        static string Group(string name)
        {
            int dash = name.IndexOf('-');
            return dash > 0 ? name[..dash] : "기타";
        }

        static bool Contains(IReadOnlyList<UxmlElementInfo> elements, string name)
        {
            foreach (UxmlElementInfo element in elements)
                if (element.Name == name)
                    return true;
            return false;
        }
    }
}
