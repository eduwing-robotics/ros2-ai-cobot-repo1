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
        [SerializeField] string topicName = "/vision/board/image/compressed";
        [UxmlName("Image")]
        [SerializeField] string imageElementName = "RealdepthCam";
        [Tooltip("이 시간 동안 새 프레임이 없으면 스트림이 끊긴 것으로 본다.")]
        [SerializeField, Min(0.1f)] float staleAfterSeconds = 1f;

        ROSConnection connection;
        Image targetImage;
        Texture2D receivedTexture;

        /// <summary>마지막으로 영상 프레임을 받은 시각이다.</summary>
        public double LastReceiveTimeSeconds { get; private set; }

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
