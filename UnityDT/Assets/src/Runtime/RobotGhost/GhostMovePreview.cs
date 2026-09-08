// 역할: ROS JointTrajectory를 검증하고 시간값에 맞춰 Ghost 관절에 반복 재생한다.

using System;
using System.Collections;
using System.Collections.Generic;
using RosMessageTypes.Trajectory;
using UnityEngine;

namespace MainUnity.Runtime.RobotGhost
{
    [DisallowMultipleComponent]
    public sealed class GhostMovePreview : MonoBehaviour
    {
        const int JointCount = 6;

        [SerializeField] GhostJointPreview jointPreview;
        [SerializeField] bool loop = true;

        JointTrajectoryMsg trajectory;
        int[] jointMap = Array.Empty<int>();
        readonly float[] previewDegrees = new float[JointCount];
        int pointIndex;
        double startedAt;

        public bool IsPlaying { get; private set; }
        public string LastError { get; private set; } = string.Empty;

        GhostMaker manualMaker;
        Coroutine manualRoutine;
        LineRenderer manualLine;
        MaterialPropertyBlock lineColor;
        bool manualReady;
        int obstacleSignature;
        internal bool ManualCollision { get; private set; }
        internal string ManualStatus { get; private set; } = "관절 목표를 선택하세요.";
        internal bool ManualPathReady => manualReady && manualMaker != null &&
            obstacleSignature == manualMaker.ManualObstacleSignature;

        void Awake() => RefreshReference();
        void OnDisable() => Stop();

        internal bool PreviewManualPath(GhostMaker maker, IReadOnlyList<float> from, IReadOnlyList<float> target)
        {
            Stop();
            RefreshReference();
            manualMaker = maker;
            ManualCollision = false;
            maker?.SetManualCollisionVisual(false);
            if (maker == null || jointPreview == null || from == null || target == null ||
                from.Count != JointCount || target.Count != JointCount)
            {
                ManualStatus = "요청 거부 · 현재 자세 또는 Ghost 연결 없음";
                return false;
            }
            var start = new float[JointCount];
            var destination = new float[JointCount];
            float maxDelta = 0f;
            for (int i = 0; i < JointCount; i++)
            {
                if (!float.IsFinite(from[i]) || !float.IsFinite(target[i]))
                {
                    ManualStatus = "요청 거부 · 유효하지 않은 관절 각도";
                    return false;
                }
                start[i] = from[i];
                destination[i] = target[i];
                maxDelta = Mathf.Max(maxDelta, Mathf.Abs(target[i] - from[i]));
            }
            if (!jointPreview.TryApplyTrajectoryJoints(destination) || !jointPreview.TryApplyTrajectoryJoints(start))
            {
                ManualStatus = "요청 거부 · 관절 제한 범위 또는 Ghost 구성을 확인하세요.";
                return false;
            }
            if (manualLine == null)
            {
                manualLine = gameObject.AddComponent<LineRenderer>();
                manualLine.useWorldSpace = true;
                manualLine.widthMultiplier = 0.008f;
                manualLine.numCapVertices = 4;
                manualLine.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                manualLine.receiveShadows = false;
                var renderer = maker.GetOrCreateGhost().GetComponentInChildren<Renderer>();
                if (renderer != null) manualLine.sharedMaterial = renderer.sharedMaterial;
            }
            manualLine.positionCount = 0;
            manualLine.enabled = true;
            SetLineColor(new Color(1f, 0.72f, 0.22f, 0.85f));
            obstacleSignature = maker.ManualObstacleSignature;
            ManualStatus = "경로 검사 중 · 관절 보간 미리보기";
            // 1도 간격으로 물리 갱신 뒤 검사한다. 이산 검사이므로 연속 충돌 보장이나
            // Backend가 생성할 실제 계획 경로를 대신하지 않는다.
            manualRoutine = StartCoroutine(InspectManualPath(start, destination, Mathf.Max(1, Mathf.CeilToInt(maxDelta))));
            return true;
        }

