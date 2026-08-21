// 역할: 실제 TCP에서 지정 방향으로 Raycast하여 하강 지점을 붉은 선으로 표시한다.

using UnityEngine;

namespace MainUnity.Runtime.Robot
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(LineRenderer))]
    public sealed class TcpLandingLaser : MonoBehaviour
    {
        [SerializeField] Vector3 localDirection = Vector3.down;
        [SerializeField, Min(0.01f)] float maxDistance = 2f;
        [SerializeField] LayerMask collisionMask = ~0;

        LineRenderer line;

        void Awake() => line = GetComponent<LineRenderer>();

        void LateUpdate()
        {
            line ??= GetComponent<LineRenderer>();
            Vector3 direction = transform.TransformDirection(localDirection).normalized;
            float distance = Physics.Raycast(transform.position, direction, out RaycastHit hit,
                maxDistance, collisionMask, QueryTriggerInteraction.Ignore)
                ? hit.distance
                : maxDistance;
            line.SetPosition(0, Vector3.zero);
            line.SetPosition(1, transform.InverseTransformDirection(direction) * distance);
        }
    }
}
