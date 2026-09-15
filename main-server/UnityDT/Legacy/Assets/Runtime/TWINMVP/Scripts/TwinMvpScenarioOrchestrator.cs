// TWIN MVP 스캔 결과를 기존 PickPlaceOrchestrator 입력으로 연결합니다.

using System;
using FR5Mvp.PickPlace;
using UnityEngine;

namespace TWINMVP
{
    [AddComponentMenu("Robotics/TWIN MVP/Scenario Orchestrator")]
    [DisallowMultipleComponent]
    public sealed class TwinMvpScenarioOrchestrator : MonoBehaviour
    {
        [Serializable]
        public sealed class PartScan
        {
            public string label;
            public Transform part;
            [Tooltip("Camera depth and local grasp-offset reference.")]
            public Transform scanPoint;
            public Transform pickOrientation;
            public Transform placeTarget;
            [Tooltip("Optional colored marker. Only the current marker is enabled while scanning.")]
            public GameObject visionMarker;
            public Vector3 localGraspOffset;
        }

        [SerializeField] TwinMvpDepthCameraPublisher depthCamera;
        [SerializeField] TwinMvpVisionAdapter vision;
        [SerializeField] PickPlaceOrchestrator pickPlace;
        [SerializeField] PartScan[] parts = Array.Empty<PartScan>();
        [SerializeField, Min(0.1f)] float scanTimeoutSeconds = 3f;
        [SerializeField] bool planAfterDetection;
        [SerializeField, Min(0)] int currentIndex;

        TwinMvpVisionAdapter boundVision;
        bool waitingForDetection;
        float scanDeadline;

        public int CurrentIndex => currentIndex;
        public bool IsScanning => waitingForDetection;
        public string LastError { get; private set; } = string.Empty;

        void OnEnable() => BindVision();
        void OnDisable()
        {
            UnbindVision();
            SetActiveMarker(-1);
        }

        void Update()
        {
            if (!waitingForDetection || Time.unscaledTime <= scanDeadline)
                return;
            waitingForDetection = false;
            SetActiveMarker(-1);
            LastError = $"Vision timeout for part index {currentIndex}.";
            Debug.LogWarning(LastError, this);
        }

        public bool Scan(int index)
        {
            if (!Application.isPlaying)
                return Reject("Enter Play Mode before starting a ROS scan.");
            if (!TryGetPart(index, out PartScan scan))
                return false;
            if (depthCamera == null || vision == null)
                return Reject("Install or assign the TWIN MVP camera and vision adapter.");

            currentIndex = index;
            LastError = string.Empty;
            BindVision();
            SetActiveMarker(index);
            depthCamera.SetScanTarget(scan.scanPoint);
            waitingForDetection = true;
            scanDeadline = Time.unscaledTime + scanTimeoutSeconds;
            return true;
        }

        void ReceivePoint(string label, Vector3 worldPoint)
        {
            if (!waitingForDetection || !TryGetPart(currentIndex, out PartScan scan) ||
                !string.Equals(label, scan.label, StringComparison.OrdinalIgnoreCase))
                return;

            waitingForDetection = false;
            SetActiveMarker(-1);
            if (!PreparePickPlace(scan, worldPoint))
                return;
            if (planAfterDetection && !pickPlace.Plan())
                Reject(pickPlace.LastError);
        }

        bool PreparePickPlace(PartScan scan, Vector3 detectedPoint)
        {
            if (pickPlace == null)
                return Reject("Assign the existing FR5 PickPlaceOrchestrator.");

            Vector3 offset = scan.scanPoint.TransformVector(scan.localGraspOffset);
            Quaternion pickRotation = scan.pickOrientation != null
                ? scan.pickOrientation.rotation
                : scan.scanPoint.rotation;
            bool prepared = pickPlace.Target.SelectObject(scan.part) &&
                pickPlace.Target.SetPickPose(new Pose(detectedPoint + offset, pickRotation)) &&
                pickPlace.Target.SetPlacePose(new Pose(
                    scan.placeTarget.position, scan.placeTarget.rotation));
            if (!prepared)
                return Reject(pickPlace.Target.LastError);

            LastError = string.Empty;
            Debug.Log($"Prepared {scan.label}: pick={detectedPoint + offset}, " +
                $"place={scan.placeTarget.position}.", this);
            return true;
        }

