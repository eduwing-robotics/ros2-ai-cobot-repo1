// 역할: Ghost 생성, 관절 Preview, 궤적 Preview를 하나의 시각화 전용 진입점으로 묶는다.

using System.Collections.Generic;
using RosMessageTypes.Trajectory;
using UnityEngine;

namespace MainUnity.Runtime.RobotGhost
{
    [DisallowMultipleComponent]
    public sealed class GhostMaster : MonoBehaviour
    {
        [SerializeField] GhostMaker maker;
        [SerializeField] GhostJointPreview jointPreview;
        [SerializeField] GhostMovePreview movePreview;

        bool manualPreviewActive;
        internal bool ManualPathReady => movePreview != null && movePreview.ManualPathReady;
        internal bool ManualCollision => movePreview != null && movePreview.ManualCollision;
        internal string ManualStatus => movePreview != null ? movePreview.ManualStatus : "Ghost 경로 미리보기 연결 없음";

        internal bool PreviewManualPath(IReadOnlyList<float> from, IReadOnlyList<float> target)
        {
            RefreshReferences();
            if (movePreview == null || !SetVisible(true)) return false;
            manualPreviewActive = true;
            return movePreview.PreviewManualPath(maker, from, target);
        }

        internal void EndManualPreview()
        {
            if (!manualPreviewActive) return;
            manualPreviewActive = false;
            movePreview?.Stop();
            maker?.SetManualCollisionVisual(false);
            SetVisible(false);
        }

        void Awake()
        {
            RefreshReferences();
            SetVisible(false);
        }
        void OnValidate() => RefreshReferences();

        public bool PreviewJoints(IReadOnlyList<float> jointDegrees)
        {
            if (manualPreviewActive || jointPreview == null || !SetVisible(true))
                return false;

            if (jointPreview.TryPreviewJoints(jointDegrees))
                return true;

            SetVisible(false);
            return false;
        }

        public bool Play(JointTrajectoryMsg trajectory) =>
            !manualPreviewActive && movePreview != null && SetVisible(true) && movePreview.Play(trajectory);

        public bool ShowDestination(JointTrajectoryMsg trajectory)
        {
            if (manualPreviewActive || movePreview == null || !SetVisible(true))
                return false;

            if (movePreview.ShowDestination(trajectory))
                return true;

            SetVisible(false);
            return false;
        }

        public void Stop() => movePreview?.Stop();

        public bool ResetPreview() => movePreview != null && movePreview.ResetPreview();

        public bool SetVisible(bool visible)
        {
            // An inactive owner keeps the child articulation inactive even after SetActive(true).
            // Activate the owner first so Awake completes before showing the requested pose.
            if (visible && !gameObject.activeSelf)
                gameObject.SetActive(true);
            return maker != null && maker.SetGhostVisible(visible);
        }

#if UNITY_EDITOR
        [ContextMenu("Self Check Inactive Ghost Visibility")]
        void SelfCheckInactiveVisibility()
        {
            if (!Application.isPlaying)
                return;
            gameObject.SetActive(false);
            bool shown = SetVisible(true);
            Debug.Assert(shown && gameObject.activeInHierarchy &&
                maker.GetOrCreateGhost().activeInHierarchy,
                "Showing a Ghost must also activate its owner.", this);
            SetVisible(false);
        }
#endif

        void RefreshReferences()
        {
            if (maker == null)
                maker = GetComponentInChildren<GhostMaker>(true);
            if (jointPreview == null)
                jointPreview = GetComponentInChildren<GhostJointPreview>(true);
            if (movePreview == null)
                movePreview = GetComponentInChildren<GhostMovePreview>(true);
        }
    }
}