        IEnumerator InspectManualPath(float[] from, float[] target, int steps)
        {
            var physicsStep = new WaitForFixedUpdate();
            for (int step = 0; step <= steps; step++)
            {
                float t = (float)step / steps;
                for (int i = 0; i < JointCount; i++) previewDegrees[i] = Mathf.Lerp(from[i], target[i], t);
                if (!jointPreview.TryApplyTrajectoryJoints(previewDegrees))
                {
                    ManualStatus = "요청 거부 · Ghost 자세 적용 실패";
                    manualRoutine = null;
                    yield break;
                }
                yield return physicsStep;
                Physics.SyncTransforms();
                manualLine.positionCount = step + 1;
                manualLine.SetPosition(step, manualMaker.ManualPreviewPosition);
                if (!manualMaker.TryCheckManualCollision(out string reason))
                {
                    ManualCollision = true;
                    manualMaker.SetManualCollisionVisual(true);
                    SetLineColor(new Color(1f, 0.15f, 0.2f, 0.9f));
                    ManualStatus = "요청 거부 · " + reason;
                    manualRoutine = null;
                    yield break;
                }
                if (obstacleSignature != manualMaker.ManualObstacleSignature)
                {
                    ManualStatus = "요청 거부 · 검사 중 장애물이 변경되었습니다. 목표를 다시 확인하세요.";
                    manualRoutine = null;
                    yield break;
                }
            }
            manualReady = true;
            ManualStatus = "미리보기 검사 완료 · 실제 계획 경로는 실행 설비에서 별도 검증";
            manualRoutine = null;
        }

        void SetLineColor(Color color)
        {
            lineColor ??= new MaterialPropertyBlock();
            lineColor.SetColor("_BaseColor", color);
            lineColor.SetColor("_Color", color);
            manualLine.SetPropertyBlock(lineColor);
        }
        void OnValidate() => RefreshReference();

        void Update()
        {
            if (manualReady && manualMaker != null)
            {
                if (obstacleSignature != manualMaker.ManualObstacleSignature)
                {
                    manualReady = false;
                    ManualCollision = true;
                    manualMaker.SetManualCollisionVisual(true);
                    SetLineColor(new Color(1f, 0.15f, 0.2f, 0.9f));
                    ManualStatus = "요청 거부 · 장애물이 변경되었습니다. 경로를 다시 확인하세요.";
                }
            }
            if (!IsPlaying)
                return;

            JointTrajectoryPointMsg[] points = trajectory.points;
            double now = Time.realtimeSinceStartupAsDouble;
            double elapsed = now - startedAt;
            double finalTime = DurationSeconds(points[^1]);
            if (elapsed >= finalTime)
            {
                if (!Apply(points[^1]))
                {
                    Reject("Ghost rejected the final trajectory pose.");
                    return;
                }
                if (loop && finalTime > 0d)
                {
                    pointIndex = 0;
                    startedAt = now;
                }
                else
                {
                    IsPlaying = false;
                }
                return;
            }

            while (pointIndex + 1 < points.Length &&
                elapsed > DurationSeconds(points[pointIndex + 1]))
                pointIndex++;

            JointTrajectoryPointMsg from = points[pointIndex];
            JointTrajectoryPointMsg to = points[Mathf.Min(pointIndex + 1, points.Length - 1)];
            double fromTime = DurationSeconds(from);
            double toTime = DurationSeconds(to);
            float t = toTime <= fromTime
                ? 1f
                : Mathf.Clamp01((float)((elapsed - fromTime) / (toTime - fromTime)));
            if (!Apply(from, to, t))
                Reject("Ghost rejected an interpolated trajectory pose.");
        }

        /// <summary>검증된 JointTrajectory를 처음부터 Ghost에 재생한다.</summary>
        public bool Play(JointTrajectoryMsg value)
        {
            RefreshReference();
            if (jointPreview == null)
                return Reject("Assign GhostJointPreview.");
            if (!TryValidate(value, out int[] map, out string error))
                return Reject(error);
            if (!jointPreview.CaptureResetPose())
                return Reject("Ghost joints are not ready.");

            trajectory = value;
            jointMap = map;
            pointIndex = 0;
            startedAt = Time.realtimeSinceStartupAsDouble;
            LastError = string.Empty;
            IsPlaying = Apply(value.points[0]);
            return IsPlaying || Reject("Ghost rejected the first trajectory pose.");
        }

        /// <summary>검증된 궤적의 도착 관절 자세만 Ghost에 적용한다.</summary>
        public bool ShowDestination(JointTrajectoryMsg value)
        {
            RefreshReference();
            if (jointPreview == null)
                return Reject("Assign GhostJointPreview.");
            if (!TryValidate(value, out int[] map, out string error))
                return Reject(error);

            trajectory = value;
            jointMap = map;
            IsPlaying = false;
            LastError = string.Empty;
            return Apply(value.points[^1]) || Reject("Ghost rejected the destination pose.");
        }

        /// <summary>현재 Ghost 경로 재생을 중단한다.</summary>
        public void Stop()
        {
            if (manualRoutine != null) StopCoroutine(manualRoutine);
            manualRoutine = null;
            manualReady = false;
            if (manualLine != null) manualLine.enabled = false;
            IsPlaying = false;
            LastError = string.Empty;
        }

