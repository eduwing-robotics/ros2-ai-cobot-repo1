// 책임: FAIRINO 그리퍼 명령의 입력 검증·안전 상태 확인·서비스 요청을 소유한다.
// 호출자는 목표 개도만 전달하며, ROS 서비스 세부사항을 알 필요가 없다.

using System;
using System.Globalization;
using MainUnity.Runtime.Robot.Status;
using RosMessageTypes.Fairino;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Real
{
    [DisallowMultipleComponent]
    public sealed class RealGripperRequest : MonoBehaviour
    {
        const int GripperId = 1;

        [SerializeField] string serviceName = "/fairino_remote_command_service";
        [SerializeField, Range(0, 100)] int openingPercent = 100;
        [SerializeField, Range(0, 100)] int speedPercent = 50;
        [SerializeField, Range(0, 100)] int forcePercent = 30;
        [SerializeField, Range(0, 30000)] int maxTimeMilliseconds = 3000;

        RobotStatusManager statusManager;

        bool requestInFlight;

        void Awake()
        {
            ROSConnection.GetOrCreateInstance()
                .RegisterRosService<RemoteCmdInterfaceRequest, RemoteCmdInterfaceResponse>(serviceName);
        }

        /// <summary>RealMaster가 공통 안전 상태 관리자를 주입한다.</summary>
        public void Initialize(RobotStatusManager injectedStatusManager) =>
            statusManager = injectedStatusManager;

        /// <summary>Inspector에 지정된 그리퍼 열림 비율(0~100%)을 요청한다.</summary>
        public bool TryRequestOpeningPercent() => TryRequestOpeningPercent(openingPercent);

        [ContextMenu("Request Gripper Opening")]
        void RequestOpeningFromContextMenu()
        {
            if (!TryRequestOpeningPercent())
                Debug.LogWarning("FAIRINO gripper request was rejected.", this);
        }

        /// <summary>그리퍼 열림 비율(0~100%)을 요청한다.</summary>
        public bool TryRequestOpeningPercent(float targetOpeningPercent)
        {
            if (!float.IsFinite(targetOpeningPercent) || targetOpeningPercent < 0f || targetOpeningPercent > 100f)
            {
                Debug.LogWarning("Gripper opening must be between 0 and 100 percent.", this);
                return false;
            }
            if (speedPercent < 0 || speedPercent > 100 || forcePercent < 0 || forcePercent > 100 ||
                maxTimeMilliseconds < 0 || maxTimeMilliseconds > 30000)
            {
                Debug.LogWarning("Gripper speed and force must be between 0 and 100 percent, and max time between 0 and 30000 milliseconds.", this);
                return false;
            }
            if (!TryPrepare(out _))
                return false;

            float opening = Mathf.Round(targetOpeningPercent);
            requestInFlight = true;
            string command = string.Format(CultureInfo.InvariantCulture,
                "MoveGripper({0},{1},{2},{3},{4},0,0,0,0,0)", GripperId, opening,
                speedPercent, forcePercent, maxTimeMilliseconds);
            Debug.Log("[FAIRINO] TX " + serviceName + ": " + command, this);
            RequestOpeningAsync(command);
            return true;
        }

        bool TryPrepare(out string error)
        {
            if (statusManager == null)
            {
                error = "RobotStatusManager is not assigned.";
                return false;
            }
            if (!statusManager.CanAcceptCommand(out error))
                return false;
            if (!Application.isPlaying)
            {
                error = "FAIRINO gripper requests require Play Mode.";
                return false;
            }
            if (requestInFlight)
            {
                error = "A FAIRINO gripper request is already in flight.";
                return false;
            }
            if (string.IsNullOrWhiteSpace(serviceName))
            {
                error = "FAIRINO service name must not be empty.";
                return false;
            }

            error = string.Empty;
            return true;
        }

        async void RequestOpeningAsync(string command)
        {
            try
            {
                RemoteCmdInterfaceResponse response = await ROSConnection.GetOrCreateInstance()
                    .SendServiceMessage<RemoteCmdInterfaceResponse>(serviceName,
                        new RemoteCmdInterfaceRequest(command));
                string value = response?.cmd_res ?? string.Empty;
                Debug.Log("[FAIRINO] RX " + serviceName + ": " + value, this);

                if (value != "0")
                    Debug.LogWarning("[FAIRINO] Gripper command returned: " + value, this);
            }
            catch (Exception exception)
            {
                Debug.LogError("[FAIRINO] Gripper request failed: " + exception.Message, this);
            }
            finally
            {
                requestInFlight = false;
            }
        }
    }
}
