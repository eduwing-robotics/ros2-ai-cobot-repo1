// 승인된 내부 경로의 실행, 취소와 정지 상태를 관리합니다.

using System;
using FR5Mvp.RobotData;
using UnityEngine;

namespace FR5Mvp.PickPlace
{
    /// <summary>검증된 경로의 실행, 취소, 정지와 완료 상태를 관리합니다.</summary>
    [AddComponentMenu("Robotics/FR5/Pick Place/Motion Execution")]
    [DisallowMultipleComponent]
    public sealed class MotionExecution : MonoBehaviour
    {
        public enum ExecutionState { Idle, Executing, Completed, Failed, Cancelled, Stopped }

        public ExecutionState State { get; private set; }
        public bool IsExecuting => State == ExecutionState.Executing;
        public string LastError { get; private set; } = string.Empty;

        /// <summary>외부 실행 전송 계층에 내부 경로 실행을 요청합니다.</summary>
        public event Action<RobotTrajectory> ExecutionRequested;
        public event Action CancelRequested;
        public event Action StopRequested;

        public bool Execute(RobotTrajectory trajectory)
        {
            if (IsExecuting)
                return Reject("A trajectory is already executing.");
            if (trajectory == null)
                return Reject("A valid trajectory is required.");
            if (ExecutionRequested == null)
                return Reject("Robot execution transport is not connected.");

            LastError = string.Empty;
            State = ExecutionState.Executing;
            ExecutionRequested.Invoke(trajectory);
            return true;
        }

        public void Complete()
        {
            if (!IsExecuting)
                return;
            LastError = string.Empty;
            State = ExecutionState.Completed;
        }

        public void Fail(string error)
        {
            if (!IsExecuting)
                return;
            LastError = string.IsNullOrWhiteSpace(error)
                ? "Motion execution failed."
                : error;
            State = ExecutionState.Failed;
        }

        public void Cancel()
        {
            if (IsExecuting)
                CancelRequested?.Invoke();
            LastError = string.Empty;
            State = ExecutionState.Cancelled;
        }

        /// <summary>실행 전송 계층에 정지를 요청합니다. 하드웨어 E-Stop을 대체하지 않습니다.</summary>
        public void Stop()
        {
            if (IsExecuting)
                StopRequested?.Invoke();
            LastError = string.Empty;
            State = ExecutionState.Stopped;
        }

        public void Clear()
        {
            LastError = string.Empty;
            State = ExecutionState.Idle;
        }

        bool Reject(string error)
        {
            LastError = error;
            State = ExecutionState.Failed;
            return false;
        }
    }
}
