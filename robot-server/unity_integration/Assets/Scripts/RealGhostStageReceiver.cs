using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;
using RosMessageTypes.Std;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

/// Attach only to a visual Ghost instance. Never publishes robot commands.
public sealed class RealGhostStageReceiver : MonoBehaviour
{
    [SerializeField] private string topic = "/real/ghost/stage_target";
    [SerializeField] private ArticulationBody[] ghostJoints = new ArticulationBody[6];
    [SerializeField] private float[] jointSigns = { 1, 1, 1, 1, 1, 1 };
    [SerializeField] private float[] jointOffsetsDeg = new float[6];
    [SerializeField] private float previewSpeedDegPerSec = 90f;
    public string OperationId { get; private set; }
    public string Phase { get; private set; }
    public string TargetId { get; private set; }
    public bool TargetValid { get; private set; }
    public string ExecutionId { get; private set; }
    private string serverInstance;
    private long targetSequence = -1;
    private readonly HashSet<string> retiredInstances = new HashSet<string>();
    public event Action<string, string> StageChanged;
    private float[] targets;
    private long lastStamp = -1;
    private bool subscribed;

    private void Start()
    {
        if (ghostJoints.Length != 6 || jointSigns.Length != 6 || jointOffsetsDeg.Length != 6)
        { Debug.LogError("Ghost needs six joints, signs and offsets."); enabled = false; return; }
        for (int i = 0; i < 6; i++)
            if (ghostJoints[i] == null || ghostJoints[i].jointType != ArticulationJointType.RevoluteJoint ||
                (jointSigns[i] != 1 && jointSigns[i] != -1) ||
                float.IsNaN(jointOffsetsDeg[i]) || float.IsInfinity(jointOffsetsDeg[i]))
            { Debug.LogError("Assign only calibrated Ghost revolute joints J1..J6."); enabled = false; return; }
        if (float.IsNaN(previewSpeedDegPerSec) || float.IsInfinity(previewSpeedDegPerSec) || previewSpeedDegPerSec <= 0)
        { enabled = false; return; }
        ROSConnection.GetOrCreateInstance().Subscribe<StringMsg>(topic, OnMessage);
        subscribed = true;
    }

    private void OnDestroy()
    {
        if (subscribed) ROSConnection.GetOrCreateInstance().Unsubscribe(topic);
    }

    private void OnMessage(StringMsg message)
    {
        try
        {
            JObject data = JObject.Parse(message.data);
            if ((string)data["schema"] != "fr5.ghost_stage_target/v1" ||
                (bool?)data["visualization_only"] != true) return;
            long stamp = (long)data["timestamp_ros_ns"];
            string targetId = (string)data["target_id"];
            string instance = (string)data["server_instance_id"];
            long? sequence = (long?)data["target_sequence"];
            bool ordered = !string.IsNullOrEmpty(instance) && sequence.HasValue;
            if (string.IsNullOrEmpty(targetId)) return;
            if (ordered)
            {
                if (retiredInstances.Contains(instance) || sequence.Value < 1 ||
                    (instance == serverInstance && sequence.Value <= targetSequence)) return;
            }
            else if (serverInstance != null || stamp < lastStamp || targetId == TargetId) return;
            if (ordered && (string)data["target_state"] == "invalid")
            {
                AcceptVersion(instance, sequence.Value);
                targets = null; TargetValid = false; TargetId = targetId;
                return;
            }
            if (ordered && (string)data["target_state"] != "valid") return;
            JArray names = data["joint_names"] as JArray;
            JArray radians = data["positions_rad"] as JArray;
            if (names == null || names.Count != 6 || radians == null || radians.Count != 6) return;
            float[] next = new float[6];
            for (int i = 0; i < 6; i++)
            {
                if ((string)names[i] != $"j{i + 1}") return;
                double value = (double)radians[i];
                if (double.IsNaN(value) || double.IsInfinity(value)) return;
                next[i] = (float)(value * 180.0 / Math.PI) * jointSigns[i] + jointOffsetsDeg[i];
                if (float.IsNaN(next[i]) || float.IsInfinity(next[i])) return;
            }
            if (ordered) AcceptVersion(instance, sequence.Value);
            lastStamp = stamp; targets = next; TargetId = targetId; TargetValid = true;
            ExecutionId = (string)data["execution_id"];
            OperationId = (string)data["operation_id"]; Phase = (string)data["phase"];
            StageChanged?.Invoke(OperationId, Phase);
        }
        catch (Exception error) { Debug.LogWarning($"Invalid Ghost stage: {error.Message}"); }
    }

    private void AcceptVersion(string instance, long sequence)
    {
        if (serverInstance != null && serverInstance != instance) retiredInstances.Add(serverInstance);
        serverInstance = instance; targetSequence = sequence;
    }

    private void Update()
    {
        if (targets == null) return;
        for (int i = 0; i < 6; i++)
        {
            ArticulationDrive drive = ghostJoints[i].xDrive;
            drive.target = Mathf.MoveTowards(drive.target, targets[i], previewSpeedDegPerSec * Time.deltaTime);
            ghostJoints[i].xDrive = drive;
        }
    }
}
