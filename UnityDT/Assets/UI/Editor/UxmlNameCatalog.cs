// 역할: .uxml 파일에서 name 속성을 긁어와 (이름, 태그) 목록으로 들고 있는 에디터 전용 캐시.
//
// UxmlNameDrawer(드롭다운)와 UxmlBindingEditor(검사 버튼)가 같이 씁니다.
// VisualTreeAsset 은 요소 이름을 공개 API 로 열어주지 않으므로 텍스트를 직접 읽습니다.

using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text.RegularExpressions;
using MainUnity.UI;
using UnityEditor;
using UnityEngine;
using UnityEngine.UIElements;

namespace MainUnity.UI.EditorTools
{
    /// <summary>UXML 한 개에서 찾은 요소 하나.</summary>
    public readonly struct UxmlElementInfo
    {
        public readonly string Name;
        public readonly string Tag;

        public UxmlElementInfo(string name, string tag)
        {
            Name = name;
            Tag = tag;
        }
    }

    /// <summary>[UxmlName] 이 붙은 필드 하나의 현재 값.</summary>
    public readonly struct UxmlNameBinding
    {
        public readonly string FieldPath;
        public readonly string Value;
        public readonly string ElementTag;

        public UxmlNameBinding(string fieldPath, string value, string elementTag)
        {
            FieldPath = fieldPath;
            Value = value;
            ElementTag = elementTag;
        }
    }

    public static class UxmlNameCatalog
    {
        // <ui:Button ... name="stop-all-button" ...> 형태에서 태그와 이름을 뽑는다.
        static readonly Regex ElementPattern = new(
            @"<(?:[\w.]+:)?(?<tag>[\w.]+)\b(?<attrs>[^>]*)",
            RegexOptions.Compiled);

        static readonly Regex NamePattern = new(
            @"\bname\s*=\s*""(?<name>[^""]+)""",
            RegexOptions.Compiled);

        static readonly Dictionary<string, (long stamp, List<UxmlElementInfo> items)> Cache = new();

        /// <summary>UXML 의 요소 목록. 파일이 바뀌면 자동으로 다시 읽는다.</summary>
        public static IReadOnlyList<UxmlElementInfo> GetElements(VisualTreeAsset asset)
        {
            if (asset == null)
                return Array.Empty<UxmlElementInfo>();

            string path = AssetDatabase.GetAssetPath(asset);
            if (string.IsNullOrEmpty(path) || !File.Exists(path))
                return Array.Empty<UxmlElementInfo>();

            long stamp = File.GetLastWriteTimeUtc(path).Ticks;
            if (Cache.TryGetValue(path, out var cached) && cached.stamp == stamp)
                return cached.items;

            var items = Parse(File.ReadAllText(path));
            Cache[path] = (stamp, items);
            return items;
        }

        static List<UxmlElementInfo> Parse(string text)
        {
            var items = new List<UxmlElementInfo>();
            var seen = new HashSet<string>();

            foreach (Match element in ElementPattern.Matches(text))
            {
                Match name = NamePattern.Match(element.Groups["attrs"].Value);
                if (!name.Success)
                    continue;

                string value = name.Groups["name"].Value;
                if (seen.Add(value))
                    items.Add(new UxmlElementInfo(value, element.Groups["tag"].Value));
            }

            items.Sort((a, b) => string.CompareOrdinal(a.Name, b.Name));
            return items;
        }

        /// <summary>대상 컴포넌트가 참조하는 UXML. 같은 GameObject 의 UIDocument 를 먼저 본다.</summary>
        public static VisualTreeAsset FindSourceAsset(UnityEngine.Object target)
        {
            if (target is not Component component)
                return null;

            var document = component.GetComponent<UIDocument>();
            if (document == null)
                document = FindReferencedDocument(component);

            return document != null ? document.visualTreeAsset : null;
        }

        /// <summary>UIDocument 가 같은 오브젝트에 없을 때 직렬화 필드에서 찾는다(CamVisionReceiver 처럼).</summary>
        static UIDocument FindReferencedDocument(Component component)
        {
            foreach (FieldInfo field in component.GetType().GetFields(
                         BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
            {
                if (typeof(UIDocument).IsAssignableFrom(field.FieldType) &&
                    field.GetValue(component) is UIDocument document && document != null)
                    return document;
            }
            return null;
        }

        /// <summary>대상에 붙은 [UxmlName] 필드를 중첩 클래스·배열까지 훑어서 모은다.</summary>
        public static List<UxmlNameBinding> CollectBindings(UnityEngine.Object target)
        {
            var result = new List<UxmlNameBinding>();
            Collect(target, string.Empty, result, 0);
            return result;
        }

        static void Collect(object owner, string prefix, List<UxmlNameBinding> result, int depth)
        {
            if (owner == null || depth > 4)
                return;

            foreach (FieldInfo field in owner.GetType().GetFields(
                         BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
            {
                object value = field.GetValue(owner);
                string path = prefix + field.Name;

                if (field.FieldType == typeof(string))
                {
                    var attribute = field.GetCustomAttribute<UxmlNameAttribute>();
                    if (attribute != null)
                        result.Add(new UxmlNameBinding(path, (string)value, attribute.ElementTag));
                    continue;
                }

                if (value is Array array && IsSerializableGroup(field.FieldType.GetElementType()))
                {
                    for (int i = 0; i < array.Length; i++)
                        Collect(array.GetValue(i), $"{path}[{i}].", result, depth + 1);
                    continue;
                }

                if (IsSerializableGroup(field.FieldType))
                    Collect(value, path + ".", result, depth + 1);
            }
        }

        /// <summary>중첩해서 들어갈 값 타입인지. UnityEngine.Object 참조는 따라가지 않는다.</summary>
        static bool IsSerializableGroup(Type type) =>
            type != null &&
            !type.IsPrimitive &&
            type != typeof(string) &&
            !typeof(UnityEngine.Object).IsAssignableFrom(type) &&
            type.IsDefined(typeof(SerializableAttribute), false);
    }
}
