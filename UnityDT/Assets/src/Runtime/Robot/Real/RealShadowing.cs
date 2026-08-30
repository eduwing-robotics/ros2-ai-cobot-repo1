// 역할: 검증된 실제 로봇 관절 상태를 Unity FR5 Articulation 자세에 반영한다.

using System;
using System.Collections.Generic;
using MainUnity.UrdfImport;
using MainUnity.Runtime.Robot.Status;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Real
{
    [DisallowMultipleComponent]
    public sealed class RealShadowing : MonoBehaviour
    {
        const int JointCount = 6;

        [SerializeField, Min(1f)] float followSpeedDegreesPerSecond = 360f;

        ArticulationBody articulationRoot;
        bool hasTarget;
        bool hasPose;
        bool faulted;

        readonly ArticulationBody[] joints = new ArticulationBody[JointCount];
        readonly float[] targetDegrees = new float[JointCount];
        readonly float[] currentDegrees = new float[JointCount];
        readonly List<float> reducedJointPositions = new List<float>(JointCount);
        readonly List<int> dofStartIndices = new List<int>(JointCount + 1);

        public void Initialize(ArticulationBody root)
        {
            articulationRoot = root;
            RefreshJoints();
        }

        /// <summary>마지막 그리퍼 열림 요청값(0~100%)을 Unity 모델에 반영한다.</summary>
        public void ApplyGripperOpeningPercent(float openingPercent)
        {
            GripperAttacher gripper = articulationRoot != null
                ? articulationRoot.GetComponentInChildren<GripperAttacher>(true) : null;
            gripper?.SetOpeningPercent(openingPercent);
        }

        public void ApplyState(RobotStatusFrame frame)
        {
            if (frame?.JointDegrees == null || frame.JointDegrees.Length != JointCount)
                return;
            Array.Copy(frame.JointDegrees, targetDegrees, JointCount);
            hasTarget = true;
            if (frame.GripperFeedbackValid)
                ApplyGripperOpeningPercent(frame.GripperPosition);
        }

        void OnEnable()
        {
            hasPose = false;
            faulted = false;
            RefreshJoints();
        }

        void OnDisable() => hasTarget = false;

        void FixedUpdate()
        {
            if (!hasTarget || faulted || !EnsureJoints())
                return;

            try
            {
                if (!hasPose)
                {
                    for (int i = 0; i < JointCount; i++)
                        currentDegrees[i] = joints[i].jointPosition[0] * Mathf.Rad2Deg;
                    hasPose = true;
                }

                float maxDelta = Mathf.Max(1f, followSpeedDegreesPerSecond) *
                    Time.fixedDeltaTime;
                for (int i = 0; i < JointCount; i++)
                {
                    ArticulationDrive drive = joints[i].xDrive;
                    float target = Mathf.Clamp(
                        targetDegrees[i], drive.lowerLimit, drive.upperLimit);
                    currentDegrees[i] = Mathf.MoveTowards(
                        currentDegrees[i], target, maxDelta);
                    drive.target = currentDegrees[i];
                    drive.targetVelocity = 0f;
                    joints[i].xDrive = drive;
                }

                reducedJointPositions.Clear();
                dofStartIndices.Clear();
                articulationRoot.GetJointPositions(reducedJointPositions);
                articulationRoot.GetDofStartIndices(dofStartIndices);
                for (int i = 0; i < JointCount; i++)
                {
                    int dofIndex = dofStartIndices[joints[i].index];
                    reducedJointPositions[dofIndex] = currentDegrees[i] * Mathf.Deg2Rad;
                }
                articulationRoot.SetJointPositions(reducedJointPositions);
            }
            catch (Exception exception)
            {
                faulted = true;
                Debug.LogError($"Real shadowing failed: {exception.Message}", this);
            }
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

        bool RefreshJoints()
        {
            Array.Clear(joints, 0, joints.Length);
            if (articulationRoot == null || !articulationRoot.isRoot)
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
                if (joints[jointIndex] == null)
                    return false;
            }

            hasPose = false;
            faulted = false;
            return true;
        }

#if UNITY_EDITOR
        [ContextMenu("Self Check Real Shadowing")]
        void SelfCheckRealShadowing() =>
            Debug.Assert(RefreshJoints(),
                "FR5 Articulation root or j1~j6 could not be found.", this);
#endif
    }
}
