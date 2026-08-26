// 책임: Mock TCP 이동을 수동으로 시험하고 목표와 TCP의 월드 좌표 차이를 출력한다.

using System.Collections;
using MainUnity.Runtime.Robot;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Mock
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(MockRobotControl))]
    public sealed class MockTcpMoveDebug : MonoBehaviour
    {
        [SerializeField] MockRobotControl control;
        [SerializeField] Transform debugTarget;
        [SerializeField] Transform debugTcp;

        void Awake() => RefreshReferences();
        void OnValidate() => RefreshReferences();

        [ContextMenu("Debug/Move To Target")]
        void MoveToDebugTarget()
        {
            if (!Application.isPlaying || control == null || !TryGetTargetPose(out Pose target))
            {
                Debug.LogWarning("[MOCK-DEBUG-400] Assign Debug Target Renderer and enter Play Mode.", this);
                return;
            }

            StartCoroutine(MoveToDebugTargetRoutine(target));
        }

        IEnumerator MoveToDebugTargetRoutine(Pose target)
        {
            LogDebugWorldDelta("[MOCK-DEBUG-110] Before move", target.position);
            Debug.Log("[MOCK-DEBUG-100] Moving to " + debugTarget.name + ".", this);
            yield return control.MoveTo(target);

            if (control.LastCommandSucceeded)
                Debug.Log("[MOCK-DEBUG-200] Reached " + debugTarget.name + ".", this);
            else
                Debug.LogWarning("[MOCK-DEBUG-400] Failed to reach " + debugTarget.name + ".", this);
            LogDebugWorldDelta("[MOCK-DEBUG-210] After move", target.position);
        }

        bool TryGetTargetPose(out Pose target)
        {
            Renderer renderer = debugTarget != null ? debugTarget.GetComponentInChildren<Renderer>(true) : null;
            if (renderer == null)
            {
                target = default;
                return false;
            }

            target = new Pose(renderer.bounds.center, debugTarget.rotation);
            return true;
        }

        void LogDebugWorldDelta(string prefix, Vector3 targetPosition)
        {
            if (debugTcp == null)
            {
                Debug.LogWarning("[MOCK-DEBUG-410] Assign Debug TCP to compare world positions.", this);
                return;
            }

            Vector3 delta = debugTcp.position - targetPosition;
            Debug.Log(prefix +
                " targetWorld=" + targetPosition.ToString("F4") +
                " tcpWorld=" + debugTcp.position.ToString("F4") +
                " tcp-target=" + delta.ToString("F4"), this);
        }

        void RefreshReferences()
        {
            if (control == null)
                control = GetComponent<MockRobotControl>();
            if (debugTcp == null)
                debugTcp = FindAnyObjectByType<RobotMaster>()?.Tcp;
        }
    }
}
