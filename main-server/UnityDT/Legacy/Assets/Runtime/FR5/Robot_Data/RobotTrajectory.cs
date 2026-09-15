using System;

namespace FR5Mvp.RobotData
{
    /// <summary>ROS 전송 형식과 독립적인 FR5 관절 경로입니다.</summary>
    public sealed class RobotTrajectory
    {
        public RobotTrajectory(string frameId, int stampSeconds, uint stampNanoseconds,
            string[] jointNames, RobotTrajectoryPoint[] points)
        {
            FrameId = frameId ?? string.Empty;
            StampSeconds = stampSeconds;
            StampNanoseconds = stampNanoseconds;
            JointNames = jointNames ?? Array.Empty<string>();
            Points = points ?? Array.Empty<RobotTrajectoryPoint>();
        }

        public string FrameId { get; }
        public int StampSeconds { get; }
        public uint StampNanoseconds { get; }
        public string[] JointNames { get; }
        public RobotTrajectoryPoint[] Points { get; }
    }

    /// <summary>한 시점의 관절 위치와 선택적 동역학 값입니다.</summary>
    public sealed class RobotTrajectoryPoint
    {
        public RobotTrajectoryPoint(double[] positions, double[] velocities,
            double[] accelerations, double[] effort, double timeFromStartSeconds)
        {
            Positions = positions ?? Array.Empty<double>();
            Velocities = velocities ?? Array.Empty<double>();
            Accelerations = accelerations ?? Array.Empty<double>();
            Effort = effort ?? Array.Empty<double>();
            TimeFromStartSeconds = timeFromStartSeconds;
        }

        public double[] Positions { get; }
        public double[] Velocities { get; }
        public double[] Accelerations { get; }
        public double[] Effort { get; }
        public double TimeFromStartSeconds { get; }
    }
}
