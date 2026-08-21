// FR5 본체의 관절이 움직이도록 무게와 구동 값을 설정합니다.
// 그리퍼 동작과 외형은 변경하지 않습니다.

using FR5Mvp.RobotControl;
using UnityEngine;

#if UNITY_EDITOR
using System;
using System.Linq;
#endif

namespace FR5Mvp.UrdfImport
{
    internal static class RobotArticulationBuilder
    {
#if UNITY_EDITOR
        internal static void Apply(
            UrdfModel model,
            RobotBuildResult robot,
            float driveStiffness,
            float driveDamping)
        {
            int revoluteCount = model.OrderedJoints.Count(
                joint => joint.Type == UrdfJointType.Revolute);
            if (robot.Joints.Length != revoluteCount)
                throw new InvalidOperationException(
                    "FR5 revolute joint component count does not match its URDF.");

            ArticulationBody baseBody = ConfigureInertial(
                robot.Root, model.Links[model.BaseLink]);
            baseBody.immovable = true;

            foreach (UrdfJoint data in model.OrderedJoints)
            {
                if (data.Type != UrdfJointType.Revolute)
                    continue;

                GameObject jointObject = robot.JointTransforms[data.Name].gameObject;
                ArticulationBody body = ConfigureInertial(
                    jointObject, model.Links[data.Child]);
                body.linearDamping = data.Damping;
                body.angularDamping = data.Damping;
                body.jointFriction = data.Friction;

                body.anchorRotation = Quaternion.FromToRotation(
                    Vector3.right,
                    -RosUnityCoordinates.Position(data.AxisRos));
                body.maxJointVelocity = data.Velocity;

                body.jointType = ArticulationJointType.RevoluteJoint;
                body.twistLock = ArticulationDofLock.LimitedMotion;

                ArticulationDrive drive = body.xDrive;
                drive.lowerLimit = data.LowerLimit;
                drive.upperLimit = data.UpperLimit;
                drive.forceLimit = data.Effort;
                drive.stiffness = Mathf.Max(0f, driveStiffness);
                drive.damping = Mathf.Max(0f, driveDamping);
                body.xDrive = drive;

                JointController joint =
                    jointObject.GetComponent<JointController>();
                FR5Mvp.RobotControl.JointDrive.Attach(joint, body);
            }

            Collider[] colliders = robot.Root.GetComponentsInChildren<Collider>();
            // ponytail: 안정적인 시각화 우선. 실제 self-contact가 필요할 때 링크별 규칙으로 교체합니다.
            for (int i = 0; i < colliders.Length; i++)
                for (int j = i + 1; j < colliders.Length; j++)
                    Physics.IgnoreCollision(colliders[i], colliders[j]);
        }

        static ArticulationBody ConfigureInertial(GameObject target, UrdfLink link)
        {
            ArticulationBody body = target.GetComponent<ArticulationBody>();
            if (body == null)
                body = target.AddComponent<ArticulationBody>();

            if (!link.HasInertial)
            {
                // ponytail: 제조사 질량/관성값이 없는 부품에 임의 중력 하중을 만들지 않습니다.
                // 실제 값을 URDF에 추가하면 자동으로 정상 중력 물리 경로를 사용합니다.
                body.mass = 0.1f;
                body.useGravity = false;
                body.automaticCenterOfMass = true;
                body.automaticInertiaTensor = true;
                return body;
            }

            body.mass = link.Mass;
            body.useGravity = true;
            body.automaticCenterOfMass = false;
            body.centerOfMass = RosUnityCoordinates.Position(link.CenterOfMassRos);
            body.automaticInertiaTensor = false;
            SetInertia(body, link);
            return body;
        }

