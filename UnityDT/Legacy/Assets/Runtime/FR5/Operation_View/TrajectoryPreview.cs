// 내부 관절 경로를 별도의 Unity 프리뷰 로봇에 재생합니다.

using FR5Mvp.RobotControl;
using FR5Mvp.RobotData;
using UnityEngine;

namespace FR5Mvp.OperationView
{
    /// <summary>내부 관절 경로를 실제 제어 대상과 분리된 프리뷰 로봇에 재생합니다.</summary>
    [AddComponentMenu("Robotics/FR5/Operation View/Trajectory Preview")]
    [DisallowMultipleComponent]
    public sealed class TrajectoryPreview : MonoBehaviour
    {
        [SerializeField, Tooltip("실제 제어 대상이 아닌 경로 미리보기용 로봇을 지정합니다.")]
        RobotControlOrchestrator previewRobot;

        RobotTrajectory trajectory;
        float[] previewDegrees = System.Array.Empty<float>();
        float[] resetDegrees = System.Array.Empty<float>();
        int pointIndex;
        double startedAt;
        bool hasResetPose;

        public bool IsPlaying { get; private set; }
        public string LastError { get; private set; } = string.Empty;
        public RobotControlOrchestrator PreviewRobot => previewRobot;

        void Update()
        {
            if (!IsPlaying)
                return;

            RobotTrajectoryPoint[] points = trajectory.Points;
            double elapsed = Time.realtimeSinceStartupAsDouble - startedAt;
            double finalTime = points[^1].TimeFromStartSeconds;
            if (elapsed >= finalTime)
            {
                Apply(points[^1].Positions);
                IsPlaying = false;
                return;
            }

            while (pointIndex + 1 < points.Length &&
                elapsed > points[pointIndex + 1].TimeFromStartSeconds)
                pointIndex++;

            RobotTrajectoryPoint from = points[pointIndex];
            RobotTrajectoryPoint to = points[Mathf.Min(pointIndex + 1, points.Length - 1)];
            float t = to.TimeFromStartSeconds <= from.TimeFromStartSeconds
                ? 1f
                : Mathf.Clamp01((float)((elapsed - from.TimeFromStartSeconds) /
                    (to.TimeFromStartSeconds - from.TimeFromStartSeconds)));

            for (int i = 0; i < previewDegrees.Length; i++)
                previewDegrees[i] = Mathf.Lerp(
                    (float)from.Positions[i], (float)to.Positions[i], t) * Mathf.Rad2Deg;
            previewRobot.SetShadowPose(previewDegrees);
        }

        /// <summary>검증된 내부 경로를 처음부터 프리뷰 로봇에 재생합니다.</summary>
        public bool Play(RobotTrajectory value)
        {
            JointController[] joints = previewRobot != null
                ? previewRobot.GetJoints()
                : System.Array.Empty<JointController>();
            if (!MatchesRobot(value, joints))
                return Reject("Assign a matching preview robot and trajectory.");

            previewDegrees = new float[joints.Length];
            resetDegrees = new float[joints.Length];
            for (int i = 0; i < joints.Length; i++)
                resetDegrees[i] = joints[i].ActualDegrees;

            trajectory = value;
            pointIndex = 0;
            startedAt = Time.realtimeSinceStartupAsDouble;
            hasResetPose = true;
            IsPlaying = true;
            LastError = string.Empty;
            return true;
        }

        public void Stop()
        {
            IsPlaying = false;
            LastError = string.Empty;
        }

        public void ResetPreview()
        {
            Stop();
            if (previewRobot != null && hasResetPose)
                previewRobot.SetShadowPose(resetDegrees);
        }

        void Apply(double[] radians)
        {
            for (int i = 0; i < previewDegrees.Length; i++)
                previewDegrees[i] = (float)radians[i] * Mathf.Rad2Deg;
            previewRobot.SetShadowPose(previewDegrees);
        }

        bool Reject(string error)
        {
            IsPlaying = false;
            LastError = error;
            return false;
        }

        static bool MatchesRobot(RobotTrajectory value, JointController[] joints)
        {
            if (value?.JointNames == null || value.Points == null ||
                joints.Length == 0 || value.JointNames.Length != joints.Length ||
                value.Points.Length == 0)
                return false;

            double previousTime = 0d;
            for (int i = 0; i < joints.Length; i++)
            {
                if (value.JointNames[i] != joints[i].JointName)
                    return false;
            }
            foreach (RobotTrajectoryPoint point in value.Points)
            {
                if (point?.Positions == null || point.Positions.Length != joints.Length ||
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
