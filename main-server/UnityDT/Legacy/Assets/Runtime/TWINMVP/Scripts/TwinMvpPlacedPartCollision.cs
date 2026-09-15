using UnityEngine;

namespace TWINMVP
{
    [DisallowMultipleComponent]
    public sealed class TwinMvpPlacedPartCollision : MonoBehaviour
    {
        Transform robotRoot;

        public void Configure(Transform value) => robotRoot = value;

        void OnCollisionEnter(Collision collision)
        {
            if (robotRoot == null || !collision.transform.IsChildOf(robotRoot))
                return;
            Debug.LogWarning(
                $"TWIN MVP collision: placed '{name}' interfered with " +
                $"'{collision.collider.name}'.", this);
        }
    }
}
