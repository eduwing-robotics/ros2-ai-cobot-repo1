// 기능별 Orchestrator를 연결하고 FR5 시스템 명령과 상태를 한곳에 제공합니다.

using System.Collections.Generic;
using FR5Mvp.OperationView;
using FR5Mvp.PickPlace;
using FR5Mvp.RobotControl;
using FR5Mvp.RobotData;
using FR5Mvp.RosCommunication;
using FR5Mvp.SafetyMonitoring;
using UnityEngine;
using UnityEngine.Serialization;

namespace FR5Mvp
{
    /// <summary>FR5 기능 그룹의 명령, 결과, 안전 정지를 연결하는 최상위 구성 진입점입니다.</summary>
    [AddComponentMenu("Robotics/FR5/System Orchestrator")]
    [DisallowMultipleComponent]
    [DefaultExecutionOrder(-100)]
    public sealed class FR5SystemOrchestrator : MonoBehaviour
    {
        public enum SystemState
        {
            Unconfigured,
            WaitingForRos,
            Ready,
            Working,
            Stopped,
            Faulted
        }

        [SerializeField] Transform modelRoot;
        [FormerlySerializedAs("robotController")]
        [SerializeField] RobotControlOrchestrator robotControl;
        [FormerlySerializedAs("jointStateSubscriber")]
        [SerializeField] RosCommunicationOrchestrator rosCommunication;
        [FormerlySerializedAs("watchdog")]
        [SerializeField] SafetyMonitor safetyMonitor;
        [FormerlySerializedAs("workOrchestrator")]
        [SerializeField] PickPlaceOrchestrator pickPlace;
        [SerializeField] TrajectoryPreview trajectoryPreview;
        [SerializeField] CameraSelector cameraSelector;

        string systemError = string.Empty;
        bool runtimeEventsBound;

        public Transform ModelRoot => modelRoot;
        public RobotControlOrchestrator RobotControl => robotControl;
        public RosCommunicationOrchestrator RosCommunication => rosCommunication;
        public PickPlaceOrchestrator PickPlace => pickPlace;
        public CameraSelector CameraSelector => cameraSelector;
        public bool IsConfigured =>
            modelRoot != null &&
            robotControl != null &&
            rosCommunication != null &&
            rosCommunication.IsConfigured &&
            safetyMonitor != null &&
            pickPlace != null &&
            trajectoryPreview != null;
        public SystemState State => ResolveState();

        public string LastError
        {
            get
            {
                if (!IsConfigured)
                    return "FR5 system components are not fully assigned.";
                if (!string.IsNullOrEmpty(systemError))
                    return systemError;
                if (!string.IsNullOrEmpty(pickPlace.LastError))
                    return pickPlace.LastError;
                if (!string.IsNullOrEmpty(safetyMonitor.LastError))
                    return safetyMonitor.LastError;
                if (!string.IsNullOrEmpty(rosCommunication.LastError))
                    return rosCommunication.LastError;
                return trajectoryPreview.LastError;
            }
        }

        void Awake() => RefreshReferences();

        void OnEnable()
        {
            RefreshReferences();
            BindRuntimeEvents();
        }

        void OnDisable() => UnbindRuntimeEvents();
        void OnValidate() => RefreshReferences();

        /// <summary>현재 FR5 자식 구조에서 기능 진입점을 찾고 정적 구성을 전달합니다.</summary>
        public void RefreshReferences()
        {
            if (modelRoot == null)
                modelRoot = transform.Find("Model");
            if (robotControl == null)
                robotControl = GetComponentInChildren<RobotControlOrchestrator>(true);
            if (rosCommunication == null)
                rosCommunication = GetComponentInChildren<RosCommunicationOrchestrator>(true);
            if (safetyMonitor == null)
                safetyMonitor = GetComponentInChildren<SafetyMonitor>(true);
            if (pickPlace == null)
                pickPlace = GetComponentInChildren<PickPlaceOrchestrator>(true);
            if (trajectoryPreview == null)
                trajectoryPreview = GetComponentInChildren<TrajectoryPreview>(true);
            if (cameraSelector == null)
                cameraSelector = GetComponentInChildren<CameraSelector>(true);

            GripperController gripper = modelRoot != null
                ? modelRoot.GetComponentInChildren<GripperController>(true)
                : null;
            robotControl?.UseGripper(gripper);
            safetyMonitor?.Configure(robotControl?.GetJointSpecifications());
            rosCommunication?.RefreshAdapters(transform);
            rosCommunication?.UsePlanningFrame(modelRoot);
        }

        /// <summary>현재 대상과 Pick/Place 자세로 경로 계획을 시작합니다.</summary>
        public bool PlanPickPlace()
        {
            systemError = string.Empty;
            trajectoryPreview?.Stop();
            return pickPlace != null && pickPlace.Plan();
        }

        /// <summary>현재 계획을 실제 제어와 분리된 프리뷰 로봇에 재생합니다.</summary>
        public bool PreviewPickPlace()
        {
            systemError = string.Empty;
            if (pickPlace?.Trajectory == null)
                return Reject("Create a valid motion plan first.");
            if (trajectoryPreview?.PreviewRobot == robotControl)
                return Reject("Trajectory preview must use a separate preview robot.");
            return trajectoryPreview != null && trajectoryPreview.Play(pickPlace.Trajectory);
        }

