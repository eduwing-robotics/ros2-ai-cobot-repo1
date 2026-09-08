// 역할: 주입된 런타임 참조와 페이지 전환 중 유지할 UI 세션 이력을 소유한다.
//
// UI 컴포넌트(FR5RunBinder, ManualJointPanel 등)는 씬을 직접 뒤지지 않는다.
// RobotMaster가 주입한 경로를 따라간다.
//   RobotMaster ─ Status(RobotStatusMaster) ─ StatusManager / Gripper
//               ├ AssemblyProgress(AssemblyProgressManager)
//               └ Scenario
// 기판 슬롯 구성(ItemManager)은 로봇이 아니라 트윈 쪽 데이터라 여기서 따로 들고 있는다.
// Ghost는 RobotMaster 계층 밖의 시각화 전용이라 여기서만 별도로 들고 있는다.

using System;
using System.Collections;
using System.Collections.Generic;
using MainUnity.Runtime.Camera;
using MainUnity.Runtime.Robot.Assembly;
using MainUnity.Runtime.Robot;
using MainUnity.Runtime.Robot.Status;
using MainUnity.Runtime.RobotGhost;
using MainUnity.Static;
using UnityEngine;
using UnityEngine.UIElements;
using ScenarioController = MainUnity.Runtime.Scenario.Scenario;

namespace MainUnity.UI
{
    // 페이지별 UIDocument 는 자식 오브젝트로 갈라지고 UIMaster 는 그 부모에 하나만 둔다.
    // 그래서 UIDocument 를 강제하지 않는다.
    [DisallowMultipleComponent]
    public sealed class UIMaster : MonoBehaviour
    {
        [Header("런타임 참조")]
        [Tooltip("HUD가 로봇 계층으로 들어가는 유일한 입구입니다.")]
        [SerializeField] RobotMaster robotMaster;

        [Tooltip("RobotMaster 계층 밖의 시각화 전용 컴포넌트입니다.")]
        [SerializeField] GhostMaster ghostMaster;

        [Tooltip("ROBOT 뷰포트에 실카메라 영상을 넣는 수신기입니다.")]
        [SerializeField] CamVisionReceiver visionImage;

        [Tooltip("기판 슬롯 구성을 들고 있는 트윈 쪽 데이터입니다.")]
        [SerializeField] ItemManager board;

        // 화면 전환으로 사라지지 않는 현재 세션의 관측 이력이다. 생산 DB 기록이 아니다.
        internal readonly List<(DateTime Time, string Source, string Message, bool Error, int Count)> Events = new();
        internal int EventVersion { get; private set; }
        RobotStatusManager observedStatus;
        AssemblyProgressManager observedProgress;
        TrayPartCalibrator observedCalibration;
        BoardPartCalibrator observedBoardCalibration;
        internal BoardPartCalibrator BoardCalibration => RobotMaster != null ? RobotMaster.BoardCalibration : null;
        internal TrayPartCalibrator Calibration => RobotMaster != null ? RobotMaster.Calibration : null;
        RobotRunState? lastRobotState;
        AssemblyProgressFrame lastProgress;

        void OnEnable() => StartCoroutine(ObserveSources());

        void OnDisable()
        {
            StopAllCoroutines();
            if (observedStatus != null) observedStatus.StatusChanged -= OnStatusChanged;
            if (observedProgress != null) observedProgress.ProgressChanged -= OnProgressChanged;
            if (observedCalibration != null) observedCalibration.ProgressChanged -= OnCalibrationChanged;
            if (observedBoardCalibration != null) observedBoardCalibration.ProgressChanged -= OnBoardCalibrationChanged;
            observedBoardCalibration = null;
            observedCalibration = null;
            observedStatus = null;
            observedProgress = null;
            lastRobotState = null;
            lastProgress = null;
        }

