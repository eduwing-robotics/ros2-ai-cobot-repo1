// 역할: Real 비전의 트레이 부품 상태를 base_link 기준 Unity 프리팹 배치로 반영한다.

using System;
using System.Collections.Generic;
using RosMessageTypes.Std;
using Unity.Robotics.ROSTCPConnector;
using Unity.Robotics.ROSTCPConnector.ROSGeometry;
using UnityEngine;

namespace MainUnity.Runtime.Camera
{
    [DisallowMultipleComponent]
    public sealed class TrayPartCalibrator : MonoBehaviour
    {
        const string TopicName = "/vision/tray/unity_state";
        const string SchemaName = "fr5.tray.unity_state/v1";

        [Serializable]
        sealed class PrefabBinding
        {
            [SerializeField] string partType;
            [SerializeField] GameObject prefab;
            [Tooltip("검출 자세 기준으로 더할 프리팹 위치 보정값입니다. 단위는 m입니다.")]
            [SerializeField] Vector3 positionOffsetMeters;
            [Tooltip("검출 자세 뒤에 적용할 프리팹 회전 보정값입니다. 단위는 degree입니다.")]
            [SerializeField] Vector3 rotationOffsetDegrees;

            public PrefabBinding(string type) => partType = type;

            public string PartType => partType;
            public GameObject Prefab => prefab;
            public Vector3 PositionOffsetMeters => positionOffsetMeters;
            public Quaternion RotationOffset => Quaternion.Euler(rotationOffsetDegrees);
        }

        [Serializable]
        sealed class TrayState
        {
            public string schema;
            public long sequence;
            public bool valid;
            public string registration_state;
            public string coordinate_frame;
            public string position_units;
            public TrayPart[] parts;
        }

        [Serializable]
        sealed class TrayPart
        {
            public string id;
            public string part_type;
            public int instance_index;
            public float[] base_xyz_mm;
            public float angle_base_deg;
        }

        sealed class PartPose
        {
            public string Id;
            public PrefabBinding Binding;
            public Vector3 Position;
            public Quaternion Rotation;
        }

        [Tooltip("로봇 제어와 동일한 ROS 기준 Transform(최상위 ArticulationBody)을 연결합니다. 시각 모델의 회전된 base_link를 연결하지 않습니다.")]
        [SerializeField] Transform baseLink;
        [Tooltip("생성한 부품의 부모입니다. 비워두면 이 GameObject 아래에 생성합니다.")]
        [SerializeField] Transform spawnRoot;
        [SerializeField] PrefabBinding[] prefabBindings =
        {
            new PrefabBinding("black_block"),
            new PrefabBinding("long_orange"),
            new PrefabBinding("marked_white"),
            new PrefabBinding("right_white_brown"),
            new PrefabBinding("gpu"),
            new PrefabBinding("hbm")
        };

        readonly Dictionary<string, PrefabBinding> bindingsByType =
            new Dictionary<string, PrefabBinding>(StringComparer.Ordinal);
        readonly Dictionary<string, GameObject> instancesById =
            new Dictionary<string, GameObject>(StringComparer.Ordinal);

        List<PartPose> latestPoses;

        ROSConnection connection;
        bool hasSequence;
        long lastSequence;
        string lastRejectedReason;

        internal enum ProgressState { Waiting, Preparing, Applied, Rejected, ConfigurationError }
        internal ProgressState Progress { get; private set; }
        internal string ProgressDetail { get; private set; } = "트레이 좌표 수신 대기";
        // 수신 시각과 배치 반영 시각은 다르다. 준비/거부 메시지도 수신은 계속될 수 있다.
        internal double LastReceiveTime { get; private set; } = -1d;
        internal double LastAppliedTime { get; private set; } = -1d;
        internal event Action ProgressChanged;

        void SetProgress(ProgressState state, string detail)
        {
            if (Progress == state && ProgressDetail == detail) return;
            Progress = state;
            ProgressDetail = detail;
            ProgressChanged?.Invoke();
        }

        Transform SpawnRoot => spawnRoot != null ? spawnRoot : transform;

        void Start()
        {
            if (!TryBuildBindingLookup(out string error))
            {
                SetProgress(ProgressState.ConfigurationError, error);
                Debug.LogError($"[TrayPartCalibrator] {error}", this);
                enabled = false;
                return;
            }

            // Real Backend가 이 컴포넌트를 활성화한 경우에만 Start가 실행된다.
            // Items의 초기 공급 부품만 제거한다. motherBoard와 다른 설비 자식은 보존한다.
            if (spawnRoot != null)
                foreach (Transform child in spawnRoot)
                {
                    if (!IsInitialSupplyPart(child.name)) continue;
                    child.gameObject.SetActive(false);
                    Destroy(child.gameObject);
                }

            connection = ROSConnection.GetOrCreateInstance();
            connection.Subscribe<StringMsg>(TopicName, ReceiveState);
        }

