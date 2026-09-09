// 역할: 기판 관측을 검증하고 ItemManager가 소유한 관측·Unit 기판의 슬롯 배치에 반영한다.

using System;
using System.Collections.Generic;
using MainUnity.Static;
using Newtonsoft.Json.Linq;
using RosMessageTypes.Std;
using Unity.Robotics.ROSTCPConnector;
using Unity.Robotics.ROSTCPConnector.ROSGeometry;
using UnityEngine;

namespace MainUnity.Runtime.Camera
{
    [DisallowMultipleComponent]
    public sealed class BoardPartCalibrator : MonoBehaviour
    {
        const string TopicName = "/vision/board/unity_state";
        const double ObservationLifetimeSeconds = 2.5d;
        const double StaleAfterSeconds = 3d;
        // 표시 전용 지수 보간의 시간 상수. 0.2초에 오차의 약 63%를 따라가며
        // 실제 기울기와 ROS 원본 자세는 유지한다. 로봇 제어 목표에는 사용하지 않는다.
        const float DisplaySmoothingSeconds = 0.2f;

        [Tooltip("트레이와 동일한 ROS 기준 Transform(최상위 ArticulationBody). 기준 계층의 스케일은 1이어야 합니다.")]
        [SerializeField] Transform baseLink;
        [SerializeField] ItemManager itemManager;
        [Tooltip("FLU→RUF 변환 후 기판 기준에서 모델 원점까지의 보정 거리(m). 슬롯 좌표에는 더하지 않습니다.")]
        [SerializeField] Vector3 modelPositionOffsetMeters;
        [Tooltip("FLU→RUF 변환 후 기판 기준에 대한 모델 축 보정(degree). 슬롯 자세에는 더하지 않습니다.")]
        [SerializeField] Vector3 modelRotationOffsetDegrees;

        internal enum ProgressState { Waiting, Preparing, Applied, Rejected, ConfigurationError }
        internal ProgressState Progress { get; private set; }
        internal string ProgressDetail { get; private set; } = "기판 좌표 수신 대기";
        internal double LastReceiveTime { get; private set; } = -1d;
        internal double LastAppliedTime { get; private set; } = -1d;
        internal string CalibrationId { get; private set; }
        internal event Action ProgressChanged;

        ROSConnection connection;
        Transform currentBoard;
        internal Transform AttachmentBoard => LastAppliedTime >= 0d ? currentBoard : null;
        readonly Dictionary<string, Transform> slots = new(StringComparer.Ordinal);
        Dictionary<string, Pose> targetSlotPoses;
        readonly Dictionary<string, Pose> displayedSlotPoses = new(StringComparer.Ordinal);
        Pose targetBoardPose;
        Pose displayedBoardPose;
        string publisherId;
        long lastSequence = -1;
        long lastFrame;
        bool waitingForNewFrame = true;

        void Start()
        {
            if (!ConfigurationValid())
            {
                SetProgress(ProgressState.ConfigurationError, "ROS 기준 Transform(scale 1), ItemManager와 모델 보정값 확인 필요");
                enabled = false;
                return;
            }
            connection = ROSConnection.GetOrCreateInstance();
            connection.Subscribe<StringMsg>(TopicName, ReceiveState);
        }

        void OnDisable()
        {
            itemManager?.ReleaseObservationBoard();
            currentBoard = null;
            slots.Clear();
            targetSlotPoses = null;
            displayedSlotPoses.Clear();
            LastAppliedTime = -1d;
            CalibrationId = null;
            waitingForNewFrame = true;
            if (Progress != ProgressState.ConfigurationError)
                SetProgress(ProgressState.Waiting, "기판 수신 비활성");
        }

        void OnDestroy()
        {
            if (connection != null) connection.Unsubscribe(TopicName);
        }

