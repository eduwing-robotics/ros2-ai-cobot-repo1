using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;
using RosMessageTypes.Std;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

/// Visual board frame and calibrated slot anchors. No robot commands.
public sealed class BoardVisionSynchronizer : MonoBehaviour
{
    [SerializeField] private string topic = "/vision/board/unity_state";
    [SerializeField] private Transform baseFrameOrigin;
    [SerializeField] private Transform boardFrame;
    [SerializeField] private bool rosXyzToUnityXzy = true;
    [Tooltip("Match signs used by TrayVisionSynchronizer. Units here are already metres.")]
    [SerializeField] private Vector3 axisSigns = Vector3.one;
    [SerializeField] private float staleAfterSeconds = 3f;
    public bool IsLive { get; private set; }
    public string CalibrationId { get; private set; }
    public string LastError { get; private set; }
    public event Action BoardUpdated;
    private string publisherId;
    private long lastSequence = -1;
    private float receivedAt;
    private readonly Dictionary<string, Transform> slots = new Dictionary<string, Transform>();
    public IReadOnlyDictionary<string, Transform> Slots => slots;

    private void Start()
    {
        if (baseFrameOrigin == null || boardFrame == null || baseFrameOrigin == boardFrame ||
            (Mathf.Abs(axisSigns.x) != 1) || (Mathf.Abs(axisSigns.y) != 1) || (Mathf.Abs(axisSigns.z) != 1))
        { Debug.LogError("Assign distinct FR5 Base and board-frame transforms; axis signs must be +/-1."); enabled = false; return; }
        ROSConnection.GetOrCreateInstance().Subscribe<StringMsg>(topic, OnMessage);
    }
    private void OnDestroy() { if (enabled) ROSConnection.GetOrCreateInstance().Unsubscribe(topic); }
    private void Update() { if (Time.realtimeSinceStartup - receivedAt > staleAfterSeconds) IsLive = false; }

    private void OnMessage(StringMsg message)
    {
        try
        {
            JObject state = JObject.Parse(message.data);
            string id = (string)state["publisher_id"];
            long sequence = (long?)state["sequence"] ?? -1;
            if (id == publisherId && sequence <= lastSequence) return;
            publisherId = id; lastSequence = sequence;
            ApplySnapshot(state);
        }
        catch (Exception error) { IsLive = false; LastError = error.Message; }
    }

    private static double[] Numbers(JToken value, int count)
    {
        JArray array = value as JArray;
        if (array == null || array.Count != count) throw new FormatException("Incorrect pose array length");
        double[] result = new double[count];
        for (int i = 0; i < count; i++)
        {
            result[i] = (double)array[i];
            if (double.IsNaN(result[i]) || double.IsInfinity(result[i])) throw new FormatException("Non-finite coordinate");
        }
        return result;
    }
    private Vector3 Position(JToken value)
    {
        double[] p = Numbers(value, 3);
        Vector3 result = new Vector3((float)p[0] * axisSigns.x, (float)p[1] * axisSigns.y, (float)p[2] * axisSigns.z);
        return rosXyzToUnityXzy ? new Vector3(result.x, result.z, result.y) : result;
    }
    private Quaternion Orientation(JToken value)
    {
        double[] q = Numbers(value, 4);
        double norm = Math.Sqrt(q[0]*q[0]+q[1]*q[1]+q[2]*q[2]+q[3]*q[3]);
        if (norm < 1e-9) throw new FormatException("Zero quaternion");
        // Basis change R_unity = S R_ros S^-1, including reflected handedness.
        float determinant = axisSigns.x * axisSigns.y * axisSigns.z * (rosXyzToUnityXzy ? -1 : 1);
        Vector3 v = new Vector3((float)(q[0]/norm)*axisSigns.x, (float)(q[1]/norm)*axisSigns.y, (float)(q[2]/norm)*axisSigns.z);
        if (rosXyzToUnityXzy) v = new Vector3(v.x, v.z, v.y);
        return new Quaternion(determinant*v.x, determinant*v.y, determinant*v.z, (float)(q[3]/norm));
    }
    public void ApplySnapshot(JObject state)
    {
        if ((string)state["schema"] != "fr5.board.unity_state/v1" ||
            (bool?)state["valid"] != true || (bool?)state["stable"] != true)
        { IsLive = false; LastError = (string)state["reason"] ?? "Waiting for stable board"; return; }
        if ((string)state["coordinate_frame"] != "base_link" || (string)state["position_units"] != "m")
            throw new FormatException("Expected base_link metres");
        Vector3 position = Position(state["board_pose"]?["position_m"]);
        Quaternion rotation = Orientation(state["board_pose"]?["orientation_xyzw"]);
        JArray rows = state["slots"] as JArray;
        if (rows == null || rows.Count != 25) throw new FormatException("Expected 25 slots");
        var pending = new Dictionary<string, KeyValuePair<Vector3, Quaternion>>();
        foreach (JToken row in rows)
        {
            string code = (string)row["slot_code"];
            if (string.IsNullOrEmpty(code) || pending.ContainsKey(code)) throw new FormatException("Invalid slot ID");
            pending.Add(code, new KeyValuePair<Vector3, Quaternion>(Position(row["board_position_m"]), Orientation(row["board_orientation_xyzw"])));
        }
        // This component owns the board frame, not the visual mesh child/scale.
        boardFrame.SetParent(baseFrameOrigin, false);
        boardFrame.localPosition = position; boardFrame.localRotation = rotation; boardFrame.localScale = Vector3.one;
        foreach (var entry in pending)
        {
            if (!slots.TryGetValue(entry.Key, out Transform anchor) || anchor == null)
            {
                anchor = new GameObject("VisionSlot_" + entry.Key).transform;
                anchor.SetParent(boardFrame, false); slots[entry.Key] = anchor;
            }
            anchor.localPosition = entry.Value.Key; anchor.localRotation = entry.Value.Value;
        }
        CalibrationId = (string)state["calibration_id"]; IsLive = true; LastError = "";
        receivedAt = Time.realtimeSinceStartup; BoardUpdated?.Invoke();
    }
}
