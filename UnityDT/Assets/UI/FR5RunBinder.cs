// 역할: RUN 페이지(FR5Run.uxml)를 채운다.
//
//   실연결 : 모드 · 로봇 상태 · 링크 2개 · 관절 6개 · TCP · RPY · 그리퍼 · 워치독
//            (TCP · RPY · SAFETY 는 Real 전용이라 Mock 에서는 접는다)
//            조립 진행 — 하단 패널과 JOB 패널의 phase · 슬롯 줄
//   미연결 : 작업(jobs) · 수량 · 사이클 · 이벤트 로그 — 값을 지어내지 않고
//            FR5EmptyState 로 "연결 없음 + 필요한 조회"를 적는다  [TODO(API)]
//
// 이 화면의 가운데(500..1560 × 68..1080)는 비워 둔다. 로봇이 움직이는 영역이고,
// 계기는 화면 양 가장자리에 얹힌다 (Docs/ui-design.md 2절).

using System.Collections.Generic;
using MainUnity.Runtime.Camera;
using MainUnity.Runtime.Robot;
using MainUnity.Runtime.Robot.Assembly;
using MainUnity.Runtime.Robot.Status;
using MainUnity.Static;
using UnityEngine;
using UnityEngine.UIElements;

namespace MainUnity.UI
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(UIDocument))]
    public sealed class FR5RunBinder : MonoBehaviour
    {
        const int JointCount = 6;

        // 진행 칸 치수 — FR5Theme.uss 의 .cell 과 맞춘다
        const int CellWidth = 15, CellGap = 4, MinHeadWidth = 96;
        static readonly float[] LimitLow  = { -175f, -265f, -162f, -265f, -175f, -175f };
        static readonly float[] LimitHigh = {  175f,   85f,  162f,   85f,  175f,  175f };

        [Header("데이터 소스")]
        [SerializeField] UIMaster uiMaster;
        [SerializeField] RobotStatusManager statusManager;
        [SerializeField] GripperSubscriber gripper;
        [SerializeField] CamVisionReceiver vision;

        [SerializeField] float gripperStrokeMillimeters = 40f;
        [SerializeField] float watchdogLimitMilliseconds = 50f;

        readonly VisualElement[] jointFills = new VisualElement[JointCount];
        readonly Label[] jointValues = new Label[JointCount];
        readonly Label[] tcpValues = new Label[3];
        readonly Label[] rpyValues = new Label[3];

        Label gripperText, gripperValue, watchdogValue, toolValue, visionStats, realSource, mockNote, abortNote;
        Label progressNow, progressCount, unitPhase, unitStep;
        Button pauseButton, stepButton, abortButton;
        VisualElement progressHost, progressRailFill;
        readonly List<SlotGroup> slotGroups = new();
        int planTotal;
        bool warnedStepCount;
        VisualElement gripperChip, gripperFill, watchdogDot, visionEmpty, realStatus, poseBlock, safetyBlock;

        // 추세 (Docs/ui-design.md 3.1절). 값 하나만으로는 방향을 알 수 없어서,
        // 운전자가 이상을 알람이 뜬 뒤에야 알아채게 된다.
        // 4Hz × 120 표본 = 30초 창이다. 매 프레임 표본을 넣으면 30초가 1800 표본이 되어
        // 가로 340px 에 그릴 수 없고, 다시 그리는 비용만 늘어난다.
        const float SampleHz = 4f;
        const int SampleCapacity = 120;
        Sparkline gripperSpark, watchdogSpark, tcpSpark;
        double nextSampleTime;
        readonly System.Collections.Generic.List<(Label Value, System.Func<RobotStatusFrame, string> Read)> realRows = new();
        bool cached;

        void OnEnable() => cached = false;

        void Update()
        {
            // 기판 묶음을 세우려면 UIMaster 가 먼저 잡혀 있어야 하므로 Build 앞에 둔다.
            ResolveReferences();

            // UIDocument 는 활성화된 뒤에야 rootVisualElement 를 만든다.
            if (!cached) { Build(); if (!cached) return; }

            RefreshJoints();
            RefreshPose();
            RefreshGripper();
            RefreshLink();
            SampleTrends();
            RefreshRealStatus();
            RefreshAssembly();
        }

        void ResolveReferences()
        {
            if (uiMaster == null) uiMaster = GetComponentInParent<UIMaster>();
            if (uiMaster == null) return;
            if (statusManager == null) statusManager = uiMaster.StatusManager;
            if (gripper == null) gripper = uiMaster.Gripper;
            if (vision == null) vision = uiMaster.VisionImage;
        }

        void Build()
        {
            VisualElement root = GetComponent<UIDocument>().rootVisualElement;
            if (root == null) return;

            BuildAxisRow(root.Q<VisualElement>("tcp-row"), new[] { "X", "Y", "Z" }, tcpValues, 26);
            BuildAxisRow(root.Q<VisualElement>("rpy-row"), new[] { "R", "P", "Y" }, rpyValues, 20);
            BuildJoints(root.Q<VisualElement>("joint-list"));
            BuildJob(root);
            progressHost = root.Q<VisualElement>("progress-groups");
            progressRailFill = root.Q<VisualElement>("run-progress-fill");
            progressNow = root.Q<Label>("progress-now");
            progressCount = root.Q<Label>("progress-count");
            unitPhase = root.Q<Label>("unit-phase");
            unitStep = root.Q<Label>("unit-step");
            pauseButton = root.Q<Button>("job-pause-button");
            stepButton = root.Q<Button>("job-step-button");
            abortButton = root.Q<Button>("job-abort-button");
            abortNote = root.Q<Label>("abort-note");
            ConfigureJobControls();
            BuildEvents(root.Q<VisualElement>("event-list"), root.Q<Label>("events-summary"));

            gripperChip = root.Q<VisualElement>("gripper-state-chip");
            gripperText = root.Q<Label>("gripper-state-text");
            gripperValue = root.Q<Label>("gripper-value");
            gripperFill = root.Q<VisualElement>("gripper-fill");
            watchdogDot = root.Q<VisualElement>("watchdog-dot");
            watchdogValue = root.Q<Label>("watchdog-value");
            toolValue = root.Q<Label>("tool-value");
            visionEmpty = root.Q<VisualElement>("vision-empty");
            visionStats = root.Q<Label>("vision-stats");
            realStatus = root.Q<VisualElement>("real-status");
            realSource = root.Q<Label>("real-source");
            poseBlock = root.Q<VisualElement>("pose-block");
            safetyBlock = root.Q<VisualElement>("safety-block");
            mockNote = root.Q<Label>("mock-note");
            BuildSparklines(root);
            BuildRealStatus();
            cached = true;
        }

        void BuildSparklines(VisualElement root)
        {
            gripperSpark = Attach(root, "gripper-spark");
            // 그리퍼는 0~100% 로 범위가 정해져 있다. 자동 범위로 두면 26.0~26.4 같은
            // 미세한 흔들림이 화면 전체 높이로 확대돼 큰 사건처럼 보인다.
            gripperSpark?.SetRange(0f, 100f);

            watchdogSpark = Attach(root, "watchdog-spark");
            // 지연은 자동 범위다. 한계(50ms)를 넘는 순간이 아니라 한계로 다가가는
            // 기울기를 읽는 것이 목적이라, 실제 변동 폭에 맞춰야 기울기가 보인다.
            if (watchdogSpark != null) watchdogSpark.Limit = watchdogLimitMilliseconds;

            // TCP Z 는 Real 전용이다. Mock 에서는 pose-block 째 접히므로 보이지 않는다.
            tcpSpark = Attach(root, "tcp-spark");
        }

        static Sparkline Attach(VisualElement root, string hostName)
        {
            VisualElement host = root.Q<VisualElement>(hostName);
            if (host == null) return null;
            var spark = new Sparkline(SampleCapacity);
            spark.style.flexGrow = 1;
            host.Add(spark);
            return spark;
        }

        /// <summary>
        /// 고정 주기로만 표본을 넣는다. 프레임률이 바뀌어도 창 길이(30초)가 같아야
        /// 두 번 본 기울기를 비교할 수 있다.
        /// </summary>
        void SampleTrends()
        {
            double now = Time.realtimeSinceStartupAsDouble;
            if (now < nextSampleTime) return;
            nextSampleTime = now + 1d / SampleHz;

            RobotStatusFrame frame = statusManager != null ? statusManager.Latest : null;

            if (watchdogSpark != null)
            {
                if (frame == null) watchdogSpark.ClearHistory();
                else watchdogSpark.Push((float)((now - frame.ReceiveTimeSeconds) * 1000d));
            }

            if (gripperSpark != null)
            {
                if (gripper != null && gripper.TryGetOpeningPercent(out float percent))
                    gripperSpark.Push(percent);
                else gripperSpark.ClearHistory();
            }

            if (tcpSpark != null)
            {
                // Mock 은 TCP 를 채우지 않는다. 0 을 실측으로 오인하지 않게 비운다.
                bool blank = frame == null ||
                    (uiMaster != null && uiMaster.IsSimulated &&
                     Mathf.Approximately(frame.TcpPositionMillimeters.z, 0f));
                if (blank) tcpSpark.ClearHistory();
                else tcpSpark.Push(frame.TcpPositionMillimeters.z);
            }
        }
        void ConfigureJobControls()
        {
            // 자동 조립 계약은 ExecuteAsync 하나뿐이다. 없는 제어를 UI에서 흉내 내면
            // 작업이 멈춘 것처럼 보여 실제 장비 상태와 화면이 어긋난다.
            pauseButton?.SetEnabled(false);
            stepButton?.SetEnabled(false);
            abortButton?.SetEnabled(false);
            if (pauseButton != null) pauseButton.tooltip = "PAUSE 제어 계약이 아직 없습니다.";
            if (stepButton != null) stepButton.tooltip = "STEP 제어 계약이 아직 없습니다.";
            if (abortButton != null) abortButton.tooltip = "ABORT 제어 계약이 아직 없습니다.";
            if (abortNote != null) abortNote.text = "PAUSE · STEP · ABORT 제어 계약 미구현";
        }



        static void BuildAxisRow(VisualElement host, string[] axes, Label[] sink, int fontSize)
        {
            if (host == null) return;
            host.Clear();
            for (int i = 0; i < axes.Length; i++)
            {
                var box = new VisualElement { style = { width = 112 } };
                var k = new Label(axes[i]);
                k.AddToClassList("micro");
                box.Add(k);

                var v = new Label("—");
                v.style.color = new Color(0.886f, 0.925f, 0.945f);
                v.style.fontSize = fontSize;
                v.style.unityFontStyleAndWeight = FontStyle.Bold;
                v.style.marginTop = 4;
                // 오른쪽 정렬이다. 왼쪽 정렬이면 412.8 에서 48.1 로 바뀔 때 소수점이
                // 가로로 뛰어, 값이 아니라 자리가 움직이는 것처럼 보인다.
                // (폰트에 tabular figures 가 없어 자릿수마다 폭이 다르다.)
                v.style.width = 104;
                v.style.unityTextAlign = TextAnchor.MiddleRight;
                sink[i] = v;
                box.Add(v);
                host.Add(box);
            }
        }

        void BuildJoints(VisualElement host)
        {
            if (host == null) return;
            host.Clear();
            for (int i = 0; i < JointCount; i++)
            {
                var row = new VisualElement();
                row.AddToClassList("row");
                // 26px × 6 행. 좌측 열(88..500 × 68..1080, 안여백 제하고 968px)에서
                // 관절이 가져갈 수 있는 몫이다.
                row.style.height = 26;

                var k = new Label($"J{i + 1}");
                k.AddToClassList("muted");
                k.style.width = 30;
                row.Add(k);

                var track = new VisualElement();
                track.AddToClassList("gauge");
                track.style.flexGrow = 1;
                var fill = new VisualElement();
                fill.AddToClassList("gauge__fill");
                fill.AddToClassList("gauge__fill--neutral");
                fill.style.width = Length.Percent(0f);
                jointFills[i] = fill;
                track.Add(fill);
                row.Add(track);

                var v = new Label("—");
                v.style.color = new Color(0.886f, 0.925f, 0.945f);
                v.style.fontSize = 16;
                v.style.unityFontStyleAndWeight = FontStyle.Bold;
                v.style.width = 66;
                v.style.unityTextAlign = TextAnchor.MiddleRight;
                jointValues[i] = v;
                row.Add(v);
                host.Add(row);
            }
        }

        /// <summary>
        /// 작업 정보는 조회 경로가 없다. 지어내지 않고 무엇이 없는지 적는다.
        /// jobs 조회가 생기면 이 메서드만 갈아끼운다.
        /// </summary>
        void BuildJob(VisualElement root)
        {
            FR5EmptyState.Missing(root.Q<Label>("job-id"));
            FR5EmptyState.Missing(root.Q<Label>("job-product"));
            FR5EmptyState.Detail(root.Q<Label>("job-recipe"), "jobs · products 조회 필요");
            FR5EmptyState.Dash(root.Q<Label>("job-progress-text"));
            FR5EmptyState.Dash(root.Q<Label>("cycle-value"));
            // unit-phase · unit-step 은 RefreshAssembly 가 조립 피드백으로 채운다

            VisualElement fill = root.Q<VisualElement>("job-progress-fill");
            if (fill != null) fill.style.width = 0;
        }

        // ─────────────────────── 조립 진행 ───────────────────────
        //
        // 칸 하나 = 슬롯 하나 = 레시피 스텝 하나다. 묶음 하나 = 부품 타입 하나.
        // 칸 수와 순서는 씬의 기판이, 어디까지 놓였는지는 조립 피드백이 답한다.

        /// <summary>부품 타입 하나의 진행 묶음이다. Start 는 첫 슬롯의 0-기준 스텝 번호다.</summary>
        sealed class SlotGroup
        {
            public int Start;
            public int Total;
            public VisualElement Root;
            public Label Count;
            public VisualElement[] Cells;
        }

        /// <summary>
        /// 기판 구성으로 묶음을 세운다. ItemManager 를 아직 못 잡았으면 다음 프레임에 다시 시도한다.
        /// Build 에서 한 번만 하지 않는 이유는, UIDocument 가 씬 로드보다 먼저 살아날 수 있어서다.
        /// </summary>
        bool EnsureSlotGroups()
        {
            if (slotGroups.Count > 0) return true;
            if (progressHost == null) return false;

            ItemManager board = uiMaster != null ? uiMaster.Board : null;
            if (board == null) return false;

            progressHost.Clear();
            planTotal = 0;
            foreach (ItemManager.AssemblySlot group in board.AssemblySlots)
            {
                int total = group.Slots.Length;
                if (total <= 0) continue;
                slotGroups.Add(BuildSlotGroup(group.RequiredItemType, planTotal, total));
                planTotal += total;
            }
            return slotGroups.Count > 0;
        }

        SlotGroup BuildSlotGroup(string partId, int start, int total)
        {
            var box = new VisualElement();
            box.AddToClassList("grp");

            var head = new VisualElement();
            head.AddToClassList("grp__head");
            // 머리줄을 칸 줄과 같은 너비로 묶는다. 묶음 상자는 서로 같은 폭으로 늘어나므로
            // 그냥 두면 개수가 칸에서 한참 떨어진 곳에 떠서 어느 묶음의 수인지 흐려진다.
            head.style.width = Mathf.Max(total * (CellWidth + CellGap) - CellGap, MinHeadWidth);

            var name = new Label(string.IsNullOrEmpty(partId) ? "—" : partId.ToUpperInvariant());
            name.AddToClassList("grp__name");
            head.Add(name);

            var spacer = new VisualElement();
            spacer.AddToClassList("spacer");
            head.Add(spacer);

            var count = new Label(total.ToString());
            count.AddToClassList("grp__count");
            head.Add(count);
            box.Add(head);

            var cells = new VisualElement();
            cells.AddToClassList("grp__cells");
            var sink = new VisualElement[total];
            for (int i = 0; i < total; i++)
            {
                var cell = new VisualElement();
                cell.AddToClassList("cell");
                cells.Add(cell);
                sink[i] = cell;
            }
            box.Add(cells);
            progressHost.Add(box);

            return new SlotGroup { Start = start, Total = total, Root = box, Count = count, Cells = sink };
        }

        void RefreshAssembly()
        {
            if (!EnsureSlotGroups()) return;

            AssemblyProgressManager manager = uiMaster != null ? uiMaster.AssemblyProgress : null;
            AssemblyProgressFrame frame = manager != null ? manager.Latest : null;

            int placed = frame != null ? frame.PlacedCount : 0;

            // StepOrder 는 1부터다. 진행 중인 스텝의 부품은 아직 기판에 없다.
            bool running = frame != null && !frame.IsTerminal && frame.StepOrder > 0;
            int nowIndex = running ? frame.StepOrder - 1 : -1;
            int badIndex = frame != null && frame.State == AssemblyState.Failed && frame.StepOrder > 0
                ? frame.StepOrder - 1
                : -1;

            foreach (SlotGroup group in slotGroups)
            {
                int done = Mathf.Clamp(placed - group.Start, 0, group.Total);
                bool isNow = nowIndex >= group.Start && nowIndex < group.Start + group.Total;

                group.Count.text = frame != null ? $"{done} / {group.Total}" : group.Total.ToString();
                group.Root.EnableInClassList("grp--now", isNow);

                for (int i = 0; i < group.Cells.Length; i++)
                {
                    int step = group.Start + i;
                    VisualElement cell = group.Cells[i];
                    cell.EnableInClassList("cell--done", i < done);
                    cell.EnableInClassList("cell--now", step == nowIndex);
                    cell.EnableInClassList("cell--bad", step == badIndex);
                }
            }

            WarnOnStepCountMismatch(frame);
            RefreshProgressHeader(frame, placed);
            RefreshUnitLine(frame);
        }

        /// <summary>
        /// 레시피 스텝 수와 씬 슬롯 수가 다르면 화면의 칸이 실제 작업과 다른 것을 세게 된다.
        /// 조립을 막지는 않는다 — 로봇은 옳은 자리에 놓고 표시만 어긋나기 때문이다.
        /// </summary>
        void WarnOnStepCountMismatch(AssemblyProgressFrame frame)
        {
            if (warnedStepCount || frame == null || frame.ExpectedStepCount <= 0) return;
            if (frame.ExpectedStepCount == planTotal) return;
            warnedStepCount = true;
            Debug.LogWarning(
                "조립 스텝 수가 기판 슬롯 수와 다르다 — 레시피 " + frame.ExpectedStepCount +
                " vs 씬 " + planTotal + ". 둘 중 하나가 갱신되지 않았다.", this);
        }

        void RefreshProgressHeader(AssemblyProgressFrame frame, int placed)
        {
            if (progressCount != null)
                progressCount.text = frame != null ? $"{placed} / {planTotal}" : $"{planTotal} 슬롯";

            // 상단 진행 레일. 화면에서 크게 움직이는 유일한 것이라 여기 하나에서만 값을 준다.
            // 슬롯이 0 이면 나눌 수 없고, 그 경우 레일은 비어 있는 것이 맞다 — 0% 는
            // "아직 아무것도 안 놓았다"가 아니라 "셀 수 있는 것이 없다"이기 때문이다.
            if (progressRailFill != null)
                progressRailFill.style.width = Length.Percent(
                    planTotal > 0 ? Mathf.Clamp01((float)placed / planTotal) * 100f : 0f);

            if (progressNow == null) return;
            progressNow.text = frame == null ? "작업 없음" : Describe(frame);
            SetTone(progressNow, frame == null || frame.State == AssemblyState.Completed
                ? "muted"
                : frame.State == AssemblyState.Failed ? "bad" : "accent");
        }

        /// <summary>JOB 패널의 현재 phase 와 슬롯 줄이다. 하단 패널과 같은 프레임을 읽는다.</summary>
        void RefreshUnitLine(AssemblyProgressFrame frame)
        {
            if (unitPhase != null)
            {
                unitPhase.text = frame != null ? frame.State.ToString().ToUpperInvariant() : "IDLE";
                // FAILED 가 RUNNING·IDLE 과 같은 무게로 보이면 실패를 못 알아본다.
                // 진행 중은 색을 얻지 않는다 — 이상만 색을 얻는다(Docs/ui-design.md 1절).
                SetTone(unitPhase, frame != null && frame.State == AssemblyState.Failed ? "bad" : "none");
            }

            if (unitStep == null) return;
            if (frame == null)
            {
                unitStep.text = $"슬롯 {planTotal}개   ·   대기";
                return;
            }

            string step = $"step {Mathf.Clamp(frame.StepOrder, 0, planTotal)} / {planTotal}";
            unitStep.text = string.IsNullOrEmpty(frame.SlotCode)
                ? step
                : step + "   ·   slot " + frame.SlotCode;
        }

        static string Describe(AssemblyProgressFrame frame)
        {
            switch (frame.State)
            {
                case AssemblyState.Failed:
                    string reason = !string.IsNullOrEmpty(frame.ErrorCode) ? frame.ErrorCode : frame.Message;
                    return string.IsNullOrEmpty(reason) ? "실패" : "실패   ·   " + reason;
                case AssemblyState.Completed:
                    return "완료";
                default:
                    if (string.IsNullOrEmpty(frame.SlotCode))
                        return string.IsNullOrEmpty(frame.PartId) ? "시작" : frame.PartId;
                    return frame.IsHolding
                        ? $"{frame.PartId} 파지   →   {frame.SlotCode}"
                        : $"{frame.PartId}   ·   {frame.SlotCode}";
            }
        }

        /// <summary>색 클래스는 하나만 걸린다. 정상에는 색을 주지 않는다(Docs/ui-design.md 1절).</summary>
        static void SetTone(Label label, string tone)
        {
            if (label == null) return;
            label.EnableInClassList("muted", tone == "muted");
            label.EnableInClassList("accent", tone == "accent");
            label.EnableInClassList("bad", tone == "bad");
        }

        /// <summary>이벤트 로그를 받을 경로가 없다. 지난 일을 지어내면 사고 조사가 틀어진다.</summary>
        static void BuildEvents(VisualElement host, Label summary)
        {
            FR5EmptyState.Fill(host, "이벤트 로그 경로 없음");
            FR5EmptyState.Dash(summary);
        }


        /// <summary>
        /// Real 백엔드만 채우는 안전·상태 값이다 (/nonrt_state_data).
        ///
        /// 6행에서 2행으로 줄였다. E-STOP · ALARM · 이상 정지는 셋 다 "지금 멈춰야 하는가"
        /// 하나에 답하고, 그 세부는 이미 알람 띠가 크게 말한다. 좌측 열의 세로 예산은
        /// 766px 이라 같은 답을 여섯 줄로 적을 자리가 없다.
        /// </summary>
        void BuildRealStatus()
        {
            if (realStatus == null) return;
            realStatus.Clear();
            realRows.Clear();

            AddRealRow("안전", f =>
                f.EmergencyStop != 0 ? "E-STOP 작동" :
                f.Alarm != 0 ? "ALARM 발생" :
                f.AbnormalStop != 0 ? "이상 정지" : "정상");
            AddRealRow("프로그램", f => f.MainErrorCode == 0 && f.SubErrorCode == 0
                ? $"mode {f.RobotMode} · state {f.ProgramState}"
                : $"error {f.MainErrorCode}:{f.SubErrorCode}");
        }

        void AddRealRow(string key, System.Func<RobotStatusFrame, string> read)
        {
            var row = new VisualElement();
            row.AddToClassList("row");
            row.style.height = 20;

            var k = new Label(key);
            k.AddToClassList("muted");
            k.style.fontSize = 12;
            row.Add(k);

            var spacer = new VisualElement();
            spacer.AddToClassList("spacer");
            row.Add(spacer);

            var v = new Label("—");
            v.style.fontSize = 13;
            v.style.unityFontStyleAndWeight = FontStyle.Bold;
            v.style.color = new Color(0.58f, 0.65f, 0.70f);
            row.Add(v);

            realRows.Add((v, read));
            realStatus.Add(row);
        }

        /// <summary>
        /// Mock 에서는 TCP · RPY · SAFETY 를 통째로 접는다.
        ///
        /// 값이 없다고 "—" 를 296px 만큼 세워 두면 자리만 먹고 아무 것도 답하지 않는다.
        /// 접은 자리에는 한 줄 사유를 남긴다. Real 로 바꾸면 그대로 다시 펴진다.
        /// </summary>
        void RefreshModeBlocks(bool mock)
        {
            DisplayStyle real = mock ? DisplayStyle.None : DisplayStyle.Flex;
            if (poseBlock != null) poseBlock.style.display = real;
            if (safetyBlock != null) safetyBlock.style.display = real;
            if (mockNote != null) mockNote.style.display = mock ? DisplayStyle.Flex : DisplayStyle.None;
        }

        void RefreshRealStatus()
        {
            bool mock = uiMaster == null || uiMaster.IsSimulated;
            RobotStatusFrame frame = statusManager != null ? statusManager.Latest : null;

            RefreshModeBlocks(mock);

            if (realSource != null)
                realSource.text = mock ? "Mock 미제공" : "/nonrt_state_data";

            foreach ((Label value, System.Func<RobotStatusFrame, string> read) in realRows)
            {
                if (mock || frame == null)
                {
                    value.text = "—";
                    value.style.color = new Color(0.29f, 0.33f, 0.37f);
                    continue;
                }
                string text = read(frame);
                value.text = text;
                // 이상만 색을 얻는다. 정상 값에는 색을 주지 않는다.
                bool bad = text != "정상" && !text.StartsWith("mode");
                value.style.color = bad
                    ? new Color(1f, 0.56f, 0.61f)
                    : new Color(0.58f, 0.65f, 0.70f);
            }
        }

        // ── 실데이터 ────────────────────────────────────────────────
        void RefreshJoints()
        {
            float[] joints = statusManager != null ? statusManager.Latest?.JointDegrees : null;
            bool live = joints != null && joints.Length == JointCount;
            for (int i = 0; i < JointCount; i++)
            {
                if (jointValues[i] != null) jointValues[i].text = live ? joints[i].ToString("0.0") : "—";
                if (jointFills[i] == null) continue;

                float ratio = live ? Mathf.InverseLerp(LimitLow[i], LimitHigh[i], joints[i]) : 0f;
                jointFills[i].style.width = Length.Percent(ratio * 100f);
                // 가동범위 양 끝 어느 쪽이든 가까우면 경고색
                bool near = live && (ratio >= 0.8f || ratio <= 0.2f);
                jointFills[i].EnableInClassList("gauge__fill--warn", near);
                jointFills[i].EnableInClassList("gauge__fill--neutral", !near);
            }
        }

        void RefreshPose()
        {
            RobotStatusFrame frame = statusManager != null ? statusManager.Latest : null;
            if (frame == null)
            {
                foreach (Label l in tcpValues) if (l != null) l.text = "—";
                foreach (Label l in rpyValues) if (l != null) l.text = "—";
                return;
            }
            Vector3 p = frame.TcpPositionMillimeters, r = frame.TcpRotationDegrees;
            SetAxis(tcpValues, 0, p.x); SetAxis(tcpValues, 1, p.y); SetAxis(tcpValues, 2, p.z);
            SetAxis(rpyValues, 0, r.x); SetAxis(rpyValues, 1, r.y); SetAxis(rpyValues, 2, r.z);
        }

        /// <summary>Mock Backend 는 TCP/RPY 를 채우지 않는다. 0 을 실측으로 오인하지 않게 비운다.</summary>
        void SetAxis(Label[] sink, int i, float v)
        {
            if (sink[i] == null) return;
            bool blank = uiMaster != null && uiMaster.IsSimulated && Mathf.Approximately(v, 0f);
            sink[i].text = blank ? "—" : v.ToString("0.0");
        }

        /// <summary>
        /// TODO(API·Real): Real 그리퍼는 개폐 명령만 있고 열림 폭 피드백이 없다.
        ///                 RobotNonrtState 에 폭이 들어오면 여기서 percent 를 그 값으로 바꾼다.
        ///                 지금 Real 모드의 폭 표시는 GripperSubscriber 추정치다.
        /// </summary>
        void RefreshGripper()
        {
            if (gripper == null || !gripper.TryGetOpeningPercent(out float percent))
            {
                if (gripperValue != null) gripperValue.text = "—";
                if (gripperText != null) gripperText.text = "—";
                if (gripperFill != null) gripperFill.style.width = Length.Percent(0f);
                gripperChip?.EnableInClassList("chip--accent", false);
                return;
            }
            float mm = gripperStrokeMillimeters * percent * 0.01f;
            if (gripperValue != null) gripperValue.text = $"{mm:0.0} / {gripperStrokeMillimeters:0}";
            if (gripperFill != null) gripperFill.style.width = Length.Percent(percent);
            bool holding = percent < 95f;
            if (gripperText != null) gripperText.text = holding ? "HOLDING" : "OPEN";
            gripperChip?.EnableInClassList("chip--accent", holding);
        }

        /// <summary>모드·로봇상태·링크는 FR5ShellBinder 가 맡는다. 여기서는 페이지 고유값만 본다.</summary>
        void RefreshLink()
        {
            bool live = statusManager != null && statusManager.Latest != null;
            // 워치독이 살아 있는 것은 정상이다. 초록을 주면 화면에서 가장 눈에 띄는 것이
            // "정상"이 된다. 늦어지는 것은 아래 스파크라인이 알람 전에 보여 준다.
            watchdogDot?.EnableInClassList("dot--ok", live);
            watchdogDot?.EnableInClassList("dot--good", false);
            watchdogDot?.EnableInClassList("dot--bad", !live);
            // "OK" 는 값이 아니다. 한계까지 얼마나 남았는지 알 수 없으므로 실측 지연을 적는다.
            // 위 스파크라인이 그 값의 30초 기울기를 함께 보여 준다.
            if (watchdogValue != null)
            {
                double ageMs = live
                    ? (Time.realtimeSinceStartupAsDouble - statusManager.Latest.ReceiveTimeSeconds) * 1000d
                    : -1d;
                watchdogValue.text = live
                    ? $"{ageMs:0} / {watchdogLimitMilliseconds:0} ms"
                    : "STALE";
                // 한계를 넘은 것만 색을 얻는다.
                SetTone(watchdogValue, !live || ageMs > watchdogLimitMilliseconds ? "bad" : "none");
            }
            // TODO(API): tool offset 은 레시피/툴 정의에서 온다. 지금은 표시만.
            // TODO(API·Real): 속도 오버라이드는 Mock·Real 모두 지령 경로가 없다.
            //                 fairino_msgs 의 속도 설정 명령이 붙으면 셸의 SPEED 를 슬라이더로 바꾼다.
            if (toolValue != null) toolValue.text = "tool Z +142.0 mm · payload 1.85 kg";

            bool received = vision != null && vision.HasReceivedImage;
            double age = vision != null ? Time.realtimeSinceStartupAsDouble - vision.LastReceiveTimeSeconds : -1;
            bool fresh = received && age >= 0 && age < 2;

            if (visionEmpty != null) visionEmpty.style.display = fresh ? DisplayStyle.None : DisplayStyle.Flex;
            if (visionStats != null) visionStats.text = fresh ? $"수신 중 · {age * 1000:0} ms 전" : "수신 없음";
        }
    }
}
