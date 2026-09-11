using System;
using RosMessageTypes.Std;
using RosMessageTypes.StdSrvs;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

public class ConveyorRosClient : MonoBehaviour
{
    [Serializable]
    public class Arrival
    {
        public string station;
        public string motion_id;
        public long timestamp_ns;
        public string basis;
    }

    [Serializable]
    public class ConveyorState
    {
        public int schema_version;
        public long timestamp_ns;
        public string state;
        public bool moving;
        public string target_station;
        public string completed_station;
        public string motion_id;
        public Arrival arrival;
        public string reason;
        public bool armed;
        public float command_linear_x_mps;
        public bool vision_ready;
        public bool vision_ready_fresh;
        public bool command_receiver_connected;
        public bool assembly_trigger;
        public bool inspection_trigger;
        public bool fr5_clear;
        public bool fr5_clear_fresh;
        public bool fr5_interlock_required;
    }

    public string LastState { get; private set; } = "DISCONNECTED";
    public string LastReason { get; private set; } = "No state received";
    public bool IsMoving { get; private set; }
    // Compatibility flag: true until a valid state arrives. The client no
    // longer turns a delayed state sample into a local conveyor FAULT.
    public bool ConnectionStale { get; private set; } = true;
    public Arrival LastArrival { get; private set; }

    ROSConnection ros;
    string lastArrivalId;
    string previousReceivedState;
    // Service response means accepted; these events mean vision-triggered HOLD.
    public event Action<string> AssemblyArrived;
    public event Action<string> InspectionArrived;

    void Start()
    {
        ros = ROSConnection.GetOrCreateInstance();
        ros.Subscribe<StringMsg>("/conveyor/state", OnState);
        ros.Subscribe<BoolMsg>("/conveyor/moving", msg => IsMoving = msg.data);
    }

    void OnState(StringMsg message)
    {
        ConveyorState state = JsonUtility.FromJson<ConveyorState>(message.data);
        if (state == null || state.schema_version != 1)
        {
            LastState = "FAULT";
            LastReason = "Unsupported conveyor state schema";
            return;
        }

        ConnectionStale = false;
        LastState = state.state;
        LastReason = state.reason;
        IsMoving = state.moving;
        LastArrival = state.arrival;
        string station = state.state == "ASSEMBLY_STOP" ? "assembly" :
            state.state == "INSPECTION_STOP" ? "inspection" : null;
        if (!state.moving && station != null)
        {
            string arrivalId = state.arrival != null ? state.arrival.motion_id : null;
            bool matched = state.arrival == null || state.arrival.station == station;
            bool freshEvent = !String.IsNullOrEmpty(arrivalId) ? arrivalId != lastArrivalId :
                previousReceivedState != state.state;
            if (matched && freshEvent)
            {
                lastArrivalId = arrivalId;
                if (station == "assembly") AssemblyArrived?.Invoke(arrivalId);
                else InspectionArrived?.Invoke(arrivalId);
            }
        }
        previousReceivedState = state.state;
    }

    public void MoveToAssembly()
    {
        CallTrigger("/conveyor/move_to_assembly");
    }

    public void MoveToInspection()
    {
        CallTrigger("/conveyor/move_to_inspection");
    }

    public void Stop()
    {
        CallTrigger("/conveyor/stop");
    }

    public void ResetController()
    {
        CallTrigger("/conveyor/reset");
    }

    void CallTrigger(string serviceName)
    {
        ros.SendServiceMessage<TriggerRequest, TriggerResponse>(
            serviceName,
            new TriggerRequest(),
            response => Debug.Log(
                $"{serviceName}: success={response.success}, {response.message}"));
    }
}
