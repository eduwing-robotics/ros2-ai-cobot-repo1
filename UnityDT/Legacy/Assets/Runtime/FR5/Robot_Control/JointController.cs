// FR5 관절 하나의 범위와 목표값을 관리하고 해당 관절 구동기에 명령을 전달합니다.

using UnityEngine;

namespace FR5Mvp.RobotControl
{
    /// <summary>관절 하나의 제한, 목표 위치와 목표 속도를 관리합니다.</summary>
    public sealed class JointController : MonoBehaviour
    {
        [SerializeField, HideInInspector] string jointName;
        [SerializeField, HideInInspector] Vector3 localAxis;
        [SerializeField, HideInInspector] float lowerDegrees;
        [SerializeField, HideInInspector] float upperDegrees;
        [SerializeField, HideInInspector] float valueDegrees;
        [SerializeField, HideInInspector] float maxVelocityDegreesPerSecond;
        [SerializeField, HideInInspector] Quaternion zeroRotation = Quaternion.identity;

        JointDrive drive;
        float targetVelocityDegreesPerSecond;

        public string JointName => jointName;
        public Vector3 LocalAxis => localAxis;
        public float LowerDegrees => lowerDegrees;
        public float UpperDegrees => upperDegrees;
        public float ValueDegrees => valueDegrees;
        public float MaxVelocityDegreesPerSecond => maxVelocityDegreesPerSecond;
        public float TargetVelocityDegreesPerSecond => targetVelocityDegreesPerSecond;
        public bool HasArticulationBody => Drive != null && Drive.IsBound;
        public float ActualDegrees => HasArticulationBody
            ? Drive.ActualDegrees
            : ValueDegrees;
        public float ActualVelocityDegreesPerSecond => HasArticulationBody
            ? Drive.ActualVelocityDegreesPerSecond
            : 0f;

        JointDrive Drive => drive != null
            ? drive
            : drive = GetComponent<JointDrive>();

        /// <summary>관절을 움직이는 데 필요한 기본 정보를 설정합니다.</summary>
        public void Configure(
            string jointName,
            Vector3 localAxis,
            float lowerDegrees,
            float upperDegrees,
            float maxVelocityRadiansPerSecond = float.PositiveInfinity)
        {
            this.jointName = jointName;
            this.localAxis = localAxis.normalized;
            this.lowerDegrees = lowerDegrees;
            this.upperDegrees = upperDegrees;
            maxVelocityDegreesPerSecond = maxVelocityRadiansPerSecond * Mathf.Rad2Deg;
            zeroRotation = transform.localRotation;
        }

        internal void UseDrive(JointDrive jointDrive) => drive = jointDrive;

        /// <summary>관절을 허용 범위 안에서 요청한 각도로 움직입니다.</summary>
        public void SetDegrees(float degrees)
        {
            valueDegrees = Mathf.Clamp(degrees, LowerDegrees, UpperDegrees);
            targetVelocityDegreesPerSecond = 0f;
            if (!HasArticulationBody)
            {
                transform.localRotation = zeroRotation * Quaternion.AngleAxis(ValueDegrees, LocalAxis);
                return;
            }

            Drive.SetPositionDegrees(ValueDegrees);
        }

        /// <summary>현재 관절 각도를 허용 범위 안에서 따라가도록 설정합니다.</summary>
        public void FollowDegrees(float degrees) => SetDegrees(degrees);

        /// <summary>관절의 목표 속도를 허용 범위 안에서 설정합니다.</summary>
        public void SetVelocityDegreesPerSecond(float degreesPerSecond)
        {
            targetVelocityDegreesPerSecond = Mathf.Clamp(
                degreesPerSecond,
                -MaxVelocityDegreesPerSecond,
                MaxVelocityDegreesPerSecond);
            if (!HasArticulationBody)
                return;
            Drive.SetVelocityDegreesPerSecond(TargetVelocityDegreesPerSecond);
        }
    }
}
