// 역할: UXML 요소 이름(name 속성)을 담는 string 필드를 Inspector 드롭다운으로 노출한다.
//
// 코드에 이름을 하드코딩하는 대신 이 특성을 붙이면
// 같은 GameObject 의 UIDocument 가 물고 있는 .uxml 을 읽어
// 실제 존재하는 이름 목록에서 고를 수 있게 됩니다.
// 이름이 UXML 에 없으면 Inspector 에서 빨갛게 표시됩니다.
//
//   [UxmlName]          → 모든 요소 (VisualElement 로 조회하는 필드)
//   [UxmlName("Button")] → ui:Button 만 목록에 표시
//
// 빈 문자열로 두면 "이 요소는 쓰지 않는다" 는 뜻이고 조회를 건너뜁니다.

using System;
using UnityEngine;

namespace MainUnity.UI
{
    [AttributeUsage(AttributeTargets.Field)]
    public sealed class UxmlNameAttribute : PropertyAttribute
    {
        /// <summary>목록에 남길 UXML 태그명. ui: 접두사는 뺀 이름이며 null 이면 전부 표시한다.</summary>
        public string ElementTag { get; }

        public UxmlNameAttribute(string elementTag = null) => ElementTag = elementTag;
    }
}
