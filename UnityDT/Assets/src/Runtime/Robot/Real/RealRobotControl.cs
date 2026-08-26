// 책임: Real 로봇의 이동·수동 제어 명령을 검증하고 FAIRINO 서비스 완료까지 기다린다.

using System;
using System.Collections.Generic;
using System.Globalization;
using System.Threading.Tasks;
using MainUnity.Runtime.Robot.Interface;
using MainUnity.Runtime.Robot.Status;
using RosMessageTypes.Fairino;
using Unity.Robotics.ROSTCPConnector;
using Unity.Robotics.ROSTCPConnector.ROSGeometry;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Real
{
    [DisallowMultipleComponent]
    public sealed class RealRobotControl : MonoBehaviour, IRobotControl
    {
        [Header("FAIRINO Service")]
        [SerializeField] string serviceName = "/fairino_remote_command_service";
        [SerializeField, Min(0.1f)] float completionTimeoutSeconds = 30f;

        [Header("Teaching Points")]
        [SerializeField] Transform homePoint;
        [SerializeField] Transform itemReadyPoint;
        [SerializeField] Transform assemblyReadyPoint;

        [Header("Debug Target")]
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

        [SerializeField] RealGripperRequest gripperRequest;

        Transform robotBase;
        RobotStatusManager statusManager;
        bool requestInFlight;

        sealed class CommandRejectedException : Exception
        {
            public CommandRejectedException(string message) : base(message) { }
        }

        void Awake()
        {
            RefreshReferences();
            ROSConnection.GetOrCreateInstance()
                .RegisterRosService<RemoteCmdInterfaceRequest, RemoteCmdInterfaceResponse>(serviceName);
        }

        void OnValidate() => RefreshReferences();

        /// <summary>RealMaster가 Unity 로봇 루트와 공통 상태 관리자를 주입한다.</summary>
        public void Initialize(ArticulationBody articulationRoot, RobotStatusManager injectedStatusManager)
        {
            robotBase = articulationRoot != null ? articulationRoot.transform : null;
            statusManager = injectedStatusManager;
        }

        /// <summary>지정된 티칭 포인트로 이동하고 실제 완료 신호까지 기다린다.</summary>
        public Task MoveJ(RobotPoint point)
        {
            if (!TryEnsureReady(out InvalidOperationException preparationFailure))
                return Task.FromException(preparationFailure);

            if (point != RobotPoint.Home && point != RobotPoint.ItemReady &&
                point != RobotPoint.AssemblyReady)
                return RejectExecution(RobotErrorLabel.InvalidData, "Unknown robot teaching point.");

            Transform teachingPoint = GetTeachingPoint(point);
            if (teachingPoint == null)
                return RejectExecution(RobotErrorLabel.InvalidData,
                    $"Assign a Transform for the {TeachingPointName(point)} teaching point.");

            if (!TryGetRobotPose(new Pose(teachingPoint.position, teachingPoint.rotation),
                    out Vector3 position, out Vector3 rotation, out string error))
                return RejectExecution(RobotErrorLabel.InvalidData, error);

            return RequestMoveAsync(moveJ: true, position, rotation);
        }

        /// <summary>
        /// 현재 FAIRINO 원격 서비스에는 관절 직접 명령 경로가 연결되어 있지 않다.
        /// TODO: SDK의 안전한 관절 명령 계약이 확정되면 여기에서 연결한다.
        /// </summary>
        public bool TrySetJointTarget(IReadOnlyList<float> jointDegrees) =>
            Reject("REAL joint control is not implemented.");

        public bool TryOpenGripper() => TrySetGripperOpeningPercent(100f);
        public bool TryCloseGripper() => TrySetGripperOpeningPercent(0f);

        public bool TrySetGripperOpeningPercent(float openingPercent) =>
            gripperRequest != null && gripperRequest.TryRequestOpeningPercent(openingPercent);

        [ContextMenu("Request MoveJ")]
        async void RequestMoveJFromContextMenu()
        {
            try
            {
                if (!TryEnsureReady(out InvalidOperationException preparationFailure))
                    throw preparationFailure;
                if (!TryGetDebugTargetPose(out Vector3 position, out Vector3 rotation, out string error))
                    throw RejectOperation(RobotErrorLabel.InvalidData, error);
                await RequestMoveAsync(moveJ: true, position, rotation);
            }
            catch (Exception exception)
            {
                Debug.LogError("[FAIRINO] MoveJ request failed: " + exception.Message, this);
            }
        }

        [ContextMenu("Request MoveCart")]
        async void RequestMoveCartFromContextMenu()
        {
            try
            {
                if (!TryEnsureReady(out InvalidOperationException preparationFailure))
                    throw preparationFailure;
                if (!TryGetDebugTargetPose(out Vector3 position, out Vector3 rotation, out string error))
                    throw RejectOperation(RobotErrorLabel.InvalidData, error);
                await RequestMoveAsync(moveJ: false, position, rotation);
            }
            catch (Exception exception)
            {
                Debug.LogError("[FAIRINO] MoveCart request failed: " + exception.Message, this);
            }
        }

        async Task RequestMoveAsync(bool moveJ, Vector3 position, Vector3 rotation)
        {
            if (!TryEnsureReady(out InvalidOperationException preparationFailure))
                throw preparationFailure;

            if (!IsValid(position, 10000f) || !IsValid(rotation, 360f) || pointIndex < 1)
                throw RejectOperation(RobotErrorLabel.InvalidData,
                    "FAIRINO target pose is outside the supported range.");

            requestInFlight = true;
            var completion = new TaskCompletionSource<bool>();
            bool observedRunning = false;

            void OnStatusChanged(RobotRunState state, RobotErrorLabel statusLabel, string detail)
            {
                if (state == RobotRunState.Running)
                {
                    observedRunning = true;
                    return;
                }

                if (state == RobotRunState.Error || state == RobotRunState.Disconnected)
                {
                    completion.TrySetException(new InvalidOperationException(
                        string.IsNullOrWhiteSpace(detail) ? state.ToString() : detail));
                    return;
                }

                if (observedRunning && state == RobotRunState.Idle &&
                    statusManager.Latest?.RobotMotionDone != 0)
                    completion.TrySetResult(true);
            }

            statusManager.StatusChanged += OnStatusChanged;
            try
            {
                Task timeoutTask = Task.Delay(TimeSpan.FromSeconds(completionTimeoutSeconds));
                Task commandTask = moveJ
                    ? SendMoveJAsync(position, rotation)
                    : SendMoveCartAsync(position, rotation);
                _ = commandTask.ContinueWith(task => _ = task.Exception,
                    TaskContinuationOptions.OnlyOnFaulted);
                await WaitForCommandAndCompletionAsync(commandTask, completion.Task, timeoutTask);
            }
            catch (TimeoutException)
            {
                if (completion.Task.IsFaulted)
                    await completion.Task;
                statusManager.StatusChanged -= OnStatusChanged;
                statusManager.ReportError(RobotErrorLabel.Timeout,
                    "FAIRINO command or motion did not complete before the timeout.");
                throw;
            }
            catch (Exception exception)
            {
                if (completion.Task.IsFaulted)
                    await completion.Task;

                statusManager.StatusChanged -= OnStatusChanged;
                RobotErrorLabel label = exception is CommandRejectedException
                    ? RobotErrorLabel.CommandRejected
                    : RobotErrorLabel.Connection;
                statusManager.ReportError(label, exception.Message);
                throw;
            }
            finally
            {
                statusManager.StatusChanged -= OnStatusChanged;
                requestInFlight = false;
            }
        }

        async Task SendMoveJAsync(Vector3 position, Vector3 rotation)
        {
            string pointCommand = string.Format(CultureInfo.InvariantCulture,
                "CARTPoint({0},{1},{2},{3},{4},{5},{6})",
                pointIndex, position.x, position.y, position.z,
                rotation.x, rotation.y, rotation.z);
            await SendCommandAsync(pointCommand);

            string moveJCommand = string.Format(CultureInfo.InvariantCulture,
                "MoveJ(CART{0},{1},{2},{3})", pointIndex, speedPercent, tool, user);
            await SendCommandAsync(moveJCommand);
        }

        async Task SendMoveCartAsync(Vector3 position, Vector3 rotation)
        {
            string moveCartCommand = string.Format(CultureInfo.InvariantCulture,
                "MoveCart({0},{1},{2},{3},{4},{5},{6},{7},{8},{9},{10},{11},{12})",
                position.x, position.y, position.z,
                rotation.x, rotation.y, rotation.z,
                tool, user, speedPercent, accelerationPercent,
                overridePercent, blendTimeMilliseconds, configuration);
            await SendCommandAsync(moveCartCommand);
        }

        static async Task WaitForCommandAndCompletionAsync(
            Task commandTask, Task completionTask, Task timeoutTask)
        {
            while (!commandTask.IsCompleted || !completionTask.IsCompleted)
            {
                Task completedTask;
                if (!commandTask.IsCompleted && !completionTask.IsCompleted)
                    completedTask = await Task.WhenAny(commandTask, completionTask, timeoutTask);
                else if (!commandTask.IsCompleted)
                    completedTask = await Task.WhenAny(commandTask, timeoutTask);
                else
                    completedTask = await Task.WhenAny(completionTask, timeoutTask);

                if (completedTask == timeoutTask)
                    throw new TimeoutException("FAIRINO command or motion did not complete before the timeout.");

                await completedTask;
            }

            await Task.WhenAll(commandTask, completionTask);
        }

        async Task SendCommandAsync(string command)
        {
            Debug.Log("[FAIRINO] TX " + serviceName + ": " + command, this);
            RemoteCmdInterfaceResponse response = await ROSConnection.GetOrCreateInstance()
                .SendServiceMessage<RemoteCmdInterfaceResponse>(serviceName,
                    new RemoteCmdInterfaceRequest(command));
            string value = response?.cmd_res ?? string.Empty;
            Debug.Log("[FAIRINO] RX " + serviceName + ": " + value, this);
            if (value == "0")
                return;

            string detail = "[FAIRINO] Move command returned: " + value;
            throw new CommandRejectedException(detail);
        }

        bool TryPrepare(out RobotErrorLabel label, out string error, out bool reportError)
        {
            if (statusManager == null)
            {
                label = RobotErrorLabel.InvalidData;
                error = "RobotStatusManager is not assigned.";
                reportError = true;
                return false;
            }
            if (!statusManager.CanAcceptCommand(out error))
            {
                label = statusManager.ErrorLabel;
                reportError = false;
                return false;
            }
            if (!Application.isPlaying)
            {
                label = RobotErrorLabel.CommandRejected;
                error = "FAIRINO requests require Play Mode.";
                reportError = true;
                return false;
            }
            if (requestInFlight)
            {
                label = RobotErrorLabel.CommandRejected;
                error = "A FAIRINO move request is already in flight.";
                reportError = true;
                return false;
            }
            if (string.IsNullOrWhiteSpace(serviceName))
            {
                label = RobotErrorLabel.InvalidData;
                error = "FAIRINO service name must not be empty.";
                reportError = true;
                return false;
            }
            if (!float.IsFinite(completionTimeoutSeconds) || completionTimeoutSeconds < 0.1f)
            {
                label = RobotErrorLabel.InvalidData;
                error = "FAIRINO completion timeout must be at least 0.1 seconds.";
                reportError = true;
                return false;
            }

            label = RobotErrorLabel.None;
            error = string.Empty;
            reportError = false;
            return true;
        }

        bool TryEnsureReady(out InvalidOperationException failure)
        {
            if (TryPrepare(out RobotErrorLabel label, out string error, out bool reportError))
            {
                failure = null;
                return true;
            }

            if (reportError)
                statusManager?.ReportError(label, error);
            failure = new InvalidOperationException(error);
            return false;
        }

        Transform GetTeachingPoint(RobotPoint point) => point switch
        {
            RobotPoint.Home => homePoint,
            RobotPoint.ItemReady => itemReadyPoint,
            RobotPoint.AssemblyReady => assemblyReadyPoint,
            _ => null
        };

        static string TeachingPointName(RobotPoint point) => point switch
        {
            RobotPoint.Home => "Home",
            RobotPoint.ItemReady => "Item Ready",
            RobotPoint.AssemblyReady => "Assembly Ready",
            _ => "unknown"
        };

        bool TryGetDebugTargetPose(out Vector3 position, out Vector3 rotation, out string error)
        {
            position = positionMillimeters;
            rotation = rotationDegrees;
            if (target == null)
            {
                error = string.Empty;
                return true;
            }

            return TryGetRobotPose(new Pose(target.position, target.rotation), out position, out rotation,
                out error);
        }

        bool TryGetRobotPose(Pose targetPose, out Vector3 position, out Vector3 rotation, out string error)
        {
            position = default;
            rotation = default;
            if (robotBase == null)
            {
                error = "FAIRINO target requires an initialized robot base.";
                return false;
            }

            Vector3 basePosition = robotBase.InverseTransformPoint(targetPose.position);
            position = FLU.ConvertFromRUF(basePosition) * 1000f;
            rotation = rotationDegrees;
            rotation.z = targetPose.rotation.eulerAngles.y;
            if (!IsValid(position, 10000f) || !IsValid(rotation, 360f))
            {
                error = "FAIRINO target pose is outside the supported range.";
                return false;
            }

            error = string.Empty;
            return true;
        }

        InvalidOperationException RejectOperation(RobotErrorLabel label, string detail)
        {
            statusManager?.ReportError(label, detail);
            return new InvalidOperationException(detail);
        }

        Task RejectExecution(RobotErrorLabel label, string detail) =>
            Task.FromException(RejectOperation(label, detail));

        bool Reject(string detail)
        {
            Debug.LogWarning(detail, this);
            return false;
        }

        static bool IsValid(Vector3 value, float maximum) =>
            float.IsFinite(value.x) && float.IsFinite(value.y) && float.IsFinite(value.z) &&
            Mathf.Abs(value.x) <= maximum && Mathf.Abs(value.y) <= maximum &&
            Mathf.Abs(value.z) <= maximum;

#if UNITY_EDITOR
        [ContextMenu("Self Check Real Move Input")]
        void SelfCheckMoveInput()
        {
            Debug.Assert(IsValid(Vector3.zero, 1f) && !IsValid(new Vector3(float.NaN, 0f, 0f), 1f),
                "Move input validation must reject non-finite values.");
            Debug.Assert(GetTeachingPoint(RobotPoint.Home) == homePoint &&
                         GetTeachingPoint(RobotPoint.ItemReady) == itemReadyPoint &&
                         GetTeachingPoint(RobotPoint.AssemblyReady) == assemblyReadyPoint,
                "Real MoveJ teaching points must map to their matching RobotPoint values.");
            Debug.Assert(TeachingPointName(RobotPoint.Home) != TeachingPointName(RobotPoint.ItemReady) &&
                         TeachingPointName(RobotPoint.ItemReady) != TeachingPointName(RobotPoint.AssemblyReady) &&
                         TeachingPointName(RobotPoint.Home) != TeachingPointName(RobotPoint.AssemblyReady),
                "Real MoveJ teaching point names must distinguish all RobotPoint values.");
        }
#endif

        void RefreshReferences()
        {
            gripperRequest = gripperRequest != null
                ? gripperRequest
                : GetComponentInChildren<RealGripperRequest>(true);
        }
    }
}