        void ReceiveState(StringMsg message)
        {
            if (!isActiveAndEnabled) return;
            LastReceiveTime = Time.realtimeSinceStartupAsDouble;
            if (string.IsNullOrWhiteSpace(message?.data))
            {
                Reject("Empty tray state received.");
                return;
            }

            TrayState state;
            try
            {
                state = JsonUtility.FromJson<TrayState>(message.data);
            }
            catch (ArgumentException exception)
            {
                Reject($"JSON parsing failed: {exception.Message}");
                return;
            }

            // valid=false는 추적 준비 중의 정상 상태다. 마지막 정상 배치를 유지한다.
            if (state == null || state.schema != SchemaName)
            {
                Reject("Rejected a tray state with an unsupported schema.");
                return;
            }
            if (!state.valid)
            {
                lastRejectedReason = null;
                SetProgress(ProgressState.Preparing, hasSequence ? "추적 준비 중 · 이전 배치 유지" : "유효한 트레이 좌표 대기");
                return;
            }
            // 정상 상태의 동일 결과는 재배치/재할당하지 않는다. 준비나 거부 뒤에는 재검증한다.
            if (hasSequence && state.sequence == lastSequence && Progress == ProgressState.Applied) return;
            if (!TryCreatePoses(state, out List<PartPose> poses, out string error))
            {
                Reject(error);
                return;
            }

            if (!hasSequence || state.sequence != lastSequence)
            {
                Apply(poses);
                latestPoses = poses;
                LastAppliedTime = Time.realtimeSinceStartupAsDouble;
            }
            lastRejectedReason = null;
            lastSequence = state.sequence;
            hasSequence = true;
            SetProgress(ProgressState.Applied, error ?? "트레이 좌표 검증 및 Unity 배치 반영됨");
        }

        bool TryBuildBindingLookup(out string error)
        {
            bindingsByType.Clear();
            if (baseLink == null)
            {
                error = "Assign the robot control ROS reference Transform (root ArticulationBody).";
                return false;
            }

            if (prefabBindings == null || prefabBindings.Length == 0)
            {
                error = "Assign at least one part prefab binding.";
                return false;
            }

            foreach (PrefabBinding binding in prefabBindings)
            {
                if (binding == null || string.IsNullOrWhiteSpace(binding.PartType) || binding.Prefab == null)
                {
                    error = "Every prefab binding needs a part type and prefab.";
                    return false;
                }

                if (!bindingsByType.TryAdd(binding.PartType, binding))
                {
                    error = $"Duplicate part type binding: {binding.PartType}";
                    return false;
                }
            }

            error = null;
            return true;
        }

        bool TryCreatePoses(TrayState state, out List<PartPose> poses, out string error)
        {
            poses = null;
            if (state.schema != SchemaName || state.registration_state != "TRACKING" ||
                state.coordinate_frame != "base_link" || state.position_units != "mm" ||
                state.parts == null)
            {
                error = "Rejected a tray state with an unsupported schema, tracking state, frame, or unit.";
                return false;
            }

            var ids = new HashSet<string>(StringComparer.Ordinal);
            var result = new List<PartPose>(state.parts.Length);
            int skippedParts = 0;
            foreach (TrayPart part in state.parts)
            {
                if (part == null || string.IsNullOrWhiteSpace(part.part_type) ||
                    part.instance_index < 1 || part.base_xyz_mm == null || part.base_xyz_mm.Length != 3 ||
                    !IsFinite(part.base_xyz_mm[0]) || !IsFinite(part.base_xyz_mm[1]) ||
                    !IsFinite(part.base_xyz_mm[2]) || !IsFinite(part.angle_base_deg) ||
                    !bindingsByType.TryGetValue(part.part_type, out PrefabBinding binding))
                {
                    skippedParts++;
                    continue;
                }

                // ID 누락 시 타입·순번은 화면 객체 추적에만 사용한다. ROS 원본 ID를
                // 채우거나 생산 요청에 전달하지 않는다. 정상 ID 수신 시 Apply가 임시 객체를 제거한다.
                string displayId = string.IsNullOrWhiteSpace(part.id)
                    ? $"display-only:{part.part_type}:{part.instance_index}"
                    : part.id;
                if (!ids.Add(displayId))
                {
                    skippedParts++;
                    continue;
                }

                Vector3 rosPositionMeters = new Vector3(
                    part.base_xyz_mm[0], part.base_xyz_mm[1], part.base_xyz_mm[2]) * 0.001f;
                float halfYawRadians = part.angle_base_deg * Mathf.Deg2Rad * 0.5f;
                Quaternion rosRotation = new Quaternion(
                    0f, 0f, Mathf.Sin(halfYawRadians), Mathf.Cos(halfYawRadians));
                Vector3 localPosition = FLU.ConvertToRUF(rosPositionMeters);
                Quaternion localRotation = FLU.ConvertToRUF(rosRotation);
                Quaternion detectedRotation = baseLink.rotation * localRotation;

                result.Add(new PartPose
                {
                    Id = displayId,
                    Binding = binding,
                    Position = baseLink.TransformPoint(localPosition) +
                        detectedRotation * binding.PositionOffsetMeters,
                    Rotation = detectedRotation * binding.RotationOffset
                });
            }

            poses = result;
            error = skippedParts == 0 ? null :
                $"트레이 {result.Count}개 배치 반영 · 무효/중복/미지원 부품 {skippedParts}개 제외";
            return true;
        }

