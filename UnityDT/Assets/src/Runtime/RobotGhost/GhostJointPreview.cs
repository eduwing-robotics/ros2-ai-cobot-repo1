// 역할: 실제 ROS 제어 없이 6축 관절 자세를 Ghost Articulation에만 적용한다.

using System;
using System.Collections.Generic;
using UnityEngine;

namespace MainUnity.Runtime.RobotGhost
{
    [DisallowMultipleComponent]
    public sealed class GhostJointPreview : MonoBehaviour
    {
        const int JointCount = 6;

        [SerializeField] GhostMaker ghostMaker;
        [SerializeField] GhostMovePreview movePreview;
        [SerializeField] ArticulationBody articulationRoot;

        readonly ArticulationBody[] joints = new ArticulationBody[JointCount];
        readonly float[] resetDegrees = new float[JointCount];
        readonly float[] targetDegrees = new float[JointCount];
        readonly int[] jointDofIndices = new int[JointCount];
        readonly List<float> reducedJointPositions = new List<float>(JointCount);
        readonly List<int> dofStartIndices = new List<int>(JointCount + 1);
        bool hasResetPose;

        void Awake()
        {
            RefreshReferences();
            RefreshJoints();
        }

        void OnValidate() => RefreshReferences();

        /// <summary>Ghost의 현재 6축 자세를 ResetPreview()에서 사용할 초기 자세로 저장한다.</summary>
        public bool CaptureResetPose()
        {
            if (!EnsureJoints())
                return false;
            for (int i = 0; i < JointCount; i++)
            {
                ArticulationReducedSpace position = joints[i].jointPosition;
                if (position.dofCount == 0)
                    return false;
                resetDegrees[i] = position[0] * Mathf.Rad2Deg;
            }
            hasResetPose = true;
            return true;
        }

        /// <summary>6개 관절 목표 각도(deg)를 Ghost에만 즉시 적용하고 경로 Preview를 중단한다.</summary>
        public bool TryPreviewJoints(IReadOnlyList<float> jointDegrees)
        {
            movePreview?.Stop();
            if (!hasResetPose && !CaptureResetPose())
                return false;
            return TryApplyJoints(jointDegrees);
        }

        /// <summary>저장된 초기 관절 자세로 Ghost를 되돌리고 경로 Preview를 중단한다.</summary>
        public bool ResetPreview()
        {
            movePreview?.Stop();
            return hasResetPose && TryApplyJoints(resetDegrees);
        }

        /// <summary>Ghost 계층에서 Articulation 루트와 j1~j6 관절을 다시 찾는다.</summary>
        public bool RefreshJoints()
        {
            Array.Clear(joints, 0, joints.Length);
            GameObject ghost = ghostMaker != null ? ghostMaker.GetOrCreateGhost() : null;
            if (ghost == null)
                return false;

            if (articulationRoot == null || !articulationRoot.transform.IsChildOf(ghost.transform))
            {
                articulationRoot = null;
                foreach (ArticulationBody body in
                    ghost.GetComponentsInChildren<ArticulationBody>(true))
                {
                    if (!body.isRoot)
                        continue;
                    articulationRoot = body;
                    break;
                }
            }

            if (articulationRoot == null)
                return false;

            ArticulationBody[] bodies =
                articulationRoot.GetComponentsInChildren<ArticulationBody>(true);
            for (int jointIndex = 0; jointIndex < JointCount; jointIndex++)
            {
                string jointName = $"j{jointIndex + 1}";
                for (int bodyIndex = 0; bodyIndex < bodies.Length; bodyIndex++)
                {
                    if (!string.Equals(bodies[bodyIndex].name, jointName,
                        StringComparison.OrdinalIgnoreCase))
                        continue;
                    joints[jointIndex] = bodies[bodyIndex];
                    break;
                }
                if (joints[jointIndex] == null || joints[jointIndex].jointPosition.dofCount == 0)
                    return false;
            }
            return true;
        }

        /// <summary>검증된 경로 관절값(deg)을 수동 Preview 중단 처리 없이 Ghost에 적용한다.</summary>
        internal bool TryApplyTrajectoryJoints(IReadOnlyList<float> jointDegrees) =>
            TryApplyJoints(jointDegrees);

        bool TryApplyJoints(IReadOnlyList<float> jointDegrees)
        {
            if (jointDegrees == null || jointDegrees.Count != JointCount || !EnsureJoints())
                return false;

            reducedJointPositions.Clear();
            dofStartIndices.Clear();
            articulationRoot.GetJointPositions(reducedJointPositions);
            articulationRoot.GetDofStartIndices(dofStartIndices);

            for (int i = 0; i < JointCount; i++)
            {
                float degrees = jointDegrees[i];
                if (!float.IsFinite(degrees))
                    return false;
                ArticulationDrive drive = joints[i].xDrive;
                targetDegrees[i] = Mathf.Clamp(degrees, drive.lowerLimit, drive.upperLimit);
                int bodyIndex = joints[i].index;
                if (bodyIndex < 0 || bodyIndex >= dofStartIndices.Count)
                    return false;
                int dofIndex = dofStartIndices[bodyIndex];
                if (dofIndex < 0 || dofIndex >= reducedJointPositions.Count)
                    return false;
                jointDofIndices[i] = dofIndex;
            }

            for (int i = 0; i < JointCount; i++)
            {
                reducedJointPositions[jointDofIndices[i]] = targetDegrees[i] * Mathf.Deg2Rad;
                ArticulationDrive drive = joints[i].xDrive;
                drive.target = targetDegrees[i];
                drive.targetVelocity = 0f;
                joints[i].xDrive = drive;
            }

            articulationRoot.SetJointPositions(reducedJointPositions);
            return true;
        }

        bool EnsureJoints()
        {
            if (articulationRoot == null)
                return RefreshJoints();
            for (int i = 0; i < joints.Length; i++)
                if (joints[i] == null)
                    return RefreshJoints();
            return true;
        }

        void RefreshReferences()
        {
            if (ghostMaker == null)
                ghostMaker = GetComponentInParent<GhostMaker>();
            if (movePreview == null)
                movePreview = GetComponentInParent<GhostMovePreview>();
        }

#if UNITY_EDITOR
        [ContextMenu("Self Check Ghost Joints")]
        void SelfCheckGhostJoints() => Debug.Assert(
            RefreshJoints(), "Ghost Articulation root or j1~j6 could not be found.", this);
#endif
    }
}
