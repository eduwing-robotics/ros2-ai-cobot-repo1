// 관제 작업에 사용할 대상과 집기·놓기 위치를 보관합니다.

using UnityEngine;

namespace FR5Mvp.PickPlace
{
    /// <summary>Pick & Place 대상과 두 작업 자세를 선택·보관합니다.</summary>
    [AddComponentMenu("Robotics/FR5/Pick Place/Target Selection")]
    [DisallowMultipleComponent]
    public sealed class TargetSelection : MonoBehaviour
    {
        [SerializeField] Transform selectedObject;
        [SerializeField, HideInInspector] Pose pickPose;
        [SerializeField, HideInInspector] Pose placePose;
        [SerializeField, HideInInspector] bool hasPickPose;
        [SerializeField, HideInInspector] bool hasPlacePose;

        public Transform SelectedObject => selectedObject;
        public Pose PickPose => pickPose;
        public Pose PlacePose => placePose;
        public bool IsReady => selectedObject != null && hasPickPose && hasPlacePose;
        public string LastError { get; private set; } = string.Empty;

        /// <summary>Pick & Place 작업의 대상 오브젝트를 지정합니다.</summary>
        public bool SelectObject(Transform target)
        {
            if (target == null)
                return Reject("Select a work object.");
            selectedObject = target;
            LastError = string.Empty;
            return true;
        }

        /// <summary>Unity 월드 좌표계의 Pick 자세를 저장합니다.</summary>
        public bool SetPickPose(Pose pose)
        {
            if (!IsFinite(pose))
                return Reject("Pick pose must contain finite values.");
            pickPose = Normalize(pose);
            hasPickPose = true;
            LastError = string.Empty;
            return true;
        }

        /// <summary>Unity 월드 좌표계의 Place 자세를 저장합니다.</summary>
        public bool SetPlacePose(Pose pose)
        {
            if (!IsFinite(pose))
                return Reject("Place pose must contain finite values.");
            placePose = Normalize(pose);
            hasPlacePose = true;
            LastError = string.Empty;
            return true;
        }

        /// <summary>현재 작업 대상을 모두 비웁니다.</summary>
        public void Clear()
        {
            selectedObject = null;
            pickPose = default;
            placePose = default;
            hasPickPose = false;
            hasPlacePose = false;
            LastError = string.Empty;
        }

        bool Reject(string error)
        {
            LastError = error;
            return false;
        }

        static Pose Normalize(Pose pose) =>
            new(pose.position, pose.rotation.normalized);

        static bool IsFinite(Pose pose)
        {
            Vector3 p = pose.position;
            Quaternion r = pose.rotation;
            return float.IsFinite(p.x) && float.IsFinite(p.y) && float.IsFinite(p.z) &&
                float.IsFinite(r.x) && float.IsFinite(r.y) &&
                float.IsFinite(r.z) && float.IsFinite(r.w) &&
                r.x * r.x + r.y * r.y + r.z * r.z + r.w * r.w > Mathf.Epsilon;
        }
    }
}