        IEnumerator ObserveSources()
        {
            var interval = new WaitForSecondsRealtime(0.25f);
            while (true)
            {
                // RobotMaster의 주입이 끝난 뒤 구독한다. 페이지나 전역 객체를 검색하지 않는다.
                if (observedStatus != StatusManager)
                {
                    if (observedStatus != null) observedStatus.StatusChanged -= OnStatusChanged;
                    observedStatus = StatusManager;
                    lastRobotState = null;
                    if (observedStatus != null)
                    {
                        observedStatus.StatusChanged += OnStatusChanged;
                        OnStatusChanged(observedStatus.State, observedStatus.ErrorLabel, observedStatus.ErrorDetail);
                    }
                }
                if (observedProgress != AssemblyProgress)
                {
                    if (observedProgress != null) observedProgress.ProgressChanged -= OnProgressChanged;
                    observedProgress = AssemblyProgress;
                    lastProgress = null;
                    if (observedProgress != null)
                    {
                        observedProgress.ProgressChanged += OnProgressChanged;
                        if (observedProgress.Latest != null)
                        {
                            lastProgress = observedProgress.Latest;
                            RecordEvent("조립", "현재 상태 확인 · " + lastProgress.State + " · Job " + lastProgress.JobId, false);
                        }
                    }
                }
                var calibration = IsSimulated ? null : Calibration;
                if (observedCalibration != calibration)
                {
                    if (observedCalibration != null) observedCalibration.ProgressChanged -= OnCalibrationChanged;
                    observedCalibration = calibration;
                    if (observedCalibration != null)
                    {
                        observedCalibration.ProgressChanged += OnCalibrationChanged;
                        OnCalibrationChanged();
                    }
                }
                var boardCalibration = IsSimulated ? null : BoardCalibration;
                if (observedBoardCalibration != boardCalibration)
                {
                    if (observedBoardCalibration != null) observedBoardCalibration.ProgressChanged -= OnBoardCalibrationChanged;
                    observedBoardCalibration = boardCalibration;
                    if (observedBoardCalibration != null)
                    {
                        observedBoardCalibration.ProgressChanged += OnBoardCalibrationChanged;
                        OnBoardCalibrationChanged();
                    }
                }
                yield return interval;
            }
        }

        void OnCalibrationChanged()
        {
            if (observedCalibration == null) return;
            RecordEvent("Calibration", observedCalibration.ProgressDetail,
                observedCalibration.Progress == TrayPartCalibrator.ProgressState.Rejected ||
                observedCalibration.Progress == TrayPartCalibrator.ProgressState.ConfigurationError);
        }

        void OnBoardCalibrationChanged()
        {
            if (observedBoardCalibration == null) return;
            RecordEvent("기판 Calibration", observedBoardCalibration.ProgressDetail,
                observedBoardCalibration.Progress == BoardPartCalibrator.ProgressState.Rejected ||
                observedBoardCalibration.Progress == BoardPartCalibrator.ProgressState.ConfigurationError);
        }

        void OnStatusChanged(RobotRunState state, RobotErrorLabel error, string detail)
        {
            if (state == RobotRunState.Disconnected)
                RecordEvent("로봇", "상태 수신 없음 · " + detail, true);
            else if (state == RobotRunState.Error)
                RecordEvent("로봇", "오류 · " + error + " · " + detail, true);
            else if (lastRobotState == RobotRunState.Disconnected || lastRobotState == RobotRunState.Error)
                RecordEvent("로봇", "수신 오류 신호 해소 · 설비 준비는 별도 확인", false);
            lastRobotState = state;
        }