        static void SetInertia(ArticulationBody body, UrdfLink link)
        {
            Vector3 diagonal = link.InertiaDiagonalRos;
            Vector3 offDiagonal = link.InertiaOffDiagonalRos;
            Matrix4x4 rosTensor = Matrix4x4.zero;
            rosTensor[0, 0] = diagonal.x;
            rosTensor[1, 1] = diagonal.y;
            rosTensor[2, 2] = diagonal.z;
            rosTensor[0, 1] = rosTensor[1, 0] = offDiagonal.x;
            rosTensor[0, 2] = rosTensor[2, 0] = offDiagonal.y;
            rosTensor[1, 2] = rosTensor[2, 1] = offDiagonal.z;
            rosTensor[3, 3] = 1f;

            Matrix4x4 basis = Matrix4x4.zero;
            basis[0, 1] = -1f;
            basis[1, 2] = 1f;
            basis[2, 0] = 1f;
            basis[3, 3] = 1f;
            Matrix4x4 tensor = basis * rosTensor * basis.transpose;
            Matrix4x4 inertialRotation = Matrix4x4.Rotate(
                RosUnityCoordinates.Rotation(link.InertialRpyRos));
            tensor = inertialRotation * tensor * inertialRotation.transpose;

            Diagonalize(tensor, out Vector3 principal, out Quaternion rotation);
            const float minimumInertia = 1e-6f;
            body.inertiaTensor = new Vector3(
                Mathf.Max(minimumInertia, principal.x),
                Mathf.Max(minimumInertia, principal.y),
                Mathf.Max(minimumInertia, principal.z));
            body.inertiaTensorRotation = rotation;
        }

        /// <summary>URDF의 무게 중심 정보를 Unity 관절 움직임에 맞게 바꿉니다.</summary>
        static void Diagonalize(
            Matrix4x4 tensor,
            out Vector3 diagonal,
            out Quaternion rotation)
        {
            Matrix4x4 axes = Matrix4x4.identity;
            for (int iteration = 0; iteration < 16; iteration++)
            {
                int p = 0, q = 1;
                float largest = Mathf.Abs(tensor[0, 1]);
                if (Mathf.Abs(tensor[0, 2]) > largest)
                {
                    p = 0;
                    q = 2;
                    largest = Mathf.Abs(tensor[0, 2]);
                }
                if (Mathf.Abs(tensor[1, 2]) > largest)
                {
                    p = 1;
                    q = 2;
                    largest = Mathf.Abs(tensor[1, 2]);
                }
                if (largest < 1e-10f)
                    break;

                float app = tensor[p, p];
                float aqq = tensor[q, q];
                float apq = tensor[p, q];
                float angle = 0.5f * Mathf.Atan2(2f * apq, aqq - app);
                float c = Mathf.Cos(angle);
                float s = Mathf.Sin(angle);
                for (int k = 0; k < 3; k++)
                {
                    if (k != p && k != q)
                    {
                        float akp = tensor[k, p];
                        float akq = tensor[k, q];
                        tensor[k, p] = tensor[p, k] = c * akp - s * akq;
                        tensor[k, q] = tensor[q, k] = s * akp + c * akq;
                    }

                    float axisP = axes[k, p];
                    float axisQ = axes[k, q];
                    axes[k, p] = c * axisP - s * axisQ;
                    axes[k, q] = s * axisP + c * axisQ;
                }

                tensor[p, p] =
                    c * c * app - 2f * s * c * apq + s * s * aqq;
                tensor[q, q] =
                    s * s * app + 2f * s * c * apq + c * c * aqq;
                tensor[p, q] = tensor[q, p] = 0f;
            }

            diagonal = new Vector3(
                tensor[0, 0], tensor[1, 1], tensor[2, 2]);
            Vector3 x = new(axes[0, 0], axes[1, 0], axes[2, 0]);
            Vector3 y = new(axes[0, 1], axes[1, 1], axes[2, 1]);
            Vector3 z = new(axes[0, 2], axes[1, 2], axes[2, 2]);
            if (Vector3.Dot(Vector3.Cross(x, y), z) < 0f)
                z = -z;
            rotation = Quaternion.LookRotation(z, y);
        }
#endif
    }
}
