// 역할: Real 비전의 트레이 부품 상태를 base_link 기준 Unity 프리팹 배치로 반영한다.

using System;
using System.Collections;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;
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
        const string RobotEventTopic = "/real/robot/event";
        const string RobotStatusService = "/real/robot/status";

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
            public string tray_registration_id;
            public string source_observation_id;
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

        // The tray owns these objects even after reparenting. Reservation prevents a
        // subsequent detector frame or manual recreation from moving/deleting them.
        sealed class Attachment
        {
            public string Job, PickOperation, PlaceOperation, Registration, Observation, Slot, Part, Server, Plan, Cycle;
            public readonly HashSet<long> Seen = new();
            public long Sequence;
            public Transform Board;
            public string State = "reserved";
            public bool Uncertain;
        }

        readonly Dictionary<string, Attachment> attachments = new(StringComparer.Ordinal);
        readonly Dictionary<string, string> instanceRegistrations = new(StringComparer.Ordinal);
        readonly Dictionary<string, string> instanceTypes = new(StringComparer.Ordinal);
        readonly HashSet<string> observations = new(StringComparer.Ordinal);
        string registration;
        Transform measuredGripper;
        BoardPartCalibrator boardCalibration;
        bool robotSubscribed;
        System.Threading.Tasks.Task<TriggerResponse> statusRequest;
        bool wasConnected;
        int eventRevision;
        internal string RobotDetail { get; private set; } = "로봇 동작 이벤트 대기";
        internal double LastRobotReceiveTime { get; private set; } = -1d;

        internal void InitializeAttachments(Transform gripper, BoardPartCalibrator board)
        {
            measuredGripper = gripper;
            boardCalibration = board;
        }

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
            ConnectRobotEvents();
        }

        void OnEnable()
        {
            if (connection != null) ConnectRobotEvents();
        }

        void ConnectRobotEvents()
        {
            if (robotSubscribed) return;
            connection.Subscribe<StringMsg>(RobotEventTopic, ReceiveRobotEvent);
            connection.RegisterRosService<TriggerRequest, TriggerResponse>(RobotStatusService);
            robotSubscribed = true;
            StartCoroutine(ReconcileConnection());
        }

        void OnDisable()
        {
            StopAllCoroutines();
            if (connection != null && robotSubscribed) connection.Unsubscribe(RobotEventTopic);
            robotSubscribed = false;
            wasConnected = false;
            foreach (Attachment value in attachments.Values) value.Uncertain = true;
            RobotDetail = "로봇 시각화 비활성 · 상태 재확인 필요";
        }

        IEnumerator ReconcileConnection()
        {
            // No network work in Update. At most one service request remains pending;
            // ROSConnection cannot cancel a pending service Future safely.
            var delay = new WaitForSecondsRealtime(1f);
            while (isActiveAndEnabled)
            {
                bool connected = connection.HasConnectionThread && !connection.HasConnectionError;
                if (!connected && wasConnected)
                {
                    foreach (Attachment value in attachments.Values) value.Uncertain = true;
                    RobotDetail = "로봇 연결 중단 · 마지막 부착 유지";
                }
                if (connected && !wasConnected && statusRequest == null)
                {
                    statusRequest = connection.SendServiceMessage<TriggerResponse>(RobotStatusService, new TriggerRequest());
                    int revision = eventRevision;
                    double deadline = Time.realtimeSinceStartupAsDouble + 5d;
                    while (!statusRequest.IsCompleted && Time.realtimeSinceStartupAsDouble < deadline)
                        yield return null;
                    if (statusRequest.IsCompleted)
                    {
                        if (!statusRequest.IsFaulted && !statusRequest.IsCanceled && statusRequest.Result.success &&
                            revision == eventRevision && connection.HasConnectionThread && !connection.HasConnectionError)
                            ReconcileSnapshot(statusRequest.Result.message);
                        else
                        {
                            _ = statusRequest.Exception;
                            RobotDetail = "로봇 상태 조회 미확정 · 이벤트 확인 필요";
                        }
                        statusRequest = null;
                    }
                    else RobotDetail = "로봇 상태 조회 시간초과 · 복원 미확인";
                }
                if (statusRequest != null && statusRequest.IsCompleted)
                {
                    // A late reply cannot overwrite newer live events.
                    _ = statusRequest.Exception;
                    statusRequest = null;
                }
                wasConnected = connected;
                yield return delay;
            }
        }

        void ReceiveRobotEvent(StringMsg message)
        {
            if (!isActiveAndEnabled) return;
            ProcessRobotEvent(message?.data);
        }

        void ProcessRobotEvent(string json)
        {
            LastRobotReceiveTime = Time.realtimeSinceStartupAsDouble;
            eventRevision++;
            Attachment affected = null;
            try
            {
                JObject envelope = JObject.Parse(json ?? "");
                string action = (string)envelope["action"];
                string kind = (string)envelope["event"];
                if (kind == "REQUEST_REJECTED") return;
                if (kind is "OPERATION_FAILED" or "PAUSED" or "CONTROL_FAILED")
                {
                    // Failure/control messages can have plain-text context. Do not lose
                    // the stop boundary just because no source ID can be decoded.
                    string failedJob = (string)envelope["job_id"];
                    if (Guid.TryParse(failedJob, out _))
                        foreach (Attachment value in attachments.Values)
                            if (value.Job == failedJob) value.Uncertain = true;
                    RobotDetail = "로봇 정지/실패 · 마지막 부착 유지 · 재확인 필요";
                    return;
                }
                if (action != "robot.pick" && action != "robot.place") return;
                if (!Guid.TryParse((string)envelope["job_id"], out _) ||
                    !Guid.TryParse((string)envelope["operation_id"], out _))
                    throw new FormatException("실행·동작 ID 누락");
                JObject context = JObject.Parse((string)envelope["message"] ?? "");
                if ((string)context["schema"] != "fr5.robot_event_context/v1" ||
                    !Guid.TryParse((string)context["server_instance_id"], out _) ||
                    context["event_sequence"]?.Type != JTokenType.Integer || (long)context["event_sequence"] < 0)
                    throw new FormatException("이벤트 식별 정보 누락");
                string id = (string)context["source_id"];
                string job = (string)envelope["job_id"];
                string operation = (string)envelope["operation_id"];
                string server = (string)context["server_instance_id"];
                long sequence = (long)context["event_sequence"];
                string phase = (string)envelope["phase"];
                attachments.TryGetValue(id ?? "", out Attachment record);
                affected = record;
                if (record != null && record.Job == job && record.Server == server && record.Seen.Contains(sequence)) return;
                if (record != null && (record.Job != job || record.Server != server))
                    throw new FormatException("다른 실행 또는 API 재시작 · 부착 복원 미확인");
                if (context["attachment_binding_valid"]?.Type != JTokenType.Boolean ||
                    !(bool)context["attachment_binding_valid"] || string.IsNullOrWhiteSpace(id) ||
                    !instancesById.TryGetValue(id, out GameObject instance) || instance == null)
                {
                    if (record != null) record.Uncertain = true;
                    throw new FormatException("부품 식별 불명확 또는 원래 객체 없음");
                }
                string reg = (string)context["tray_registration_id"];
                string observation = (string)context["source_observation_id"];
                string slot = (string)context["slot_code"];
                string part = (string)context["part_id"];
                string plan = (string)context["plan_sha256"];
                string cycle = (string)context["source_cycle_id"];
                if (string.IsNullOrWhiteSpace(slot) || string.IsNullOrWhiteSpace(part) ||
                    string.IsNullOrWhiteSpace(reg) || string.IsNullOrWhiteSpace(observation) ||
                    string.IsNullOrWhiteSpace(plan) || string.IsNullOrWhiteSpace(cycle))
                    throw new FormatException("부품·슬롯·관측 식별 누락");
                if (record == null)
                {
                    if (action != "robot.pick" || kind != "PHASE_STARTED" || reg != registration ||
                        !observations.Contains(observation) || !instanceRegistrations.TryGetValue(id, out string sourceReg) || sourceReg != reg ||
                        !instanceTypes.TryGetValue(id, out string type) || PartCode(type) != part)
                        throw new FormatException("Pick 시작·원래 관측 미수신 · 부착 복원 미확인");
                    record = new Attachment { Job = job, PickOperation = operation, Registration = reg,
                        Observation = observation, Slot = slot, Part = part, Server = server, Plan = plan, Cycle = cycle,
                        Board = boardCalibration != null ? boardCalibration.AttachmentBoard : null };
                    attachments.Add(id, record);
                    affected = record;
                }
                if (record.Registration != reg || record.Observation != observation || record.Slot != slot || record.Part != part || record.Plan != plan || record.Cycle != cycle ||
                    (action == "robot.pick" && record.PickOperation != operation))
                {
                    record.Uncertain = true;
                    throw new FormatException("실행 중 부품 대응 변경");
                }
                if (action == "robot.place")
                {
                    if (record.PlaceOperation == null) record.PlaceOperation = operation;
                    else if (record.PlaceOperation != operation)
                        throw new FormatException("다른 Place 동작 ID");
                }
                record.Sequence = Math.Max(record.Sequence, sequence);
                if (record.Seen.Count >= 4096) throw new FormatException("이벤트 추적 한도 초과 · 상태 확인 필요");
                record.Seen.Add(sequence);
                if (!string.IsNullOrEmpty((string)envelope["error_code"]))
                {
                    record.Uncertain = true;
                    RobotDetail = $"{slot} · 정지/실패 · 마지막 부착 유지";
                    return;
                }
                bool grasp = action == "robot.pick" && phase == "GRASP";
                bool release = action == "robot.place" && phase == "RELEASE";
                if (kind == "PHASE_COMPLETED" && (grasp || release))
                {
                    JObject feedback = context["feedback"] as JObject;
                    if (feedback?["continuous_feedback_verified"]?.Type != JTokenType.Boolean ||
                        !(bool)feedback["continuous_feedback_verified"] ||
                        feedback["gripper_feedback_valid"]?.Type != JTokenType.Boolean || !(bool)feedback["gripper_feedback_valid"] ||
                        (string)feedback["phase"] != phase)
                    {
                        record.Uncertain = true;
                        throw new FormatException("파지/놓기 연속 피드백 검증 누락");
                    }
                    if (record.Uncertain) throw new FormatException("이전 상태 불명확 · 자동 부착 변경 차단");
                    if (grasp && record.State == "reserved")
                    {
                        if (measuredGripper == null) throw new FormatException("실측 그리퍼 참조 없음");
                        foreach (var other in attachments)
                            if (other.Key != id && other.Value.State == "attached")
                                throw new FormatException("다른 부품 보유 표시 중");
                        instance.transform.SetParent(measuredGripper, true);
                        record.State = "attached";
                    }
                    else if (release && record.State == "attached")
                    {
                        if (record.Board == null || boardCalibration == null || boardCalibration.AttachmentBoard != record.Board ||
                            record.Board.Find(slot) == null)
                        {
                            record.Uncertain = true;
                            throw new FormatException("원래 기판·슬롯 연결 미확인");
                        }
                        instance.transform.SetParent(record.Board, true);
                        record.State = "placed";
                    }
                    else if (release && record.State != "placed")
                    {
                        record.Uncertain = true;
                        throw new FormatException("파지 확인 없이 놓기 수신");
                    }
                }
                RobotDetail = $"{slot} · {record.State} · {phase} / {kind} · 컨트롤러 피드백 기준";
            }
            catch (Exception error) when (error is Newtonsoft.Json.JsonException || error is ArgumentException ||
                error is FormatException || error is InvalidCastException || error is OverflowException)
            {
                if (affected != null) affected.Uncertain = true;
                RobotDetail = "로봇 시각화 미확인 · " + error.Message;
            }
        }

        void ReconcileSnapshot(string json)
        {
            try
            {
                JObject status = JObject.Parse(json);
                if ((string)status["schema"] != "fr5.robot_api_status/v1" ||
                    status["event_context"]?["attachments"] is not JArray rows)
                    throw new FormatException("부착 snapshot 없음");
                if (status["state_fresh"]?.Type != JTokenType.Boolean || !(bool)status["state_fresh"])
                    throw new FormatException("실측 freshness 미확인");
                foreach (Attachment value in attachments.Values) value.Uncertain = true;
                int unresolved = 0;
                foreach (JObject row in rows)
                {
                    string id = (string)row["source_id"];
                    if (id == null || !attachments.TryGetValue(id, out Attachment record)) { unresolved++; continue; }
                    // Captured snapshots contain identity/state, not an object-to-gripper
                    // pose. Never attach an old tray pose at the current robot position.
                    bool matches = (string)row["job_id"] == record.Job &&
                        (string)row["server_instance_id"] == record.Server &&
                        (string)row["tray_registration_id"] == record.Registration &&
                        (string)row["source_observation_id"] == record.Observation &&
                        (string)row["slot_code"] == record.Slot && (string)row["state"] == record.State &&
                        (string)row["plan_sha256"] == record.Plan && (string)row["source_cycle_id"] == record.Cycle &&
                        (string)status["event_context"]?["server_instance_id"] == record.Server &&
                        row["event_sequence"]?.Type == JTokenType.Integer && (long)row["event_sequence"] >= record.Sequence &&
                        instancesById.TryGetValue(id, out GameObject instance) && instance != null &&
                        (record.State == "attached" ? instance.transform.parent == measuredGripper :
                            record.State == "placed" && record.Board != null && instance.transform.parent == record.Board) &&
                        row["uncertain"]?.Type == JTokenType.Boolean && !(bool)row["uncertain"] &&
                        row["attachment_binding_valid"]?.Type == JTokenType.Boolean && (bool)row["attachment_binding_valid"];
                    record.Uncertain = !matches;
                }
                foreach (Attachment value in attachments.Values)
                    if (value.Uncertain) unresolved++;
                RobotDetail = unresolved > 0 ? $"부착 snapshot {unresolved}건 복원 미확인 · 임의 배치 안 함" : "부착 snapshot 대조 완료";
            }
            catch (Exception error) when (error is Newtonsoft.Json.JsonException || error is ArgumentException ||
                error is InvalidCastException || error is FormatException)
            { RobotDetail = "부착 snapshot 미확인 · " + error.Message; }
        }

        static string PartCode(string type) => type switch
        {
            "black_block" => "VRM", "long_orange" => "PM", "marked_white" => "IND",
            "right_white_brown" => "CAP", "gpu" => "GPU", "hbm" => "HBM", _ => null
        };

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
                if (registration != state.tray_registration_id)
                {
                    observations.Clear();
                    registration = state.tray_registration_id;
                }
                if (!string.IsNullOrWhiteSpace(state.source_observation_id) && observations.Count < 4096)
                    observations.Add(state.source_observation_id);
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
                if (attachments.ContainsKey(pose.Id)) continue;
                if (!instancesById.TryGetValue(pose.Id, out GameObject instance) || instance == null)
                {
                    instance = Instantiate(pose.Binding.Prefab, SpawnRoot);
                    instance.name = pose.Id;
                    instancesById[pose.Id] = instance;
                }

                instanceRegistrations[pose.Id] = registration;
                instanceTypes[pose.Id] = pose.Binding.PartType;
                instance.transform.SetPositionAndRotation(pose.Position, pose.Rotation);
            }

            var staleIds = new List<string>();
            foreach (KeyValuePair<string, GameObject> pair in instancesById)
                if (!currentIds.Contains(pair.Key) && !attachments.ContainsKey(pair.Key)) staleIds.Add(pair.Key);

            foreach (string id in staleIds)
            {
                if (instancesById[id] != null)
                {
                    // Destroy는 프레임 끝에 실행되므로 ID 복구 시 이전 표시를 즉시 숨긴다.
                    instancesById[id].SetActive(false);
                    Destroy(instancesById[id]);
                }
                instancesById.Remove(id);
                instanceRegistrations.Remove(id);
                instanceTypes.Remove(id);
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

            if (attachments.Count > 0)
            {
                Debug.LogWarning("[TrayPartCalibrator] Robot-owned parts cannot be recreated during this session.", this);
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
            if (connection != null)
            {
                connection.Unsubscribe(TopicName);
                if (robotSubscribed) connection.Unsubscribe(RobotEventTopic);
            }
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
