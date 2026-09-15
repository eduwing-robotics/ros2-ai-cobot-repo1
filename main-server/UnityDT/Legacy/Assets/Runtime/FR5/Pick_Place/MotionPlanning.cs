// 경로 계획 요청과 결과 상태를 ROS 전송 형식과 독립적으로 관리합니다.

using System;
using FR5Mvp.RobotData;
using UnityEngine;

namespace FR5Mvp.PickPlace
{
    /// <summary>경로 계획 요청과 수신 경로의 유효 상태를 관리합니다.</summary>
    [AddComponentMenu("Robotics/FR5/Pick Place/Motion Planning")]
    [DisallowMultipleComponent]
    public sealed class MotionPlanning : MonoBehaviour
    {
        public enum PlanState { Idle, Planning, Ready, Failed, Cancelled }

        public PlanState State { get; private set; }
        public RobotTrajectory Trajectory { get; private set; }
        public bool HasValidPlan => State == PlanState.Ready && Trajectory != null;
        public string LastError { get; private set; } = string.Empty;

        /// <summary>외부 계획 전송 계층에 Pick/Place 경로를 요청합니다.</summary>
        public event Action<Pose, Pose> PlanRequested;

        /// <summary>진행 중인 외부 계획 요청의 취소를 요구합니다.</summary>
        public event Action CancelRequested;

        public bool Request(Pose pickPose, Pose placePose)
        {
            if (State == PlanState.Planning)
                return Reject("A motion plan is already in progress.");
            if (PlanRequested == null)
                return Reject("Motion planning transport is not connected.");

            Trajectory = null;
            LastError = string.Empty;
            State = PlanState.Planning;
            PlanRequested.Invoke(pickPose, placePose);
            return true;
        }

        /// <summary>외부 계획 결과를 검증하고 현재 Pick & Place 경로로 채택합니다.</summary>
        public bool Accept(RobotTrajectory trajectory)
        {
            if (State != PlanState.Planning)
                return false;
            if (!IsValid(trajectory))
                return Reject("Planner returned an empty or malformed trajectory.");

            Trajectory = trajectory;
            LastError = string.Empty;
            State = PlanState.Ready;
            return true;
        }

        public void Fail(string error)
        {
            if (State != PlanState.Planning)
                return;
            Trajectory = null;
            LastError = string.IsNullOrWhiteSpace(error)
                ? "Motion planning failed."
                : error;
            State = PlanState.Failed;
        }

        public void Cancel()
        {
            if (State == PlanState.Planning)
                CancelRequested?.Invoke();
            Trajectory = null;
            LastError = string.Empty;
            State = PlanState.Cancelled;
        }

        public void Clear()
        {
            Trajectory = null;
            LastError = string.Empty;
            State = PlanState.Idle;
        }

        bool Reject(string error)
        {
            Trajectory = null;
            LastError = error;
            State = PlanState.Failed;
            return false;
        }

        internal static bool IsValid(RobotTrajectory trajectory)
        {
            if (trajectory?.JointNames == null || trajectory.JointNames.Length == 0 ||
                trajectory.Points == null || trajectory.Points.Length == 0)
                return false;

            double previousTime = 0d;
            foreach (RobotTrajectoryPoint point in trajectory.Points)
            {
                if (point?.Positions == null ||
                    point.Positions.Length != trajectory.JointNames.Length ||
                    !double.IsFinite(point.TimeFromStartSeconds) ||
                    point.TimeFromStartSeconds < 0d ||
                    point.TimeFromStartSeconds < previousTime)
                    return false;
                foreach (double position in point.Positions)
                {
                    if (!double.IsFinite(position))
                        return false;
                }
                previousTime = point.TimeFromStartSeconds;
            }
            return true;
        }
    }
}
