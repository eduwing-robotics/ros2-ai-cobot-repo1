// 역할: 조립체 프리팹·슬롯·공급 위치와 현재 Job의 씬 객체 수명을 소유한다.

using System;
using System.Collections.Generic;
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
             Tooltip("이 타입의 조립 슬롯 Transform을 등록합니다. 이름은 YAML slot_code와 일치해야 합니다.")]
            Transform[] slots = Array.Empty<Transform>();

            [SerializeField, FormerlySerializedAs("legacyRequiredItemType"),
             Tooltip("이 슬롯 묶음에 필요한 Item Group의 타입 이름입니다.")]
            string requiredItemType;

            internal AssemblySlot(string type, Transform[] targets)
            {
                requiredItemType = type;
                slots = targets;
            }

            public AssemblySlot() { }

            /// <summary>이 타입의 부품을 배치할 슬롯 Transform 배열을 반환한다.</summary>
            public Transform[] Slots => slots != null && slots.Length > 0
                ? slots
                : legacyTarget != null ? new[] { legacyTarget } : Array.Empty<Transform>();

            /// <summary>이 슬롯 묶음에 필요한 부품 타입 문자열을 반환한다.</summary>
            public string RequiredItemType => requiredItemType;
        }

        /// <summary>같은 타입의 공급 부품과 픽업 설정 데이터다.</summary>
        [Serializable]
        public sealed class ItemGroup
        {
            // AssemblySlot의 Required Item Type과 대응하는 타입 이름이다.
            [SerializeField, Tooltip("Assembly Slot의 Required Item Type과 대응하는 타입 이름입니다.")]
            string itemType;

            // 고정된 공급 위치다. 완료품으로 이동한 부품을 이 위치로 되돌리지 않는다.
            [SerializeField, Tooltip("고정된 공급 위치 Transform을 사용할 순서대로 등록합니다.")]
            Transform[] items = Array.Empty<Transform>();

            [SerializeField, FormerlySerializedAs("gripDirection"),
             Tooltip("체크하면 세로로 집고, 해제하면 가로로 집습니다.")]
            bool pickVertically;

            [SerializeField, Tooltip("Transform 위치를 기준으로 적용할 픽업 XZ 오프셋(m)입니다.")]
            Vector2 pickupOffsetXZ;

            [SerializeField] GameObject prefab;
            [NonSerialized] internal Transform[] RuntimeItems;
            internal Transform[] SupplyPoints => items;
            internal GameObject Prefab => prefab;

            /// <summary>그룹의 부품 타입 문자열을 반환한다.</summary>
            public string ItemType => itemType;

            /// <summary>그룹에 등록된 부품 Transform 배열을 반환한다.</summary>
            public Transform[] Items => RuntimeItems ?? items;

            /// <summary>부품을 세로로 집을지 여부를 반환한다.</summary>
            public bool PickVertically => pickVertically;

            /// <summary>그룹의 픽업 XZ 오프셋(m)을 반환한다.</summary>
            public Vector2 PickupOffsetXZ => pickupOffsetXZ;
        }

        [Header("Assembly Instances")]
        [SerializeField] GameObject motherboardPrefab;
        [SerializeField] Transform spawnPoint;
        [SerializeField] Transform spawnRoot;
        [SerializeField] Transform completedRoot;

        readonly Dictionary<long, Transform> completedBoards = new();
        [NonSerialized] AssemblySlot[] currentSlots;
        Transform observedBoard;
        bool observationAwaitingUnit;

        internal Transform ObservationBoard => CurrentBoard != null ? CurrentBoard : observedBoard;
        internal bool ObservationAwaitingUnit => observationAwaitingUnit;

        internal Transform EnsureObservationBoard()
        {
            if (!Application.isPlaying)
                throw new InvalidOperationException("Board observations require Play Mode.");
            if (ObservationBoard != null) return ObservationBoard;
            if (observationAwaitingUnit) return null;
            ValidateConfiguration();
            observedBoard = Instantiate(motherboardPrefab, spawnPoint.position,
                spawnPoint.rotation, spawnRoot).transform;
            observedBoard.name = "motherBoard_observed";
            return observedBoard;
        }

        internal void ReleaseObservationBoard()
        {
            Remove(observedBoard);
            observedBoard = null;
        }

        public string JobId { get; private set; }
        public long UnitId { get; private set; }
        public Transform CurrentBoard { get; private set; }
        public Transform CurrentPicker => CurrentBoard == null ? null : CurrentBoard.Find("Picker");
        public int CompletedCount => completedBoards.Count;

        // 실행 순서는 YAML이 소유한다. Inspector 슬롯은 프리팹 내부 Transform을 참조한다.
        [SerializeField, Tooltip("PCB 조립 슬롯과 필요 부품 타입입니다. 실행 순서는 YAML을 따릅니다.")]
        AssemblySlot[] assemblySlots = Array.Empty<AssemblySlot>();

        // 타입별 공급 부품 배열과 픽업 설정 데이터다.
        [Header("Parts")]
        [SerializeField, Tooltip("타입별 공급 부품 배열과 픽업 설정입니다.")]
        ItemGroup[] itemGroups = Array.Empty<ItemGroup>();

        internal AssemblySlot[] PrefabSlots => assemblySlots;

        /// <summary>실행 중에는 현재 기판의 슬롯을, 그 외에는 프리팹 슬롯을 반환한다.</summary>
        public AssemblySlot[] AssemblySlots => currentSlots ?? assemblySlots;

        /// <summary>타입별로 등록된 공급 부품 그룹 배열을 반환한다.</summary>
        public ItemGroup[] ItemGroups => itemGroups;


        /// <summary>생성에 필요한 Inspector 참조를 검증한다. 씬 객체를 변경하지 않는다.</summary>
        public void ValidateConfiguration()
        {
            if (motherboardPrefab == null || spawnPoint == null || spawnRoot == null || completedRoot == null)
                throw new InvalidOperationException("Assign motherboard prefab, spawn point, spawn root and completed root.");
            if (motherboardPrefab.transform.Find("Picker") == null)
                throw new InvalidOperationException("The motherboard prefab requires a Picker child.");
            if (assemblySlots == null || assemblySlots.Length == 0)
                throw new InvalidOperationException("Assign motherboard prefab slots.");
            if (spawnRoot.lossyScale != Vector3.one || completedRoot.lossyScale != Vector3.one)
                throw new InvalidOperationException("Assembly roots must use unit world scale.");
            var names = new HashSet<string>(StringComparer.Ordinal);
            foreach (AssemblySlot group in assemblySlots)
            {
                if (group == null || string.IsNullOrWhiteSpace(group.RequiredItemType) || group.Slots.Length == 0)
                    throw new InvalidOperationException("Every slot group requires a type and slots.");
                foreach (Transform slot in group.Slots)
                    if (slot == null || slot.parent != motherboardPrefab.transform || !names.Add(slot.name))
                        throw new InvalidOperationException("Slots must be unique direct children of the motherboard prefab.");
            }
            Vector3 position = spawnPoint.position;
            Vector3 scale = motherboardPrefab.transform.localScale;
            if (!float.IsFinite(position.x) || !float.IsFinite(position.y) || !float.IsFinite(position.z) ||
                !float.IsFinite(scale.x) || !float.IsFinite(scale.y) || !float.IsFinite(scale.z) ||
                scale.x <= 0f || scale.y <= 0f || scale.z <= 0f)
                throw new InvalidOperationException("Motherboard pose and scale must be finite with positive scale.");
        }

        /// <summary>관측 기판을 Unit에 연결하거나 한 번 생성한다. 다른 Job의 완료품은 이 경계에서 정리한다.</summary>
        public Transform BeginUnit(string jobId, long unitId)
        {
            if (!Application.isPlaying || !Guid.TryParse(jobId, out _) || unitId <= 0)
                throw new InvalidOperationException("Unit creation requires Play Mode, a Job UUID and a positive Unit ID.");
            ValidateConfiguration();
            if (JobId == jobId && UnitId == unitId && CurrentBoard != null)
                return CurrentBoard;
            if (IsUnitCompleted(jobId, unitId))
                throw new InvalidOperationException("A completed Unit cannot be started again.");
            if (CurrentBoard != null)
                throw new InvalidOperationException("Finish or discard the current Unit before starting another.");

            // 검증·생성 실패 시 이전 Job의 완료품을 잃지 않도록 생성 후 정리한다.
            Transform board = observedBoard != null ? observedBoard : Instantiate(motherboardPrefab, spawnPoint.position,
                spawnPoint.rotation, spawnRoot).transform;
            board.name = $"motherBoard_{unitId}";
            var slots = new AssemblySlot[assemblySlots.Length];
            for (int i = 0; i < slots.Length; i++)
            {
                AssemblySlot source = assemblySlots[i];
                var targets = new Transform[source.Slots.Length];
                for (int j = 0; j < targets.Length; j++)
                    targets[j] = board.Find(source.Slots[j].name);
                slots[i] = new AssemblySlot(source.RequiredItemType, targets);
            }
            if (JobId != jobId)
            {
                foreach (Transform completed in completedBoards.Values)
                    Remove(completed);
                completedBoards.Clear();
            }
            JobId = jobId;
            UnitId = unitId;
            CurrentBoard = board;
            currentSlots = slots;
            observedBoard = null;
            observationAwaitingUnit = false;
            return board;
        }

        /// <summary>완료된 기판과 장착 부품을 현재 위치에 보존한다. 적재 동작은 수행하지 않는다.</summary>
        public void CompleteUnit(string jobId, long unitId)
        {
            if (IsUnitCompleted(jobId, unitId)) return;
            if (JobId != jobId || UnitId != unitId || CurrentBoard == null)
                throw new InvalidOperationException("Completion must match the current Job and Unit.");
            CurrentBoard.SetParent(completedRoot, true);
            completedBoards.Add(unitId, CurrentBoard);
            CurrentBoard = null;
            currentSlots = null;
            // 관측에는 PCB 개체 ID가 없다. 완료 직후의 새 프레임도 같은 PCB일 수 있으므로
            // 완료품은 보존하고, 다음 Unit이 확인될 때까지 별도 관측 객체를 생성하지 않는다.
            observationAwaitingUnit = true;
        }

        public bool IsUnitCompleted(string jobId, long unitId) =>
            JobId == jobId && completedBoards.ContainsKey(unitId);

        /// <summary>실행 실패·snapshot 재구성 시 현재 미완료 시각화만 정리한다. 완료품은 보존한다.</summary>
        public void DiscardCurrentUnit()
        {
            Remove(CurrentBoard);
            CurrentBoard = null;
            currentSlots = null;
        }

        /// <summary>Mock 공급 위치에 새 부품을 준비한다. 완료 기판에 붙은 부품은 보존한다.</summary>
        public void PrepareSupply()
        {
            if (spawnRoot == null || itemGroups == null || itemGroups.Length == 0)
                throw new InvalidOperationException("Assign supply groups and spawn root.");
            foreach (ItemGroup group in itemGroups)
            {
                if (group == null || group.Prefab == null || group.SupplyPoints == null)
                    throw new InvalidOperationException("Assign every supply prefab and its fixed supply points.");
                foreach (Transform point in group.SupplyPoints)
                {
                    if (point == null)
                        throw new InvalidOperationException("Supply points must not be missing.");
                    Vector3 position = point.position;
                    Vector3 scale = point.lossyScale;
                    if (!float.IsFinite(position.x) || !float.IsFinite(position.y) || !float.IsFinite(position.z) ||
                        !float.IsFinite(scale.x) || !float.IsFinite(scale.y) || !float.IsFinite(scale.z) ||
                        scale.x <= 0f || scale.y <= 0f || scale.z <= 0f)
                        throw new InvalidOperationException("Supply poses must be finite with positive scale.");
                }
            }
            foreach (ItemGroup group in itemGroups)
            {
                // Supply instances survive editor reload even when RuntimeItems
                // does not. This owner names them by type under spawnRoot;
                // mounted and completed parts have another parent and stay intact.
                for (int i = spawnRoot.childCount - 1; i >= 0; i--)
                {
                    Transform item = spawnRoot.GetChild(i);
                    if (item.name == group.ItemType)
                        Remove(item);
                }
                group.RuntimeItems = new Transform[group.SupplyPoints.Length];
                for (int i = 0; i < group.RuntimeItems.Length; i++)
                {
                    Transform point = group.SupplyPoints[i];
                    Transform item = Instantiate(group.Prefab, point.position, point.rotation, spawnRoot).transform;
                    item.localScale = point.lossyScale;
                    item.name = group.ItemType;
                    group.RuntimeItems[i] = item;
                }
            }
        }

        /// <summary>기판 생성 전에도 공급·목표 좌표를 준비할 수 있도록 프리팹 슬롯의 투입 자세를 반환한다.</summary>
        public Pose GetSlotPose(Transform slot)
        {
            if (slot == null) throw new ArgumentNullException(nameof(slot));
            if (CurrentBoard != null && slot.IsChildOf(CurrentBoard))
                return new Pose(slot.position, slot.rotation);
            if (motherboardPrefab == null || spawnPoint == null || slot.parent != motherboardPrefab.transform)
                throw new InvalidOperationException("Slot must belong to the current board or assigned prefab.");
            Transform prefab = motherboardPrefab.transform;
            Matrix4x4 pose = Matrix4x4.TRS(spawnPoint.position, spawnPoint.rotation, prefab.localScale);
            return new Pose(pose.MultiplyPoint3x4(prefab.InverseTransformPoint(slot.position)),
                spawnPoint.rotation * Quaternion.Inverse(prefab.rotation) * slot.rotation);
        }

        public Vector3 IncomingBoardPosition => spawnPoint.position;

        static void Remove(Transform target)
        {
            if (target == null) return;
            target.gameObject.SetActive(false);
            Destroy(target.gameObject);
        }

        public bool TryGetSlotGroup(string itemType, out AssemblySlot group)
        {
            group = null;
            if (string.IsNullOrWhiteSpace(itemType) || assemblySlots == null)
                return false;

            foreach (AssemblySlot candidate in AssemblySlots)
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
