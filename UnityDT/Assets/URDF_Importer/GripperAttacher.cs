using UnityEngine;

#if UNITY_EDITOR
using System;
using System.Linq;
#endif

namespace MainUnity.UrdfImport
{
    [DisallowMultipleComponent]
    public sealed class GripperAttacher : MonoBehaviour
    {
        [SerializeField] ArticulationBody driver;
        [SerializeField] ArticulationBody follower;
        [SerializeField] float target;
        [SerializeField, Min(0.001f)] float followSpeedMetersPerSecond = 0.05f;
        [SerializeField, HideInInspector] float driverLower;
        [SerializeField, HideInInspector] float driverUpper;
        [SerializeField, HideInInspector] float followerLower;
        [SerializeField, HideInInspector] float followerUpper;
        [SerializeField, HideInInspector] float multiplier = 1f;
        [SerializeField, HideInInspector] float offset;

        public float Target
        {
            get => target;
            set => target = Mathf.Clamp(value, driverLower, driverUpper);
        }

        /// <summary>지정한 열림 비율(0~100%)을 그리퍼 이동 범위에 반영한다.</summary>
        public void SetOpeningPercent(float openingPercent)
        {
            Target = Mathf.Lerp(driverUpper, driverLower, Mathf.Clamp01(openingPercent / 100f));
            ApplyTargets(target);
        }

#if UNITY_EDITOR
        internal static void Apply(RobotBuildResult robot, UrdfModel model)
        {
            UrdfJoint[] prismatic = model.OrderedJoints
                .Where(joint => joint.Type == UrdfJointType.Prismatic)
                .ToArray();
            UrdfJoint followerData = prismatic.Single(
                joint => !string.IsNullOrEmpty(joint.MimicJoint));
            UrdfJoint driverData = prismatic.Single(
                joint => joint.Name == followerData.MimicJoint);
            ArticulationBody driverBody = robot.JointTransforms[driverData.Name]
                .GetComponent<ArticulationBody>();
            ArticulationBody followerBody = robot.JointTransforms[followerData.Name]
                .GetComponent<ArticulationBody>();
            if (driverBody == null || followerBody == null)
                throw new InvalidOperationException(
                    "Gripper ArticulationBody components must be created first.");

            Transform gripperRoot = robot.LinkTransforms[driverData.Parent];
            GripperAttacher attacher = gripperRoot.gameObject.AddComponent<GripperAttacher>();
            attacher.Configure(driverBody, followerBody, driverData, followerData);
        }

        void Configure(
            ArticulationBody driverBody,
            ArticulationBody followerBody,
            UrdfJoint driverData,
            UrdfJoint followerData)
        {
            driver = driverBody;
            follower = followerBody;
            driverLower = driverData.LowerLimit;
            driverUpper = driverData.UpperLimit;
            followerLower = followerData.LowerLimit;
            followerUpper = followerData.UpperLimit;
            multiplier = followerData.MimicMultiplier;
            offset = followerData.MimicOffset;
            target = Mathf.Clamp(driver.xDrive.target, driverLower, driverUpper);
            ApplyTargets(target);
        }
#endif

        void Awake() => ApplyTargets(target);

        void FixedUpdate()
        {
            if (driver == null)
                return;

            float smoothedTarget = Mathf.MoveTowards(
                driver.xDrive.target,
                target,
                followSpeedMetersPerSecond * Time.fixedDeltaTime);
            ApplyTargets(smoothedTarget);
        }

        void OnValidate()
        {
            target = Mathf.Clamp(target, driverLower, driverUpper);
            followSpeedMetersPerSecond = Mathf.Max(0.001f, followSpeedMetersPerSecond);
            if (Application.isPlaying)
                ApplyTargets(driver != null ? driver.xDrive.target : target);
        }

        void ApplyTargets(float appliedTarget)
        {
            if (driver == null || follower == null)
                return;

            ArticulationDrive driverDrive = driver.xDrive;
            driverDrive.target = Mathf.Clamp(appliedTarget, driverLower, driverUpper);
            driver.xDrive = driverDrive;

            ArticulationDrive followerDrive = follower.xDrive;
            followerDrive.target = Mathf.Clamp(
                driverDrive.target * multiplier + offset,
                followerLower,
                followerUpper);
            follower.xDrive = followerDrive;
        }
    }
}