        void Update()
        {
            RefreshBoard();
            if (Progress == ProgressState.Applied &&
                Time.realtimeSinceStartupAsDouble - LastAppliedTime > StaleAfterSeconds)
                SetProgress(ProgressState.Preparing, "기판 관측 갱신 중단 · 이전 배치 유지");
            if (Progress == ProgressState.Applied && currentBoard != null && targetSlotPoses != null)
                ApplyDisplayPose(1f - Mathf.Exp(-Time.unscaledDeltaTime / DisplaySmoothingSeconds));
        }

        void RefreshBoard()
        {
            Transform board = itemManager != null ? itemManager.ObservationBoard : null;
            if (ReferenceEquals(board, currentBoard)) return;
            currentBoard = board;
            slots.Clear();
            targetSlotPoses = null;
            displayedSlotPoses.Clear();
            LastAppliedTime = -1d;
            CalibrationId = null;
            waitingForNewFrame = true;
            SetProgress(ProgressState.Waiting, board == null ? "유효한 기판 관측 대기" : "새 기판 관측 대기");
        }

        void ReceiveState(StringMsg message)
        {
            if (!isActiveAndEnabled) return;
            RefreshBoard();
            LastReceiveTime = Time.realtimeSinceStartupAsDouble;
            try
            {
                JObject state = JObject.Parse(message?.data ?? "");
                if ((string)state["schema"] != "fr5.board.unity_state/v1")
                    throw new FormatException("Unsupported board schema.");
                string publisher = (string)state["publisher_id"];
                if (string.IsNullOrWhiteSpace(publisher) || state["sequence"]?.Type != JTokenType.Integer)
                    throw new FormatException("Missing publisher or sequence.");
                long sequence = (long)state["sequence"];
                if (sequence < 0) throw new FormatException("Invalid sequence.");
                if (publisher == publisherId && sequence <= lastSequence) return;
                if (publisher != publisherId)
                {
                    lastFrame = 0;
                    waitingForNewFrame = true;
                }
                publisherId = publisher;
                lastSequence = sequence;
                if (state["valid"]?.Type != JTokenType.Boolean || state["stable"]?.Type != JTokenType.Boolean)
                    throw new FormatException("Missing observation validity or stability.");
                if (!(bool)state["valid"] || !(bool)state["stable"])
                {
                    SetProgress(ProgressState.Preparing, ((string)state["reason"] ?? "안정된 기판 관측 대기") +
                        (LastAppliedTime >= 0d ? " · 이전 배치 유지" : ""));
                    return;
                }
                if ((string)state["coordinate_frame"] != "base_link" || (string)state["position_units"] != "m" ||
                    (string)state["product_code"] != "printed_semiconductor_package_board" ||
                    (string)state["product_version"] != "assembly-r1")
                    throw new FormatException("Expected assembly-r1 board coordinates in base_link metres.");
                if (state["timestamp_ros_ns"]?.Type != JTokenType.Integer || state["published_ros_ns"]?.Type != JTokenType.Integer)
                    throw new FormatException("Missing observation or publication timestamp.");
                long frame = (long)state["timestamp_ros_ns"];
                long published = (long)state["published_ros_ns"];
                if (frame <= 0 || published < frame || (published - frame) / 1e9 > ObservationLifetimeSeconds)
                    throw new FormatException("Stale or invalid observation timestamp.");
                // 토픽에는 Unit ID가 없다. Unit 교체·publisher 재시작 후 첫 관측은 경계로만
                // 사용하고 그보다 새로운 원본 프레임을 기다린다. 이전 관측을 새 Unit에 복사하지 않는다.
                if (waitingForNewFrame)
                {
                    lastFrame = Math.Max(lastFrame, frame);
                    waitingForNewFrame = false;
                    SetProgress(ProgressState.Waiting, "새 원본 기판 프레임 대기");
                    return;
                }
                if (frame <= lastFrame) return;
                if (!ConfigurationValid()) throw new FormatException("Invalid board calibration configuration.");
                if (itemManager.ObservationAwaitingUnit && currentBoard == null)
                {
                    SetProgress(ProgressState.Waiting, "완료품 배치 유지 · 다음 Unit 확인 대기");
                    return;
                }
                itemManager.ValidateConfiguration();
                if (currentBoard != null && (!Finite(currentBoard.lossyScale) || currentBoard.lossyScale.x <= 0f ||
                    currentBoard.lossyScale.y <= 0f || currentBoard.lossyScale.z <= 0f))
                    throw new FormatException("Board scale must be finite and positive.");
                Vector3 boardPosition = Position(state["board_pose"]?["position_m"]);
                Quaternion boardRotation = Orientation(state["board_pose"]?["orientation_xyzw"]);

                if (slots.Count == 0)
                {
                    foreach (ItemManager.AssemblySlot group in itemManager.PrefabSlots)
                    {
                        if (group == null) throw new FormatException("Missing slot group.");
                        foreach (Transform template in group.Slots)
                        {
                            Transform slot = currentBoard != null ? currentBoard.Find(template.name) : template;
                            if (slot == null || (currentBoard != null && slot.parent != currentBoard) || !slots.TryAdd(slot.name, slot))
                                throw new FormatException("Slots must be unique children of the current board.");
                        }
                    }
                }
                JArray rows = state["slots"] as JArray;
                if (slots.Count != 25 || rows == null || rows.Count != slots.Count)
                    throw new FormatException("Expected the current board's 25 slots.");
                var pending = new Dictionary<string, Pose>(StringComparer.Ordinal);
                Quaternion worldRotation = baseLink.rotation * boardRotation;
                Vector3 worldPosition = baseLink.TransformPoint(boardPosition);
                foreach (JToken row in rows)
                {
                    if (row is not JObject) throw new FormatException("Invalid slot entry.");
                    string code = (string)row["slot_code"];
                    if (string.IsNullOrWhiteSpace(code) || !slots.TryGetValue(code, out Transform slot) ||
                        slot == null || (currentBoard != null && slot.parent != currentBoard))
                        throw new FormatException("Unknown or missing slot code.");
                    Vector3 position = Position(row["board_position_m"]);
                    Quaternion rotation = Orientation(row["board_orientation_xyzw"]);
                    if (!Finite(worldPosition + worldRotation * position) || !pending.TryAdd(code, new Pose(position, rotation)))
                        throw new FormatException("Invalid or duplicate slot pose.");
                }
                Vector3 modelPosition = worldPosition + worldRotation * modelPositionOffsetMeters;
                if (!Finite(modelPosition)) throw new FormatException("Non-finite board position.");
                string calibration = (string)state["calibration_id"];
                // 전부 검증한 다음 반영한다. 프리팹 스케일·계층은 유지하고 슬롯은 보정 완료된
                // 표면 중심의 월드 자세로 갱신한다. 모델 축/원점 보정이나 잔차를 슬롯에 다시 더하지 않는다.
                if (currentBoard == null)
                {
                    currentBoard = itemManager.EnsureObservationBoard();
                    slots.Clear();
                    foreach (string code in pending.Keys)
                        slots.Add(code, currentBoard.Find(code));
                }
                targetBoardPose = new Pose(worldPosition, worldRotation);
                targetSlotPoses = pending;
                // 최초 배치만 즉시 적용한다. Unit 교체 시 RefreshBoard에서 보간 이력을 비운다.
                if (LastAppliedTime < 0d)
                    ApplyDisplayPose(1f);
                lastFrame = frame;
                LastAppliedTime = Time.realtimeSinceStartupAsDouble;
                CalibrationId = calibration;
                SetProgress(ProgressState.Applied, "기판 자세 및 25개 슬롯 배치 반영됨");
            }
            catch (Exception error) when (error is Newtonsoft.Json.JsonException ||
                error is FormatException || error is InvalidCastException || error is ArgumentException ||
                error is InvalidOperationException || error is OverflowException)
            {
                slots.Clear();
                SetProgress(ProgressState.Rejected, error.Message +
                    (LastAppliedTime >= 0d ? " · 이전 배치 유지" : " · 유효한 배치 없음"));
            }
        }

