using System;
using System.Globalization;
using System.Threading.Tasks;
using MainUnity.Runtime.Robot.Status;
using MainUnity.Runtime.RobotGhost;
using RosMessageTypes.Geometry;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Real
{
    [DisallowMultipleComponent]
    public sealed class RealFairinoSdkGhostSolver : MonoBehaviour
    {
        const int JointCount = 6;

        [SerializeField] string targetTopic = "/real/ghost/target";
        [SerializeField] string expectedFrame = "base_link";

        ROSConnection connection;
        GhostMaster ghostMaster;
        RobotStatusManager statusManager;
        RealRobotControl robotControl;
        RealGhostToolPose toolPose;
        RealGhostTarget pendingTarget;
        bool active;
        bool subscribed;
        bool solving;
        bool hasPendingTarget;
        int targetVersion;
        int activationVersion;

        void OnDisable() => Deactivate();

        internal bool Initialize(GhostMaster destination,
            RobotStatusManager injectedStatusManager, RealRobotControl injectedRobotControl,
            Vector3 toolPositionMillimeters, Vector3 toolRotationDegrees)
        {
            ghostMaster = destination;
            statusManager = injectedStatusManager;
            robotControl = injectedRobotControl;
            toolPose = new RealGhostToolPose(toolPositionMillimeters, toolRotationDegrees);
            if (active)
                Subscribe();
            return ghostMaster != null && statusManager != null && robotControl != null &&
                !string.IsNullOrWhiteSpace(targetTopic) && !string.IsNullOrWhiteSpace(expectedFrame);
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
            activationVersion++;
            enabled = true;
            Subscribe();
        }

        void Subscribe()
        {
            if (subscribed || !active || ghostMaster == null || statusManager == null ||
                robotControl == null)
                return;
            if (string.IsNullOrWhiteSpace(targetTopic) || string.IsNullOrWhiteSpace(expectedFrame))
            {
                Debug.LogError("Real FAIRINO SDK Ghost target topic and frame are required.", this);
                return;
            }

            connection ??= ROSConnection.GetOrCreateInstance();
            connection.Subscribe<PoseStampedMsg>(targetTopic, ReceiveTarget);
            subscribed = true;
        }

        void Deactivate()
        {
            if (active)
                activationVersion++;
            active = false;
            hasPendingTarget = false;
            if (!subscribed)
                return;
            connection?.Unsubscribe(targetTopic);
            subscribed = false;
        }

        void ReceiveTarget(PoseStampedMsg message)
        {
            if (!RealGhostPose.TryGetFlangeTarget(message, expectedFrame, toolPose,
                    out pendingTarget, out string error))
            {
                Debug.LogWarning(error, this);
                return;
            }

            hasPendingTarget = true;
            targetVersion++;
            _ = SolvePendingAsync();
        }

        async Task SolvePendingAsync()
        {
            if (solving)
                return;

            solving = true;
            try
            {
                while (active && hasPendingTarget)
                {
                    RealGhostTarget target = pendingTarget;
                    hasPendingTarget = false;
                    int requestedTargetVersion = targetVersion;
                    int requestedActivationVersion = activationVersion;
                    float[] referenceJoints = statusManager.Latest?.JointDegrees;
                    if (!TryBuildCommand(target, referenceJoints, out string command,
                            out string error))
                    {
                        Debug.LogWarning(error, this);
                        continue;
                    }

                    double startedAt = Time.realtimeSinceStartupAsDouble;
                    string response;
                    try
                    {
                        response = await robotControl.QueryInverseKinRefAsync(command);
                    }
                    catch (Exception exception)
                    {
                        Debug.LogWarning("Real FAIRINO SDK Ghost query failed: " + exception.Message,
                            this);
                        continue;
                    }

                    if (!active || requestedActivationVersion != activationVersion)
                        return;
                    if (requestedTargetVersion != targetVersion)
                        continue;
                    if (!TryParseResponse(response, out float[] jointDegrees, out error))
                    {
                        Debug.LogWarning(error, this);
                        continue;
                    }
                    if (!ghostMaster.PreviewJoints(jointDegrees))
                    {
                        Debug.LogWarning("Real FAIRINO SDK Ghost rejected the solved joints.", this);
                        continue;
                    }

                    double elapsed = Time.realtimeSinceStartupAsDouble - startedAt;
                    Debug.Log($"Real FAIRINO SDK Ghost solved in {elapsed * 1000d:0} ms.", this);
                }
            }
            finally
            {
                solving = false;
                if (active && hasPendingTarget)
                    _ = SolvePendingAsync();
            }
        }

        static bool TryBuildCommand(RealGhostTarget target, float[] referenceJoints,
            out string command, out string error)
        {
            command = string.Empty;
            if (referenceJoints == null || referenceJoints.Length != JointCount)
            {
                error = "Real FAIRINO SDK Ghost requires the latest six robot joints.";
                return false;
            }
            for (int i = 0; i < referenceJoints.Length; i++)
            {
                if (float.IsFinite(referenceJoints[i]))
                    continue;
                error = "Real FAIRINO SDK Ghost rejected non-finite robot joints.";
                return false;
            }

            Vector3 position = target.PositionMeters * 1000f;
            Vector3 rotation = RealGhostPose.QuaternionToRpyDegrees(target.Rotation);
            command = string.Format(CultureInfo.InvariantCulture,
                "GetInverseKinRef(0,{0},{1},{2},{3},{4},{5},{6},{7},{8},{9},{10},{11})",
                position.x, position.y, position.z, rotation.x, rotation.y, rotation.z,
                referenceJoints[0], referenceJoints[1], referenceJoints[2],
                referenceJoints[3], referenceJoints[4], referenceJoints[5]);
            error = string.Empty;
            return true;
        }

        static bool TryParseResponse(string response, out float[] jointDegrees, out string error)
        {
            jointDegrees = Array.Empty<float>();
            string[] values = (response ?? string.Empty).Split(',');
            if (values.Length != JointCount + 1 ||
                !int.TryParse(values[0].Trim(), NumberStyles.Integer,
                    CultureInfo.InvariantCulture, out int resultCode))
            {
                error = "FAIRINO GetInverseKinRef returned an invalid response: " + response;
                return false;
            }
            if (resultCode != 0)
            {
                error = $"FAIRINO GetInverseKinRef failed with code {resultCode}.";
                return false;
            }

            jointDegrees = new float[JointCount];
            for (int i = 0; i < jointDegrees.Length; i++)
            {
                if (float.TryParse(values[i + 1].Trim(), NumberStyles.Float,
                        CultureInfo.InvariantCulture, out jointDegrees[i]) &&
                    float.IsFinite(jointDegrees[i]))
                    continue;
                jointDegrees = Array.Empty<float>();
                error = "FAIRINO GetInverseKinRef returned invalid joint values: " + response;
                return false;
            }

            error = string.Empty;
            return true;
        }

#if UNITY_EDITOR
        [ContextMenu("Self Check FAIRINO Ghost Response")]
        void SelfCheckResponse()
        {
            Debug.Assert(TryParseResponse("0,1,2,3,4,5,6", out float[] joints,
                out string error) && joints.Length == JointCount, error, this);
            Debug.Assert(!TryParseResponse("1,1,2,3,4,5,6", out _, out _),
                "A non-zero FAIRINO result must be rejected.", this);
        }
#endif
    }
}
