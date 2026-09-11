using System;
using Newtonsoft.Json.Linq;
using RosMessageTypes.Std;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

/// Explicit UI calls only: enabling/reconnecting this component never starts motion.
/// Actual joints arrive separately; phase completion is not inspection PASS.
public sealed class AssemblyCycleClient : MonoBehaviour
{
    private const string CommandTopic = "/real/assembly/command";
    private const string StateTopic = "/real/assembly/state";
    private const string EventTopic = "/real/assembly/event";
    private const string RobotTopic = "/real/assembly/robot_state";
    private ROSConnection ros;
    public string JobId { get; private set; }
    public string OperationId { get; private set; }
    public string RecipeRevision { get; private set; }
    public string Status { get; private set; }
    public bool HardwareEnabled { get; private set; }
    public event Action<JObject> StateChanged;
    public event Action<JObject> RequestRejected;
    public event Action<JObject> MeasuredRobotState;
    private float lastStateReceipt = float.NegativeInfinity;
    private bool startPending;

    private void Start()
    {
        ros = ROSConnection.GetOrCreateInstance();
        ros.RegisterPublisher<StringMsg>(CommandTopic);
        ros.Subscribe<StringMsg>(StateTopic, OnState);
        ros.Subscribe<StringMsg>(EventTopic, OnEvent);
        ros.Subscribe<StringMsg>(RobotTopic, OnRobot);
    }

    // Call only from the operator's explicit Start action, after preparing the cell.
    // sceneReady means empty board/gripper, all 25 parts restored, fixed jig and clear cell.
    public void StartAssembly(bool sceneReady, string profile = "full")
    {
        if (ros == null || !sceneReady || !HardwareEnabled || startPending ||
            Time.realtimeSinceStartup - lastStateReceipt > 2f ||
            string.IsNullOrEmpty(RecipeRevision) ||
            !(Status == "idle" || Status == "check_completed" || Status == "check_failed" || Status == "motion_complete_awaiting_physical_verification"))
            throw new InvalidOperationException("Reconcile current server state and prepare the cell before starting.");
        JobId = Guid.NewGuid().ToString(); OperationId = Guid.NewGuid().ToString();
        startPending = true;
        Publish(new JObject { ["schema"] = "fr5.assembly_cycle/v1", ["action"] = "assembly.start",
            ["job_id"] = JobId, ["operation_id"] = OperationId,
            ["recipe_revision"] = RecipeRevision, ["confirm_scene_ready"] = true, ["profile"] = profile });
    }

    public void RequestStop()
    {
        if (ros == null || string.IsNullOrEmpty(JobId) || string.IsNullOrEmpty(OperationId)) return;
        Publish(new JObject { ["schema"] = "fr5.assembly_cycle/v1", ["action"] = "assembly.stop",
            ["job_id"] = JobId, ["operation_id"] = OperationId });
        // Wait for server state. This is a stop request, not proof of physical stop.
    }

    private void Publish(JObject value) => ros.Publish(CommandTopic, new StringMsg(value.ToString(Newtonsoft.Json.Formatting.None)));

    private void OnState(StringMsg message)
    {
        try {
            JObject value = JObject.Parse(message.data);
            if ((string)value["schema"] != "fr5.assembly_cycle/v1") return;
            lastStateReceipt = Time.realtimeSinceStartup;
            RecipeRevision = (string)value["recipe_revision"];
            HardwareEnabled = (bool?)value["hardware_execution_enabled"] == true;
            // A latched pre-start idle state cannot clear a delivery-unknown request.
            if (startPending && (string)value["operation_id"] != OperationId) return;
            Adopt(value);
        } catch (Exception e) { Debug.LogWarning(e.Message); }
    }

    private void Adopt(JObject value)
    {
        Status = (string)value["status"];
        JobId = (string)value["job_id"]; OperationId = (string)value["operation_id"];
        startPending = false;
        StateChanged?.Invoke(value);
    }

    private void OnEvent(StringMsg message)
    {
        try {
            JObject value = JObject.Parse(message.data);
            if ((string)value["schema"] != "fr5.assembly_cycle/v1") return;
            if ((string)value["status"] == "request_rejected") { RequestRejected?.Invoke(value); return; }
            if ((string)value["operation_id"] == OperationId && (string)value["job_id"] == JobId) Adopt(value);
        } catch (Exception e) { Debug.LogWarning(e.Message); }
    }

    private void OnRobot(StringMsg message)
    {
        try {
            JObject value = JObject.Parse(message.data);
            if ((string)value["schema"] == "fr5.assembly_robot_state/v1") MeasuredRobotState?.Invoke(value);
        } catch (Exception e) { Debug.LogWarning(e.Message); }
    }

    private void OnDestroy()
    {
        if (ros == null) return;
        ros.Unsubscribe(StateTopic); ros.Unsubscribe(EventTopic); ros.Unsubscribe(RobotTopic);
    }
}
