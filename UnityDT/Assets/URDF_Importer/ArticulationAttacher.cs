using UnityEngine;

#if UNITY_EDITOR
using System;
#endif

namespace MainUnity.UrdfImport
{
    [DisallowMultipleComponent]
    public sealed class ArticulationAttacher : MonoBehaviour
    {
#if UNITY_EDITOR
        internal static void Apply(
            RobotBuildResult robot,
            UrdfModel model,
            float driveStiffness,
            float driveDamping)
        {
            ArticulationBody baseBody = ConfigureInertial(
                robot.Root,
                model.Links[model.BaseLink]);
            baseBody.immovable = true;

            foreach (UrdfJoint joint in model.OrderedJoints)
            {
                GameObject target = robot.JointTransforms[joint.Name].gameObject;
                ArticulationBody body = ConfigureInertial(target, model.Links[joint.Child]);
                body.linearDamping = Mathf.Max(0f, joint.Damping);
                body.angularDamping = Mathf.Max(0f, joint.Damping);
                body.jointFriction = Mathf.Max(0f, joint.Friction);

                switch (joint.Type)
                {
                    case UrdfJointType.Fixed:
                        body.jointType = ArticulationJointType.FixedJoint;
                        break;
                    case UrdfJointType.Revolute:
                        ConfigureRevolute(body, joint, driveStiffness, driveDamping);
                        break;
                    case UrdfJointType.Prismatic:
                        ConfigurePrismatic(body, joint, driveStiffness, driveDamping);
                        break;
                    default:
                        throw new ArgumentOutOfRangeException();
                }
            }

            ArticulationAttacher attacher = robot.Root.AddComponent<ArticulationAttacher>();
            attacher.IgnoreSelfCollisions();
        }

        static void ConfigureRevolute(
            ArticulationBody body,
            UrdfJoint joint,
            float stiffness,
            float damping)
        {
            body.jointType = ArticulationJointType.RevoluteJoint;
            body.anchorRotation = Quaternion.FromToRotation(
                Vector3.right,
                Ros2UnityCoordinate.AngularAxis(joint.AxisRos));
            body.twistLock = ArticulationDofLock.LimitedMotion;
            body.swingYLock = ArticulationDofLock.LockedMotion;
            body.swingZLock = ArticulationDofLock.LockedMotion;
            body.maxJointVelocity = joint.Velocity;

            ArticulationDrive drive = body.xDrive;
            drive.lowerLimit = joint.LowerLimit * Mathf.Rad2Deg;
            drive.upperLimit = joint.UpperLimit * Mathf.Rad2Deg;
            drive.forceLimit = joint.Effort;
            drive.stiffness = Mathf.Max(0f, stiffness);
            drive.damping = Mathf.Max(0f, damping);
            drive.target = Mathf.Clamp(0f, drive.lowerLimit, drive.upperLimit);
            body.xDrive = drive;
        }

        static void ConfigurePrismatic(
            ArticulationBody body,
            UrdfJoint joint,
            float stiffness,
            float damping)
        {
            body.jointType = ArticulationJointType.PrismaticJoint;
            body.anchorRotation = Quaternion.FromToRotation(
                Vector3.right,
                Ros2UnityCoordinate.LinearAxis(joint.AxisRos));
            body.linearLockX = ArticulationDofLock.LimitedMotion;
            body.linearLockY = ArticulationDofLock.LockedMotion;
            body.linearLockZ = ArticulationDofLock.LockedMotion;
            body.maxJointVelocity = joint.Velocity;

            ArticulationDrive drive = body.xDrive;
            drive.lowerLimit = joint.LowerLimit;
            drive.upperLimit = joint.UpperLimit;
            drive.forceLimit = joint.Effort;
            drive.stiffness = Mathf.Max(0f, stiffness);
            drive.damping = Mathf.Max(0f, damping);
            drive.target = Mathf.Clamp(0f, drive.lowerLimit, drive.upperLimit);
            body.xDrive = drive;
        }

        static ArticulationBody ConfigureInertial(GameObject target, UrdfLink link)
        {
            ArticulationBody body = target.GetComponent<ArticulationBody>();
            if (body == null)
                body = target.AddComponent<ArticulationBody>();

            if (!link.HasInertial)
            {
                body.mass = 0.1f;
                body.useGravity = false;
                body.automaticCenterOfMass = true;
                body.automaticInertiaTensor = true;
                Debug.LogWarning(
                    $"Link '{link.Name}' has no inertial data; using automatic inertia without gravity.",
                    target);
                return body;
            }

            body.mass = link.Mass;
            body.useGravity = true;
            body.automaticCenterOfMass = false;
            body.centerOfMass = Ros2UnityCoordinate.Position(link.CenterOfMassRos);
            body.automaticInertiaTensor = false;
            Ros2UnityCoordinate.Inertia(
                link,
                out Vector3 inertiaTensor,
                out Quaternion inertiaRotation);
            body.inertiaTensor = inertiaTensor;
            body.inertiaTensorRotation = inertiaRotation;
            return body;
        }
#endif

        void Awake() => IgnoreSelfCollisions();

        void IgnoreSelfCollisions()
        {
            Collider[] colliders = GetComponentsInChildren<Collider>(true);
            for (int i = 0; i < colliders.Length; i++)
                for (int j = i + 1; j < colliders.Length; j++)
                    Physics.IgnoreCollision(colliders[i], colliders[j], true);
        }
    }
}