        bool TryGetPart(int index, out PartScan scan)
        {
            scan = index >= 0 && index < parts.Length ? parts[index] : null;
            if (scan == null || string.IsNullOrWhiteSpace(scan.label) || scan.part == null ||
                scan.scanPoint == null || scan.placeTarget == null)
                return Reject($"Part index {index} is missing label, part, scan point or place target.");
            return true;
        }

        void BindVision()
        {
            if (boundVision == vision)
                return;
            UnbindVision();
            boundVision = vision;
            if (boundVision != null)
                boundVision.PointDetected += ReceivePoint;
        }

        void UnbindVision()
        {
            if (boundVision != null)
                boundVision.PointDetected -= ReceivePoint;
            boundVision = null;
        }

        void SetActiveMarker(int activeIndex)
        {
            for (int i = 0; i < parts.Length; i++)
                if (parts[i]?.visionMarker != null)
                    parts[i].visionMarker.SetActive(i == activeIndex);
        }

        bool Reject(string error)
        {
            LastError = error;
            Debug.LogWarning(error, this);
            return false;
        }

        [ContextMenu("TWIN MVP/Install Demo Components")]
        void InstallDemoComponents()
        {
            GameObject cameraObject = GameObject.Find("Depth Cam");
            if (cameraObject == null)
            {
                Reject("The scene does not contain a GameObject named 'Depth Cam'.");
                return;
            }

            depthCamera = cameraObject.GetComponent<TwinMvpDepthCameraPublisher>();
            if (depthCamera == null)
                depthCamera = cameraObject.AddComponent<TwinMvpDepthCameraPublisher>();
            vision = cameraObject.GetComponent<TwinMvpVisionAdapter>();
            if (vision == null)
                vision = cameraObject.AddComponent<TwinMvpVisionAdapter>();
            vision.UseCameraFrame(cameraObject.transform);
            pickPlace ??= FindFirstObjectByType<PickPlaceOrchestrator>();
            BindVision();
            Debug.Log("TWIN MVP camera components installed; assign the Parts array next.", this);
        }

        [ContextMenu("TWIN MVP/Scan First Part")]
        void ScanFirstPart() => Scan(0);

        [ContextMenu("TWIN MVP/Scan Next Part")]
        void ScanNextPart() => Scan(parts.Length == 0 ? 0 : (currentIndex + 1) % parts.Length);

        [ContextMenu("TWIN MVP/Prepare Current From Scan Point")]
        void PrepareCurrentFromScanPoint()
        {
            if (TryGetPart(currentIndex, out PartScan scan))
                PreparePickPlace(scan, scan.scanPoint.position);
        }

        [ContextMenu("TWIN MVP/Plan Prepared Part")]
        void PlanPreparedPart()
        {
            if (pickPlace == null || !pickPlace.Plan())
                Reject(pickPlace == null ? "Assign PickPlaceOrchestrator." : pickPlace.LastError);
        }

        [ContextMenu("TWIN MVP/Run Local Smoke Test")]
        void RunLocalSmokeTest()
        {
            BindVision();
            if (!TryGetPart(currentIndex, out PartScan scan) || vision == null)
            {
                Reject("Assign a valid current part and Vision Adapter first.");
                return;
            }
            waitingForDetection = true;
            vision.SimulateWorldPoint(scan.label, scan.scanPoint.position);
            Debug.Assert(pickPlace != null && pickPlace.Target.IsReady,
                "Local scan did not prepare Pick/Place.", this);
        }

        [ContextMenu("TWIN MVP/Validate Scenario")]
        void ValidateScenario()
        {
            bool valid = depthCamera != null && vision != null && pickPlace != null && parts.Length > 0;
            for (int i = 0; i < parts.Length; i++)
                valid &= parts[i] != null && !string.IsNullOrWhiteSpace(parts[i].label) &&
                    parts[i].part != null && parts[i].scanPoint != null &&
                    parts[i].placeTarget != null;
            Debug.Assert(valid, "TWIN MVP scenario references are incomplete.", this);
        }
    }
}
