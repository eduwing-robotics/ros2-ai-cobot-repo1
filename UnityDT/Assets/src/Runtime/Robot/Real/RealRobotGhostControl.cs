using MainUnity.Runtime.Robot.Interface;
using MainUnity.Runtime.Robot.Status;
using MainUnity.Runtime.RobotGhost;
using RosMessageTypes.Geometry;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Real
{
    readonly struct RealGhostToolPose
    {
        public RealGhostToolPose(Vector3 positionMillimeters, Vector3 rotationDegrees)
        {
            PositionMeters = positionMillimeters * 0.001f;
            Rotation = RealGhostPose.RpyDegreesToQuaternion(rotationDegrees);
        }

        public Vector3 PositionMeters { get; }
        public Quaternion Rotation { get; }
    }

    readonly struct RealGhostTarget
    {
        public RealGhostTarget(Vector3 positionMeters, Quaternion rotation)
        {
            PositionMeters = positionMeters;
            Rotation = rotation;
        }

        public Vector3 PositionMeters { get; }
        public Quaternion Rotation { get; }
    }

    static class RealGhostPose
    {
        public static bool TryGetFlangeTarget(PoseStampedMsg message, string expectedFrame,
            RealGhostToolPose toolPose, out RealGhostTarget target, out string error)
        {
            target = default;
            if (message?.header == null || message.pose?.position == null ||
                message.pose.orientation == null)
            {
                error = "Real Ghost target requires a complete PoseStamped message.";
                return false;
            }
            if (!string.Equals(message.header.frame_id, expectedFrame,
                    System.StringComparison.Ordinal))
            {
                error = $"Real Ghost target frame must be '{expectedFrame}'.";
                return false;
            }

            var position = new Vector3((float)message.pose.position.x,
                (float)message.pose.position.y, (float)message.pose.position.z);
            var rotation = new Quaternion((float)message.pose.orientation.x,
                (float)message.pose.orientation.y, (float)message.pose.orientation.z,
                (float)message.pose.orientation.w);
            float rotationLengthSquared = Quaternion.Dot(rotation, rotation);
            if (!IsFinite(position, 10f) || !IsFinite(rotation) ||
                !float.IsFinite(rotationLengthSquared) || rotationLengthSquared < 1e-12f)
            {
                error = "Real Ghost target pose must be finite, within ±10 m, and have a valid quaternion.";
                return false;
            }

            rotation = Quaternion.Normalize(rotation);
            Quaternion flangeRotation = rotation * Quaternion.Inverse(toolPose.Rotation);
            Vector3 flangePosition = position - flangeRotation * toolPose.PositionMeters;
            if (!IsFinite(flangePosition, 10f) || !IsFinite(flangeRotation))
            {
                error = "Real Ghost tool correction produced an invalid flange pose.";
                return false;
            }
            target = new RealGhostTarget(flangePosition, flangeRotation);
            error = string.Empty;
            return true;
        }

        public static Vector3 QuaternionToRpyDegrees(Quaternion rotation)
        {
            double sinRollCosPitch = 2d * (rotation.w * rotation.x + rotation.y * rotation.z);
            double cosRollCosPitch = 1d - 2d * (rotation.x * rotation.x + rotation.y * rotation.y);
            double sinPitch = 2d * (rotation.w * rotation.y - rotation.z * rotation.x);
            double sinYawCosPitch = 2d * (rotation.w * rotation.z + rotation.x * rotation.y);
            double cosYawCosPitch = 1d - 2d * (rotation.y * rotation.y + rotation.z * rotation.z);
            return new Vector3(
                (float)(System.Math.Atan2(sinRollCosPitch, cosRollCosPitch) * Mathf.Rad2Deg),
                (float)(System.Math.Asin(System.Math.Max(-1d, System.Math.Min(1d, sinPitch))) * Mathf.Rad2Deg),
                (float)(System.Math.Atan2(sinYawCosPitch, cosYawCosPitch) * Mathf.Rad2Deg));
        }

        public static Quaternion RpyDegreesToQuaternion(Vector3 rpy) =>
            Quaternion.AngleAxis(rpy.z, Vector3.forward) *
            Quaternion.AngleAxis(rpy.y, Vector3.up) *
            Quaternion.AngleAxis(rpy.x, Vector3.right);

        static bool IsFinite(Vector3 value, float maximum) =>
            float.IsFinite(value.x) && float.IsFinite(value.y) && float.IsFinite(value.z) &&
            Mathf.Abs(value.x) <= maximum && Mathf.Abs(value.y) <= maximum &&
            Mathf.Abs(value.z) <= maximum;

        static bool IsFinite(Quaternion value) =>
            float.IsFinite(value.x) && float.IsFinite(value.y) &&
            float.IsFinite(value.z) && float.IsFinite(value.w);
    }

    [DisallowMultipleComponent]
    public sealed class RealRobotGhostControl : MonoBehaviour, IRobotGhostControl
    {
        [SerializeField] RealFairinoSdkGhostSolver fairinoSdkSolver;

        [Header("Tool 1 TCP relative to wrist3_link / flange")]
        [SerializeField] Vector3 toolPositionMillimeters = new(-2f, -2f, 157f);
        [SerializeField] Vector3 toolRotationDegrees;

        GhostMaster ghostMaster;
        RobotStatusManager statusManager;
        RealRobotControl robotControl;

        void OnDisable() => fairinoSdkSolver?.SetActive(false);
        void OnValidate() => RefreshReferences();

        public bool Initialize(GhostMaster destination)
        {
            ghostMaster = destination;
            RefreshReferences();
            if (ghostMaster != null)
                return InitializeSolver();
            Debug.LogError("Assign the common GhostMaster.", this);
            return false;
        }

        internal void InitializeReal(RobotStatusManager injectedStatusManager,
            RealRobotControl injectedRobotControl)
        {
            statusManager = injectedStatusManager;
            robotControl = injectedRobotControl;
            InitializeSolver();
        }

        public void SetActive(bool value)
        {
            fairinoSdkSolver?.SetActive(value);
            enabled = value;
        }

        bool InitializeSolver()
        {
            if (ghostMaster == null || statusManager == null || robotControl == null)
                return false;

            return fairinoSdkSolver != null && fairinoSdkSolver.Initialize(
                ghostMaster, statusManager, robotControl,
                toolPositionMillimeters, toolRotationDegrees);
        }

        void RefreshReferences()
        {
            if (fairinoSdkSolver == null)
                fairinoSdkSolver = GetComponent<RealFairinoSdkGhostSolver>();
        }

#if UNITY_EDITOR
        [ContextMenu("Self Check Real Ghost Pose")]
        void SelfCheckRealGhostPose()
        {
            var message = new PoseStampedMsg
            {
                header = new RosMessageTypes.Std.HeaderMsg { frame_id = "base_link" },
                pose = new PoseMsg(new PointMsg(0.4, 0.0, 0.3),
                    new QuaternionMsg(0.0, 0.0, 0.0, 1.0))
            };
            Debug.Assert(RealGhostPose.TryGetFlangeTarget(message, "base_link",
                new RealGhostToolPose(Vector3.zero, Vector3.zero), out RealGhostTarget target,
                out string error), error, this);
            Debug.Assert(Vector3.Distance(target.PositionMeters, new Vector3(0.4f, 0f, 0.3f)) < 1e-5f,
                "Identity tool pose must preserve the target position.", this);
        }
#endif
    }
}
