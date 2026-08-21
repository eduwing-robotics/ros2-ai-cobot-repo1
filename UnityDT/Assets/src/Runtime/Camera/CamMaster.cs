// 역할: 카메라 컴포넌트를 시나리오와 수동 제어에서 호출할 단일 진입점으로 묶는다.

using UnityEngine;

namespace MainUnity.Runtime.Camera
{
    [DisallowMultipleComponent]
    public sealed class CamMaster : MonoBehaviour
    {
        [SerializeField] Calibration calibration;
        [SerializeField] VisionDetector visionDetector;
        [SerializeField] CamVisionReceiver visionReceiver;

        void Awake() => RefreshReferences();
        void OnValidate() => RefreshReferences();

        public bool RequestDetection() => visionDetector != null && visionDetector.RequestDetection();

        public bool TryApplyDetectedPose(Pose detectedWorldPose) =>
            calibration != null && calibration.TryApplyDetectedPose(detectedWorldPose);

        public void RefreshReferences()
        {
            calibration = calibration != null ? calibration : GetComponentInChildren<Calibration>(true);
            visionDetector = visionDetector != null ? visionDetector : GetComponentInChildren<VisionDetector>(true);
            visionReceiver = visionReceiver != null ? visionReceiver : GetComponentInChildren<CamVisionReceiver>(true);
        }
    }
}
