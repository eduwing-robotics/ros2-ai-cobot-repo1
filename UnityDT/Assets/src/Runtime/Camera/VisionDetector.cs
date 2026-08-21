// 역할: Vision이 검출한 보드 Pose와 선택 대상을 ROS 토픽에서 수신한다.

using RosMessageTypes.Geometry;
using RosMessageTypes.Std;
using Unity.Robotics.ROSTCPConnector;
using Unity.Robotics.ROSTCPConnector.ROSGeometry;
using UnityEngine;

namespace MainUnity.Runtime.Camera
{
    [DisallowMultipleComponent]
    public sealed class VisionDetector : MonoBehaviour
    {
        const string BaseFrameId = "base";

        [SerializeField] GameObject targetPart;
        [SerializeField] string targetPoseTopic = "/vision/board/capture/target_pose";
        [SerializeField] string selectedTargetTopic = "/vision/board/selected_target";

        ROSConnection connection;

        /// <summary>마지막으로 수신한 base 좌표계 Pose를 Unity 좌표계로 변환한 값이다.</summary>
        public Pose LastTargetPose { get; private set; }
        public bool HasTargetPose { get; private set; }
        public string SelectedTarget { get; private set; } = string.Empty;

        void OnEnable()
        {
            if (string.IsNullOrWhiteSpace(targetPoseTopic) ||
                string.IsNullOrWhiteSpace(selectedTargetTopic))
            {
                Debug.LogError("Assign both Vision ROS topics.", this);
                enabled = false;
                return;
            }

            connection = ROSConnection.GetOrCreateInstance();
            connection.Subscribe<PoseStampedMsg>(targetPoseTopic, ReceiveTargetPose);
            connection.Subscribe<StringMsg>(selectedTargetTopic, ReceiveSelectedTarget);
        }

        void OnDisable()
        {
            if (connection == null)
                return;
            connection.Unsubscribe(targetPoseTopic);
            connection.Unsubscribe(selectedTargetTopic);
            connection = null;
        }

        /// <summary>검출 요청 토픽은 아직 계약되지 않아 마지막 수신 Pose만 반환한다.</summary>
        public bool RequestDetection()
        {
            if (targetPart == null)
                Debug.LogWarning("Assign a target part before requesting vision detection.", this);
            return HasTargetPose;
        }

        void ReceiveTargetPose(PoseStampedMsg message)
        {
            if (!TryConvertBasePose(message, out Pose pose))
            {
                Debug.LogWarning("Vision target pose must use finite values in frame_id base.", this);
                return;
            }

            LastTargetPose = pose;
            HasTargetPose = true;
        }

        void ReceiveSelectedTarget(StringMsg message) =>
            SelectedTarget = message?.data ?? string.Empty;

        static bool TryConvertBasePose(PoseStampedMsg message, out Pose pose)
        {
            pose = default;
            if (message?.header == null || message.pose?.position == null ||
                message.pose.orientation == null || message.header.frame_id != BaseFrameId)
                return false;

            Vector3 position = message.pose.position.From<FLU>();
            Quaternion rotation = message.pose.orientation.From<FLU>();
            if (!float.IsFinite(position.x) || !float.IsFinite(position.y) ||
                !float.IsFinite(position.z) || !float.IsFinite(rotation.x) ||
                !float.IsFinite(rotation.y) || !float.IsFinite(rotation.z) ||
                !float.IsFinite(rotation.w) || Quaternion.Dot(rotation, rotation) == 0f)
                return false;

            pose = new Pose(position, Quaternion.Normalize(rotation));
            return true;
        }

#if UNITY_EDITOR
        [ContextMenu("Self Check Vision Pose")]
        void SelfCheckVisionPose()
        {
            var message = new PoseStampedMsg();
            message.header.frame_id = BaseFrameId;
            message.pose.position.x = 1d;
            message.pose.orientation.w = 1d;
            Debug.Assert(TryConvertBasePose(message, out _),
                "Vision PoseStamped conversion failed.", this);
        }
#endif
    }
}