        /// <summary>통신이 건강할 때만 현재 Pick & Place 계획의 실행을 요청합니다.</summary>
        public bool ExecutePickPlace()
        {
            systemError = string.Empty;
            if (safetyMonitor == null || !safetyMonitor.IsHealthy)
                return Reject("Robot joint-state communication is not healthy.");
            trajectoryPreview?.Stop();
            return pickPlace != null && pickPlace.Execute();
        }

        /// <summary>현재 계획/실행 요청과 프리뷰를 취소합니다.</summary>
        public void CancelPickPlace()
        {
            trajectoryPreview?.Stop();
            pickPlace?.Cancel();
            systemError = string.Empty;
        }

        /// <summary>
        /// 계획 실행, 프리뷰와 Unity 관절 동작을 정지합니다.
        /// 하드웨어 비상 정지와 그리퍼 동작 취소를 대체하지 않습니다.
        /// </summary>
        public void StopAllMotion()
        {
            pickPlace?.StopMotion();
            trajectoryPreview?.Stop();
            robotControl?.StopAllMotion();
            systemError = string.Empty;
        }

        /// <summary>Manual 목표 자세를 Unity 로봇에만 적용합니다.</summary>
        public void ApplyManualPose(IReadOnlyList<float> degrees)
        {
            systemError = string.Empty;
            robotControl?.ApplyManualPose(degrees);
        }

        /// <summary>로컬 그리퍼를 열고 구성된 ROS 전송 계층에도 명령을 전달합니다.</summary>
        public void OpenGripper() => robotControl?.OpenGripper();

        /// <summary>로컬 그리퍼를 닫고 구성된 ROS 전송 계층에도 명령을 전달합니다.</summary>
        public void CloseGripper() => robotControl?.CloseGripper();

        void BindRuntimeEvents()
        {
            if (runtimeEventsBound || !Application.isPlaying ||
                pickPlace == null || rosCommunication == null)
                return;

            pickPlace.PlanRequested += rosCommunication.RequestPlan;
            pickPlace.PlanCancelRequested += rosCommunication.CancelPlan;
            pickPlace.ExecutionRequested += rosCommunication.Execute;
            pickPlace.ExecutionCancelRequested += rosCommunication.CancelExecution;
            pickPlace.ExecutionStopRequested += rosCommunication.StopExecution;
            rosCommunication.PlanReceived += ReceivePlan;
            rosCommunication.PlanFailed += pickPlace.FailPlan;
            rosCommunication.ExecutionCompleted += pickPlace.CompleteExecution;
            rosCommunication.ExecutionFailed += pickPlace.FailExecution;
            rosCommunication.JointStateReceived += ReceiveJointState;
            rosCommunication.GripperStateReceived += ReceiveGripperState;
            if (robotControl != null)
                robotControl.GripperCommandRequested += rosCommunication.SendGripperCommand;
            if (safetyMonitor != null)
                safetyMonitor.StopRequested += StopAllMotion;
            runtimeEventsBound = true;
        }

        void UnbindRuntimeEvents()
        {
            if (!runtimeEventsBound)
                return;
            if (pickPlace != null && rosCommunication != null)
            {
                pickPlace.PlanRequested -= rosCommunication.RequestPlan;
                pickPlace.PlanCancelRequested -= rosCommunication.CancelPlan;
                pickPlace.ExecutionRequested -= rosCommunication.Execute;
                pickPlace.ExecutionCancelRequested -= rosCommunication.CancelExecution;
                pickPlace.ExecutionStopRequested -= rosCommunication.StopExecution;
                rosCommunication.PlanReceived -= ReceivePlan;
                rosCommunication.PlanFailed -= pickPlace.FailPlan;
                rosCommunication.ExecutionCompleted -= pickPlace.CompleteExecution;
                rosCommunication.ExecutionFailed -= pickPlace.FailExecution;
                rosCommunication.JointStateReceived -= ReceiveJointState;
                rosCommunication.GripperStateReceived -= ReceiveGripperState;
            }
            if (robotControl != null && rosCommunication != null)
                robotControl.GripperCommandRequested -= rosCommunication.SendGripperCommand;
            if (safetyMonitor != null)
                safetyMonitor.StopRequested -= StopAllMotion;
            runtimeEventsBound = false;
        }

        void ReceiveJointState(
            IReadOnlyList<string> names,
            IReadOnlyList<float> degrees,
            double timestamp)
        {
            if (safetyMonitor == null || robotControl == null)
                return;
            if (!safetyMonitor.SubmitJointState(names, degrees, timestamp))
                return;
            robotControl.FollowJointState(
                degrees,
                safetyMonitor.InterpolationSeconds,
                Time.realtimeSinceStartupAsDouble);
        }

        void ReceiveGripperState(float meters) => robotControl?.ApplyGripperState(meters);

        void ReceivePlan(RobotTrajectory trajectory) => pickPlace?.AcceptPlan(trajectory);

        SystemState ResolveState()
        {
            if (!IsConfigured)
                return SystemState.Unconfigured;
            if (!string.IsNullOrEmpty(LastError))
                return SystemState.Faulted;
            if (trajectoryPreview.IsPlaying ||
                pickPlace.State == PickPlaceOrchestrator.WorkState.Planning ||
                pickPlace.State == PickPlaceOrchestrator.WorkState.Executing)
                return SystemState.Working;
            if (pickPlace.State == PickPlaceOrchestrator.WorkState.Stopped)
                return SystemState.Stopped;
            return safetyMonitor.IsHealthy
                ? SystemState.Ready
                : SystemState.WaitingForRos;
        }

        bool Reject(string error)
        {
            systemError = error;
            return false;
        }
    }
}
