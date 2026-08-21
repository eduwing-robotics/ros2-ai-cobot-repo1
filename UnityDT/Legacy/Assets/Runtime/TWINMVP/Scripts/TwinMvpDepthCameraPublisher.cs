// TWIN MVP 전용 RGB + 합성 aligned-depth 센서입니다. 기존 카메라 코드는 수정하지 않습니다.

using System;
using System.Collections;
using RosMessageTypes.BuiltinInterfaces;
using RosMessageTypes.Sensor;
using RosMessageTypes.Std;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

namespace TWINMVP
{
    [AddComponentMenu("Robotics/TWIN MVP/Depth Camera Publisher")]
    [DisallowMultipleComponent]
    [RequireComponent(typeof(Camera))]
    public sealed class TwinMvpDepthCameraPublisher : MonoBehaviour
    {
        [Header("AIO-compatible topics")]
        [SerializeField] string colorTopic = "/camera/camera/color/image_raw";
        [SerializeField] string depthTopic = "/camera/camera/aligned_depth_to_color/image_raw";
        [SerializeField] string colorInfoTopic = "/camera/camera/color/camera_info";
        [SerializeField] string depthInfoTopic = "/camera/camera/aligned_depth_to_color/camera_info";
        [SerializeField] string frameId = "sim_camera_optical_frame";

        [Header("MVP sensor")]
        [SerializeField, Min(16)] int width = 640;
        [SerializeField, Min(16)] int height = 480;
        [SerializeField, Range(1, 30)] int framesPerSecond = 5;
        [SerializeField] Transform activeScanTarget;

        Camera sourceCamera;
        ROSConnection connection;
        RenderTexture colorRenderTexture;
        Texture2D colorTexture;
        byte[] depthData;
        Coroutine publishLoop;

        public Transform ActiveScanTarget => activeScanTarget;
        public bool IsReady => sourceCamera != null && colorTexture != null && connection != null;

        void Start()
        {
            sourceCamera = GetComponent<Camera>();
            connection = ROSConnection.GetOrCreateInstance();
            connection.RegisterPublisher<ImageMsg>(colorTopic);
            connection.RegisterPublisher<ImageMsg>(depthTopic);
            connection.RegisterPublisher<CameraInfoMsg>(colorInfoTopic);
            connection.RegisterPublisher<CameraInfoMsg>(depthInfoTopic);
            CreateBuffers();
            publishLoop = StartCoroutine(PublishFrames());
        }

        public void SetScanTarget(Transform target) => activeScanTarget = target;

        IEnumerator PublishFrames()
        {
            var wait = new WaitForSecondsRealtime(1f / framesPerSecond);
            while (enabled)
            {
                PublishOneFrame();
                yield return wait;
            }
        }

        public bool PublishOneFrame()
        {
            if (!IsReady || activeScanTarget == null)
                return false;

            Vector3 cameraPoint = sourceCamera.transform.InverseTransformPoint(
                activeScanTarget.position);
            if (cameraPoint.z <= 0f || cameraPoint.z * 1000f >= ushort.MaxValue)
            {
                Debug.LogWarning("TWIN MVP scan target must be in front of the camera and within 65.535 m.", this);
                return false;
            }

            byte[] rgb = CaptureRgbTopLeft();
            FillDepth((ushort)Mathf.RoundToInt(cameraPoint.z * 1000f));
            HeaderMsg header = new(UtcNow(), frameId);

            connection.Publish(colorTopic, new ImageMsg(
                header, (uint)height, (uint)width, "rgb8", 0, (uint)(width * 3), rgb));
            connection.Publish(depthTopic, new ImageMsg(
                header, (uint)height, (uint)width, "16UC1", 0, (uint)(width * 2), depthData));

            CameraInfoMsg info = CreateCameraInfo(header);
            connection.Publish(colorInfoTopic, info);
            connection.Publish(depthInfoTopic, info);
            return true;
        }

