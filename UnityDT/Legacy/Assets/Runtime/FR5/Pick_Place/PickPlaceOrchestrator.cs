// 대상 선택부터 계획과 실행까지 Pick & Place 상태 순서를 조정합니다.

using System;
using FR5Mvp.RobotData;
using UnityEngine;

namespace FR5Mvp.PickPlace
{
    /// <summary>대상 선택, 경로 계획과 실행 상태를 순서대로 조정합니다.</summary>
    [AddComponentMenu("Robotics/FR5/Pick Place Orchestrator")]
    [DisallowMultipleComponent]
    [RequireComponent(typeof(TargetSelection), typeof(MotionPlanning), typeof(MotionExecution))]
    public sealed class PickPlaceOrchestrator : MonoBehaviour
    {
        public enum WorkState
        {
            Idle,
            TargetReady,
            Planning,
            PlanReady,
            Executing,
            Completed,
            Error,
            Stopped
        }

        TargetSelection target;
        MotionPlanning planning;
        MotionExecution execution;
        string orchestrationError = string.Empty;

        public WorkState State
        {
            get
            {
                EnsureComponents();
                if (!string.IsNullOrEmpty(LastError))
                    return WorkState.Error;
                if (execution.State == MotionExecution.ExecutionState.Stopped)
                    return WorkState.Stopped;
                if (execution.State == MotionExecution.ExecutionState.Completed)
                    return WorkState.Completed;
                if (execution.IsExecuting)
                    return WorkState.Executing;
                if (planning.State == MotionPlanning.PlanState.Planning)
                    return WorkState.Planning;
                if (planning.HasValidPlan)
                    return WorkState.PlanReady;
                return target.IsReady ? WorkState.TargetReady : WorkState.Idle;
            }
        }

        public string LastError
        {
            get
            {
                EnsureComponents();
                if (!string.IsNullOrEmpty(orchestrationError))
                    return orchestrationError;
                if (planning.State == MotionPlanning.PlanState.Failed)
                    return planning.LastError;
                return execution.State == MotionExecution.ExecutionState.Failed
                    ? execution.LastError
                    : string.Empty;
            }
        }

        public TargetSelection Target
        {
            get
            {
                EnsureComponents();
                return target;
            }
        }

        public RobotTrajectory Trajectory
        {
            get
            {
                EnsureComponents();
                return planning.Trajectory;
            }
        }

        public event Action<Pose, Pose> PlanRequested
        {
            add { EnsureComponents(); planning.PlanRequested += value; }
            remove { EnsureComponents(); planning.PlanRequested -= value; }
        }

        public event Action PlanCancelRequested
        {
            add { EnsureComponents(); planning.CancelRequested += value; }
            remove { EnsureComponents(); planning.CancelRequested -= value; }
        }

        public event Action<RobotTrajectory> ExecutionRequested
        {
            add { EnsureComponents(); execution.ExecutionRequested += value; }
            remove { EnsureComponents(); execution.ExecutionRequested -= value; }
        }

        public event Action ExecutionCancelRequested
        {
            add { EnsureComponents(); execution.CancelRequested += value; }
            remove { EnsureComponents(); execution.CancelRequested -= value; }
        }

        public event Action ExecutionStopRequested
        {
            add { EnsureComponents(); execution.StopRequested += value; }
            remove { EnsureComponents(); execution.StopRequested -= value; }
        }

        void Awake() => RefreshComponents();
        void OnValidate() => RefreshComponents();

        /// <summary>현재 Pick/Place 자세로 외부 경로 계획을 요청합니다.</summary>
        public bool Plan()
        {
            EnsureComponents();
            orchestrationError = string.Empty;
            if (!target.IsReady)
                return Reject("Select an object and set both Pick and Place poses.");
            execution.Clear();
            return planning.Request(target.PickPose, target.PlacePose);
        }

        /// <summary>검증된 현재 경로의 외부 실행을 요청합니다.</summary>
        public bool Execute()
        {
            EnsureComponents();
            orchestrationError = string.Empty;
            return planning.HasValidPlan
                ? execution.Execute(planning.Trajectory)
                : Reject("Create a valid motion plan first.");
        }

        /// <summary>진행 중인 계획과 실행 요청을 모두 취소합니다.</summary>
        public void Cancel()
        {
            EnsureComponents();
            planning.Cancel();
            execution.Cancel();
            orchestrationError = string.Empty;
        }

        /// <summary>경로 실행 계층에 즉시 소프트웨어 정지를 요청합니다.</summary>
        public void StopMotion()
        {
            EnsureComponents();
            execution.Stop();
            orchestrationError = string.Empty;
        }

        /// <summary>외부에서 수신한 경로를 현재 계획으로 검증·채택합니다.</summary>
        public bool AcceptPlan(RobotTrajectory trajectory)
        {
            EnsureComponents();
            return planning.Accept(trajectory);
        }

        public void FailPlan(string error)
        {
            EnsureComponents();
            planning.Fail(error);
        }

        public void CompleteExecution()
        {
            EnsureComponents();
            execution.Complete();
        }

        public void FailExecution(string error)
        {
            EnsureComponents();
            execution.Fail(error);
        }

        void EnsureComponents()
        {
            if (target == null || planning == null || execution == null)
                RefreshComponents();
        }

        void RefreshComponents()
        {
            target = GetComponent<TargetSelection>();
            planning = GetComponent<MotionPlanning>();
            execution = GetComponent<MotionExecution>();
        }

        bool Reject(string error)
        {
            orchestrationError = error;
            return false;
        }
    }
}