        void ApplyDisplayPose(float blend)
        {
            // 기판 기준 자세를 한 번 보간하고 같은 기준으로 모든 슬롯을 재구성한다.
            // 월드 위치를 각각 보간하면 회전 도중 슬롯이 PCB 표면에서 어긋날 수 있다.
            foreach (string code in targetSlotPoses.Keys)
                if (!slots.TryGetValue(code, out Transform slot) || slot == null || slot.parent != currentBoard)
                {
                    SetProgress(ProgressState.Rejected, "기판 슬롯 연결 변경 · 이전 배치 유지");
                    return;
                }
            displayedBoardPose = new Pose(
                Vector3.Lerp(displayedBoardPose.position, targetBoardPose.position, blend),
                blend >= 1f ? targetBoardPose.rotation : Quaternion.Slerp(displayedBoardPose.rotation, targetBoardPose.rotation, blend));
            currentBoard.SetPositionAndRotation(
                displayedBoardPose.position + displayedBoardPose.rotation * modelPositionOffsetMeters,
                displayedBoardPose.rotation * Quaternion.Euler(modelRotationOffsetDegrees));
            foreach (var entry in targetSlotPoses)
            {
                Pose pose = entry.Value;
                if (displayedSlotPoses.TryGetValue(entry.Key, out Pose previous))
                    pose = new Pose(Vector3.Lerp(previous.position, pose.position, blend),
                        Quaternion.Slerp(previous.rotation, pose.rotation, blend));
                displayedSlotPoses[entry.Key] = pose;
                slots[entry.Key].SetPositionAndRotation(
                    displayedBoardPose.position + displayedBoardPose.rotation * pose.position,
                    displayedBoardPose.rotation * pose.rotation);
            }
        }

