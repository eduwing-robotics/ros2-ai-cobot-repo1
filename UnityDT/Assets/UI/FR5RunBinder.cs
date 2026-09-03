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

        [Header("카메라")]
        // MOCK 에는 실제 카메라가 없다. 트윈의 RenderTexture 가 그 자리를 대신한다.
        // REAL 에서는 CamVisionReceiver 가 ROS 스트림으로 덮어쓴다.
        [Tooltip("ROBOT 소스로 쓸 트윈 카메라의 RenderTexture 입니다.")]
        [SerializeField] RenderTexture robotCamTexture;
        [Tooltip("BOARD 소스로 쓸 기판 카메라의 RenderTexture 입니다.")]
        [SerializeField] RenderTexture boardCamTexture;

        // RenderTexture 카메라는 켜 두면 매 프레임 씬을 통째로 한 번 더 그린다.
        // 화면에 보이는 것은 한 번에 하나뿐이므로 고른 것만 켠다.
        [Tooltip("원본 대체용 트윈 카메라입니다. 고르지 않은 동안 꺼 둡니다.")]
        [SerializeField] UnityEngine.Camera robotCamCamera;
        [Tooltip("검출 대체용 기판 카메라입니다. 고르지 않은 동안 꺼 둡니다.")]
        [SerializeField] UnityEngine.Camera boardCamCamera;

        readonly VisualElement[] jointFills = new VisualElement[JointCount];
        readonly Label[] jointValues = new Label[JointCount];
        readonly Label[] tcpValues = new Label[3];
        readonly Label[] rpyValues = new Label[3];

        Label gripperText, gripperValue, watchdogValue, toolValue, visionStats, realSource, mockNote;
        Label progressNow, progressCount, unitPhase, unitStep;
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
        Sparkline gripperSpark, watchdogSpark;
        double nextSampleTime;

        // 관측 칸. 이름은 카메라가 실제로 무엇을 비추는지에서 왔다.
        //   TRAY      트레이 구획·수량 검출 (LIVE VIEW · DETECTION ENABLED)
        //   PARTS     부품 OBB 검출 (TRAY PART OBB · ROI FILTERED)
        //   CONVEYOR  정지선 모니터 (DUAL STOP-LINE MONITOR)
        //   CELL      셀 전경 광각 원본. 대응하는 검출 스트림이 없다 (BEST_EFFORT 발행)
        // 엔드포인트가 이미지 토픽에 qos_profile_sensor_data 를 쓰므로 BEST_EFFORT
        // 발행자도 받는다.
        sealed class CamTile
        {
            public string Title;
            public string Topic;
            public int Index;
            public bool On;
            public CamVisionReceiver Receiver;
            public VisualElement Root;
            public Label Age;
            public Button Chip;
            public Image Image;
        }

        readonly CamTile[] camTiles =
        {
            new CamTile { Index = 1, Title = "TRAY",     Topic = "/vision/tray/detections_image/compressed", On = true },
            new CamTile { Index = 2, Title = "PARTS",    Topic = "/vision/parts_obb/image/compressed" },
            new CamTile { Index = 3, Title = "CONVEYOR", Topic = "/vision/conveyor/stop_image/compressed" },
            // 전경 카메라에는 대응하는 검출 스트림이 없다. 유일한 광각이라 원본으로 남긴다.
            new CamTile { Index = 4, Title = "CELL · RAW", Topic = "/camera3/image_raw/compressed" },
        };

        // 이 시간을 넘겨 프레임이 없으면 그 칸만 늦은 것으로 표시한다.
        const double CamStaleSeconds = 2d;
        bool camExpanded;
        Label camBadge;
        VisualElement camPanel, camGrid;
        Button camExpandButton;

        Label nowSlot, nowPart, recipeVersion, requestId, twinSource;

        readonly System.Collections.Generic.List<(Label Value, System.Func<RobotStatusFrame, string> Read)> realRows = new();
        bool cached;

        void OnEnable()
        {
            cached = false;
            slotGroups.Clear();
        }

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
            RefreshCamera();
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

            BuildPoseGrid(root.Q<VisualElement>("tcp-row"));
            BuildJoints(root.Q<VisualElement>("joint-list"));
            BuildJob(root);
            progressHost = root.Q<VisualElement>("progress-groups");
            progressRailFill = root.Q<VisualElement>("run-progress-fill");
            progressNow = root.Q<Label>("progress-now");
            progressCount = root.Q<Label>("progress-count");
            unitPhase = root.Q<Label>("unit-phase");
            unitStep = root.Q<Label>("unit-step");
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
            nowSlot = root.Q<Label>("now-slot");
            nowPart = root.Q<Label>("now-part");
            recipeVersion = root.Q<Label>("recipe-version");
            requestId = root.Q<Label>("request-id");
            twinSource = root.Q<Label>("twin-source");
            BuildCamera(root);
            BuildSparklines(root);
            BuildRealStatus();
            cached = true;
        }

        void BuildCamera(VisualElement root)
        {
            camPanel = root.Q<VisualElement>("cam-panel");
            camGrid = root.Q<VisualElement>("cam-grid");
            camBadge = root.Q<Label>("cam-badge");
            camExpandButton = root.Q<Button>("cam-expand");

            UnbindCamera();
            bool mock = uiMaster == null || uiMaster.IsSimulated;
            SetMockCameras(false, false);
            foreach (CamTile tile in camTiles)
            {
                tile.Root = root.Q<VisualElement>("cam-tile-" + tile.Index);
                tile.Age = root.Q<Label>("cam-age-" + tile.Index);
                tile.Chip = root.Q<Button>("cam-chip-" + tile.Index);
                tile.Image = root.Q<Image>("cam-image-" + tile.Index);
                bool supported = !mock || tile.Index <= 2;
                if (mock && !supported) tile.On = false;

                Label title = root.Q<Label>("cam-title-" + tile.Index);
                if (title != null)
                    title.text = mock && supported ? (tile.Index == 1 ? "ROBOT" : "BOARD") : tile.Title;
                if (tile.Chip != null)
                {
                    tile.Chip.style.display = supported ? DisplayStyle.Flex : DisplayStyle.None;
                    if (mock && supported)
                    {
                        Label chipText = tile.Chip.Q<Label>();
                        if (chipText != null)
                            chipText.text = tile.Index == 1 ? "ROBOT" : "BOARD";
                    }
                }
                if (!supported) continue;

                if (mock)
                {
                    if (tile.Image != null) tile.Image.image = GetMockTexture(tile);
                }
                else
                {
                    // 칸마다 수신기를 하나씩 붙인다. 하나로 돌려 쓰면 칸을 바꿀 때마다
                    // 구독을 갈아타야 하고, 그러면 여러 칸을 동시에 볼 수 없다.
                    //
                    // CamVisionReceiver 는 DisallowMultipleComponent 라 한 오브젝트에
                    // 둘을 못 붙인다. 칸마다 자식 오브젝트를 만들어 하나씩 얹는다.
                    //
                    // 이름으로 먼저 찾는다. 도메인 리로드로 바인더 인스턴스가 새로 생기면
                    // 필드는 비지만 앞서 만든 자식 오브젝트는 씬에 남아 있다. 확인 없이
                    // 만들면 실행할수록 수신기가 늘어 같은 토픽을 여러 번 구독하게 된다.
                    if (tile.Receiver == null)
                    {
                        string hostName = "CamReceiver " + tile.Index;
                        Transform found = transform.Find(hostName);
                        if (found != null)
                            tile.Receiver = found.GetComponent<CamVisionReceiver>();
                        if (tile.Receiver == null)
                        {
                            var host = found != null ? found.gameObject : new GameObject(hostName);
                            host.transform.SetParent(transform, false);
                            tile.Receiver = host.AddComponent<CamVisionReceiver>();
                            tile.Receiver.Configure(GetComponent<UIDocument>(), tile.Topic, "cam-image-" + tile.Index);
                        }
                    }

                    // 토픽이 바뀌었으면 갈아탄다. 이름으로 되찾은 수신기는 이전 토픽을
                    // 물고 있을 수 있다.
                    tile.Receiver.TrySetTopic(tile.Topic);

                    // 페이지를 껐다 켜면 UIDocument 가 비주얼 트리를 새로 만든다.
                    // 수신기가 Start 에서 잡아 둔 Image 는 버려진 트리에 남으므로,
                    // 화면을 다시 세우는 이쪽에서 새 Image 를 넘긴다.
                    tile.Receiver.SetTargetImage(tile.Image);
                }

                CamTile captured = tile;
                if (tile.Chip != null) tile.Chip.clicked += () => ToggleCamTile(captured);
            }
            if (camExpandButton != null) camExpandButton.clicked += ToggleCamExpand;
        }

        void UnbindCamera()
        {
            if (camExpandButton != null) camExpandButton.clicked -= ToggleCamExpand;
        }

        void OnDisable()
        {
            UnbindCamera();
            SetMockCameras(false, false);
        }

        void ToggleCamExpand() => camExpanded = !camExpanded;

        /// <summary>
        /// 칸을 켜고 끈다. 전부 끄면 화면 절반이 빈 상자가 되므로 마지막 하나는 남긴다.
        /// </summary>
        void ToggleCamTile(CamTile tile)
        {
            if ((uiMaster == null || uiMaster.IsSimulated) && tile.Index > 2)
                return;
            if (tile.On)
            {
                int on = 0;
                foreach (CamTile t in camTiles) if (t.On) on++;
                if (on <= 1) return;
            }
            tile.On = !tile.On;
        }

        /// <summary>
        /// 켠 칸 수에 따라 1 · 2 · 4 로 나눈다. 셋이면 넷과 같은 격자를 쓰고 한 자리를
        /// 비운다 — 셋을 3등분하면 칸마다 종횡비가 달라져 같은 장면도 다르게 보인다.
        /// </summary>
        void RefreshCamera()
        {
            if (camGrid == null) return;

            bool mock = uiMaster == null || uiMaster.IsSimulated;
            SetMockCameras(
                mock && camTiles[0].On && GetMockTexture(camTiles[0]) != null,
                mock && camTiles[1].On && GetMockTexture(camTiles[1]) != null);
            camExpandButton?.EnableInClassList("chip--accent", camExpanded);
            camPanel?.EnableInClassList("run-cam-panel--expanded", camExpanded);

            int visible = 0;
            foreach (CamTile t in camTiles) if (t.On) visible++;
            float w = visible <= 1 ? 100f : 50f;
            float h = visible <= 2 ? 100f : 50f;

            double now = Time.realtimeSinceStartupAsDouble;
            int live = 0;
            foreach (CamTile tile in camTiles)
            {
                tile.Chip?.EnableInClassList("chip--accent", tile.On);
                if (tile.Root == null) continue;

                tile.Root.style.display = tile.On ? DisplayStyle.Flex : DisplayStyle.None;
                if (!tile.On) continue;

                tile.Root.style.width = Length.Percent(w);
                tile.Root.style.height = Length.Percent(h);

                if (mock)
                {
                    RenderTexture texture = GetMockTexture(tile);
                    if (tile.Image != null) tile.Image.image = texture;
                    bool assigned = texture != null;
                    if (assigned) live++;
                    if (tile.Age != null)
                    {
                        tile.Age.text = assigned ? "SIM" : "카메라 미할당";
                        tile.Age.EnableInClassList("run-cam-tile__age--late", !assigned);
                    }
                    continue;
                }

                bool received = tile.Receiver != null && tile.Receiver.HasReceivedImage;
                double age = received ? now - tile.Receiver.LastReceiveTimeSeconds : -1d;
                bool late = !received || age > CamStaleSeconds;
                if (!late) live++;

                if (tile.Age != null)
                {
                    tile.Age.text = received ? (age * 1000d).ToString("0") + " ms" : "수신 없음";
                    tile.Age.EnableInClassList("run-cam-tile__age--late", late);
                }
            }

            if (camBadge != null)
                camBadge.text = mock ? live + " / " + visible + " SIM" :
                    live + " / " + visible + " 수신 중";
        }

        RenderTexture GetMockTexture(CamTile tile)
        {
            UnityEngine.Camera camera = tile.Index == 1 ? robotCamCamera : boardCamCamera;
            if (camera == null) return null;

            RenderTexture assigned = tile.Index == 1 ? robotCamTexture : boardCamTexture;
            if (assigned != null) camera.targetTexture = assigned;
            return assigned != null ? assigned : camera.targetTexture;
        }

        void SetMockCameras(bool robotOn, bool boardOn)
        {
            if (robotCamCamera != null) robotCamCamera.enabled = robotOn;
            if (boardCamCamera != null) boardCamCamera.enabled = boardOn;
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

        }

        /// <summary>
        /// TCP 와 RPY 를 3행 2열로 짠다. 같은 포즈의 두 축이므로 나란히 두면
        /// 세로가 절반이 되고, 좌측 열의 세로 예산(Real 704px)이 그만큼 산다.
        /// 이전에는 X|Y|Z 가로 한 줄 + R|P|Y 가로 한 줄이라 98px 를 썼다.
        /// </summary>
        void BuildPoseGrid(VisualElement host)
        {
            if (host == null) return;
            host.Clear();
            string[] pos = { "X", "Y", "Z" };
            string[] rot = { "R", "P", "Y" };
            for (int i = 0; i < 3; i++)
            {
                var row = new VisualElement();
                row.AddToClassList("row");
                row.style.height = 24;
                row.Add(AxisKey(pos[i]));
                tcpValues[i] = AxisValue();
                row.Add(tcpValues[i]);
                row.Add(AxisKey(rot[i]));
                rpyValues[i] = AxisValue();
                row.Add(rpyValues[i]);
                host.Add(row);
            }
        }

        static Label AxisKey(string text)
        {
            var k = new Label(text);
            k.AddToClassList("micro");
            k.style.width = 22;
            return k;
        }

        /// <summary>
        /// 오른쪽 정렬이다. 왼쪽 정렬이면 412.8 에서 48.1 로 바뀔 때 소수점이
        /// 가로로 뛰어, 값이 아니라 자리가 움직이는 것처럼 보인다.
        /// (폰트에 tabular figures 가 없어 자릿수마다 폭이 다르다.)
        /// </summary>
        static Label AxisValue()
        {
            var v = new Label("—");
            v.style.color = new Color(0.886f, 0.925f, 0.945f);
            v.style.fontSize = 17;
            v.style.unityFontStyleAndWeight = FontStyle.Bold;
            // 계기 띠의 TCP 열은 245px 다. 키 22 + 값 95 를 두 벌 놓으면 234 로 들어간다.
            v.style.width = 95;
            v.style.unityTextAlign = TextAnchor.MiddleRight;
            return v;
        }

        void BuildJoints(VisualElement host)
        {
            if (host == null) return;
            host.Clear();
            for (int i = 0; i < JointCount; i++)
            {
                var row = new VisualElement();
                row.AddToClassList("row");
                // 24px × 6 행 = 144px. 좌측 열은 카메라 타일 위(y772)에서 끝나야 하므로
                // Real 에서 쓸 수 있는 세로가 704px 뿐이고, 관절이 그중 가장 큰 몫이다.
                row.style.height = 24;

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
            AssemblyProgressManager manager = uiMaster != null ? uiMaster.AssemblyProgress : null;
            AssemblyProgressFrame frame = manager != null ? manager.Latest : null;
            if (!EnsureSlotGroups()) return;

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
            SetTone(progressNow, frame == null || frame.State == AssemblyState.Completed ||
                frame.State == AssemblyState.Paused
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

            RefreshNow(frame);

            if (unitStep == null) return;
            if (frame == null)
            {
                unitStep.text = $"슬롯 {planTotal}개 · 대기";
                return;
            }

            unitStep.text = $"step {Mathf.Clamp(frame.StepOrder, 0, planTotal)} / {planTotal}";
        }

        /// <summary>
        /// "지금 무엇을, 어디에". 슬롯 코드가 화면에서 가장 큰 글자다 —
        /// 실패했을 때 사람이 갈 좌표이고 DB · 레시피 · 검사가 같은 값을 쓴다.
        /// 레시피 버전과 요청 ID 는 스텝 수가 어긋났을 때 되짚을 유일한 값이다.
        /// </summary>
        void RefreshNow(AssemblyProgressFrame frame)
        {
            if (nowSlot != null)
            {
                bool has = frame != null && !string.IsNullOrEmpty(frame.SlotCode);
                nowSlot.text = has ? frame.SlotCode : "—";
                // 실패한 슬롯만 색을 얻는다. 진행 중은 색을 얻지 않는다.
                SetTone(nowSlot, frame != null && frame.State == AssemblyState.Failed ? "bad" : "none");
            }
            if (nowPart != null)
                nowPart.text = frame != null && !string.IsNullOrEmpty(frame.PartId) ? frame.PartId : "";

            if (recipeVersion != null)
                FR5EmptyState.Present(recipeVersion,
                    frame != null && !string.IsNullOrEmpty(frame.RecipeVersion) ? frame.RecipeVersion : "—");
            if (requestId != null)
                FR5EmptyState.Present(requestId,
                    frame != null && !string.IsNullOrEmpty(frame.JobId) ? frame.JobId : "—");
        }

        static string Describe(AssemblyProgressFrame frame)
        {
            switch (frame.State)
            {
                case AssemblyState.Failed:
                    string reason = !string.IsNullOrEmpty(frame.ErrorCode) ? frame.ErrorCode : frame.Message;
                    return string.IsNullOrEmpty(reason) ? "실패" : "실패   ·   " + reason;
                case AssemblyState.ConveyorMoving:
                    return "컨베이어 이동 중";
                case AssemblyState.Paused:
                    return "일시정지";
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

            // 좌측 「기준」 창의 출처. 트윈이 무엇을 근거로 그려지는지 밝힌다.
            if (twinSource != null)
                twinSource.text = mock ? "SIM · joint_states" : "/nonrt_state_data";

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
            if (gripperValue != null) gripperValue.text = $"{percent:0.0} / 100 %";
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
            // 툴 오프셋 · 페이로드는 하드코딩된 상수였다. 레시피/툴 정의에서 오는 값이
            // 생기기 전까지 지어낸 숫자를 띄우지 않는다. 카메라는 RefreshCamera 가 맡는다.
        }
    }
}
