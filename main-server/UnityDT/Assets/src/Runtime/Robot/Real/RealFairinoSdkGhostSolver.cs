using System;
using System.Collections;
using MainUnity.Runtime.Robot.Status;
using MainUnity.Runtime.RobotGhost;
using RosMessageTypes.Sensor;
using RosMessageTypes.Std;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Real
{
    // Scene 직렬화 참조를 보존하기 위해 클래스명은 유지하지만 IK는 Robot Backend가 소유한다.
    [DisallowMultipleComponent]
    public sealed class RealFairinoSdkGhostSolver : MonoBehaviour
    {
        const int JointCount = 6;
        // 시각화 종료용 관절 오차(deg)이며 설비의 동작 완료 판정을 변경하지 않는다.
        const float ArrivalToleranceDegrees = 0.5f;

        [SerializeField] string targetTopic = "/real/ghost/target";
        [SerializeField] string expectedFrame = "base_link";

        ROSConnection connection;
        GhostMaster ghostMaster;
        RobotStatusManager statusManager;
        Coroutine arrivalRoutine;
        bool active;
        bool subscribed;

        void OnDisable() => Deactivate();

        internal bool Initialize(GhostMaster destination, RobotStatusManager injectedStatusManager)
        {
            ghostMaster = destination;
            statusManager = injectedStatusManager;
            if (active)
                Subscribe();
            return ghostMaster != null &&
                !string.IsNullOrWhiteSpace(targetTopic) &&
                !string.IsNullOrWhiteSpace(expectedFrame);
        }

        internal void SetActive(bool value)
        {
            if (!value)
            {
                Deactivate();
                enabled = false;
                return;
            }

            active = true;
            enabled = true;
            Subscribe();
        }

        void Subscribe()
        {
            if (subscribed || !active || ghostMaster == null)
                return;
            if (string.IsNullOrWhiteSpace(targetTopic) ||
                string.IsNullOrWhiteSpace(expectedFrame))
            {
                Debug.LogError("Real Ghost target topic and frame are required.", this);
                return;
            }

            connection ??= ROSConnection.GetOrCreateInstance();
            connection.Subscribe<JointStateMsg>(targetTopic, ReceiveTarget);
            subscribed = true;
        }

        void Deactivate()
        {
            active = false;
            if (arrivalRoutine != null)
            {
                StopCoroutine(arrivalRoutine);
                arrivalRoutine = null;
                ghostMaster?.SetVisible(false);
            }
            if (!subscribed)
                return;
            connection?.Unsubscribe(targetTopic);
            subscribed = false;
        }

        void ReceiveTarget(JointStateMsg message)
        {
            if (!active)
                return;
            if (!TryGetJointDegrees(message, expectedFrame,
                    out float[] jointDegrees, out string error))
            {
                Debug.LogWarning(error, this);
                return;
            }

            if (!ghostMaster.PreviewJoints(jointDegrees))
            {
                Debug.LogWarning("Real Ghost rejected the joint target.", this);
                return;
            }

            if (arrivalRoutine != null)
                StopCoroutine(arrivalRoutine);
            arrivalRoutine = StartCoroutine(HideWhenArrived(jointDegrees, Time.realtimeSinceStartupAsDouble));
        }

        IEnumerator HideWhenArrived(float[] targetDegrees, double targetReceiveTime)
        {
            // 첫 yield로 코루틴 핸들 저장을 보장한다. 목표 교체 시 이전 감시는 중단한다.
            do
            {
                yield return null;
            }
            while (active && !HasArrived(targetDegrees, targetReceiveTime));

            if (active)
                ghostMaster.SetVisible(false);
            arrivalRoutine = null;
        }

        bool HasArrived(float[] targetDegrees, double targetReceiveTime)
        {
            if (statusManager == null || !statusManager.HasFreshState ||
                statusManager.State != RobotRunState.Idle)
                return false;

            var frame = statusManager.Latest;
            // 목표 수신 이전의 캐시된 상태로 새 목표의 도달을 판정하지 않는다.
            if (frame == null || frame.ReceiveTimeSeconds <= targetReceiveTime ||
                frame.RobotMotionDone == 0)
                return false;

            for (int i = 0; i < JointCount; i++)
            {
                // 실제 관절의 회전수도 목표의 일부이므로 360도 차이를 같은 도달로 취급하지 않는다.
                float difference = frame.JointDegrees[i] - targetDegrees[i];
                if (!float.IsFinite(difference) || Mathf.Abs(difference) > ArrivalToleranceDegrees)
                    return false;
            }
            return true;
        }

        static bool TryGetJointDegrees(JointStateMsg message, string expectedFrame,
            out float[] jointDegrees, out string error)
        {
            jointDegrees = Array.Empty<float>();
            if (message?.name == null || message.position == null ||
                message.name.Length != JointCount ||
                message.position.Length != JointCount)
            {
                error = "Real Ghost requires exactly six joint names and positions.";
                return false;
            }

            string frame = message.header?.frame_id ?? string.Empty;
            if (frame.Length > 0 &&
                !string.Equals(frame, expectedFrame, StringComparison.Ordinal))
            {
                error = $"Real Ghost target frame must be '{expectedFrame}' when provided.";
                return false;
            }

            var mappedDegrees = new float[JointCount];
            var seen = new bool[JointCount];
            for (int i = 0; i < JointCount; i++)
            {
                int jointIndex = GetJointIndex(message.name[i]);
                if (jointIndex < 0 || seen[jointIndex])
                {
                    error = "Real Ghost joint names must contain j1 through j6 exactly once.";
                    return false;
                }

                double radians = message.position[i];
                float degrees = (float)(radians * Mathf.Rad2Deg);
                if (double.IsNaN(radians) || double.IsInfinity(radians) ||
                    !float.IsFinite(degrees))
                {
                    error = $"Real Ghost joint {message.name[i]} is not finite.";
                    return false;
                }

                seen[jointIndex] = true;
                mappedDegrees[jointIndex] = degrees;
            }

            jointDegrees = mappedDegrees;
            error = string.Empty;
            return true;
        }

        static int GetJointIndex(string jointName)
        {
            if (jointName == null || jointName.Length != 2 ||
                jointName[0] != 'j' || jointName[1] < '1' || jointName[1] > '6')
                return -1;
            return jointName[1] - '1';
        }

#if UNITY_EDITOR
        [ContextMenu("Self Check Real Ghost Joint Target")]
        void SelfCheckJointTarget()
        {
            var message = new JointStateMsg(
                new HeaderMsg { frame_id = "base_link" },
                new[] { "j6", "j1", "j2", "j3", "j4", "j5" },
                new[] { Math.PI, 0d, Math.PI / 2d, -Math.PI / 2d, 0.25d, -0.25d },
                Array.Empty<double>(),
                Array.Empty<double>());

            Debug.Assert(TryGetJointDegrees(message, "base_link",
                    out float[] joints, out string error) &&
                Mathf.Approximately(joints[0], 0f) &&
                Mathf.Approximately(joints[1], 90f) &&
                Mathf.Approximately(joints[5], 180f), error, this);

            message.name[0] = "j1";
            Debug.Assert(!TryGetJointDegrees(message, "base_link", out _, out _),
                "Duplicate Real Ghost joint names must be rejected.", this);
        }
#endif
    }
}
