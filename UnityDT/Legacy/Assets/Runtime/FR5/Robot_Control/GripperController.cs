// 그리퍼의 양쪽 손가락을 함께 열고 닫습니다.
// 수동 설정과 URDF로 불러온 그리퍼를 같은 방식으로 제어합니다.

using System;
using UnityEngine;

#if UNITY_EDITOR
using UnityEditor;
#endif

namespace FR5Mvp.RobotControl
{
    /// <summary>수동 또는 URDF 기반 양쪽 그리퍼 조를 하나의 개폐 값으로 제어합니다.</summary>
    [DisallowMultipleComponent]
    public sealed class GripperController : MonoBehaviour
    {
        [Header("Moving Objects")]
        [SerializeField] Transform leftJaw;
        [SerializeField] Transform rightJaw;

        [Header("TCP")]
        [SerializeField, Tooltip("Place this transform at the center of the gripping spot.")]
        Transform tcp;
        [SerializeField, Min(0.001f)] float tcpMarkerRadius = 0.008f;

        [Header("Movement")]
        [SerializeField, Tooltip("Opening axis in this controller's local space.")]
        Vector3 openingAxis = Vector3.right;
        [SerializeField, Min(0f), Tooltip("Maximum total opening distance in meters.")]
        float maximumOpening = 0.04f;
        [SerializeField, Range(0f, 1f), Tooltip("Open command amount: 0 = closed, 1 = maximum.")]
        float openingAmount = 1f;
        [SerializeField, Min(0f), Tooltip("Opening and closing speed in meters per second.")]
        float speed = 0.05f;

        [SerializeField, HideInInspector] Transform capturedLeftJaw;
        [SerializeField, HideInInspector] Transform capturedRightJaw;
        [SerializeField, HideInInspector] Vector3 leftClosedPosition;
        [SerializeField, HideInInspector] Vector3 rightClosedPosition;
        [SerializeField, HideInInspector] float currentOpening;

        // URDF로 불러온 경우 두 손가락의 이동 방향과 연동 범위를 사용합니다.
        [SerializeField, HideInInspector] bool useUrdfJointAxes;
        [SerializeField, HideInInspector] Vector3 leftJointAxisLocal;
        [SerializeField, HideInInspector] Vector3 rightJointAxisLocal;
        [SerializeField, HideInInspector] float driverLowerMeters;
        [SerializeField, HideInInspector] float driverUpperMeters;
        [SerializeField, HideInInspector] float followerLowerMeters;
        [SerializeField, HideInInspector] float followerUpperMeters;
        [SerializeField, HideInInspector] float mimicMultiplier = 1f;
        [SerializeField, HideInInspector] float mimicOffsetMeters;

        float targetOpening;

        // 사용자가 요청한 그리퍼 관절 위치를 외부 실행 기능에 전달합니다.
        public event Action<float> CommandRequested;

        public Transform Tcp => tcp;
        public Transform DriverJaw => rightJaw;
        public Transform FollowerJaw => leftJaw;
        public bool IsBound =>
            leftJaw != null && rightJaw != null && leftJaw != rightJaw;
        public float LowerMeters => driverLowerMeters;
        public float UpperMeters => driverUpperMeters;
        public float OpeningMeters => useUrdfJointAxes
            ? Mathf.Lerp(
                driverLowerMeters,
                driverUpperMeters,
                maximumOpening > 0f ? currentOpening / maximumOpening : 0f)
            : currentOpening;

        void Awake()
        {
            if (!TryInitialize())
            {
                Debug.LogError("Assign two different jaw objects and a non-zero opening axis.", this);
                enabled = false;
                return;
            }
            targetOpening = currentOpening;
        }

        void Update()
        {
            float next = Mathf.MoveTowards(
                currentOpening,
                targetOpening,
                speed * Time.deltaTime);
            if (Mathf.Approximately(next, currentOpening))
                return;
            currentOpening = next;
            ApplyPose();
        }

        [ContextMenu("Gripper/Open")]
        public void Open() => RequestOpeningMeters(
            useUrdfJointAxes ? driverLowerMeters : maximumOpening * openingAmount);

        [ContextMenu("Gripper/Close")]
        public void Close() => RequestOpeningMeters(
            useUrdfJointAxes ? driverUpperMeters : 0f);

        /// <summary>기준 손가락의 이동 거리를 미터 단위로 지정합니다.</summary>
        public void SetOpeningMeters(float meters)
        {
            if (!useUrdfJointAxes)
            {
                SetTarget(meters, "Set Gripper Opening");
                return;
            }
            float normalized = Mathf.InverseLerp(
                driverLowerMeters,
                driverUpperMeters,
                meters);
            SetTarget(normalized * maximumOpening, "Set Gripper Opening");
        }