        void Apply(List<PartPose> poses)
        {
            var currentIds = new HashSet<string>(StringComparer.Ordinal);
            foreach (PartPose pose in poses)
            {
                currentIds.Add(pose.Id);
                if (!instancesById.TryGetValue(pose.Id, out GameObject instance) || instance == null)
                {
                    instance = Instantiate(pose.Binding.Prefab, SpawnRoot);
                    instance.name = pose.Id;
                    instancesById[pose.Id] = instance;
                }

                instance.transform.SetPositionAndRotation(pose.Position, pose.Rotation);
            }

            var staleIds = new List<string>();
            foreach (KeyValuePair<string, GameObject> pair in instancesById)
                if (!currentIds.Contains(pair.Key)) staleIds.Add(pair.Key);

            foreach (string id in staleIds)
            {
                if (instancesById[id] != null)
                {
                    // Destroy는 프레임 끝에 실행되므로 ID 복구 시 이전 표시를 즉시 숨긴다.
                    instancesById[id].SetActive(false);
                    Destroy(instancesById[id]);
                }
                instancesById.Remove(id);
            }
        }

        [ContextMenu("Recreate Parts From Latest Calibration")]
        void RecreatePartsFromLatestCalibration()
        {
            if (!Application.isPlaying || latestPoses == null)
            {
                Debug.LogWarning("[TrayPartCalibrator] Enter Play Mode and wait for a valid tray state first.", this);
                return;
            }

            foreach (GameObject instance in instancesById.Values)
                if (instance != null) Destroy(instance);

            instancesById.Clear();
            Apply(latestPoses);
        }


        void Reject(string reason)
        {
            SetProgress(ProgressState.Rejected, reason +
                (hasSequence ? " · 이전 배치 유지" : " · 유효한 배치 없음"));
            if (reason == lastRejectedReason) return;
            lastRejectedReason = reason;
            Debug.LogWarning($"[TrayPartCalibrator] {reason} Last valid placement was preserved.", this);
        }

        // 현재 Scene의 ItemManager에 등록된 공급 부품 이름이다.
        static bool IsInitialSupplyPart(string name) =>
            name is "VRM" or "PM" or "GPU" or "HBM" or "CAP" or "IND";

        static bool IsFinite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);

        void OnDestroy()
        {
            if (connection != null) connection.Unsubscribe(TopicName);
        }

        [ContextMenu("Run Tray Part Calibrator Self Check")]
        void RunSelfCheck()
        {
            const string json = "{\"schema\":\"fr5.tray.unity_state/v1\",\"sequence\":7," +
                "\"valid\":true,\"registration_state\":\"TRACKING\",\"coordinate_frame\":\"base_link\"," +
                "\"position_units\":\"mm\",\"parts\":[{\"id\":\"gpu:01\",\"part_type\":\"gpu\"," +
                "\"instance_index\":1,\"base_xyz_mm\":[1000,2000,3000],\"angle_base_deg\":0}]}";
            TrayState state = JsonUtility.FromJson<TrayState>(json);
            Vector3 converted = FLU.ConvertToRUF(new Vector3(1f, 2f, 3f));
            if (state?.parts?.Length != 1 || state.parts[0].id != "gpu:01" ||
                (converted - new Vector3(-2f, 3f, 1f)).sqrMagnitude > 0.000001f)
                throw new InvalidOperationException("TrayPartCalibrator self-check failed.");

            if (!IsInitialSupplyPart("VRM") || !IsInitialSupplyPart("HBM") ||
                IsInitialSupplyPart("motherBoard") || IsInitialSupplyPart("gpu:01") ||
                IsInitialSupplyPart("Fixture"))
                throw new InvalidOperationException("Initial supply part filtering failed.");
            if (Application.isPlaying && spawnRoot != null)
                foreach (Transform child in spawnRoot)
                    if (IsInitialSupplyPart(child.name) && child.gameObject.activeSelf)
                        throw new InvalidOperationException("An initial supply part remains active.");

            Debug.Log("[TrayPartCalibrator] Self-check passed: parsed one part and converted " +
                "ROS FLU (1, 2, 3) m to Unity RUF (-2, 3, 1) m.", this);
        }
    }
}
