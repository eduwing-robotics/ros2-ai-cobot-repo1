// 역할: PCB 조립 슬롯과 타입별 공급 부품 데이터를 Inspector에 저장한다.

using System;
using UnityEngine;
using UnityEngine.Serialization;

namespace MainUnity.Static
{
    [DisallowMultipleComponent]
    public sealed class ItemManager : MonoBehaviour
    {
        /// <summary>같은 타입을 배치할 조립 슬롯 묶음 데이터다.</summary>
        [Serializable]
        public sealed class AssemblySlot
        {
            [SerializeField, HideInInspector, FormerlySerializedAs("target")]
            Transform legacyTarget;

            [SerializeField, FormerlySerializedAs("targets"),
             Tooltip("이 타입의 부품을 배치할 조립 슬롯 Transform을 순서대로 등록합니다.")]
            Transform[] slots = Array.Empty<Transform>();

            [SerializeField, FormerlySerializedAs("legacyRequiredItemType"),
             Tooltip("이 슬롯 묶음에 필요한 Item Group의 타입 이름입니다.")]
            string requiredItemType;

            /// <summary>이 타입의 부품을 배치할 슬롯 Transform 배열을 반환한다.</summary>
            public Transform[] Slots => slots != null && slots.Length > 0
                ? slots
                : legacyTarget != null ? new[] { legacyTarget } : Array.Empty<Transform>();

            /// <summary>이 슬롯 묶음에 필요한 부품 타입 문자열을 반환한다.</summary>
            public string RequiredItemType => requiredItemType;
        }

        /// <summary>같은 타입의 공급 부품과 그리퍼 설정 데이터다.</summary>
        [Serializable]
        public sealed class ItemGroup
        {
            // AssemblySlot의 Required Item Type과 대응하는 타입 이름이다.
            [SerializeField, Tooltip("Assembly Slot의 Required Item Type과 대응하는 타입 이름입니다.")]
            string itemType;

            // 픽업할 실제 부품 Transform을 사용할 순서대로 등록한다.
            [SerializeField, Tooltip("픽업할 부품 Transform을 사용할 순서대로 등록합니다.")]
            Transform[] items = Array.Empty<Transform>();

            // 이 타입을 잡을 때 사용할 그리퍼 열림 비율이다.
            [SerializeField, Range(0f, 100f), Tooltip("이 타입을 잡을 때 사용할 그리퍼 열림 비율입니다.")]
            float gripperOpeningPercent;

            [SerializeField, FormerlySerializedAs("gripDirection"),
             Tooltip("체크하면 세로로 집고, 해제하면 가로로 집습니다.")]
            bool pickVertically;

            [SerializeField, Tooltip("Transform 위치를 기준으로 적용할 픽업 XZ 오프셋(m)입니다.")]
            Vector2 pickupOffsetXZ;

            /// <summary>그룹의 부품 타입 문자열을 반환한다.</summary>
            public string ItemType => itemType;

            /// <summary>그룹에 등록된 부품 Transform 배열을 반환한다.</summary>
            public Transform[] Items => items;

            /// <summary>그룹의 그리퍼 열림 비율을 반환한다.</summary>
            public float GripperOpeningPercent => gripperOpeningPercent;

            /// <summary>부품을 세로로 집을지 여부를 반환한다.</summary>
            public bool PickVertically => pickVertically;

            /// <summary>그룹의 픽업 XZ 오프셋(m)을 반환한다.</summary>
            public Vector2 PickupOffsetXZ => pickupOffsetXZ;
        }

        // 배열 순서대로 실행할 PCB 조립 위치와 필요 부품 타입 데이터다.
        [SerializeField, Tooltip("배열 순서대로 실행할 PCB 조립 위치와 필요 부품 타입입니다.")]
        AssemblySlot[] assemblySlots = Array.Empty<AssemblySlot>();

        // 타입별 공급 부품 배열과 그리퍼 설정 데이터다.
        [Header("Parts")]
        [SerializeField, Tooltip("타입별 공급 부품 배열과 그리퍼 설정입니다.")]
        ItemGroup[] itemGroups = Array.Empty<ItemGroup>();

        /// <summary>조립 순서대로 등록된 슬롯 배열을 반환한다.</summary>
        public AssemblySlot[] AssemblySlots => assemblySlots;

        /// <summary>타입별로 등록된 공급 부품 그룹 배열을 반환한다.</summary>
        public ItemGroup[] ItemGroups => itemGroups;


        public bool TryGetSlotGroup(string itemType, out AssemblySlot group)
        {
            group = null;
            if (string.IsNullOrWhiteSpace(itemType) || assemblySlots == null)
                return false;

            foreach (AssemblySlot candidate in assemblySlots)
            {
                if (candidate == null || !string.Equals(candidate.RequiredItemType, itemType,
                        StringComparison.Ordinal))
                    continue;
                if (group != null)
                {
                    group = null;
                    return false;
                }
                group = candidate;
            }

            return group != null;
        }

        public bool TryGetItemGroup(string itemId, out ItemGroup group)
        {
            group = null;
            if (string.IsNullOrWhiteSpace(itemId) || itemGroups == null)
                return false;

            foreach (ItemGroup candidate in itemGroups)
            {
                if (candidate == null || !string.Equals(candidate.ItemType, itemId,
                        StringComparison.Ordinal))
                    continue;
                if (group != null)
                {
                    group = null;
                    return false;
                }
                group = candidate;
            }

            return group != null;
        }
    }
}