        bool ConfigurationValid() => baseLink != null && itemManager != null &&
            (baseLink.lossyScale - Vector3.one).sqrMagnitude <= 1e-8f &&
            Finite(modelPositionOffsetMeters) && Finite(modelRotationOffsetDegrees);

        static Vector3 Position(JToken token)
        {
            float[] values = Numbers(token, 3);
            return FLU.ConvertToRUF(new Vector3(values[0], values[1], values[2]));
        }

        static Quaternion Orientation(JToken token)
        {
            float[] values = Numbers(token, 4);
            double norm = Math.Sqrt((double)values[0] * values[0] + (double)values[1] * values[1] +
                (double)values[2] * values[2] + (double)values[3] * values[3]);
            if (norm < 1e-9) throw new FormatException("Zero quaternion.");
            return FLU.ConvertToRUF(new Quaternion((float)(values[0] / norm), (float)(values[1] / norm),
                (float)(values[2] / norm), (float)(values[3] / norm)));
        }

        static float[] Numbers(JToken token, int count)
        {
            if (token is not JArray array || array.Count != count)
                throw new FormatException("Incorrect pose array length.");
            var values = new float[count];
            for (int i = 0; i < count; i++)
            {
                if (array[i].Type != JTokenType.Integer && array[i].Type != JTokenType.Float)
                    throw new FormatException("Expected numeric pose values.");
                values[i] = (float)array[i];
                if (!float.IsFinite(values[i])) throw new FormatException("Non-finite pose value.");
            }
            return values;
        }

        static bool Finite(Vector3 value) =>
            float.IsFinite(value.x) && float.IsFinite(value.y) && float.IsFinite(value.z);

        void SetProgress(ProgressState state, string detail)
        {
            if (Progress == state && ProgressDetail == detail) return;
            Progress = state;
            ProgressDetail = detail;
            ProgressChanged?.Invoke();
        }
    }
}
