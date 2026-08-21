// FR5 관절과 그리퍼 제어를 하나의 기능 진입점으로 묶습니다.

using System;
using System.Collections.Generic;
using FR5Mvp.RobotData;
using UnityEngine;

namespace FR5Mvp.RobotControl
{
    /// <summary>관절 추종, 수동 제어와 그리퍼 명령을 묶는 Robot_Control 진입점입니다.</summary>
    [AddComponentMenu("Robotics/FR5/Robot Control Orchestrator")]
    [DisallowMultipleComponent]
    public sealed class RobotControlOrchestrator : MonoBehaviour
    {
        [SerializeField] GameObject importedRoot;
        [SerializeField] GripperController gripper;
        [SerializeField, Tooltip("Mirror ROS joint positions directly instead of simulating motor motion.")]
        bool kinematicMirror;
        [SerializeField, HideInInspector] bool shadowFollowEnabled;
        [SerializeField, HideInInspector] float[] shadowTargetDegrees = new float[6];
        [SerializeField, HideInInspector] float[] twinVelocityDegreesPerSecond = new float[6];

        readonly List<float> kinematicJointPositions = new(6);
        JointController[] joints;
        float[] streamTargetDegrees = Array.Empty<float>();
        float[] streamOutputDegrees = Array.Empty<float>();
        float streamInterpolationSeconds;
        double lastStreamTickSeconds;
        bool hasStreamSample;

        public bool ShadowFollowEnabled => shadowFollowEnabled;
        public bool KinematicMirror => kinematicMirror;
        public GripperController Gripper => gripper;

        /// <summary>로컬 그리퍼 명령을 외부 실행 계층으로 전달합니다.</summary>
        public event Action<float> GripperCommandRequested;

        void Awake() => RefreshJoints();
        void OnEnable() => SubscribeGripper();
        void OnDisable() => UnsubscribeGripper();

        void FixedUpdate()
        {
            if (!shadowFollowEnabled)
                return;
            if (hasStreamSample)
                TickJointState(Time.realtimeSinceStartupAsDouble);
            else
                ApplyShadowPose();
        }

        /// <summary>URDF로 생성된 로봇 루트를 제어 대상으로 지정합니다.</summary>
        public void SetImportedRoot(GameObject root)
        {
            importedRoot = root;
            RefreshJoints();
        }

        /// <summary>시스템이 발견한 그리퍼를 로봇 제어 기능에 연결합니다.</summary>
        public void UseGripper(GripperController value)
        {
            UnsubscribeGripper();
            gripper = value;
            SubscribeGripper();
        }

        /// <summary>현재 제어 중인 관절을 URDF 계층 순서로 반환합니다.</summary>
        public JointController[] GetJoints()
        {
            if ((joints == null || joints.Length == 0) && importedRoot != null)
                RefreshJoints();
            return joints ?? Array.Empty<JointController>();
        }

        /// <summary>안전 검증에 사용할 관절 이름과 제한값의 복사본을 만듭니다.</summary>
        public JointSpecification[] GetJointSpecifications()
        {
            JointController[] current = GetJoints();
            var result = new JointSpecification[current.Length];
            for (int i = 0; i < current.Length; i++)
                result[i] = new JointSpecification(
                    current[i].JointName,
                    current[i].LowerDegrees,
                    current[i].UpperDegrees);
            return result;
        }

        /// <summary>검증된 관절 상태를 끊김 없이 추종할 새 목표로 등록합니다.</summary>
        public void FollowJointState(
            IReadOnlyList<float> degrees,
            float interpolationSeconds,
            double nowSeconds)
        {
            JointController[] current = GetJoints();
            CheckJointValues(degrees, current.Length);
            EnsureControlTargets(current.Length);
            EnsureStreamBuffers(current.Length);

            bool reset = !hasStreamSample || !shadowFollowEnabled;
            for (int i = 0; i < current.Length; i++)
            {
                streamTargetDegrees[i] = Mathf.Clamp(
                    degrees[i], current[i].LowerDegrees, current[i].UpperDegrees);
                if (reset)
                    streamOutputDegrees[i] = current[i].ActualDegrees;
            }

            streamInterpolationSeconds = Mathf.Max(0f, interpolationSeconds);
            if (reset)
                lastStreamTickSeconds = nowSeconds;
            hasStreamSample = true;
            SetShadowFollowEnabled(true);
        }

        /// <summary>지정한 시각까지 관절 상태 스트림을 보간해 로봇에 적용합니다.</summary>
        public void TickJointState(double nowSeconds)
        {
            if (shadowFollowEnabled && hasStreamSample)
                ApplyStreamPose(nowSeconds);
        }

        public void SetShadowFollowEnabled(bool enabled)
        {
            if (shadowFollowEnabled == enabled)
                return;
            shadowFollowEnabled = enabled;
            if (enabled)
                StopTwinMotion();
            else
                hasStreamSample = false;
        }

        public void SetShadowTargetDegrees(int index, float degrees)
        {
            JointController[] current = GetJoints();
            CheckJointIndex(index, current.Length);
            EnsureControlTargets(current.Length);
            hasStreamSample = false;
            shadowTargetDegrees[index] = Mathf.Clamp(
                degrees, current[index].LowerDegrees, current[index].UpperDegrees);
            if (shadowFollowEnabled)
                ApplyShadowPose();
        }

