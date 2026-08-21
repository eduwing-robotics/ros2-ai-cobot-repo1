// 관제 화면에서 사용할 Unity 카메라 하나를 선택합니다.

using UnityEngine;

namespace FR5Mvp.OperationView
{
    /// <summary>작업 화면에 노출할 카메라와 AudioListener를 하나만 선택합니다.</summary>
    [AddComponentMenu("Robotics/FR5/Operation View/Camera Selector")]
    [DisallowMultipleComponent]
    public sealed class CameraSelector : MonoBehaviour
    {
        [SerializeField] Camera mainCamera;
        [SerializeField] Camera globalCamera;

        public Camera SelectedCamera { get; private set; }

        public void SelectMain() => Select(mainCamera);
        public void SelectGlobal() => Select(globalCamera);

        /// <summary>지정한 카메라와 해당 AudioListener만 활성화합니다.</summary>
        public bool Select(Camera selected)
        {
            if (selected == null)
                return false;

            SetActive(mainCamera, mainCamera == selected);
            SetActive(globalCamera, globalCamera == selected);
            SelectedCamera = selected;
            return true;
        }

        static void SetActive(Camera camera, bool active)
        {
            if (camera == null)
                return;
            camera.enabled = active;
            if (camera.TryGetComponent(out AudioListener listener))
                listener.enabled = active;
        }
    }
}
