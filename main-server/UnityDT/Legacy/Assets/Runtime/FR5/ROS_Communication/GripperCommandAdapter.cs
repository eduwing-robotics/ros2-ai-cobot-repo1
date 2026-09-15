// 그리퍼 위치 명령과 상태 문자열의 ROS 전송만 담당합니다.

using System;
using RosMessageTypes.Std;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

namespace FR5Mvp.RosCommunication
{
    /// <summary>그리퍼 위치 명령과 실행 상태의 ROS 전송 경계입니다.</summary>
    [AddComponentMenu("Robotics/FR5/ROS/Gripper Command Adapter")]
    [DisallowMultipleComponent]
    public sealed class GripperCommandAdapter : MonoBehaviour
    {
        [SerializeField] string requestTopic = "/fr5_unity/gripper_request";
        [SerializeField] string statusTopic = "/fr5_unity/gripper_status";

        ROSConnection connection;

        public string LastStatus { get; private set; } = "idle";
        public event Action<string> StatusReceived;

        void Awake() => connection = ROSConnection.GetOrCreateInstance();

        void Start()
        {
            connection.RegisterPublisher<Float64Msg>(requestTopic);
            connection.Subscribe<StringMsg>(statusTopic, ReceiveStatus);
        }

        void OnDestroy()
        {
            if (connection != null)
                connection.Unsubscribe(statusTopic);
        }

        /// <summary>그리퍼 기준 관절 위치를 미터 단위로 ROS 실행기에 발행합니다.</summary>
        public void SendCommand(float jointMeters)
        {
            LastStatus = "executing";
            connection.Publish(requestTopic, new Float64Msg(jointMeters));
        }

        void ReceiveStatus(StringMsg message)
        {
            LastStatus = message?.data ?? "error: empty gripper status";
            StatusReceived?.Invoke(LastStatus);
        }
    }
}