        byte[] CaptureRgbTopLeft()
        {
            RenderTexture previousTarget = sourceCamera.targetTexture;
            RenderTexture previousActive = RenderTexture.active;
            sourceCamera.targetTexture = colorRenderTexture;
            sourceCamera.Render();
            RenderTexture.active = colorRenderTexture;
            colorTexture.ReadPixels(new Rect(0, 0, width, height), 0, 0);
            colorTexture.Apply(false);
            sourceCamera.targetTexture = previousTarget;
            RenderTexture.active = previousActive;

            byte[] pixels = colorTexture.GetRawTextureData<byte>().ToArray();
            FlipRows(pixels, width * 3, height);
            return pixels;
        }

        void FillDepth(ushort millimetres)
        {
            byte low = (byte)millimetres;
            byte high = (byte)(millimetres >> 8);
            for (int i = 0; i < depthData.Length; i += 2)
            {
                depthData[i] = low;
                depthData[i + 1] = high;
            }
        }

        CameraInfoMsg CreateCameraInfo(HeaderMsg header)
        {
            double fy = height * 0.5d /
                Math.Tan(sourceCamera.fieldOfView * Mathf.Deg2Rad * 0.5d);
            double fx = fy;
            double cx = width * 0.5d;
            double cy = height * 0.5d;
            double[] k = { fx, 0d, cx, 0d, fy, cy, 0d, 0d, 1d };
            double[] r = { 1d, 0d, 0d, 0d, 1d, 0d, 0d, 0d, 1d };
            double[] p = { fx, 0d, cx, 0d, 0d, fy, cy, 0d, 0d, 0d, 1d, 0d };
            return new CameraInfoMsg(
                header, (uint)height, (uint)width, "plumb_bob", new double[5],
                k, r, p, 0, 0, new RegionOfInterestMsg());
        }

        void CreateBuffers()
        {
            colorRenderTexture = new RenderTexture(
                width, height, 24, RenderTextureFormat.ARGB32);
            colorTexture = new Texture2D(width, height, TextureFormat.RGB24, false);
            depthData = new byte[width * height * 2];
        }

        static void FlipRows(byte[] pixels, int rowBytes, int rows)
        {
            var row = new byte[rowBytes];
            for (int y = 0; y < rows / 2; y++)
            {
                int top = y * rowBytes;
                int bottom = (rows - y - 1) * rowBytes;
                Buffer.BlockCopy(pixels, top, row, 0, rowBytes);
                Buffer.BlockCopy(pixels, bottom, pixels, top, rowBytes);
                Buffer.BlockCopy(row, 0, pixels, bottom, rowBytes);
            }
        }

        static TimeMsg UtcNow()
        {
            long milliseconds = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            return new TimeMsg(
                (int)(milliseconds / 1000),
                (uint)(milliseconds % 1000 * 1_000_000));
        }

        void OnDestroy()
        {
            if (publishLoop != null)
                StopCoroutine(publishLoop);
            if (colorRenderTexture != null)
            {
                colorRenderTexture.Release();
                Destroy(colorRenderTexture);
            }
            if (colorTexture != null)
                Destroy(colorTexture);
        }

        [ContextMenu("TWIN MVP/Publish One Scan Frame")]
        void PublishOneScanFrameContext()
        {
            if (!Application.isPlaying)
            {
                Debug.LogWarning("Enter Play Mode before publishing a ROS scan frame.", this);
                return;
            }
            Debug.Log(PublishOneFrame()
                ? "TWIN MVP scan frame published."
                : "TWIN MVP scan frame was not published; assign an active scan target.", this);
        }

        [ContextMenu("TWIN MVP/Validate Depth Camera")]
        void ValidateDepthCamera() => Debug.Assert(
            GetComponent<Camera>() != null && width > 0 && height > 0 && framesPerSecond > 0 &&
            !string.IsNullOrWhiteSpace(colorTopic) && !string.IsNullOrWhiteSpace(depthTopic),
            "TWIN MVP depth camera settings are invalid.", this);
    }
}
