using System;
using MainUnity.Runtime.Robot.Status;
using MainUnity.Runtime.RobotGhost;
using RosMessageTypes.Geometry;
using RosMessageTypes.Sensor;
using RosMessageTypes.Std;
using RosMessageTypes.Trajectory;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Real
{
    [DisallowMultipleComponent]
    public sealed class RealMoveItGhostSolver : MonoBehaviour, IRealGhostSolver
    {
        static readonly string[] JointNames = { "j1", "j2", "j3", "j4", "j5", "j6" };

        [SerializeField] string targetTopic = "/real/ghost/target";
        [SerializeField] string moveItTargetTopic = "/twin_visual/movel_target";
        [SerializeField] string previewTopic = "/twin_visual/movel_preview";
        [SerializeField] string statusTopic = "/twin_visual/status";
        [SerializeField] string jointStateTopic = "/joint_states";
        [SerializeField] string expectedFrame = "base_link";

        ROSConnection connection;
        GhostMaster ghostMaster;
        RobotStatusManager statusManager;
        RealGhostToolPose toolPose;
        RealGhostTarget pendingTarget;
        bool active;
        bool subscribed;
        bool publishersRegistered;
        bool awaitingPreview;
        bool hasPendingTarget;

        void OnDisable() => Deactivate();

        bool IRealGhostSolver.Initialize(GhostMaster destination,
            RobotStatusManager injectedStatusManager, RealRobotControl _,
            Vector3 toolPositionMillimeters, Vector3 toolRotationDegrees)
        {
            ghostMaster = destination;
            statusManager = injectedStatusManager;
            toolPose = new RealGhostToolPose(toolPositionMillimeters, toolRotationDegrees);
            if (active)
                Subscribe();
            return ghostMaster != null && statusManager != null && IsConfigured();
        }

        void IRealGhostSolver.SetActive(bool value)
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
            if (subscribed || !active || ghostMaster == null || statusManager == null)
                return;
            if (!IsConfigured())
            {
                Debug.LogError("Real MoveIt Ghost topics and frame are required and must be unique.", this);
                return;
            }

            connection ??= ROSConnection.GetOrCreateInstance();
            if (!publishersRegistered)
            {
                connection.RegisterPublisher<PoseStampedMsg>(moveItTargetTopic);
                connection.RegisterPublisher<JointStateMsg>(jointStateTopic);
                publishersRegistered = true;
            }
            connection.Subscribe<PoseStampedMsg>(targetTopic, ReceiveTarget);
            connection.Subscribe<JointTrajectoryMsg>(previewTopic, ReceivePreview);
            connection.Subscribe<StringMsg>(statusTopic, ReceiveMoveItStatus);
            statusManager.StatusChanged += ReceiveRobotStatus;
            subscribed = true;
        }

        void Deactivate()
        {
            active = false;
            awaitingPreview = false;
            hasPendingTarget = false;
            if (!subscribed)
                return;

            statusManager.StatusChanged -= ReceiveRobotStatus;
            if (connection != null)
            {
                connection.Unsubscribe(targetTopic);
                connection.Unsubscribe(previewTopic);
                connection.Unsubscribe(statusTopic);
            }
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
            PublishPendingTarget();
        }

        void PublishPendingTarget()
        {
            if (!active || awaitingPreview || !hasPendingTarget)
                return;
            float[] joints = statusManager.Latest?.JointDegrees;
            if (joints == null || joints.Length != JointNames.Length)
            {
                Debug.LogWarning("Real MoveIt Ghost requires the latest six robot joints.", this);
                return;
            }

            var positions = new double[JointNames.Length];
            for (int i = 0; i < positions.Length; i++)
            {
                if (!float.IsFinite(joints[i]))
                {
                    Debug.LogWarning("Real MoveIt Ghost rejected non-finite robot joints.", this);
                    return;
                }
                positions[i] = joints[i] * Mathf.Deg2Rad;
            }

            try
            {
                connection.Publish(jointStateTopic, new JointStateMsg(new HeaderMsg(), JointNames,
                    positions, Array.Empty<double>(), Array.Empty<double>()));
                connection.Publish(moveItTargetTopic, ToPoseStamped(pendingTarget));
                hasPendingTarget = false;
                awaitingPreview = true;
            }
            catch (Exception exception)
            {
                Debug.LogWarning("Real MoveIt Ghost publish failed: " + exception.Message, this);
            }
        }

        void ReceivePreview(JointTrajectoryMsg trajectory)
        {
            if (!active || !awaitingPreview || trajectory?.points == null ||
                trajectory.points.Length == 0)
                return;

            awaitingPreview = false;
            if (!hasPendingTarget && !ghostMaster.ShowDestination(trajectory))
                Debug.LogWarning("Real MoveIt Ghost rejected the destination trajectory.", this);
            PublishPendingTarget();
        }

        void ReceiveMoveItStatus(StringMsg message)
        {
            string value = message?.data ?? string.Empty;
            if (!active || !awaitingPreview ||
                !value.StartsWith("error:", StringComparison.OrdinalIgnoreCase))
                return;

            awaitingPreview = false;
            Debug.LogWarning("Real MoveIt Ghost: " + value, this);
            PublishPendingTarget();
        }

        void ReceiveRobotStatus(RobotRunState _, RobotErrorLabel __, string ___) =>
            PublishPendingTarget();

        PoseStampedMsg ToPoseStamped(RealGhostTarget target) => new(
            new HeaderMsg { frame_id = expectedFrame },
            new PoseMsg(new PointMsg(target.PositionMeters.x, target.PositionMeters.y,
                    target.PositionMeters.z),
                new QuaternionMsg(target.Rotation.x, target.Rotation.y,
                    target.Rotation.z, target.Rotation.w)));

        bool IsConfigured() =>
            !string.IsNullOrWhiteSpace(targetTopic) &&
            !string.IsNullOrWhiteSpace(moveItTargetTopic) &&
            !string.IsNullOrWhiteSpace(previewTopic) &&
            !string.IsNullOrWhiteSpace(statusTopic) &&
            !string.IsNullOrWhiteSpace(jointStateTopic) &&
            !string.IsNullOrWhiteSpace(expectedFrame) &&
            targetTopic != moveItTargetTopic && targetTopic != previewTopic &&
            targetTopic != statusTopic && targetTopic != jointStateTopic &&
            moveItTargetTopic != previewTopic && moveItTargetTopic != statusTopic &&
            moveItTargetTopic != jointStateTopic && previewTopic != statusTopic &&
            previewTopic != jointStateTopic && statusTopic != jointStateTopic;
    }
}
