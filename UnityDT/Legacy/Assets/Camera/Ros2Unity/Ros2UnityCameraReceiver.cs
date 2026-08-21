// ROS2 카메라 영상을 받아 지정한 Unity UI에 표시합니다.

using RosMessageTypes.Sensor;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;
using UnityEngine.UIElements;

namespace FR5Mvp
{
    [DisallowMultipleComponent]
    public sealed class Ros2UnityCameraReceiver : MonoBehaviour
    {
        [SerializeField] string topicName = "/sim_camera/image_raw/compressed";
        [SerializeField] UIDocument targetDocument;
        [SerializeField] string imageElementName = "camera-feed";

        ROSConnection connection;
        Image targetImage;
        Texture2D receivedTexture;

        void Start()
        {
            // UXML의 <ui:Image name="camera-feed" />를 찾아 출력 대상으로 사용합니다.
            targetImage = targetDocument?.rootVisualElement.Q<Image>(imageElementName);
            if (string.IsNullOrWhiteSpace(topicName) || targetImage == null)
            {
                Debug.LogError("ROS camera receiver needs a topic and a valid UI Image.", this);
                enabled = false;
                return;
            }

            // 매 프레임 새 Texture2D를 만들지 않고 하나를 계속 재사용합니다.
            receivedTexture = new Texture2D(2, 2, TextureFormat.RGB24, false);
            targetImage.scaleMode = ScaleMode.ScaleToFit;

            connection = ROSConnection.GetOrCreateInstance();
            connection.Subscribe<CompressedImageMsg>(topicName, ReceiveImage);
        }

        void ReceiveImage(CompressedImageMsg message)
        {
            if (message?.data == null || message.data.Length == 0)
                return;

            // LoadImage가 JPEG 바이트를 해제해 같은 Texture2D에 최신 프레임을 씁니다.
            if (receivedTexture.LoadImage(message.data))
                targetImage.image = receivedTexture;
        }

        void OnDestroy()
        {
            if (connection != null)
                connection.Unsubscribe(topicName);
            if (receivedTexture != null)
                Destroy(receivedTexture);
        }

        [ContextMenu("Validate ROS Camera Receiver")]
        void ValidateReceiver() => Debug.Assert(
            !string.IsNullOrWhiteSpace(topicName) && targetDocument != null,
            "Assign a ROS camera topic and UIDocument.", this);
    }
}
