#if UNITY_EDITOR
using UnityEngine;

namespace MainUnity.UrdfImport
{
    internal static class Ros2UnityCoordinate
    {
        internal static Vector3 Position(Vector3 ros) => new(-ros.y, ros.z, ros.x);

        internal static Vector3 Scale(Vector3 ros) => new(ros.y, ros.z, ros.x);

        internal static Vector3 LinearAxis(Vector3 ros) => Position(ros).normalized;

        internal static Vector3 AngularAxis(Vector3 ros) => -Position(ros).normalized;

        internal static Quaternion Rotation(Vector3 rpy)
        {
            float cr = Mathf.Cos(rpy.x), sr = Mathf.Sin(rpy.x);
            float cp = Mathf.Cos(rpy.y), sp = Mathf.Sin(rpy.y);
            float cy = Mathf.Cos(rpy.z), sy = Mathf.Sin(rpy.z);

            Vector3 Rotate(Vector3 value) => new(
                cy * cp * value.x + (cy * sp * sr - sy * cr) * value.y +
                    (cy * sp * cr + sy * sr) * value.z,
                sy * cp * value.x + (sy * sp * sr + cy * cr) * value.y +
                    (sy * sp * cr - cy * sr) * value.z,
                -sp * value.x + cp * sr * value.y + cp * cr * value.z);

            return Quaternion.LookRotation(
                Position(Rotate(Vector3.right)),
                Position(Rotate(Vector3.forward)));
        }

        internal static void Inertia(
            UrdfLink link,
            out Vector3 principal,
            out Quaternion principalRotation)
        {
            Vector3 diagonal = link.InertiaDiagonalRos;
            Vector3 offDiagonal = link.InertiaOffDiagonalRos;
            Matrix4x4 ros = Matrix4x4.zero;
            ros[0, 0] = diagonal.x;
            ros[1, 1] = diagonal.y;
            ros[2, 2] = diagonal.z;
            ros[0, 1] = ros[1, 0] = offDiagonal.x;
            ros[0, 2] = ros[2, 0] = offDiagonal.y;
            ros[1, 2] = ros[2, 1] = offDiagonal.z;
            ros[3, 3] = 1f;

            Matrix4x4 basis = Matrix4x4.zero;
            basis[0, 1] = -1f;
            basis[1, 2] = 1f;
            basis[2, 0] = 1f;
            basis[3, 3] = 1f;
            Matrix4x4 tensor = basis * ros * basis.transpose;
            Matrix4x4 inertialRotation = Matrix4x4.Rotate(Rotation(link.InertialRpyRos));
            tensor = inertialRotation * tensor * inertialRotation.transpose;

            Diagonalize(tensor, out principal, out principalRotation);
            const float minimum = 1e-6f;
            principal = new Vector3(
                Mathf.Max(minimum, principal.x),
                Mathf.Max(minimum, principal.y),
                Mathf.Max(minimum, principal.z));
        }

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

                tensor[p, p] = c * c * app - 2f * s * c * apq + s * s * aqq;
                tensor[q, q] = s * s * app + 2f * s * c * apq + c * c * aqq;
                tensor[p, q] = tensor[q, p] = 0f;
            }

            diagonal = new Vector3(tensor[0, 0], tensor[1, 1], tensor[2, 2]);
            Vector3 x = new(axes[0, 0], axes[1, 0], axes[2, 0]);
            Vector3 y = new(axes[0, 1], axes[1, 1], axes[2, 1]);
            Vector3 z = new(axes[0, 2], axes[1, 2], axes[2, 2]);
            if (Vector3.Dot(Vector3.Cross(x, y), z) < 0f)
                z = -z;
            rotation = Quaternion.LookRotation(z, y);
        }
    }
}
#endif
