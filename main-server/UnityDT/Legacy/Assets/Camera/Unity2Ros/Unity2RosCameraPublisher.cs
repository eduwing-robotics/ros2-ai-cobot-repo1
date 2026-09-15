// Unity 카메라 영상을 압축해 지정한 ROS2 토픽으로 보냅니다.

using System;
using System.Collections;
using RosMessageTypes.BuiltinInterfaces;
using RosMessageTypes.Sensor;
using RosMessageTypes.Std;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

namespace FR5Mvp
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(Camera))]
    public sealed class Unity2RosCameraPublisher : MonoBehaviour
    {
        [SerializeField] string topicName = "/sim_camera/image_raw/compressed";
        [SerializeField] string frameId = "sim_camera_optical_frame";
        [SerializeField, Min(1)] int width = 640;
        [SerializeField, Min(1)] int height = 480;
        [SerializeField, Range(1, 60)] int framesPerSecond = 10;
        [SerializeField, Range(1, 100)] int jpegQuality = 75;

        Camera sourceCamera;
        ROSConnection connection;
        RenderTexture renderTexture;
        Texture2D captureTexture;

        void Start()
        {
            if (string.IsNullOrWhiteSpace(topicName) || string.IsNullOrWhiteSpace(frameId))
            {
                Debug.LogError("Unity camera publisher needs a topic and frame ID.", this);
                enabled = false;
                return;
            }

            sourceCamera = GetComponent<Camera>();
            renderTexture = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32);
            captureTexture = new Texture2D(width, height, TextureFormat.RGB24, false);

            connection = ROSConnection.GetOrCreateInstance();
            connection.RegisterPublisher<CompressedImageMsg>(topicName);
            StartCoroutine(PublishFrames());
        }

        IEnumerator PublishFrames()
        {
            var endOfFrame = new WaitForEndOfFrame();
            float nextPublishTime = 0f;

            while (enabled)
            {
                yield return endOfFrame;
                if (Time.unscaledTime < nextPublishTime)
                    continue;
                nextPublishTime = Time.unscaledTime + 1f / framesPerSecond;

                // 기존 Camera/RenderTexture 상태를 보존한 채 한 프레임만 별도로 렌더링합니다.
                RenderTexture previousTarget = sourceCamera.targetTexture;
                RenderTexture previousActive = RenderTexture.active;
                sourceCamera.targetTexture = renderTexture;
                sourceCamera.Render();
                RenderTexture.active = renderTexture;
                captureTexture.ReadPixels(new Rect(0, 0, width, height), 0, 0);
                captureTexture.Apply(false);
                sourceCamera.targetTexture = previousTarget;
                RenderTexture.active = previousActive;

                var header = new HeaderMsg(UtcNow(), frameId);
                var message = new CompressedImageMsg(
                    header, "jpeg", captureTexture.EncodeToJPG(jpegQuality));
                connection.Publish(topicName, message);
            }
        }

        // ROS2 Header에 사용할 Unix 시각을 초/나노초로 나눕니다.
        static TimeMsg UtcNow()
        {
            long milliseconds = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            return new TimeMsg(
                (int)(milliseconds / 1000),
                (uint)(milliseconds % 1000 * 1_000_000));
        }

        void OnDestroy()
        {
            if (renderTexture != null)
            {
                renderTexture.Release();
                Destroy(renderTexture);
            }
            if (captureTexture != null)
                Destroy(captureTexture);
        }

        [ContextMenu("Validate Unity Camera Publisher")]
        void ValidatePublisher() => Debug.Assert(
            !string.IsNullOrWhiteSpace(topicName) && !string.IsNullOrWhiteSpace(frameId) &&
            width > 0 && height > 0 && framesPerSecond > 0,
            "Camera publisher settings are invalid.", this);
    }
}
