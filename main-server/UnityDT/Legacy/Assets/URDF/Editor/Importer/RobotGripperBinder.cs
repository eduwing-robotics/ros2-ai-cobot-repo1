// URDF의 두 그리퍼 관절과 연동 규칙을 그리퍼 제어기에 연결합니다.
// 로봇 본체 관절은 변경하지 않습니다.

using FR5Mvp.RobotControl;
using UnityEngine;

#if UNITY_EDITOR
using System;
using System.Linq;
#endif

namespace FR5Mvp.UrdfImport
{
    internal static class RobotGripperBinder
    {
#if UNITY_EDITOR
        internal static void Apply(UrdfModel model, RobotBuildResult robot)
        {
            UrdfJoint[] prismatic = model.OrderedJoints
                .Where(joint => joint.Type == UrdfJointType.Prismatic)
                .ToArray();
            UrdfJoint[] followers = prismatic
                .Where(joint => !string.IsNullOrEmpty(joint.MimicJoint))
                .ToArray();
            if (prismatic.Length != 2 || followers.Length != 1)
                throw new InvalidOperationException(
                    "FR5 gripper requires two prismatic joints and one mimic joint.");

            UrdfJoint follower = followers[0];
            UrdfJoint driver = prismatic.Single(
                joint => joint.Name == follower.MimicJoint);
            Transform driverTransform = robot.JointTransforms[driver.Name];
            Transform followerTransform = robot.JointTransforms[follower.Name];
            Transform gripperRoot = robot.LinkTransforms[driver.Parent];
            GripperController controller =
                gripperRoot.gameObject.AddComponent<GripperController>();
            controller.ConfigureUrdfJaws(
                driverTransform,
                followerTransform,
                driverTransform.localRotation *
                    RosUnityCoordinates.Position(driver.AxisRos),
                followerTransform.localRotation *
                    RosUnityCoordinates.Position(follower.AxisRos),
                driver.LowerLimit,
                driver.UpperLimit,
                follower.LowerLimit,
                follower.UpperLimit,
                follower.MimicMultiplier,
                follower.MimicOffset);
        }
#endif
    }
}
