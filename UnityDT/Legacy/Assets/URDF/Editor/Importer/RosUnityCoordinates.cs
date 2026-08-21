#if UNITY_EDITOR
// URDF의 위치와 방향을 Unity 장면 기준으로 바꿉니다.
// 로봇 오브젝트는 변경하지 않습니다.

using UnityEngine;

namespace FR5Mvp.UrdfImport
{
    internal static class RosUnityCoordinates
    {
        /// <summary>URDF 위치와 방향을 Unity 장면 기준으로 바꿉니다.</summary>
        internal static Vector3 Position(Vector3 ros) => new(-ros.y, ros.z, ros.x);

        /// <summary>URDF 크기를 Unity 장면의 축 순서에 맞춥니다.</summary>
        internal static Vector3 Scale(Vector3 ros) => new(ros.y, ros.z, ros.x);

        /// <summary>URDF 회전을 Unity 장면의 방향으로 바꿉니다.</summary>
        internal static Quaternion Rotation(Vector3 rpy)
        {
            float cr = Mathf.Cos(rpy.x), sr = Mathf.Sin(rpy.x);
            float cp = Mathf.Cos(rpy.y), sp = Mathf.Sin(rpy.y);
            float cy = Mathf.Cos(rpy.z), sy = Mathf.Sin(rpy.z);

            Vector3 Rotate(Vector3 value) => new(
                (cy * cp) * value.x +
                    (cy * sp * sr - sy * cr) * value.y +
                    (cy * sp * cr + sy * sr) * value.z,
                (sy * cp) * value.x +
                    (sy * sp * sr + cy * cr) * value.y +
                    (sy * sp * cr - cy * sr) * value.z,
                (-sp) * value.x +
                    (cp * sr) * value.y +
                    (cp * cr) * value.z);

            return Quaternion.LookRotation(
                Position(Rotate(Vector3.right)),
                Position(Rotate(Vector3.forward)));
        }
    }
}
#endif