        /// <summary>경로 재생을 중단하고 Ghost를 Play() 직전 자세로 되돌린다.</summary>
        public bool ResetPreview()
        {
            Stop();
            return jointPreview != null && jointPreview.ResetPreview();
        }

        bool Apply(JointTrajectoryPointMsg point)
        {
            for (int i = 0; i < JointCount; i++)
                previewDegrees[i] = (float)(point.positions[jointMap[i]] * Mathf.Rad2Deg);
            return jointPreview.TryApplyTrajectoryJoints(previewDegrees);
        }

        bool Apply(JointTrajectoryPointMsg from, JointTrajectoryPointMsg to, float t)
        {
            for (int i = 0; i < JointCount; i++)
            {
                int sourceIndex = jointMap[i];
                double radians = from.positions[sourceIndex] +
                    (to.positions[sourceIndex] - from.positions[sourceIndex]) * t;
                previewDegrees[i] = (float)(radians * Mathf.Rad2Deg);
            }
            return jointPreview.TryApplyTrajectoryJoints(previewDegrees);
        }

        bool Reject(string error)
        {
            IsPlaying = false;
            LastError = error;
            return false;
        }

        void RefreshReference()
        {
            if (jointPreview == null)
                jointPreview = GetComponentInChildren<GhostJointPreview>(true);
        }

        static bool TryValidate(JointTrajectoryMsg value, out int[] map, out string error)
        {
            map = Array.Empty<int>();
            if (value?.joint_names == null || value.points == null ||
                value.joint_names.Length < JointCount || value.points.Length == 0)
            {
                error = "Trajectory requires j1~j6 and at least one point.";
                return false;
            }

            map = new int[JointCount];
            for (int jointIndex = 0; jointIndex < JointCount; jointIndex++)
            {
                string expected = $"j{jointIndex + 1}";
                int found = -1;
                for (int nameIndex = 0; nameIndex < value.joint_names.Length; nameIndex++)
                {
                    if (!string.Equals(value.joint_names[nameIndex], expected,
                        StringComparison.OrdinalIgnoreCase))
                        continue;
                    if (found >= 0)
                    {
                        error = $"Trajectory contains duplicate joint '{expected}'.";
                        return false;
                    }
                    found = nameIndex;
                }
                if (found < 0)
                {
                    error = $"Trajectory is missing joint '{expected}'.";
                    return false;
                }
                map[jointIndex] = found;
            }

            double previousTime = 0d;
            foreach (JointTrajectoryPointMsg point in value.points)
            {
                if (point?.positions == null ||
                    point.positions.Length != value.joint_names.Length ||
                    !TryDurationSeconds(point, out double time) || time < previousTime)
                {
                    error = "Trajectory point positions or time_from_start are invalid.";
                    return false;
                }
                for (int i = 0; i < JointCount; i++)
                {
                    if (!double.IsFinite(point.positions[map[i]]))
                    {
                        error = "Trajectory joint positions must be finite.";
                        return false;
                    }
                }
                previousTime = time;
            }

            error = string.Empty;
            return true;
        }

        static bool TryDurationSeconds(JointTrajectoryPointMsg point, out double seconds)
        {
            seconds = 0d;
            if (point?.time_from_start == null)
                return false;
            double nanoseconds = point.time_from_start.nanosec;
            if (point.time_from_start.sec < 0 || nanoseconds < 0d || nanoseconds >= 1_000_000_000d)
                return false;
            seconds = point.time_from_start.sec + nanoseconds * 1e-9d;
            return double.IsFinite(seconds);
        }

        static double DurationSeconds(JointTrajectoryPointMsg point)
        {
            TryDurationSeconds(point, out double seconds);
            return seconds;
        }

#if UNITY_EDITOR
        [ContextMenu("Self Check Ghost Trajectory")]
        void SelfCheckGhostTrajectory()
        {
            var point = new JointTrajectoryPointMsg
            {
                positions = new double[JointCount],
                time_from_start = new RosMessageTypes.BuiltinInterfaces.DurationMsg
                {
                    sec = 1,
                    nanosec = 500_000_000
                }
            };
            var value = new JointTrajectoryMsg
            {
                joint_names = new[] { "j1", "j2", "j3", "j4", "j5", "j6" },
                points = new[] { point }
            };
            Debug.Assert(TryValidate(value, out _, out string error), error, this);
            Debug.Assert(Math.Abs(DurationSeconds(point) - 1.5d) < 1e-9d,
                "Trajectory duration conversion failed.", this);
        }
#endif
    }
}
