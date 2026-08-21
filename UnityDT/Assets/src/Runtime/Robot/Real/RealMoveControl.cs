// 책임: FAIRINO 이동 명령의 입력 검증·안전 상태 확인·서비스 요청을 소유한다.
// 호출자는 Unity 월드 Pose만 전달하며, 좌표 변환과 ROS 세부사항을 알 필요가 없다.

using System;
using System.Globalization;
using System.Threading.Tasks;
using MainUnity.Runtime.Robot.Status;
using RosMessageTypes.Fairino;
using Unity.Robotics.ROSTCPConnector;
using Unity.Robotics.ROSTCPConnector.ROSGeometry;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Real
{
    [DisallowMultipleComponent]
    public sealed class RealMoveControl : MonoBehaviour
    {
        [SerializeField] string serviceName = "/fairino_remote_command_service";
        [Header("Target")]
        [SerializeField] Transform target;
        [Tooltip("Target이 비어 있을 때 사용할 FAIRINO 좌표계 위치(mm).")]
        [SerializeField] Vector3 positionMillimeters;
        [SerializeField] Vector3 rotationDegrees = new(180f, 0f, 0f);
        [Header("Motion")]
        [SerializeField, Min(1)] int pointIndex = 1;
        [SerializeField, Range(1, 100)] int speedPercent = 20;
        [SerializeField, Range(0, 14)] int tool;
        [SerializeField, Range(0, 14)] int user;
        [SerializeField, Range(0, 100)] float accelerationPercent = 100f;
        [SerializeField, Range(0, 100)] float overridePercent = 100f;
        [SerializeField] float blendTimeMilliseconds = -1f;
        [SerializeField, Range(-1, 7)] int configuration = -1;

        Transform robotBase;
        RobotStatusManager statusManager;
        bool requestInFlight;

        void Awake() => ROSConnection.GetOrCreateInstance()
            .RegisterRosService<RemoteCmdInterfaceRequest, RemoteCmdInterfaceResponse>(serviceName);

        /// <summary>RealMaster가 Unity 로봇 루트를 주입해 Target 좌표를 FAIRINO 좌표계로 변환한다.</summary>
        public void Initialize(ArticulationBody articulationRoot, RobotStatusManager injectedStatusManager)
        {
            robotBase = articulationRoot != null ? articulationRoot.transform : null;
            statusManager = injectedStatusManager;
        }

        /// <summary>Target 또는 Inspector의 좌표로 AIO CARTPoint와 MoveJ를 순서대로 요청한다.</summary>
        public bool TryRequestMoveJ() => TryRequest(moveJ: true);

        /// <summary>Target 또는 Inspector의 좌표로 AIO MoveCart를 요청한다.</summary>
        public bool TryRequestMoveCart() => TryRequest(moveJ: false);

        /// <summary>Unity 월드 TCP 목표로 AIO CARTPoint와 MoveJ를 요청한다.</summary>
        public bool TryRequestMoveJ(Pose target)
        {
            if (robotBase == null)
            {
                Debug.LogWarning("FAIRINO MoveJ requires an initialized robot base.", this);
                return false;
            }

            Vector3 basePosition = robotBase.InverseTransformPoint(target.position);
            Vector3 position = FLU.ConvertFromRUF(basePosition) * 1000f;
            Vector3 rotation = rotationDegrees;

            // TODO: FAIRINO의 전체 RPY 축 매핑이 확정되면 현재 yaw->Z 변환을 확장한다.
            rotation.z = target.rotation.eulerAngles.y;
            return TryRequest(moveJ: true, position, rotation);
        }

        /// <summary>Inspector Context Menu에서 MoveJ 요청을 실행한다.</summary>

        [ContextMenu("Request MoveJ")]
        void RequestMoveJFromContextMenu()
        {
            if (!TryRequestMoveJ())
                Debug.LogWarning("FAIRINO MoveJ request was rejected.", this);
        }

        /// <summary>Inspector Context Menu에서 MoveCart 요청을 실행한다.</summary>

        [ContextMenu("Request MoveCart")]
        void RequestMoveCartFromContextMenu()
        {
            if (!TryRequestMoveCart())
                Debug.LogWarning("FAIRINO MoveCart request was rejected.", this);
        }

        bool TryRequest(bool moveJ)
        {
            if (!TryGetTargetPose(out Vector3 position, out Vector3 rotation))
                return false;

            return TryRequest(moveJ, position, rotation);
        }

        bool TryRequest(bool moveJ, Vector3 position, Vector3 rotation)
        {
            if (!IsValid(position, 10000f) || !IsValid(rotation, 360f) || pointIndex < 1)
            {
                Debug.LogWarning("FAIRINO target pose is outside the supported range.", this);
                return false;
            }
            if (!TryPrepare(out _))
                return false;

            requestInFlight = true;
            RequestAsync(moveJ, position, rotation);
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
                error = "FAIRINO requests require Play Mode.";
                return false;
            }
            if (requestInFlight)
            {
                error = "A FAIRINO move request is already in flight.";
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

        async void RequestAsync(bool moveJ, Vector3 position, Vector3 rotation)
        {
            try
            {
                if (moveJ)
                {
                    string pointCommand = string.Format(CultureInfo.InvariantCulture,
                        "CARTPoint({0},{1},{2},{3},{4},{5},{6})",
                        pointIndex, position.x, position.y, position.z,
                        rotation.x, rotation.y, rotation.z);
                    if (!await SendCommand(pointCommand))
                        return;

                    string moveJCommand = string.Format(CultureInfo.InvariantCulture,
                        "MoveJ(CART{0},{1},{2},{3})",
                        pointIndex, speedPercent, tool, user);
                    await SendCommand(moveJCommand);
                    return;
                }

                string moveCartCommand = string.Format(CultureInfo.InvariantCulture,
                    "MoveCart({0},{1},{2},{3},{4},{5},{6},{7},{8},{9},{10},{11},{12})",
                    position.x, position.y, position.z,
                    rotation.x, rotation.y, rotation.z,
                    tool, user, speedPercent, accelerationPercent,
                    overridePercent, blendTimeMilliseconds, configuration);
                await SendCommand(moveCartCommand);
            }
            catch (Exception exception)
            {
                Debug.LogError("[FAIRINO] Move request failed: " + exception.Message, this);
            }
            finally
            {
                requestInFlight = false;
            }
        }

        async Task<bool> SendCommand(string command)
        {
            Debug.Log("[FAIRINO] TX " + serviceName + ": " + command, this);
            RemoteCmdInterfaceResponse response = await ROSConnection.GetOrCreateInstance()
                .SendServiceMessage<RemoteCmdInterfaceResponse>(serviceName,
                    new RemoteCmdInterfaceRequest(command));
            string value = response?.cmd_res ?? string.Empty;
            Debug.Log("[FAIRINO] RX " + serviceName + ": " + value, this);
            if (value == "0")
                return true;

            Debug.LogWarning("[FAIRINO] Move command returned: " + value, this);
            return false;
        }

        bool TryGetTargetPose(out Vector3 position, out Vector3 rotation)
        {
            position = positionMillimeters;
            rotation = rotationDegrees;
            if (target != null)
            {
                if (robotBase == null)
                {
                    Debug.LogWarning("FAIRINO target requires an initialized robot base.", this);
                    return false;
                }

                Vector3 basePosition = robotBase.InverseTransformPoint(target.position);
                position = FLU.ConvertFromRUF(basePosition) * 1000f;
                rotation.z = target.rotation.eulerAngles.y;
            }

            if (!IsValid(position, 10000f) || !IsValid(rotation, 360f) || pointIndex < 1)
            {
                Debug.LogWarning("FAIRINO target pose is outside the supported range.", this);
                return false;
            }
            return true;
        }

        static bool IsValid(Vector3 value, float maximum) =>
            float.IsFinite(value.x) && float.IsFinite(value.y) && float.IsFinite(value.z) &&
            Mathf.Abs(value.x) <= maximum && Mathf.Abs(value.y) <= maximum &&
            Mathf.Abs(value.z) <= maximum;

#if UNITY_EDITOR
        [ContextMenu("Self Check Move Input")]
        void SelfCheckMoveInput()
        {
            Debug.Assert(IsValid(Vector3.zero, 1f) && !IsValid(new Vector3(float.NaN, 0f, 0f), 1f),
                "Move input validation must reject non-finite values.");
        }
#endif
    }
}