        void OnProgressChanged(AssemblyProgressFrame frame)
        {
            if (frame == null)
            {
                if (lastProgress != null) RecordEvent("조립", "진행 추적 초기화 · 완료 판정 아님", false);
                lastProgress = null;
                return;
            }
            var previous = lastProgress;
            lastProgress = frame;
            if (previous != null && previous.JobId == frame.JobId && previous.State == frame.State &&
                previous.StepOrder == frame.StepOrder && previous.SlotCode == frame.SlotCode &&
                previous.ErrorCode == frame.ErrorCode && previous.Message == frame.Message) return;
            string description = frame.State switch
            {
                AssemblyState.Started => "조립 시작",
                AssemblyState.ConveyorMoving => "컨베이어 이동",
                AssemblyState.Paused => "일시정지",
                AssemblyState.Completed => "조립 완료 · 목표 PASS 달성 여부는 작업 화면에서 확인",
                AssemblyState.Failed => "조립 실패 · " + frame.ErrorCode + " · " + frame.Message,
                _ => null
            };
            if (previous?.State == AssemblyState.Paused && !frame.IsTerminal && frame.State != AssemblyState.Paused)
                description = "조립 재개";
            if (description != null)
                RecordEvent("조립", description + " · Job " + frame.JobId +
                    (string.IsNullOrEmpty(frame.SlotCode) ? "" : " · " + frame.SlotCode), frame.State == AssemblyState.Failed);
        }

        internal void RecordEvent(string source, string message, bool error)
        {
            int last = Events.Count - 1;
            if (last >= 0 && Events[last].Source == source && Events[last].Message == message && Events[last].Error == error)
            {
                var entry = Events[last];
                Events[last] = (DateTime.Now, source, message, error, entry.Count + 1);
            }
            else
            {
                // ponytail: 최근 200건만 메모리에 보관한다. 세션 간 추적은 영속 조회 계약이 생길 때 연결한다.
                if (Events.Count == 200) Events.RemoveAt(0);
                Events.Add((DateTime.Now, source, message, error, 1));
            }
            EventVersion++;
        }

        /// <summary>Mock/Real Backend를 선택해 주입하는 로봇 진입점이다.</summary>
        public RobotMaster RobotMaster => robotMaster;

        /// <summary>현재 선택된 Backend다. RobotMaster를 못 찾으면 실측으로 오인하지 않도록 Mock으로 본다.</summary>
        public RobotOperatingMode OperatingMode => RobotMaster != null
            ? RobotMaster.OperatingMode
            : RobotOperatingMode.Mock;

        /// <summary>Mock Backend는 일부 필드를 0으로 채워 보내므로 표시를 달리해야 한다.</summary>
        public bool IsSimulated => OperatingMode == RobotOperatingMode.Mock;

        /// <summary>Mock/Real과 무관하게 최신 상태를 보관하는 공통 관리자다.</summary>
        public RobotStatusManager StatusManager => RobotMaster != null
            ? RobotMaster.Status?.StatusManager
            : null;

        /// <summary>
        /// 조립 진행 상태다. Mock/Real 어느 Backend가 채웠는지 화면은 알 필요가 없다.
        /// </summary>
        public AssemblyProgressManager AssemblyProgress => RobotMaster != null
            ? RobotMaster.AssemblyProgress
            : null;

        /// <summary>
        /// 기판의 슬롯 구성이다. 타입별 슬롯 수와 실행 순서를 여기서만 읽는다.
        /// 진행 프레임은 "몇 번째까지 놓았는가"만 말하므로, "전부 몇 개인가"는 트윈이 답한다.
        /// Backend 와 무관한 씬 데이터라 Mock/Real 어느 쪽에서도 같은 값이다.
        /// TODO(API): 완성체 슬롯 조회가 생기면 그쪽으로 옮긴다 (DATA_STATION/DB/README.md의 Product Slot 계약).
        /// </summary>
        public ItemManager Board => board;

        /// <summary>공통 그리퍼 상태 컴포넌트다.</summary>
        public GripperSubscriber Gripper => RobotMaster != null
            ? RobotMaster.Status?.Gripper
            : null;

        /// <summary>선택된 Backend의 ScenarioControl을 주입받은 Scenario다.</summary>
        public ScenarioController Scenario => RobotMaster != null
            ? RobotMaster.Scenario
            : null;

        /// <summary>관절 목표 미리보기를 담당하는 Ghost 진입점이다.</summary>
        public GhostMaster Ghost => ghostMaster;

        /// <summary>ROBOT 뷰포트의 실카메라 영상 수신기다. HUD와 같은 오브젝트에 붙어 있다.</summary>
        public CamVisionReceiver VisionImage => visionImage;
    }
}