        public void SetShadowPose(IReadOnlyList<float> degrees)
        {
            JointController[] current = GetJoints();
            CheckJointValues(degrees, current.Length);
            EnsureControlTargets(current.Length);
            hasStreamSample = false;
            for (int i = 0; i < current.Length; i++)
                shadowTargetDegrees[i] = Mathf.Clamp(
                    degrees[i], current[i].LowerDegrees, current[i].UpperDegrees);
            ApplyShadowPose();
        }

        public void ApplyShadowPose()
        {
            JointController[] current = GetJoints();
            if (current.Length == 0)
                return;
            EnsureControlTargets(current.Length);

            if (kinematicMirror && importedRoot != null &&
                importedRoot.TryGetComponent(out ArticulationBody rootBody))
            {
                foreach (JointController joint in current)
                    joint.SetVelocityDegreesPerSecond(0f);
                kinematicJointPositions.Clear();
                for (int i = 0; i < current.Length; i++)
                    kinematicJointPositions.Add(shadowTargetDegrees[i] * Mathf.Deg2Rad);
                rootBody.SetJointPositions(kinematicJointPositions);
                return;
            }

            for (int i = 0; i < current.Length; i++)
                current[i].FollowDegrees(shadowTargetDegrees[i]);
        }

        public void CaptureCurrentPose()
        {
            JointController[] current = GetJoints();
            EnsureControlTargets(current.Length);
            hasStreamSample = false;
            for (int i = 0; i < current.Length; i++)
                shadowTargetDegrees[i] = current[i].ActualDegrees;
        }

        public void SetTwinVelocityDegreesPerSecond(int index, float degreesPerSecond)
        {
            JointController[] current = GetJoints();
            CheckJointIndex(index, current.Length);
            EnsureControlTargets(current.Length);
            shadowFollowEnabled = false;
            hasStreamSample = false;
            current[index].SetVelocityDegreesPerSecond(degreesPerSecond);
            twinVelocityDegreesPerSecond[index] = current[index].TargetVelocityDegreesPerSecond;
        }

        /// <summary>모든 관절을 현재 위치에 고정하고 스트림 추종을 중지합니다.</summary>
        public void StopAllMotion()
        {
            StopTwinMotion();
            SetShadowFollowEnabled(false);
        }

        public void StopTwinMotion()
        {
            JointController[] current = GetJoints();
            EnsureControlTargets(current.Length);
            for (int i = 0; i < current.Length; i++)
            {
                current[i].SetDegrees(current[i].ActualDegrees);
                twinVelocityDegreesPerSecond[i] = 0f;
            }
        }

        /// <summary>ROS 전송 없이 Manual 목표 자세를 Unity 로봇에 적용합니다.</summary>
        public void ApplyManualPose(IReadOnlyList<float> degrees)
        {
            StopAllMotion();
            SetShadowPose(degrees);
        }

        public void OpenGripper() => gripper?.Open();
        public void CloseGripper() => gripper?.Close();
        public void ApplyGripperState(float meters) => gripper?.SetOpeningMeters(meters);
        public float GetShadowTargetDegrees(int index) => shadowTargetDegrees[index];
        public float GetTwinVelocityDegreesPerSecond(int index) =>
            twinVelocityDegreesPerSecond[index];

        void ApplyStreamPose(double nowSeconds)
        {
            float t = streamInterpolationSeconds <= 0f
                ? 1f
                : Mathf.Clamp01((float)((nowSeconds - lastStreamTickSeconds) /
                    streamInterpolationSeconds));
            lastStreamTickSeconds = nowSeconds;
            for (int i = 0; i < streamOutputDegrees.Length; i++)
            {
                streamOutputDegrees[i] = Mathf.Lerp(
                    streamOutputDegrees[i], streamTargetDegrees[i], t);
                shadowTargetDegrees[i] = streamOutputDegrees[i];
            }
            ApplyShadowPose();
        }

        void RefreshJoints()
        {
            joints = importedRoot != null
                ? importedRoot.GetComponentsInChildren<JointController>()
                : Array.Empty<JointController>();
            EnsureControlTargets(joints.Length);
            EnsureStreamBuffers(joints.Length);
        }

        void SubscribeGripper()
        {
            if (!isActiveAndEnabled || gripper == null)
                return;
            gripper.CommandRequested -= ForwardGripperCommand;
            gripper.CommandRequested += ForwardGripperCommand;
        }

        void UnsubscribeGripper()
        {
            if (gripper != null)
                gripper.CommandRequested -= ForwardGripperCommand;
        }

        void ForwardGripperCommand(float meters) => GripperCommandRequested?.Invoke(meters);

        void EnsureControlTargets(int count)
        {
            if (shadowTargetDegrees == null || shadowTargetDegrees.Length != count)
                Array.Resize(ref shadowTargetDegrees, count);
            if (twinVelocityDegreesPerSecond == null ||
                twinVelocityDegreesPerSecond.Length != count)
                Array.Resize(ref twinVelocityDegreesPerSecond, count);
        }

        void EnsureStreamBuffers(int count)
        {
            if (streamTargetDegrees.Length == count)
                return;
            Array.Resize(ref streamTargetDegrees, count);
            Array.Resize(ref streamOutputDegrees, count);
        }

        static void CheckJointIndex(int index, int count)
        {
            if (index < 0 || index >= count)
                throw new ArgumentOutOfRangeException(nameof(index));
        }

        static void CheckJointValues(IReadOnlyList<float> values, int count)
        {
            if (values == null)
                throw new ArgumentNullException(nameof(values));
            if (values.Count != count)
                throw new ArgumentException($"Expected {count} joint values.", nameof(values));
        }
    }
}
