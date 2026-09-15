using System;

namespace FR5Mvp.RobotData
{
    /// <summary>관절 상태 입력을 검증하는 데 필요한 불변 메타데이터입니다.</summary>
    public readonly struct JointSpecification
    {
        public JointSpecification(string name, float lowerDegrees, float upperDegrees)
        {
            Name = string.IsNullOrWhiteSpace(name)
                ? throw new ArgumentException("Joint name is required.", nameof(name))
                : name;
            LowerDegrees = lowerDegrees;
            UpperDegrees = upperDegrees;
        }

        public string Name { get; }
        public float LowerDegrees { get; }
        public float UpperDegrees { get; }
    }
}
