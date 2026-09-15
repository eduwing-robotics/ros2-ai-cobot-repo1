using Newtonsoft.Json.Linq;
using UnityEngine;

/// Display-only actual robot model. Never assign the Ghost model or publish commands.
public sealed class AssemblyMeasuredRobotSynchronizer : MonoBehaviour
{
    [SerializeField] private AssemblyCycleClient client;
    [SerializeField] private ArticulationBody[] joints = new ArticulationBody[6];
    [SerializeField] private float[] jointSigns = { 1, 1, 1, 1, 1, 1 };
    [SerializeField] private float[] jointOffsetsDeg = new float[6];
    public bool StateFresh => latestWasFresh && Time.realtimeSinceStartup - lastReceived < 1f;
    public float GripperPosition { get; private set; }
    public bool GripperFeedbackValid { get; private set; }
    private bool latestWasFresh;
    private float lastReceived = float.NegativeInfinity;

    private void Start()
    {
        if (client == null || joints.Length != 6 || jointSigns.Length != 6 || jointOffsetsDeg.Length != 6)
        { Debug.LogError("Assign client and calibrated actual-model J1..J6."); enabled = false; return; }
        for (int i = 0; i < 6; i++)
            if (joints[i] == null || joints[i].jointType != ArticulationJointType.RevoluteJoint ||
                (jointSigns[i] != 1 && jointSigns[i] != -1) ||
                float.IsNaN(jointOffsetsDeg[i]) || float.IsInfinity(jointOffsetsDeg[i]))
            { Debug.LogError("Invalid actual-model joint calibration."); enabled = false; return; }
        client.MeasuredRobotState += Receive;
    }

    private void Receive(JObject value)
    {
        latestWasFresh = false;
        if ((bool?)value["state_fresh"] != true) return;
        JArray data = value["joints_deg"] as JArray;
        if (data == null || data.Count != 6) return;
        float[] targets = new float[6];
        for (int i = 0; i < 6; i++)
        {
            targets[i] = (float)data[i] * jointSigns[i] + jointOffsetsDeg[i];
            if (float.IsNaN(targets[i]) || float.IsInfinity(targets[i])) return;
        }
        for (int i = 0; i < 6; i++)
        {
            ArticulationDrive drive = joints[i].xDrive;
            drive.target = targets[i]; joints[i].xDrive = drive;
        }
        GripperPosition = (float?)value["gripper_position"] ?? 0f;
        GripperFeedbackValid = (bool?)value["gripper_feedback_valid"] == true;
        lastReceived = Time.realtimeSinceStartup; latestWasFresh = true;
    }

    private void OnDestroy()
    {
        if (client != null) client.MeasuredRobotState -= Receive;
    }
}
