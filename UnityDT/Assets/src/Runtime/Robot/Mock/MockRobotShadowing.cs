// 역할: MOCK joint_states를 Unity FR5 Articulation 자세와 그리퍼 모델에 반영한다.

using System;
using System.Collections.Generic;
using MainUnity.UrdfImport;
using MainUnity.Runtime.Robot.Interface;
using MainUnity.Runtime.Robot.Status;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Mock
{
    [DisallowMultipleComponent]
    public sealed class MockRobotShadowing : MonoBehaviour, IRobotShadowing
    {
        const int JointCount = 6;

        [SerializeField, Min(1f)] float kinematicFollowSpeedDegreesPerSecond = 360f;

        ArticulationBody articulationRoot;
        GripperAttacher gripperAttacher;
        bool hasShadowTarget;
        bool hasKinematicPose;
        bool shadowFaulted;

        readonly ArticulationBody[] shadowJoints = new ArticulationBody[JointCount];
        readonly float[] shadowTargetDegrees = new float[JointCount];
        readonly float[] kinematicDegrees = new float[JointCount];
        readonly List<float> reducedJointPositions = new List<float>(JointCount);
        readonly List<int> dofStartIndices = new List<int>(JointCount + 1);

        public void Initialize(ArticulationBody root)
        {
            articulationRoot = root;
            gripperAttacher = root != null
                ? root.GetComponentInChildren<GripperAttacher>(true)
                : null;
            RefreshShadowJoints();
        }

        public void ApplyState(RobotStatusFrame frame)
        {
            if (frame?.JointDegrees == null || frame.JointDegrees.Length != JointCount)
                return;
            Array.Copy(frame.JointDegrees, shadowTargetDegrees, JointCount);
            hasShadowTarget = true;
        }

        // TODO: 공통 그리퍼 상태 계약이 생기면 IRobotShadowing 경로로 통합한다.
        public void ApplyGripperJointPosition(float radians)
        {
            if (!float.IsFinite(radians) || gripperAttacher == null)
                return;
            gripperAttacher.Target = radians;
        }

        void OnEnable()
        {
            hasKinematicPose = false;
            shadowFaulted = false;
            RefreshShadowJoints();
        }

        void OnDisable() => hasShadowTarget = false;

        void FixedUpdate()
        {
            if (!hasShadowTarget || shadowFaulted || !EnsureShadowJoints())
                return;

            try
            {
                ApplyKinematicShadow();
            }
            catch (Exception exception)
            {
                shadowFaulted = true;
                Debug.LogError($"Mock shadowing failed: {exception.Message}", this);
            }
        }

        bool EnsureShadowJoints()
        {
            if (articulationRoot == null)
                return RefreshShadowJoints();
            for (int i = 0; i < shadowJoints.Length; i++)
                if (shadowJoints[i] == null)
                    return RefreshShadowJoints();
            return true;
        }

        bool RefreshShadowJoints()
        {
            Array.Clear(shadowJoints, 0, shadowJoints.Length);
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
                    shadowJoints[jointIndex] = bodies[bodyIndex];
                    break;
                }
                if (shadowJoints[jointIndex] == null)
                    return false;
            }

            hasKinematicPose = false;
            shadowFaulted = false;
            return true;
        }

        void ApplyKinematicShadow()
        {
            if (!hasKinematicPose)
            {
                for (int i = 0; i < JointCount; i++)
                    kinematicDegrees[i] = shadowJoints[i].jointPosition[0] * Mathf.Rad2Deg;
                hasKinematicPose = true;
            }

            float maxDelta = Mathf.Max(1f, kinematicFollowSpeedDegreesPerSecond) *
                Time.fixedDeltaTime;
            for (int i = 0; i < JointCount; i++)
            {
                ArticulationDrive drive = shadowJoints[i].xDrive;
                float target = Mathf.Clamp(
                    shadowTargetDegrees[i], drive.lowerLimit, drive.upperLimit);
                kinematicDegrees[i] = Mathf.MoveTowards(
                    kinematicDegrees[i], target, maxDelta);
                drive.target = kinematicDegrees[i];
                drive.targetVelocity = 0f;
                shadowJoints[i].xDrive = drive;
            }

            reducedJointPositions.Clear();
            dofStartIndices.Clear();
            articulationRoot.GetJointPositions(reducedJointPositions);
            articulationRoot.GetDofStartIndices(dofStartIndices);
            for (int i = 0; i < JointCount; i++)
            {
                int dofIndex = dofStartIndices[shadowJoints[i].index];
                reducedJointPositions[dofIndex] = kinematicDegrees[i] * Mathf.Deg2Rad;
            }
            articulationRoot.SetJointPositions(reducedJointPositions);
        }

#if UNITY_EDITOR
        [ContextMenu("Self Check Mock Shadowing")]
        void SelfCheckMockShadowing() =>
            Debug.Assert(RefreshShadowJoints(),
                "FR5 Articulation root or j1~j6 could not be found.", this);
#endif
    }
}
