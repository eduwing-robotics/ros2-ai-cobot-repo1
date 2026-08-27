// 역할: RealCam 압축 영상을 수신·디코딩해 지정한 GUI 요소에 표시한다.

using MainUnity.UI;
using RosMessageTypes.Sensor;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;
using UnityEngine.UIElements;

namespace MainUnity.Runtime.Camera
{
    [DisallowMultipleComponent]
    public sealed class CamVisionReceiver : MonoBehaviour
    {
        [SerializeField] UIDocument targetDocument;
        [Tooltip("구독할 CompressedImage 토픽입니다. 실행 중 TrySetTopic 으로 바꿀 수 있습니다.")]
        [SerializeField] string topicName = "/camera/camera/color/image_raw/compressed";
        [UxmlName("Image")]
        [SerializeField] string imageElementName = "RealdepthCam";
        [Tooltip("이 시간 동안 새 프레임이 없으면 스트림이 끊긴 것으로 본다.")]
        [SerializeField, Min(0.1f)] float staleAfterSeconds = 1f;

        ROSConnection connection;
        Image targetImage;
        Texture2D receivedTexture;

        /// <summary>마지막으로 영상 프레임을 받은 시각이다.</summary>
        public double LastReceiveTimeSeconds { get; private set; }

        /// <summary>지금 구독 중인 토픽이다.</summary>
        public string TopicName => topicName;

        /// <summary>영상 프레임을 한 번이라도 받았는지다.</summary>
        public bool HasReceivedImage { get; private set; }

        /// <summary>
        /// 지금 실제 카메라 영상을 그리고 있는지다.
        /// 프레임이 오기 전에는 UXML 에 지정된 Unity RenderTexture 가 보이므로 false 다.
        /// 스트림이 끊기면 화면에는 마지막 프레임이 남지만 최신이 아니므로 다시 false 가 된다.
        /// </summary>
        public bool IsStreaming => HasReceivedImage &&
            UnityEngine.Time.realtimeSinceStartupAsDouble - LastReceiveTimeSeconds <= staleAfterSeconds;

        void Start()
        {
            targetImage = targetDocument?.rootVisualElement.Q<Image>(imageElementName);
            if (string.IsNullOrWhiteSpace(topicName) || targetImage == null)
            {
                Debug.LogError("Assign a UIDocument containing the RealdepthCam Image.", this);
                enabled = false;
                return;
            }

            receivedTexture = new Texture2D(2, 2, TextureFormat.RGB24, false);
            targetImage.scaleMode = ScaleMode.ScaleToFit;
            connection = ROSConnection.GetOrCreateInstance();
            connection.Subscribe<CompressedImageMsg>(topicName, ReceiveImage);
        }

        void ReceiveImage(CompressedImageMsg message)
        {
            if (message?.data == null || message.data.Length == 0 ||
                !receivedTexture.LoadImage(message.data))
                return;

            targetImage.image = receivedTexture;
            LastReceiveTimeSeconds = UnityEngine.Time.realtimeSinceStartupAsDouble;
            HasReceivedImage = true;
        }

        /// <summary>
        /// 구독 토픽을 바꾼다. 이전 구독을 끊고 수신 상태를 지운다 —
        /// 지우지 않으면 이전 토픽의 마지막 프레임이 새 토픽의 영상으로 보인다.
        /// </summary>
        public bool TrySetTopic(string value)
        {
            if (string.IsNullOrWhiteSpace(value) || value == topicName) return false;
            if (connection != null) connection.Unsubscribe(topicName);

            topicName = value;
            HasReceivedImage = false;
            LastReceiveTimeSeconds = 0d;
            if (targetImage != null) targetImage.image = null;

            if (connection == null) return true;
            connection.Subscribe<CompressedImageMsg>(topicName, ReceiveImage);
            return true;
        }

        void OnDestroy()
        {
            if (connection != null)
                connection.Unsubscribe(topicName);
            if (receivedTexture != null)
                Destroy(receivedTexture);
        }

        /// <summary>수신 UI 문서와 ROS 영상 토픽 할당을 확인한다.</summary>
        [ContextMenu("Validate Real Depth Camera Receiver")]
        void ValidateReceiver() => Debug.Assert(
            !string.IsNullOrWhiteSpace(topicName) && targetDocument != null,
            "Assign the target UIDocument.", this);
    }
}
