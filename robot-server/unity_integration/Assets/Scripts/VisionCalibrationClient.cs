using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;
using RosMessageTypes.Std;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

/// Unity/Sequencer requests observations only. Does not move robot or conveyor.
public sealed class VisionCalibrationClient : MonoBehaviour
{
    [SerializeField] private string requestTopic = "/vision/unity/request";
    [SerializeField] private string responseTopic = "/vision/unity/response";
    [SerializeField] private string productCode = "printed_semiconductor_package_board";
    [SerializeField] private string productVersion = "assembly-r1";
    [SerializeField] private BoardVisionSynchronizer boardSynchronizer;
    public event Action<JObject> Completed;
    public event Action<string, string> Failed;
    private sealed class PendingRequest { public string Job; public string Action; public float Deadline; }
    private readonly Dictionary<string, PendingRequest> pending = new Dictionary<string, PendingRequest>();
    private ROSConnection ros;
    private void Awake()
    {
        ros = ROSConnection.GetOrCreateInstance();
        ros.RegisterPublisher<StringMsg>(requestTopic);
        ros.Subscribe<StringMsg>(responseTopic, OnResponse);
    }
    private void OnDestroy() { if (ros != null) ros.Unsubscribe(responseTopic); }
    private void Update()
    {
        var expired = new List<string>();
        foreach (var entry in pending)
            if (Time.realtimeSinceStartup >= entry.Value.Deadline) expired.Add(entry.Key);
        foreach (string id in expired)
        {
            pending.Remove(id);
            Failed?.Invoke("RESPONSE_TIMEOUT", "No calibration response within 15 seconds: " + id);
        }
    }
    public string GetTraySnapshot(string jobId) => Request("getTraySnapshot", jobId);
    public string GetBoardSnapshot(string jobId) => Request("getBoardSnapshot", jobId);
    public string CalibrateBoard(string jobId) => Request("calibrateBoard", jobId);
    private string Request(string action, string jobId)
    {
        if (string.IsNullOrWhiteSpace(jobId)) throw new ArgumentException("jobId required");
        if (pending.Count >= 16) throw new InvalidOperationException("Too many pending calibration requests");
        string id = Guid.NewGuid().ToString();
        JObject request = new JObject { ["request_id"] = id, ["job_id"] = jobId, ["action"] = action };
        if (action != "getTraySnapshot") { request["product_code"] = productCode; request["product_version"] = productVersion; }
        pending[id] = new PendingRequest { Job = jobId, Action = action, Deadline = Time.realtimeSinceStartup + 15f };
        ros.Publish(requestTopic, new StringMsg(request.ToString(Newtonsoft.Json.Formatting.None)));
        return id;
    }
    private void OnResponse(StringMsg message)
    {
        try
        {
            JObject response = JObject.Parse(message.data);
            string id = (string)response["request_id"];
            if ((string)response["schema"] != "fr5.unity.calibration_response/v1" || id == null ||
                !pending.TryGetValue(id, out PendingRequest job) || job.Job != (string)response["job_id"] ||
                job.Action != (string)response["action"]) return;
            pending.Remove(id);
            if ((bool?)response["success"] != true)
            { Failed?.Invoke((string)response["error_code"], (string)response["message"]); return; }
            JObject data = response["data"] as JObject;
            if ((string)data?["schema"] == "fr5.board.unity_state/v1" && boardSynchronizer != null)
                boardSynchronizer.ApplySnapshot(data);
            Completed?.Invoke(response);
        }
        catch (Exception error) { Failed?.Invoke("INVALID_RESPONSE", error.Message); }
    }
}
