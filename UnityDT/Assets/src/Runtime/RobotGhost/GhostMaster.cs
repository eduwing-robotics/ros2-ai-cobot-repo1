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

        void Awake() => RefreshReferences();
        void OnValidate() => RefreshReferences();

        public bool PreviewJoints(IReadOnlyList<float> jointDegrees) =>
            jointPreview != null && jointPreview.TryPreviewJoints(jointDegrees);

        public bool Play(JointTrajectoryMsg trajectory) =>
            movePreview != null && movePreview.Play(trajectory);

        public bool ShowDestination(JointTrajectoryMsg trajectory) =>
            movePreview != null && movePreview.ShowDestination(trajectory);

        public void Stop() => movePreview?.Stop();

        public bool ResetPreview() => movePreview != null && movePreview.ResetPreview();

        public bool SetVisible(bool visible) =>
            maker != null && maker.SetGhostVisible(visible);

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
