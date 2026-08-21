// 역할: 비전에서 받은 Unity 월드 Pose에 현장 보정값을 적용해 PCB Transform에 반영한다.

using UnityEngine;

namespace MainUnity.Runtime.Camera
{
    [DisallowMultipleComponent]
    public sealed class Calibration : MonoBehaviour
    {
        [SerializeField] Transform pcbTarget;
        [SerializeField] Vector3 positionOffsetMeters;
        [SerializeField] Vector3 rotationOffsetDegrees;

        public bool TryApplyDetectedPose(Pose detectedWorldPose)
        {
            if (pcbTarget == null || !IsFinite(detectedWorldPose))
                return false;

            pcbTarget.SetPositionAndRotation(
                detectedWorldPose.position + positionOffsetMeters,
                detectedWorldPose.rotation * Quaternion.Euler(rotationOffsetDegrees));
            return true;
        }

        static bool IsFinite(Pose pose)
        {
            Vector3 position = pose.position;
            Quaternion rotation = pose.rotation;
            return float.IsFinite(position.x) && float.IsFinite(position.y) &&
                float.IsFinite(position.z) && float.IsFinite(rotation.x) &&
                float.IsFinite(rotation.y) && float.IsFinite(rotation.z) &&
                float.IsFinite(rotation.w);
        }
    }
}
