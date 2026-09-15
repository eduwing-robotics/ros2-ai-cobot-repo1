// AIO의 카메라 optical-frame 검출 좌표를 Unity 월드 좌표로만 변환합니다.

using System;
using System.Collections.Generic;
using RosMessageTypes.Geometry;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

namespace TWINMVP
{
    [AddComponentMenu("Robotics/TWIN MVP/Vision Adapter")]
    [DisallowMultipleComponent]
    public sealed class TwinMvpVisionAdapter : MonoBehaviour
    {
        [Serializable]
        public sealed class PartChannel
        {
            public string label;
            public string topic;
        }

        [SerializeField] Transform cameraFrame;
        [SerializeField] PartChannel[] channels =
        {
            new PartChannel { label = "chip", topic = "/fr5_vision/chip/point" },
            new PartChannel { label = "led", topic = "/fr5_vision/led/point" },
            new PartChannel { label = "tantal", topic = "/fr5_vision/tantal/point" },
            new PartChannel { label = "sot", topic = "/fr5_vision/sot/point" },
            new PartChannel { label = "pinheader", topic = "/fr5_vision/pinheader/point" },
            new PartChannel { label = "cond", topic = "/fr5_vision/cond/point" }
        };
        [SerializeField] string simulatedLabel = "chip";
        [SerializeField] Vector3 simulatedCameraPoint = new(0f, 0f, 0.5f);

        ROSConnection connection;
        bool subscribed;

        public string LastLabel { get; private set; } = string.Empty;
        public Vector3 LastWorldPoint { get; private set; }
        public event Action<string, Vector3> PointDetected;

        void Awake() => connection = ROSConnection.GetOrCreateInstance();
        void OnEnable() => Subscribe();
        void OnDisable() => Unsubscribe();

        public void UseCameraFrame(Transform value) => cameraFrame = value;

        void Subscribe()
        {
            if (subscribed)
                return;
            connection ??= ROSConnection.GetOrCreateInstance();
            foreach (PartChannel channel in channels)
            {
                if (channel == null || string.IsNullOrWhiteSpace(channel.label) ||
                    string.IsNullOrWhiteSpace(channel.topic))
                    continue;
                string label = channel.label;
                connection.Subscribe<PointStampedMsg>(
                    channel.topic, message => Receive(label, message));
            }
            subscribed = true;
        }

        void Unsubscribe()
        {
            if (!subscribed || connection == null)
                return;
            foreach (PartChannel channel in channels)
                if (channel != null && !string.IsNullOrWhiteSpace(channel.topic))
                    connection.Unsubscribe(channel.topic);
            subscribed = false;
        }

        void Receive(string label, PointStampedMsg message)
        {
            if (cameraFrame == null || message?.point == null)
                return;
            double x = message.point.x;
            double y = message.point.y;
            double z = message.point.z;
            if (!double.IsFinite(x) || !double.IsFinite(y) || !double.IsFinite(z) || z <= 0d)
                return;

            Vector3 cameraLocal = new((float)x, (float)-y, (float)z);
            PublishDetection(label, cameraFrame.TransformPoint(cameraLocal));
        }

        public void SimulateWorldPoint(string label, Vector3 worldPoint)
        {
            if (string.IsNullOrWhiteSpace(label) ||
                !float.IsFinite(worldPoint.x) || !float.IsFinite(worldPoint.y) ||
                !float.IsFinite(worldPoint.z))
                return;
            PublishDetection(label, worldPoint);
        }

        void PublishDetection(string label, Vector3 worldPoint)
        {
            LastLabel = label;
            LastWorldPoint = worldPoint;
            PointDetected?.Invoke(label, worldPoint);
        }

        [ContextMenu("TWIN MVP/Simulate Detection")]
        void SimulateDetectionContext()
        {
            if (cameraFrame == null)
            {
                Debug.LogWarning("Assign the Depth Cam transform first.", this);
                return;
            }
            Vector3 local = new(
                simulatedCameraPoint.x, -simulatedCameraPoint.y, simulatedCameraPoint.z);
            PublishDetection(simulatedLabel, cameraFrame.TransformPoint(local));
            Debug.Log($"Simulated {LastLabel} at {LastWorldPoint}.", this);
        }

        [ContextMenu("TWIN MVP/Validate Vision Adapter")]
        void ValidateVisionAdapter()
        {
            var topics = new HashSet<string>();
            bool valid = cameraFrame != null && channels != null && channels.Length > 0;
            foreach (PartChannel channel in channels)
                valid &= channel != null && !string.IsNullOrWhiteSpace(channel.label) &&
                    !string.IsNullOrWhiteSpace(channel.topic) && topics.Add(channel.topic);
            Debug.Assert(valid, "Assign a camera and unique, non-empty vision channels.", this);
        }
    }
}