        public void SetOpeningNormalized(float normalized) =>
            SetTarget(
                Mathf.Clamp01(normalized) * maximumOpening,
                "Set Gripper Opening");

        void RequestOpeningMeters(float meters)
        {
            if (Application.isPlaying)
            {
                CommandRequested?.Invoke(meters);
                return;
            }
            SetOpeningMeters(meters);
        }

        /// <summary>Import된 두 손가락의 이동 방향과 연동 규칙을 연결합니다.</summary>
        public void ConfigureUrdfJaws(
            Transform driver,
            Transform follower,
            Vector3 driverAxisInParent,
            Vector3 followerAxisInParent,
            float lower,
            float upper,
            float followerLower,
            float followerUpper,
            float multiplier,
            float offset)
        {
            rightJaw = driver;
            leftJaw = follower;
            rightJointAxisLocal = driverAxisInParent.normalized;
            leftJointAxisLocal = followerAxisInParent.normalized;
            driverLowerMeters = lower;
            driverUpperMeters = upper;
            followerLowerMeters = followerLower;
            followerUpperMeters = followerUpper;
            mimicMultiplier = multiplier;
            mimicOffsetMeters = offset;
            useUrdfJointAxes = true;

            float followerAtOpen = Mathf.Clamp(
                upper * multiplier + offset,
                followerLower,
                followerUpper);
            maximumOpening = Mathf.Max(
                0f,
                upper - lower + followerAtOpen - followerLower);
            openingAmount = 1f;
            capturedLeftJaw = null;
            capturedRightJaw = null;
            TryInitialize();
            targetOpening = 0f;
            ApplyPose();
        }

        void SetTarget(float opening, string undoName)
        {
            if (!TryInitialize())
            {
                Debug.LogError("Assign two different jaw objects and a non-zero opening axis.", this);
                return;
            }

            targetOpening = Mathf.Clamp(opening, 0f, maximumOpening);
#if UNITY_EDITOR
            if (!Application.isPlaying)
            {
                Undo.RecordObjects(
                    new UnityEngine.Object[] { this, leftJaw, rightJaw }, undoName);
                currentOpening = targetOpening;
                ApplyPose();
            }
#endif
        }

        bool TryInitialize()
        {
            if (!IsBound || (!useUrdfJointAxes && openingAxis.sqrMagnitude < Mathf.Epsilon))
                return false;
            if (capturedLeftJaw != leftJaw || capturedRightJaw != rightJaw)
            {
                capturedLeftJaw = leftJaw;
                capturedRightJaw = rightJaw;
                leftClosedPosition = leftJaw.localPosition;
                rightClosedPosition = rightJaw.localPosition;
                currentOpening = 0f;
            }
            return true;
        }

        void ApplyPose()
        {
            if (useUrdfJointAxes)
            {
                float normalized = maximumOpening > 0f
                    ? currentOpening / maximumOpening
                    : 0f;
                float driverTarget = Mathf.Lerp(
                    driverLowerMeters,
                    driverUpperMeters,
                    normalized);
                float followerTarget = Mathf.Clamp(
                    driverTarget * mimicMultiplier + mimicOffsetMeters,
                    followerLowerMeters,
                    followerUpperMeters);
                rightJaw.localPosition = rightClosedPosition +
                    rightJointAxisLocal * (driverTarget - driverLowerMeters);
                leftJaw.localPosition = leftClosedPosition +
                    leftJointAxisLocal * (followerTarget - followerLowerMeters);
                return;
            }

            Vector3 worldOffset = transform.TransformDirection(openingAxis.normalized) *
                (currentOpening * 0.5f);
            leftJaw.localPosition = leftClosedPosition -
                leftJaw.parent.InverseTransformVector(worldOffset);
            rightJaw.localPosition = rightClosedPosition +
                rightJaw.parent.InverseTransformVector(worldOffset);
        }

        void OnDrawGizmos()
        {
            if (tcp == null)
                return;
            Gizmos.color = Color.yellow;
            Gizmos.DrawSphere(tcp.position, tcpMarkerRadius);
        }

        void OnValidate()
        {
            maximumOpening = Mathf.Max(0f, maximumOpening);
            openingAmount = Mathf.Clamp01(openingAmount);
            speed = Mathf.Max(0f, speed);
            tcpMarkerRadius = Mathf.Max(0.001f, tcpMarkerRadius);
            currentOpening = Mathf.Clamp(currentOpening, 0f, maximumOpening);
        }
    }
}
