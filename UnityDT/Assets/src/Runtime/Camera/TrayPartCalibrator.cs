// 역할: Real 트레이 객체 수명, callback 부착 상태와 시각화 저장·복원을 소유한다.

using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
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
        [Serializable]
        sealed class Attachment
        {
            // Names are persisted JSON keys. Job is the robot execution UUID, not a production Job UUID.
            public string Job, PickOperation, PlaceOperation, Registration, Observation, Slot, Part, Server, Plan, Cycle;
            public readonly HashSet<long> Seen = new();
            public long Sequence;
            [NonSerialized] public Transform Board;
            public long SnapshotFloor = -1;
            public bool Restored;
            public Vector3 LocalPosition;
            public Quaternion LocalRotation;
            public string State = "reserved";
            public bool Uncertain;
        }

        readonly Dictionary<string, Attachment> attachments = new(StringComparer.Ordinal);
        readonly Dictionary<string, string> instanceRegistrations = new(StringComparer.Ordinal);
        readonly Dictionary<string, string> instanceTypes = new(StringComparer.Ordinal);
        readonly HashSet<(string Registration, string Observation, string Source)> observations = new();
        string registration;
        Transform measuredGripper;
        BoardPartCalibrator boardCalibration;
        bool robotSubscribed;
        System.Threading.Tasks.Task<TriggerResponse> statusRequest;
        bool wasConnected;
        readonly List<string> bufferedEvents = new();
        bool isBufferingRobotEvents;
        bool robotEventBufferOverflow;
        bool needsStatusReconciliation = true;
        bool hasUnverifiedRestoredLayout;
        string storagePath;
        bool layoutSavePending;
        internal string SyncDetail { get; private set; } = "현재 상태 확인 대기";
        internal string StorageDetail { get; private set; } = "";

        [Serializable]
        sealed class SavedPart
        {
            public string Id, Type, Registration;
            public Vector3 Position, Scale;
            public Quaternion Rotation;
            public bool HasAttachment;
            public Attachment Attachment;
        }
        [Serializable]
        sealed class SavedObservation { public string Registration, Observation, Source; }
        [Serializable]
        sealed class SavedLayout
        {
            public int Version;
            public string Registration, SavedUtc;
            public List<SavedPart> Parts = new();
            public List<SavedObservation> Observations = new();
        }

        internal string RobotDetail { get; private set; } = "로봇 동작 이벤트 대기";
        internal double LastRobotReceiveTime { get; private set; } = -1d;

        internal void InitializeAttachments(Transform gripper, BoardPartCalibrator board)
        {
            measuredGripper = gripper;
            boardCalibration = board;
        }

        List<PartPose> latestPoses;
        string latestRegistration;
        string latestObservation;
        // Keep complete, validated observations until Pick selects one. The bounds
        // limit memory during long idle sessions; an evicted observation fails closed.
        const int MaxCandidateObservations = 1024;
        const int MaxCandidateParts = 32768;
        readonly Dictionary<(string Registration, string Observation), List<PartPose>> candidates = new();
        readonly Queue<(string Registration, string Observation)> candidateOrder = new();
        int candidatePartCount;
        double latestCandidateTime = -1d;

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
            // Separate Real caches by scene and configured ROS endpoint, never by Mock data.
            using (var hash = System.Security.Cryptography.SHA256.Create())
            {
                string key = gameObject.scene.path + "|" + name + "|" + connection.RosIPAddress + ":" + connection.RosPort;
                string suffix = BitConverter.ToString(hash.ComputeHash(System.Text.Encoding.UTF8.GetBytes(key))).Replace("-", "");
                storagePath = Path.Combine(Application.persistentDataPath, "real-visualization-" + suffix + ".json");
            }
            RestoreLayout();
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
            SaveLayout();
            StopAllCoroutines();
            isBufferingRobotEvents = false;
            bufferedEvents.Clear();
            candidates.Clear();
            candidateOrder.Clear();
            candidatePartCount = 0;
            needsStatusReconciliation = true;
            if (connection != null && robotSubscribed) connection.Unsubscribe(RobotEventTopic);
            robotSubscribed = false;
            wasConnected = false;
            foreach (Attachment value in attachments.Values) value.Uncertain = true;
            RobotDetail = "로봇 시각화 비활성 · 상태 재확인 필요";
        }

        IEnumerator ReconcileConnection()
        {
            // A timed-out ROS service Future cannot be cancelled. Keep at most one
            // outstanding request; retry only after it has completed.
            var delay = new WaitForSecondsRealtime(1f);
            double nextQuery = 0d;
            while (isActiveAndEnabled)
            {
                if (layoutSavePending) SaveLayout();
                bool connected = connection.HasConnectionThread && !connection.HasConnectionError;
                if (!connected)
                {
                    if (wasConnected)
                        foreach (Attachment value in attachments.Values) value.Uncertain = true;
                    needsStatusReconciliation = true;
                    SyncDetail = "연결 대기 · 마지막 화면 미확인";
                }
                if (statusRequest != null && statusRequest.IsCompleted)
                {
                    _ = statusRequest.Exception;
                    statusRequest = null;
                }
                if (connected && needsStatusReconciliation && statusRequest == null && Time.realtimeSinceStartupAsDouble >= nextQuery)
                {
                    isBufferingRobotEvents = true;
                    robotEventBufferOverflow = false;
                    bufferedEvents.Clear();
                    SyncDetail = "◌ 로봇 상태 동기화 중";
                    statusRequest = connection.SendServiceMessage<TriggerResponse>(RobotStatusService, new TriggerRequest());
                    double deadline = Time.realtimeSinceStartupAsDouble + 5d;
                    while (!statusRequest.IsCompleted && Time.realtimeSinceStartupAsDouble < deadline)
                        yield return null;
                    if (statusRequest.IsCompleted)
                    {
                        if (!robotEventBufferOverflow && !statusRequest.IsFaulted && !statusRequest.IsCanceled && statusRequest.Result.success &&
                            connection.HasConnectionThread && !connection.HasConnectionError)
                            ReconcileSnapshot(statusRequest.Result.message);
                        else
                        {
                            _ = statusRequest.Exception;
                            SyncDetail = "상태 조회 미확정 · 마지막 화면 미확인";
                        }
                        statusRequest = null;
                    }
                    else SyncDetail = "동기화 지연 · 조회 5초 초과 · 마지막 화면 미확인";
                    isBufferingRobotEvents = false;
                    // Matching snapshot rows set a per-part sequence floor. Unknown
                    // rows stay uncertain; never discard their failure/control events.
                    foreach (string json in bufferedEvents) ProcessRobotEvent(json);
                    bufferedEvents.Clear();
                    nextQuery = Time.realtimeSinceStartupAsDouble + 5d;
                }
                wasConnected = connected;
                yield return delay;
            }
        }

        void ReceiveRobotEvent(StringMsg message)
        {
            if (!isActiveAndEnabled) return;
            if (isBufferingRobotEvents)
            {
                LastRobotReceiveTime = Time.realtimeSinceStartupAsDouble;
                if (bufferedEvents.Count < 1024) bufferedEvents.Add(message?.data);
                else
                {
                    robotEventBufferOverflow = true;
                    foreach (Attachment value in attachments.Values) value.Uncertain = true;
                    SyncDetail = "이벤트 수집 한도 초과 · 재대조 필요";
                }
                return;
            }
            ProcessRobotEvent(message?.data);
        }

        void ProcessRobotEvent(string json)
        {
            LastRobotReceiveTime = Time.realtimeSinceStartupAsDouble;

            Attachment affected = null;
            try
            {
                JObject envelope = JObject.Parse(json ?? "");
                string action = (string)envelope["action"];
                string eventKind = (string)envelope["event"];
                if (eventKind == "REQUEST_REJECTED") return;
                if (eventKind is "OPERATION_FAILED" or "PAUSED" or "CONTROL_FAILED")
                {
                    // Failure/control messages can have plain-text context. Do not lose
                    // the stop boundary just because no source ID can be decoded.
                    string failedJob = (string)envelope["job_id"];
                    if (Guid.TryParse(failedJob, out _))
                        foreach (Attachment value in attachments.Values)
                            if (value.Job == failedJob) value.Uncertain = true;
                    needsStatusReconciliation = true;
                    SyncDetail = "로봇 정지/실패 · 상태 재대조 필요";
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
                string sourceId = (string)context["source_id"];
                string executionId = (string)envelope["job_id"];
                string operationId = (string)envelope["operation_id"];
                string serverInstanceId = (string)context["server_instance_id"];
                long eventSequence = (long)context["event_sequence"];
                string phase = (string)envelope["phase"];
                attachments.TryGetValue(sourceId ?? "", out Attachment record);
                affected = record;
                if (record != null && record.Server == serverInstanceId && record.Job == executionId && eventSequence <= record.SnapshotFloor) return;
                if (record != null && record.Job == executionId && record.Server == serverInstanceId && record.Seen.Contains(eventSequence)) return;
                if (record != null && (record.Job != executionId || record.Server != serverInstanceId))
                    throw new FormatException("다른 실행 또는 API 재시작 · 부착 복원 미확인");
                if (context["attachment_binding_valid"]?.Type != JTokenType.Boolean ||
                    !(bool)context["attachment_binding_valid"] || string.IsNullOrWhiteSpace(sourceId))
                {
                    if (record != null) record.Uncertain = true;
                    throw new FormatException("부품 식별 불명확 또는 원래 객체 없음");
                }
                string trayRegistrationId = (string)context["tray_registration_id"];
                string sourceObservationId = (string)context["source_observation_id"];
                string slotCode = (string)context["slot_code"];
                string partId = (string)context["part_id"];
                string planSha256 = (string)context["plan_sha256"];
                string sourceCycleId = (string)context["source_cycle_id"];
                if (string.IsNullOrWhiteSpace(slotCode) || string.IsNullOrWhiteSpace(partId) ||
                    string.IsNullOrWhiteSpace(trayRegistrationId) || string.IsNullOrWhiteSpace(sourceObservationId) ||
                    string.IsNullOrWhiteSpace(planSha256) || string.IsNullOrWhiteSpace(sourceCycleId))
                    throw new FormatException("부품·슬롯·관측 식별 누락");
                if (record == null)
                {
                    // This is the observed entry phase, before any grasp. A later
                    // phase or a snapshot cannot reconstruct a missed Pick start.
                    if (action != "robot.pick" || eventKind != "PHASE_STARTED" || phase != "01_pre_pick_safe_vertical")
                        throw new FormatException("Pick 시작 callback 미수신 · 소급 부착 차단");
                    if (!string.IsNullOrEmpty((string)envelope["error_code"]))
                        throw new FormatException("실패한 Pick 시작 · 배치 변경 차단");
                    foreach (Attachment existing in attachments.Values)
                        if (existing.Job != executionId || existing.Server != serverInstanceId || existing.Cycle != sourceCycleId)
                            throw new FormatException("다른 실행의 부품 배치 보존 · 새 실행 연결 차단");
                    if (attachments.Count == 0)
                    {
                        if (!candidates.TryGetValue((trayRegistrationId, sourceObservationId), out List<PartPose> candidate))
                            throw new FormatException($"실행 관측 후보 없음 또는 보관 한도 초과 · 표시 {registration} / 실행 {trayRegistrationId} · {sourceObservationId}");
                        PrepareExecutionObservation(trayRegistrationId, sourceObservationId, sourceId, partId, candidate);
                    }
                    if (trayRegistrationId != registration)
                        throw new FormatException($"실행 트레이 관측 없음 · 표시 {registration} / 실행 {trayRegistrationId} · {sourceObservationId}");
                    if (hasUnverifiedRestoredLayout ||
                        !observations.Contains((trayRegistrationId, sourceObservationId, sourceId)) || !instanceRegistrations.TryGetValue(sourceId, out string sourceReg) || sourceReg != trayRegistrationId ||
                        !instanceTypes.TryGetValue(sourceId, out string type) || PartCode(type) != partId)
                        throw new FormatException("Pick 시작·원래 관측 미수신 · 부착 복원 미확인");
                    record = new Attachment { Job = executionId, PickOperation = operationId, Registration = trayRegistrationId,
                        Observation = sourceObservationId, Slot = slotCode, Part = partId, Server = serverInstanceId, Plan = planSha256, Cycle = sourceCycleId,
                        Board = boardCalibration != null ? boardCalibration.AttachmentBoard : null };
                    attachments.Add(sourceId, record);
                    affected = record;
                }
                if (!instancesById.TryGetValue(sourceId, out GameObject instance) || instance == null)
                    throw new FormatException("원래 부품 객체 없음 · 부착 차단");
                if (record.Registration != trayRegistrationId || record.Observation != sourceObservationId || record.Slot != slotCode || record.Part != partId || record.Plan != planSha256 || record.Cycle != sourceCycleId ||
                    (action == "robot.pick" && record.PickOperation != operationId))
                {
                    record.Uncertain = true;
                    throw new FormatException("실행 중 부품 대응 변경");
                }
                if (action == "robot.place")
                {
                    if (record.PlaceOperation == null) record.PlaceOperation = operationId;
                    else if (record.PlaceOperation != operationId)
                        throw new FormatException("다른 Place 동작 ID");
                }
                record.Sequence = Math.Max(record.Sequence, eventSequence);
                if (record.Seen.Count >= 4096) throw new FormatException("이벤트 추적 한도 초과 · 상태 확인 필요");
                record.Seen.Add(eventSequence);
                if (!string.IsNullOrEmpty((string)envelope["error_code"]))
                {
                    record.Uncertain = true;
                    needsStatusReconciliation = true;
                    SyncDetail = "일부 부품 미확인 · 상태 재대조 필요";
                    RobotDetail = $"{slotCode} · 정지/실패 · 마지막 부착 유지";
                    return;
                }
                bool grasp = action == "robot.pick" && phase == "GRASP";
                bool release = action == "robot.place" && phase == "RELEASE";
                if (eventKind == "PHASE_COMPLETED" && (grasp || release))
                {
                    JObject feedback = context["feedback"] as JObject;
                    if (!HasVerifiedGripperFeedback(feedback, phase))
                    {
                        record.Uncertain = true;
                        throw new FormatException("파지/놓기 연속 피드백 검증 누락");
                    }
                    if (record.Uncertain) throw new FormatException("이전 상태 불명확 · 자동 부착 변경 차단");
                    if (grasp && record.State == "reserved")
                    {
                        if (measuredGripper == null) throw new FormatException("실측 그리퍼 참조 없음");
                        foreach (var other in attachments)
                            if (other.Key != sourceId && other.Value.State == "attached")
                                throw new FormatException("다른 부품 보유 표시 중");
                        instance.transform.SetParent(measuredGripper, true);
                        record.State = "attached";
                    }
                    else if (release && record.State == "attached")
                    {
                        if (record.Board == null || boardCalibration == null || boardCalibration.AttachmentBoard != record.Board ||
                            record.Board.Find(slotCode) == null)
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
                RobotDetail = $"{slotCode} · {record.State} · {phase} / {eventKind} · 컨트롤러 피드백 기준";
            }
            catch (Exception error) when (error is Newtonsoft.Json.JsonException || error is ArgumentException ||
                error is FormatException || error is InvalidCastException || error is OverflowException)
            {
                if (affected != null) affected.Uncertain = true;
                needsStatusReconciliation = true;
                SyncDetail = "일부 부품 미확인 · 상태 재대조 필요";
                RobotDetail = "로봇 시각화 미확인 · " + error.Message;
            }
            finally { layoutSavePending = true; SaveLayout(); }
        }

        static bool HasVerifiedGripperFeedback(JObject feedback, string phase) =>
            feedback?["continuous_feedback_verified"]?.Type == JTokenType.Boolean &&
            (bool)feedback["continuous_feedback_verified"] &&
            feedback["gripper_feedback_valid"]?.Type == JTokenType.Boolean &&
            (bool)feedback["gripper_feedback_valid"] &&
            (string)feedback["phase"] == phase;

        void ReconcileSnapshot(string json)
        {
            foreach (Attachment value in attachments.Values) value.Uncertain = true;
            try
            {
                JObject status = JObject.Parse(json);
                if ((string)status["schema"] != "fr5.robot_api_status/v1" ||
                    status["event_context"]?["attachments"] is not JArray rows)
                    throw new FormatException("부착 snapshot 없음");
                if (status["state_fresh"]?.Type != JTokenType.Boolean || !(bool)status["state_fresh"])
                    throw new FormatException("실측 freshness 미확인");
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
                        (record.State == "attached" ? measuredGripper != null &&
                            (record.Restored || instance.transform.parent == measuredGripper) :
                            record.State == "placed" && record.Board != null && instance.transform.parent == record.Board) &&
                        row["uncertain"]?.Type == JTokenType.Boolean && !(bool)row["uncertain"] &&
                        row["attachment_binding_valid"]?.Type == JTokenType.Boolean && (bool)row["attachment_binding_valid"];
                    if (matches && record.Restored)
                    {
                        // Only the same uninterrupted Pick may reuse a saved TCP-relative pose.
                        matches = (string)row["operation_id"] == record.PickOperation;
                        if (matches)
                        {
                            Transform partTransform = instancesById[id].transform;
                            partTransform.SetParent(measuredGripper, true);
                            partTransform.localPosition = record.LocalPosition;
                            partTransform.localRotation = record.LocalRotation;
                            record.Restored = false;
                        }
                    }
                    record.Uncertain = !matches;
                    if (matches) record.Sequence = record.SnapshotFloor = (long)row["event_sequence"];
                }
                foreach (Attachment value in attachments.Values)
                    if (value.Uncertain) unresolved++;
                if (hasUnverifiedRestoredLayout && attachments.Count == instancesById.Count && unresolved == 0) hasUnverifiedRestoredLayout = false;
                needsStatusReconciliation = unresolved > 0 || hasUnverifiedRestoredLayout;
                SyncDetail = needsStatusReconciliation ? "일부 복원 미확인 · 전체 부품 자세 snapshot 필요" : "부착 상태 대조 완료 · callback 수신 중";
                layoutSavePending = true;
                RobotDetail = unresolved > 0 ? $"부착 snapshot {unresolved}건 복원 미확인 · 임의 배치 안 함" : "부착 snapshot 대조 완료";
            }
            catch (Exception error) when (error is Newtonsoft.Json.JsonException || error is ArgumentException ||
                error is InvalidCastException || error is FormatException)
            {
                needsStatusReconciliation = true;
                SyncDetail = "동기화 미확인 · " + error.Message;
                RobotDetail = "부착 snapshot 미확인 · " + error.Message;
            }
        }

        void SaveLayout()
        {
            if (storagePath == null || baseLink == null || instancesById.Count == 0) return;
            try
            {
                var saved = new SavedLayout { Version = 1, Registration = registration, SavedUtc = DateTime.UtcNow.ToString("O") };
                foreach (var pair in instancesById)
                {
                    if (pair.Value == null) continue;
                    Transform part = pair.Value.transform;
                    attachments.TryGetValue(pair.Key, out Attachment record);
                    if (record != null && !record.Restored)
                    {
                        record.LocalPosition = part.localPosition;
                        record.LocalRotation = part.localRotation;
                    }
                    saved.Parts.Add(new SavedPart { Id = pair.Key, Type = instanceTypes[pair.Key],
                        Registration = instanceRegistrations[pair.Key], Position = baseLink.InverseTransformPoint(part.position),
                        Rotation = Quaternion.Inverse(baseLink.rotation) * part.rotation, Scale = part.lossyScale,
                        HasAttachment = record != null, Attachment = record });
                }
                foreach (var observation in observations)
                    saved.Observations.Add(new SavedObservation { Registration = observation.Registration,
                        Observation = observation.Observation, Source = observation.Source });
                string json = JsonUtility.ToJson(saved);
                // A same-directory replace leaves the previous complete file intact
                // if writing the temporary file fails or Unity exits during the write.
                Directory.CreateDirectory(Path.GetDirectoryName(storagePath));
                using (var stream = new FileStream(storagePath + ".tmp", FileMode.Create, FileAccess.Write))
                {
                    byte[] bytes = System.Text.Encoding.UTF8.GetBytes(json);
                    stream.Write(bytes, 0, bytes.Length);
                    stream.Flush(true);
                }
                if (File.Exists(storagePath)) File.Replace(storagePath + ".tmp", storagePath, storagePath + ".bak");
                else File.Move(storagePath + ".tmp", storagePath);
                layoutSavePending = false;
                StorageDetail = "";
            }
            catch (Exception error) when (error is IOException || error is UnauthorizedAccessException || error is ArgumentException)
            { StorageDetail = "시각화 저장 실패 · " + error.Message; }
        }

        void RestoreLayout()
        {
            if (storagePath == null || baseLink == null || instancesById.Count != 0 ||
                !Finite(SpawnRoot.lossyScale) || SpawnRoot.lossyScale.x <= 0f || SpawnRoot.lossyScale.y <= 0f || SpawnRoot.lossyScale.z <= 0f) return;
            SavedLayout saved = null;
            foreach (string path in new[] { storagePath, storagePath + ".bak" })
            {
                if (!File.Exists(path)) continue;
                try
                {
                    if (new FileInfo(path).Length > 8 * 1024 * 1024) throw new FormatException("저장 크기 초과");
                    var candidate = JsonUtility.FromJson<SavedLayout>(File.ReadAllText(path));
                    if (candidate == null || candidate.Version != 1 || candidate.Parts == null || candidate.Parts.Count > 1024 ||
                        candidate.Observations == null || candidate.Observations.Count > 16384)
                        throw new FormatException("저장 형식 불일치");
                    var ids = new HashSet<string>(StringComparer.Ordinal);
                    foreach (SavedPart part in candidate.Parts)
                    {
                        if (part == null || string.IsNullOrWhiteSpace(part.Id) || !ids.Add(part.Id) || part.Type == null ||
                            !bindingsByType.TryGetValue(part.Type, out PrefabBinding binding) || binding.Prefab == null ||
                            !Finite(part.Position) || !Finite(part.Scale) || part.Scale.x <= 0f || part.Scale.y <= 0f || part.Scale.z <= 0f ||
                            !Finite(part.Rotation)) throw new FormatException("저장 부품 또는 프리팹 불일치");
                        if (!part.HasAttachment) part.Attachment = null;
                        Attachment record = part.Attachment;
                        if (record != null && (!Guid.TryParse(record.Job, out _) || !Guid.TryParse(record.Server, out _) ||
                            !Guid.TryParse(record.PickOperation, out _) || record.Sequence < 0 ||
                            record.State is not ("reserved" or "attached" or "placed") ||
                            record.Registration != part.Registration || string.IsNullOrWhiteSpace(record.Slot) ||
                            !Finite(record.LocalPosition) || !Finite(record.LocalRotation)))
                            throw new FormatException("저장 부착 정보 불일치");
                    }
                    foreach (SavedObservation observation in candidate.Observations)
                        if (observation == null || !ids.Contains(observation.Source ?? "") ||
                            string.IsNullOrWhiteSpace(observation.Registration) || string.IsNullOrWhiteSpace(observation.Observation))
                            throw new FormatException("저장 관측 정보 불일치");
                    saved = candidate;
                    break;
                }
                catch (Exception error) when (error is IOException || error is UnauthorizedAccessException ||
                    error is ArgumentException || error is FormatException)
                { StorageDetail = "저장 화면 복원 미확인 · " + error.Message; }
            }
            if (saved == null) return;
            registration = saved.Registration;
            foreach (SavedPart part in saved.Parts)
            {
                GameObject instance = Instantiate(bindingsByType[part.Type].Prefab, SpawnRoot);
                instance.name = part.Id;
                instance.transform.SetPositionAndRotation(baseLink.TransformPoint(part.Position), baseLink.rotation * part.Rotation);
                Vector3 parentScale = SpawnRoot.lossyScale;
                instance.transform.localScale = new Vector3(part.Scale.x / parentScale.x, part.Scale.y / parentScale.y, part.Scale.z / parentScale.z);
                instancesById.Add(part.Id, instance);
                instanceRegistrations.Add(part.Id, part.Registration);
                instanceTypes.Add(part.Id, part.Type);
                if (part.Attachment != null)
                {
                    part.Attachment.Uncertain = true;
                    part.Attachment.Restored = true;
                    attachments.Add(part.Id, part.Attachment);
                }
            }
            foreach (SavedObservation observation in saved.Observations)
                observations.Add((observation.Registration, observation.Observation, observation.Source));
            hasUnverifiedRestoredLayout = saved.Parts.Count > 0;
            needsStatusReconciliation = true;
            SyncDetail = "◌ 저장 화면 · 현재 상태 확인 중 (" + saved.SavedUtc + ")";
            SetProgress(ProgressState.Preparing, "저장된 마지막 배치 · 실물 확인 전");
        }

        static bool Finite(Vector3 value) => IsFinite(value.x) && IsFinite(value.y) && IsFinite(value.z);
        static bool Finite(Quaternion value) => IsFinite(value.x) && IsFinite(value.y) && IsFinite(value.z) &&
            IsFinite(value.w) && Mathf.Abs(Quaternion.Dot(value, value) - 1f) < 0.01f;

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

            // Detector absence is not physical removal. Keep the original scene and
            // identity through gripper occlusion, partial frames and re-registration.
            if (poses.Count == 0)
            {
                SetProgress(ProgressState.Preparing, "검출 부품 없음 · 이전 배치 유지");
                return;
            }
            if (error == null && attachments.Count == 0 && poses.Count <= MaxCandidateParts &&
                !string.IsNullOrWhiteSpace(state.tray_registration_id) && !string.IsNullOrWhiteSpace(state.source_observation_id))
            {
                var key = (state.tray_registration_id, state.source_observation_id);
                // Repeated delivery of one observation must not replace its original pose.
                if (!candidates.ContainsKey(key))
                {
                    while (candidateOrder.Count >= MaxCandidateObservations || candidatePartCount + poses.Count > MaxCandidateParts)
                    {
                        var oldest = candidateOrder.Dequeue();
                        candidatePartCount -= candidates[oldest].Count;
                        candidates.Remove(oldest);
                    }
                    candidates.Add(key, poses);
                    candidateOrder.Enqueue(key);
                    candidatePartCount += poses.Count;
                }
            }
            latestPoses = poses;
            latestRegistration = state.tray_registration_id;
            latestObservation = state.source_observation_id;
            latestCandidateTime = Time.realtimeSinceStartupAsDouble;
            if (instancesById.Count > 0 && registration != state.tray_registration_id)
            {
                SetProgress(ProgressState.Preparing, "트레이 등록 세대 변경 · 기존 배치 유지 · 명시적 재생성 필요");
                return;
            }
            if (attachments.Count > 0 || hasUnverifiedRestoredLayout)
            {
                SetProgress(ProgressState.Preparing, "로봇 실행 배치 고정 · 관측으로 부품을 변경하지 않음");
                return;
            }
            if (!hasSequence || state.sequence != lastSequence)
            {
                registration = state.tray_registration_id;
                Apply(poses);
                if (!string.IsNullOrWhiteSpace(registration) && !string.IsNullOrWhiteSpace(state.source_observation_id))
                    foreach (PartPose pose in poses)
                        if (observations.Count < 16384 && !pose.Id.StartsWith("display-only:", StringComparison.Ordinal))
                            observations.Add((registration, state.source_observation_id, pose.Id));
                layoutSavePending = true;
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
                // 채우거나 생산 요청에 전달하지 않는다. 임시 객체도 명시적 재생성 전까지 유지한다.
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

        void PrepareExecutionObservation(string selectedRegistration, string selectedObservation,
            string sourceId, string partId, List<PartPose> poses)
        {
            PartPose selected = poses.Find(pose => pose.Id == sourceId);
            if (selected == null || PartCode(selected.Binding.PartType) != partId)
                throw new FormatException("실행 관측에 해당 부품 없음 · 배치 변경 차단");
            foreach (PartPose pose in poses)
                if (pose.Binding.Prefab == null ||
                    (instanceTypes.TryGetValue(pose.Id, out string existingType) && existingType != pose.Binding.PartType))
                    throw new FormatException("실행 관측 프리팹·부품 종류 불일치 · 배치 변경 차단");

            // Only an unowned display may be replaced. Keep matching objects and
            // remove surplus display parts without touching boards or other owners.
            var selectedIds = new HashSet<string>();
            foreach (PartPose pose in poses) selectedIds.Add(pose.Id);
            var obsolete = new List<string>();
            foreach (var pair in instancesById)
                if (!selectedIds.Contains(pair.Key)) obsolete.Add(pair.Key);
            foreach (string id in obsolete)
            {
                if (instancesById[id] != null)
                {
                    instancesById[id].SetActive(false);
                    Destroy(instancesById[id]);
                }
                instancesById.Remove(id);
                instanceRegistrations.Remove(id);
                instanceTypes.Remove(id);
            }
            registration = selectedRegistration;
            Apply(poses);
            observations.Clear();
            foreach (PartPose pose in poses)
                if (!pose.Id.StartsWith("display-only:", StringComparison.Ordinal))
                    observations.Add((selectedRegistration, selectedObservation, pose.Id));
            hasUnverifiedRestoredLayout = false;
            needsStatusReconciliation = false;
            candidates.Clear();
            candidateOrder.Clear();
            candidatePartCount = 0;
            LastAppliedTime = Time.realtimeSinceStartupAsDouble;
            SetProgress(ProgressState.Applied, "실행 관측 배치 준비 완료 · Pick 기준 고정");
        }

        void Apply(List<PartPose> poses)
        {
            if (attachments.Count > 0) return;
            foreach (PartPose pose in poses)
            {
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

            // Only explicit recreation removes objects. An empty/partial detector
            // list is not authoritative evidence that a physical part disappeared.
        }

        [ContextMenu("Recreate Parts From Latest Calibration")]
        void RecreatePartsFromLatestCalibration()
        {
            if (!Application.isPlaying || latestPoses == null || latestPoses.Count == 0 ||
                Time.realtimeSinceStartupAsDouble - latestCandidateTime > 3d)
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
                if (instance != null)
                {
                    instance.SetActive(false);
                    Destroy(instance);
                }

            instancesById.Clear();
            instanceRegistrations.Clear();
            instanceTypes.Clear();
            observations.Clear();
            registration = latestRegistration;
            Apply(latestPoses);
            if (!string.IsNullOrWhiteSpace(registration) && !string.IsNullOrWhiteSpace(latestObservation))
                foreach (PartPose pose in latestPoses)
                    if (!pose.Id.StartsWith("display-only:", StringComparison.Ordinal))
                        observations.Add((registration, latestObservation, pose.Id));
            hasSequence = false;
            LastAppliedTime = Time.realtimeSinceStartupAsDouble;
            hasUnverifiedRestoredLayout = false;
            SaveLayout();
            SetProgress(ProgressState.Applied, "명시적 트레이 재생성 완료");
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
