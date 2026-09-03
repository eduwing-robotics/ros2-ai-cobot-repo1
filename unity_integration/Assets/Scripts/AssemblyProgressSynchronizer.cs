using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;
using RosMessageTypes.Std;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

/// Mirrors confirmed DB-backed assembly progress. This component never commands the robot.
public sealed class AssemblyProgressSynchronizer : MonoBehaviour
{
    [SerializeField] private string topic = "/assembly/progress";
    public string CycleId { get; private set; }
    public int CompletedCount { get; private set; }
    public int TotalCount { get; private set; }
    public string NextSlotCode { get; private set; }
    public event Action ProgressChanged;

    private readonly HashSet<string> assembledSlots = new HashSet<string>();
    private long lastSequence = -1;
    public IReadOnlyCollection<string> AssembledSlots => assembledSlots;

    private void Start() => ROSConnection.GetOrCreateInstance().Subscribe<StringMsg>(topic, OnMessage);
    private void OnDestroy() => ROSConnection.GetOrCreateInstance().Unsubscribe(topic);

    private void OnMessage(StringMsg message)
    {
        JObject state;
        try { state = JObject.Parse(message.data); }
        catch (Exception error) { Debug.LogWarning($"Invalid assembly progress JSON: {error.Message}"); return; }
        if ((string)state["schema"] != "fr5.assembly.progress/v1" || (bool?)state["valid"] != true) return;
        long sequence = (long?)state["sequence"] ?? -1;
        if (sequence <= lastSequence) return;
        lastSequence = sequence;
        CycleId = (string)state["cycle_id"];
        CompletedCount = (int?)state["completed_count"] ?? 0;
        TotalCount = (int?)state["total_count"] ?? 0;
        NextSlotCode = (string)state["next_step"]?["slot_code"];
        assembledSlots.Clear();
        if (state["assembled"] is JArray rows)
            foreach (JToken row in rows)
            {
                string slot = (string)row["slot_code"];
                if (!string.IsNullOrEmpty(slot)) assembledSlots.Add(slot);
            }
        ProgressChanged?.Invoke();
    }
}
