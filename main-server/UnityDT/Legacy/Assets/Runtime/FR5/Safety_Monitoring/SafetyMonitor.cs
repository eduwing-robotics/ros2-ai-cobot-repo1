// 관절 상태와 통신 시간을 검증하고 안전 정지가 필요할 때 상위 계층에 알립니다.

using System;
using System.Collections.Generic;
using FR5Mvp.RobotData;
using UnityEngine;

namespace FR5Mvp.SafetyMonitoring
{
    /// <summary>관절 상태의 값·시간을 검증하고 통신 제한 시 정지를 요청합니다.</summary>
    [AddComponentMenu("Robotics/FR5/Safety Monitor")]
    [DisallowMultipleComponent]
    public sealed class SafetyMonitor : MonoBehaviour
    {
        [SerializeField, Min(0.01f)] float timeoutSeconds = 0.25f;
        [SerializeField, Min(0f)] float interpolationSeconds = 0.05f;

        JointSpecification[] joints = Array.Empty<JointSpecification>();
        double lastSourceTimestampSeconds;
        bool hasTimestamp;
        bool hasSample;

        public float TimeoutSeconds
        {
            get => timeoutSeconds;
            set => timeoutSeconds = Mathf.Max(0.01f, value);
        }

        public float InterpolationSeconds
        {
            get => interpolationSeconds;
            set => interpolationSeconds = Mathf.Max(0f, value);
        }

        public bool IsTimedOut { get; private set; }
        public bool IsHealthy => hasSample && !IsTimedOut;
        public string LastError { get; private set; } = string.Empty;
        public double LastReceiveTimeSeconds { get; private set; }

        /// <summary>상위 시스템이 모든 소프트웨어 동작을 정지해야 함을 알립니다.</summary>
        public event Action StopRequested;

        void FixedUpdate() => Tick(Time.realtimeSinceStartupAsDouble);

        void OnDisable()
        {
            if (Application.isPlaying && hasSample)
                StopRequested?.Invoke();
        }

        /// <summary>검증 대상 관절의 이름과 허용 범위를 복사해 구성합니다.</summary>
        public void Configure(IReadOnlyList<JointSpecification> specifications)
        {
            if (specifications == null)
            {
                joints = Array.Empty<JointSpecification>();
                return;
            }
            joints = new JointSpecification[specifications.Count];
            for (int i = 0; i < specifications.Count; i++)
                joints[i] = specifications[i];
        }

        /// <summary>수신한 관절 상태의 순서, 범위와 타임스탬프를 검증합니다.</summary>
        public bool SubmitJointState(
            IReadOnlyList<string> jointNames,
            IReadOnlyList<float> degrees,
            double sourceTimestampSeconds)
        {
            if (!Validate(jointNames, degrees, sourceTimestampSeconds))
                return false;

            lastSourceTimestampSeconds = sourceTimestampSeconds;
            hasTimestamp = true;
            hasSample = true;
            IsTimedOut = false;
            LastError = string.Empty;
            LastReceiveTimeSeconds = Time.realtimeSinceStartupAsDouble;
            return true;
        }

        /// <summary>통신 제한 시간을 검사하고 한 번만 안전 정지를 요청합니다.</summary>
        public void Tick(double nowSeconds)
        {
            if (!hasSample || IsTimedOut ||
                nowSeconds - LastReceiveTimeSeconds <= timeoutSeconds)
                return;

            IsTimedOut = true;
            hasTimestamp = false;
            LastError = $"No joint state received for {timeoutSeconds:F3} seconds.";
            StopRequested?.Invoke();
        }

        bool Validate(
            IReadOnlyList<string> jointNames,
            IReadOnlyList<float> degrees,
            double timestamp)
        {
            if (joints.Length == 0)
                return Reject("Import the FR5 robot before submitting joint states.");
            if (jointNames == null || degrees == null ||
                jointNames.Count != joints.Length || degrees.Count != joints.Length)
                return Reject($"Expected {joints.Length} joint names and degree values.");
            if (double.IsNaN(timestamp) || double.IsInfinity(timestamp))
                return Reject("Source timestamp must be finite.");
            if (hasTimestamp && timestamp <= lastSourceTimestampSeconds)
            {
                if (timestamp < lastSourceTimestampSeconds - timeoutSeconds)
                    hasTimestamp = false;
                else
                    return Reject("Source timestamp must increase monotonically.");
            }

            for (int i = 0; i < joints.Length; i++)
            {
                JointSpecification joint = joints[i];
                if (!string.Equals(jointNames[i], joint.Name, StringComparison.Ordinal))
                    return Reject($"Joint {i} must be '{joint.Name}'.");
                float value = degrees[i];
                if (!float.IsFinite(value))
                    return Reject($"{joint.Name} angle must be finite degrees.");
                if (value < joint.LowerDegrees || value > joint.UpperDegrees)
                {
                    return Reject(
                        $"{joint.Name} angle {value} is outside " +
                        $"[{joint.LowerDegrees}, {joint.UpperDegrees}] degrees.");
                }
            }
            return true;
        }

        bool Reject(string error)
        {
            LastError = error;
            return false;
        }
    }
}
