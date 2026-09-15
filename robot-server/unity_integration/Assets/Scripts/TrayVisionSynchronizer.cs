using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;
using RosMessageTypes.Std;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

/// <summary>
/// Mirrors the physical tray contents reported by the D435 detector.
/// Attach this component to the digital-twin tray root and configure one prefab per part type.
/// </summary>
public sealed class TrayVisionSynchronizer : MonoBehaviour
{
    [Serializable]
    public class PartPrefab
    {
        public string partType;
        public GameObject prefab;
        public Vector3 eulerOffset;
    }

    [Header("ROS")]
    [SerializeField] private string topic = "/vision/tray/unity_state";

    [Header("FR5 Base frame to Unity")]
    [Tooltip("Transform whose local origin represents FR5 Base (0,0,0).")]
    [SerializeField] private Transform baseFrameOrigin;
    [Tooltip("Unity metres per FR5 millimetre. Adjust signs to match the scene axes.")]
    [SerializeField] private Vector3 axisScale = new Vector3(0.001f, 0.001f, 0.001f);
    [Tooltip("Maps FR5 X,Y,Z to Unity local X,Z,Y by default.")]
    [SerializeField] private bool rosXyzToUnityXzy = true;
    [SerializeField] private PartPrefab[] partPrefabs;

    private readonly Dictionary<string, GameObject> instances = new Dictionary<string, GameObject>();
    private readonly Dictionary<string, PartPrefab> prefabByType = new Dictionary<string, PartPrefab>();
    private readonly Dictionary<string, int> currentCounts = new Dictionary<string, int>();
    private long lastSequence = -1;

    public IReadOnlyDictionary<string, int> CurrentCounts => currentCounts;

    private void Awake()
    {
        if (baseFrameOrigin == null) baseFrameOrigin = transform;
        foreach (PartPrefab entry in partPrefabs)
            if (entry != null && entry.prefab != null && !string.IsNullOrEmpty(entry.partType))
                prefabByType[entry.partType] = entry;
    }

    private void Start()
    {
        ROSConnection.GetOrCreateInstance().Subscribe<StringMsg>(topic, OnStateMessage);
    }

    private void OnDestroy()
    {
        ROSConnection.GetOrCreateInstance().Unsubscribe(topic);
    }

    private void OnStateMessage(StringMsg message)
    {
        JObject state;
        try { state = JObject.Parse(message.data); }
        catch (Exception error)
        {
            Debug.LogWarning($"Invalid tray state JSON: {error.Message}");
            return;
        }

        if ((string)state["schema"] != "fr5.tray.unity_state/v1" || (bool?)state["valid"] != true)
            return;

        long sequence = (long?)state["sequence"] ?? -1;
        if (sequence <= lastSequence) return;
        lastSequence = sequence;

        currentCounts.Clear();
        if (state["counts"] is JObject counts)
            foreach (JProperty item in counts.Properties()) currentCounts[item.Name] = (int)item.Value;

        var seen = new HashSet<string>();
        if (state["parts"] is JArray parts)
        {
            foreach (JToken part in parts)
            {
                string id = (string)part["id"];
                string type = (string)part["part_type"];
                JArray xyz = part["base_xyz_mm"] as JArray;
                if (string.IsNullOrEmpty(id) || string.IsNullOrEmpty(type) || xyz == null || xyz.Count != 3)
                    continue;
                if (!prefabByType.TryGetValue(type, out PartPrefab mapping)) continue;

                if (!instances.TryGetValue(id, out GameObject instance) || instance == null)
                {
                    instance = Instantiate(mapping.prefab, baseFrameOrigin);
                    instance.name = $"Vision_{id}";
                    instances[id] = instance;
                }

                float x = (float)xyz[0], y = (float)xyz[1], z = (float)xyz[2];
                Vector3 local = rosXyzToUnityXzy
                    ? new Vector3(x * axisScale.x, z * axisScale.z, y * axisScale.y)
                    : new Vector3(x * axisScale.x, y * axisScale.y, z * axisScale.z);
                instance.transform.localPosition = local;

                float angle = (float?)part["angle_base_deg"] ?? 0f;
                instance.transform.localRotation = Quaternion.Euler(mapping.eulerOffset) * Quaternion.AngleAxis(-angle, Vector3.up);
                seen.Add(id);
            }
        }

        var removed = new List<string>();
        foreach (KeyValuePair<string, GameObject> pair in instances)
            if (!seen.Contains(pair.Key)) removed.Add(pair.Key);
        foreach (string id in removed)
        {
            Destroy(instances[id]);
            instances.Remove(id);
        }
    }
}
