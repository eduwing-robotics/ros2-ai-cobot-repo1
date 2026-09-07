using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

namespace MainUnity.Tests.PlayMode
{
    public sealed class MockAssemblyIntegrationTests
    {
        const string ScenePath = "Assets/Scenes/SampleScene.unity";
        const string MainServerUrl = "http://127.0.0.1:8000";

        [Serializable]
        sealed class JobListResponse { public Job[] data; }

        [Serializable]
        sealed class Job
        {
            public string job_id;
            public string job_status;
        }

        [Test]
        public void JobsSelectionSeparatesPassAttemptsAndStaleActions()
        {
            var root = new GameObject("Jobs UI regression");
            root.SetActive(false);
            try
            {
                var binder = root.AddComponent(RuntimeType("MainUnity.UI.FR5RequestBinder"));
                var list = new UnityEngine.UIElements.VisualElement();
                Field(binder, "jobList").SetValue(binder, list);
                foreach (string field in new[] { "selectedStatus", "selectedName", "selectedId", "selectedProgress",
                    "selectedAttempts", "selectedResults", "selectedReason", "queryState", "jobError" })
                    Field(binder, field).SetValue(binder, new UnityEngine.UIElements.Label());
                foreach (string field in new[] { "selectedStart", "selectedCancel", "selectedInspect", "selectedMonitor" })
                    Field(binder, field).SetValue(binder, new UnityEngine.UIElements.Button());
                string Text(string field) => ((UnityEngine.UIElements.Label)Field(binder, field).GetValue(binder)).text;
                bool Enabled(string field) => ((UnityEngine.UIElements.Button)Field(binder, field).GetValue(binder)).enabledSelf;
                Invoke(binder, "BuildJobs");
                Assert.That(Text("queryState"), Does.Contain("조회 중"));
                Field(binder, "jobsLoaded").SetValue(binder, true);
                Invoke(binder, "BuildJobs");
                Assert.That(Text("queryState"), Does.Contain("작업 없음"));

                Type jobType = binder.GetType().GetNestedType("Job", BindingFlags.NonPublic);
                object job = JsonUtility.FromJson(
                    "{\"job_id\":\"test-job\",\"job_status\":\"PENDING\",\"requested_quantity\":3," +
                    "\"completed_quantity\":1,\"attempted_quantity\":5,\"inspection_failed_quantity\":2,\"failed_quantity\":1}", jobType);
                Array jobs = Array.CreateInstance(jobType, 1);
                jobs.SetValue(job, 0);
                Field(binder, "jobs").SetValue(binder, jobs);
                Field(binder, "selectedJobId").SetValue(binder, "test-job");
                Invoke(binder, "BuildJobs");
                Assert.That(Text("selectedProgress"), Is.EqualTo("1 / 3"));
                Assert.That(Text("selectedAttempts"), Is.EqualTo("5회"));
                Assert.That(Text("selectedResults"), Is.EqualTo("2건 · 1건"));
                Assert.That(list[0].ClassListContains("jobs-row--selected"), Is.True);
                Assert.That(Enabled("selectedCancel"), Is.True);
                Invoke(binder, "SetJobError", "조회 실패");
                Assert.That(Text("queryState"), Does.Contain("마지막 조회 기록"));
                Assert.That(Enabled("selectedCancel"), Is.False);
                Assert.That(Enabled("selectedStart"), Is.False);
                Assert.That(Text("selectedProgress"), Is.EqualTo("1 / 3"));
                Field(binder, "jobQueryError").SetValue(binder, null);
                Invoke(binder, "BuildJobs");
                Assert.That(Enabled("selectedCancel"), Is.True);
                foreach (string state in new[] { "RUNNING", "COMPLETED", "FAILED" })
                {
                    Field(job, "job_status").SetValue(job, state);
                    Invoke(binder, "BuildJobs");
                    Assert.That(Enabled("selectedStart"), Is.False);
                    Assert.That(Enabled("selectedCancel"), Is.False);
                }
                Invoke(binder, "SetFilter", "QUEUE");
                Assert.That(Field(binder, "selectedJobId").GetValue(binder), Is.Null);
                Assert.That(Text("selectedProgress"), Is.EqualTo("—"));
            }
            finally { UnityEngine.Object.DestroyImmediate(root); }
        }

        [UnityTest]
        public IEnumerator InspectFailureAndResultTransitionsRemainDistinct()
        {
            var root = new GameObject("Inspect regression");
            root.SetActive(false);
            try
            {
                var binder = (MonoBehaviour)root.AddComponent(RuntimeType("MainUnity.UI.FR5InspectBinder"));
                var verdict = new UnityEngine.UIElements.Label();
                var timestamp = new UnityEngine.UIElements.Label();
                var source = new UnityEngine.UIElements.Label();
                var live = new UnityEngine.UIElements.Image();
                var evidence = new UnityEngine.UIElements.Image();
                Field(binder, "verdictValue").SetValue(binder, verdict);
                Field(binder, "verdictScore").SetValue(binder, timestamp);
                Field(binder, "cameraSource").SetValue(binder, source);
                Field(binder, "liveImage").SetValue(binder, live);
                Field(binder, "evidenceImage").SetValue(binder, evidence);
                Field(binder, "mainServerBaseUrl").SetValue(binder, "http://127.0.0.1:1");
                root.SetActive(true);
                Field(binder, "cached").SetValue(binder, true);
                // 닫힌 로컬 포트로 조회 실패 경로만 검사하며 실제 서버나 설비를 호출하지 않는다.
                yield return binder.StartCoroutine((IEnumerator)Invoke(binder, "Load"));
                Assert.That(verdict.text, Is.EqualTo("조회 실패"));
                Assert.That(timestamp.text, Is.EqualTo("—"));
                Assert.That(verdict.ClassListContains("bad"), Is.True);

                Type unitType = binder.GetType().GetNestedType("Unit", BindingFlags.NonPublic);
                object unit = JsonUtility.FromJson(
                    "{\"unit_id\":1,\"unit_sequence_in_job\":1,\"unit_status\":\"COMPLETED\",\"inspection_result\":\"FAIL\",\"inspected_at\":\"invalid\"}", unitType);
                Array units = Array.CreateInstance(unitType, 1);
                units.SetValue(unit, 0);
                Invoke(binder, "ShowUnits", "review-job", units, unit);
                Assert.That(verdict.text, Is.EqualTo("FAIL"));
                Assert.That(timestamp.text, Is.EqualTo("—"));
                Assert.That(live.style.display.value, Is.EqualTo(UnityEngine.UIElements.DisplayStyle.None));
                Assert.That(source.text, Is.EqualTo("검사 기록 이미지"));

                Field(unit, "inspection_result").SetValue(unit, "PASS");
                Invoke(binder, "ShowUnits", "review-job", units, unit);
                Assert.That(verdict.text, Is.EqualTo("PASS"));
                Assert.That(verdict.ClassListContains("bad"), Is.False);
                Field(unit, "inspection_result").SetValue(unit, "PENDING");
                Field(unit, "unit_status").SetValue(unit, "FAILED");
                Invoke(binder, "ShowUnits", "review-job", units, unit);
                Assert.That(verdict.text, Is.EqualTo("검사 미완료"));
                Assert.That(verdict.ClassListContains("warn"), Is.True);
                Invoke(binder, "ShowState", "작업 없음", "현재 조회할 작업이 없습니다.", false);
                Assert.That(verdict.ClassListContains("warn"), Is.False);
                Assert.That(source.text, Is.EqualTo("현재 영상 · LIVE"));
            }
            finally { UnityEngine.Object.DestroyImmediate(root); }
        }

        [UnityTest]
        public IEnumerator UiStatusRecoveryAndSessionEventsRemainConsistent()
        {
            // alarmSinceTime의 음수는 미시작 표식이다. 시작 직후 now - 1이 음수가 되지 않게 한다.
            yield return new WaitForSecondsRealtime(1.1f);
            // 비활성 객체에서 표시 로직만 검증한다. ROS 연결과 실제 Scene의 상태는 변경하지 않는다.
            var root = new GameObject("UI status regression");
            root.SetActive(false);
            try
            {
                var status = root.AddComponent(RuntimeType("MainUnity.Runtime.Robot.Status.RobotStatusManager"));
                var shell = root.AddComponent(RuntimeType("MainUnity.UI.FR5ShellBinder"));
                var master = root.AddComponent(RuntimeType("MainUnity.UI.UIMaster"));
                var request = root.AddComponent(RuntimeType("MainUnity.UI.FR5RequestBinder"));
                var banner = new UnityEngine.UIElements.VisualElement();
                var label = new UnityEngine.UIElements.Label();
                var detail = new UnityEngine.UIElements.Label();
                var dot = new UnityEngine.UIElements.VisualElement();
                Field(shell, "statusManager").SetValue(shell, status);
                Field(shell, "alarmBanner").SetValue(shell, banner);
                Field(shell, "alarmLabel").SetValue(shell, label);
                Field(shell, "alarmDetail").SetValue(shell, detail);
                Field(shell, "linkJointDot").SetValue(shell, dot);
                var stateType = RuntimeType("MainUnity.Runtime.Robot.Status.RobotRunState");
                var errorType = RuntimeType("MainUnity.Runtime.Robot.Status.RobotErrorLabel");
                void State(string state, string error) => Invoke(status, "SetStatus",
                    Enum.Parse(stateType, state), Enum.Parse(errorType, error), "test detail");
                var frameType = RuntimeType("MainUnity.Runtime.Robot.Status.RobotStatusFrame");
                var constructor = frameType.GetConstructors(BindingFlags.Instance | BindingFlags.NonPublic).Single();
                object[] args = constructor.GetParameters().Select(parameter =>
                    parameter.ParameterType.IsValueType ? Activator.CreateInstance(parameter.ParameterType) : null).ToArray();
                args[0] = new float[6];
                object frame = constructor.Invoke(args);
                status.GetType().GetProperty("Latest").SetValue(status, frame);
                State("Disconnected", "Timeout");
                Invoke(shell, "RefreshLinks");
                Assert.That(dot.ClassListContains("dot--bad"), Is.True, "Retained frames must not imply a live link.");
                Field(shell, "alarmSinceTime").SetValue(shell, Time.realtimeSinceStartupAsDouble - 1d);
                Invoke(shell, "RefreshAlarm");
                Assert.That(label.text, Does.Contain("수신 중단"));
                State("Idle", "None");
                Field(status, "lastReceiveTimeSeconds").SetValue(status, Time.realtimeSinceStartupAsDouble);
                Invoke(shell, "RefreshAlarm");
                Assert.That(label.text, Is.EqualTo("상태 복구"));
                Assert.That(banner.ClassListContains("alarm-banner--recovered"), Is.True);
                Assert.That(detail.text, Does.Contain("수신 중단"));
                Invoke(shell, "RefreshLinks");
                Assert.That(dot.ClassListContains("dot--ok"), Is.True);

                var jobError = new UnityEngine.UIElements.Label();
                Field(request, "jobError").SetValue(request, jobError);
                Field(request, "jobActionError").SetValue(request, "작업 실행 실패");
                Field(request, "jobQueryError").SetValue(request, "조회 실패");
                Invoke(request, "RefreshJobError");
                Assert.That(jobError.text, Does.Contain("조회 실패"));
                Field(request, "jobQueryError").SetValue(request, null);
                Invoke(request, "RefreshJobError");
                Assert.That(jobError.text, Is.EqualTo("작업 실행 실패"));

                var reason = new UnityEngine.UIElements.Label();
                Field(request, "startReason").SetValue(request, reason);
                Field(request, "registrationResult").SetValue(request, "등록 응답 확인 실패");
                Invoke(request, "ApplyRegisterState", true, false, true);
                Assert.That(reason.text, Does.Contain("등록 응답 확인 실패"));
                Assert.That(reason.text, Does.Contain("재고가 부족"));

                Invoke(master, "RecordEvent", "로봇", "연결 중단", true);
                Invoke(master, "RecordEvent", "로봇", "연결 중단", true);
                var events = (IList)Field(master, "Events").GetValue(master);
                Assert.That(events.Count, Is.EqualTo(1));
                Assert.That(events[0].GetType().GetField("Item5").GetValue(events[0]), Is.EqualTo(2));
                for (int i = 0; i < 205; i++) Invoke(master, "RecordEvent", "작업", "event " + i, false);
                Assert.That(events.Count, Is.EqualTo(200));
                Invoke(master, "OnDisable");
                Assert.That(events.Count, Is.EqualTo(200), "UI deactivation must retain session history.");
            }
            finally { UnityEngine.Object.DestroyImmediate(root); }
        }

        [Test]
        public void CalibrationProgressPreservesPlacementAndReportsRecovery()
        {
            var root = new GameObject("Calibration progress regression");
            root.SetActive(false);
            var uiRoot = new GameObject("Calibration UI regression");
            uiRoot.SetActive(false);
            try
            {
                var calibration = root.AddComponent(RuntimeType("MainUnity.Runtime.Camera.TrayPartCalibrator"));
                var master = uiRoot.AddComponent(RuntimeType("MainUnity.UI.UIMaster"));
                Field(master, "observedCalibration").SetValue(master, calibration);
                Action record = () => Invoke(master, "OnCalibrationChanged");
                var changed = calibration.GetType().GetEvent("ProgressChanged", BindingFlags.Instance | BindingFlags.NonPublic);
                changed.GetAddMethod(true).Invoke(calibration, new object[] { record });
                string State() => GetProperty(calibration, "Progress").ToString();
                var receive = calibration.GetType().GetMethod("ReceiveState", BindingFlags.Instance | BindingFlags.NonPublic);
                void Receive(string json)
                {
                    var message = Activator.CreateInstance(receive.GetParameters()[0].ParameterType);
                    Field(message, "data").SetValue(message, json);
                    receive.Invoke(calibration, new[] { message });
                }
                const string preparing = "{\"schema\":\"fr5.tray.unity_state/v1\",\"valid\":false}";
                const string applied = "{\"schema\":\"fr5.tray.unity_state/v1\",\"valid\":true," +
                    "\"sequence\":7,\"registration_state\":\"TRACKING\",\"coordinate_frame\":\"base_link\"," +
                    "\"position_units\":\"mm\",\"parts\":[]}";
                Assert.That(State(), Is.EqualTo("Waiting"));
                Assert.That((double)GetProperty(calibration, "LastReceiveTime"), Is.EqualTo(-1d));
                // 동기 테스트 동안만 활성화한다. Start의 ROS 구독이 실행될 다음 프레임 전에 제거한다.
                root.SetActive(true);
                Receive(preparing);
                Assert.That(State(), Is.EqualTo("Preparing"));
                Assert.That((double)GetProperty(calibration, "LastAppliedTime"), Is.EqualTo(-1d));
                var events = (IList)Field(master, "Events").GetValue(master);
                Receive(preparing);
                Assert.That(events.Count, Is.EqualTo(1), "Repeated preparation frames must not flood the event list.");
                Receive(applied);
                Assert.That(State(), Is.EqualTo("Applied"));
                double appliedAt = (double)GetProperty(calibration, "LastAppliedTime");
                var part = new GameObject("Retained placement");
                part.transform.SetParent(root.transform);
                ((IDictionary)Field(calibration, "instancesById").GetValue(calibration)).Add("retained", part);
                Receive(applied);
                Assert.That(events.Count, Is.EqualTo(2));
                Assert.That(part != null, Is.True, "Duplicate results must not apply the placement again.");
                LogAssert.Expect(LogType.Warning, new System.Text.RegularExpressions.Regex(".*unsupported schema.*"));
                Receive("{}");
                Assert.That(State(), Is.EqualTo("Rejected"));
                Assert.That(part != null, Is.True);
                Assert.That((double)GetProperty(calibration, "LastAppliedTime"), Is.EqualTo(appliedAt));
                Assert.That(StringProperty(calibration, "ProgressDetail"), Does.Contain("이전 배치 유지"));
                Receive(preparing);
                Assert.That(State(), Is.EqualTo("Preparing"));
                Receive(applied);
                Assert.That(State(), Is.EqualTo("Applied"), "A valid duplicate after preparation must recover the display.");
                Assert.That(part != null, Is.True);
                Assert.That((double)GetProperty(calibration, "LastAppliedTime"), Is.EqualTo(appliedAt));
                Assert.That(events.Count, Is.EqualTo(5));

                var binder = uiRoot.AddComponent(RuntimeType("MainUnity.UI.FR5RunBinder"));
                var detail = new UnityEngine.UIElements.Label();
                Field(binder, "operationDetail").SetValue(binder, detail);
                Invoke(binder, "RefreshAssembly");
                Assert.That(detail.text, Does.Contain("피드백 대기"), "Missing slot geometry must not hide operation status.");
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(uiRoot);
                UnityEngine.Object.DestroyImmediate(root);
            }
        }

        [Test]
        public void SlotIdentityControlsPickupSnapAndRecovery()
        {
            // Inactive fixtures avoid lifecycle ROS connections and leave the live scene alone.
            var root = new GameObject("Slot identity test");
            root.SetActive(false);
            try
            {
                Transform Child(string name, Transform parent)
                {
                    var child = new GameObject(name).transform;
                    child.SetParent(parent, false);
                    return child;
                }
                Component Add(string name) => root.AddComponent(RuntimeType(name));
                var control = Add("MainUnity.Runtime.Robot.Mock.MockAssemblyScenarioControl");
                var robot = Add("MainUnity.Runtime.Robot.Mock.MockRobotControl");
                var manager = Add("MainUnity.Static.ItemManager");
                var status = Add("MainUnity.Runtime.Robot.Status.RobotStatusManager");
                var catcher = Child("Catcher", root.transform).gameObject.AddComponent(
                    RuntimeType("MainUnity.Runtime.Robot.Mock.SimGripperCatcher"));
                Transform board = Child("Board", root.transform);
                board.localScale = Vector3.one * 0.01f;
                Transform slot1 = Child("HBM-01", board);
                Transform slot2 = Child("HBM-02", board);
                slot1.localPosition = new Vector3(0.1f, 0, 0);
                slot2.localPosition = new Vector3(0.2f, 0, 0);
                Transform item1 = Child("Item1", root.transform);
                Transform item2 = Child("Item2", root.transform);
                item1.localPosition = new Vector3(0, 0, 0.1f);
                item2.localPosition = new Vector3(0, 0, 0.2f);

                void SetGroup(string fieldName, params (string Name, object Value)[] values)
                {
                    FieldInfo field = Field(manager, fieldName);
                    Type type = field.FieldType.GetElementType();
                    object group = Activator.CreateInstance(type);
                    foreach (var value in values)
                        Field(group, value.Name).SetValue(group, value.Value);
                    Array groups = Array.CreateInstance(type, 1);
                    groups.SetValue(group, 0);
                    field.SetValue(manager, groups);
                }
                SetGroup("assemblySlots", ("requiredItemType", "HBM"),
                    ("slots", new[] { slot2, slot1 }));
                SetGroup("itemGroups", ("itemType", "HBM"),
                    ("items", new[] { item2, item1 }));
                Field(robot, "robotBase").SetValue(robot, root.transform);
                Field(robot, "statusManager").SetValue(robot, status);
                Field(control, "control").SetValue(control, robot);
                Field(control, "itemManager").SetValue(control, manager);
                Field(control, "gripperCatcher").SetValue(control, catcher);
                Field(control, "assembledPcb").SetValue(control, board);
                Field(control, "assembledPcbAssemblyStopPoint").SetValue(control, board);
                Child("Picker", board);
                Field(manager, "motherboardPrefab").SetValue(manager, board.gameObject);
                var spawnPoint = Child("Spawn", root.transform);
                spawnPoint.SetPositionAndRotation(new Vector3(0.4972f, 0.09826766f, -0.242f), Quaternion.Euler(0, 90, 0));
                Field(manager, "spawnPoint").SetValue(manager, spawnPoint);
                Field(manager, "spawnRoot").SetValue(manager, root.transform);
                Field(manager, "completedRoot").SetValue(manager, Child("Completed", root.transform));
                object supplyGroup = ((Array)Field(manager, "itemGroups").GetValue(manager)).GetValue(0);
                Field(supplyGroup, "prefab").SetValue(supplyGroup, item1.gameObject);
                var conveyor = Add("MainUnity.Runtime.ConveyBelt.MockConveyor");
                Field(control, "conveyor").SetValue(control, conveyor);
                Field(control, "activeJobId").SetValue(control, "12345678-1234-5678-1234-567812345678");
                Field(control, "activeUnitId").SetValue(control, 1L);

                slot2.name = "HBM-01";
                Assert.That(Assert.Throws<TargetInvocationException>(() =>
                    Invoke(control, "BuildObservations", true)).InnerException,
                    Is.TypeOf<InvalidOperationException>());
                slot2.name = "HBM-02";
                Array preview = (Array)Invoke(control, "BuildObservations", true);
                Assert.That(GetProperty(manager, "CurrentBoard"), Is.Null, "Preview must not create a board.");
                Invoke(control, "ResetVisualization", false);
                board = (Transform)GetProperty(manager, "CurrentBoard");
                slot1 = board.Find("HBM-01");
                slot2 = board.Find("HBM-02");
                var runtime = (Transform[])Field(supplyGroup, "RuntimeItems").GetValue(supplyGroup);
                item1 = runtime[1];
                item2 = runtime[0];
                Array observations = (Array)Invoke(control, "BuildObservations", false);
                for (int i = 0; i < observations.Length; i++)
                    foreach (string poseName in new[] { "source", "target" })
                    {
                        var actual = Field(observations.GetValue(i), poseName).GetValue(observations.GetValue(i));
                        var expected = Field(preview.GetValue(i), poseName).GetValue(preview.GetValue(i));
                        var a = (float[])Field(actual, "xyz_mm").GetValue(actual);
                        var b = (float[])Field(expected, "xyz_mm").GetValue(expected);
                        for (int axis = 0; axis < 3; axis++)
                            Assert.That(a[axis], Is.EqualTo(b[axis]).Within(0.001f),
                                "Preview and runtime coordinates must agree to 0.001 mm.");
                    }
                Assert.That(Field(observations.GetValue(0), "slot_code").GetValue(
                    observations.GetValue(0)), Is.EqualTo("HBM-02"));
                Field(control, "lastPlacedStepOrder").SetValue(control, 0);

                object Packet(string type, string json) => JsonUtility.FromJson(json,
                    control.GetType().GetNestedType(type, BindingFlags.NonPublic));
                object feedback = Packet("AssemblyFeedback",
                    "{\"step_order\":1,\"part_id\":\"HBM\",\"slot_code\":\"HBM-01\"}");
                Invoke(control, "ApplyPicked", feedback, false);
                Assert.That(Field(control, "heldItem").GetValue(control), Is.SameAs(item1));
                Invoke(control, "ApplyPlaced", feedback, false);
                Assert.That(Vector3.Distance(item1.position, slot1.position), Is.LessThan(0.000001f));
                Assert.That(item1.parent, Is.SameAs(board));
                Assert.That(item2.parent, Is.SameAs(root.transform));

                Invoke(control, "ResetVisualization", true);
                board = (Transform)GetProperty(manager, "CurrentBoard");
                slot1 = board.Find("HBM-01");
                runtime = (Transform[])Field(supplyGroup, "RuntimeItems").GetValue(supplyGroup);
                item1 = runtime[1];
                item2 = runtime[0];
                observations = (Array)Invoke(control, "BuildObservations", false);
                object snapshot = Packet("AssemblySnapshot",
                    "{\"available\":true,\"active\":true,\"unit_id\":1," +
                    "\"job_id\":\"12345678-1234-5678-1234-567812345678\"," +
                    "\"recipe_version\":\"assembly-r1\",\"state\":\"PAUSED\"," +
                    "\"placed_count\":1,\"placed_slot_codes\":[\"HBM-01\"]," +
                    "\"expected_step_count\":2,\"held_step_order\":2," +
                    "\"held_part_id\":\"HBM\",\"held_slot_code\":\"HBM-02\"}");
                Invoke(control, "RestoreSnapshot", snapshot, observations);
                Assert.That(Vector3.Distance(item1.position, slot1.position), Is.LessThan(0.000001f));
                Assert.That(Field(control, "heldItem").GetValue(control), Is.SameAs(item2));
                Field(snapshot, "placed_slot_codes").SetValue(snapshot, new[] { "UNKNOWN" });
                Assert.That(Assert.Throws<TargetInvocationException>(() =>
                    Invoke(control, "ValidateSnapshot", snapshot, observations)).InnerException,
                    Is.TypeOf<InvalidOperationException>());

                var second = Packet("AssemblyFeedback", "{\"step_order\":2,\"part_id\":\"HBM\",\"slot_code\":\"HBM-02\"}");
                Invoke(control, "ApplyPlaced", second, false);
                Field(control, "assembledPcbDropPoint").SetValue(control, Child("Drop", root.transform));
                Invoke(control, "BuildAssembledPcbTransfer");
                Invoke(control, "ApplyAssembledPcbPicked");
                Invoke(control, "ApplyAssembledPcbPlaced");
                Assert.That(IntProperty(manager, "CompletedCount"), Is.EqualTo(1));
                Assert.That(item1.IsChildOf(board) && item2.IsChildOf(board), Is.True);
                var terminal = new System.Threading.Tasks.TaskCompletionSource<string>();
                Field(control, "terminal").SetValue(control, terminal);
                string id = "12345678-1234-5678-1234-567812345678";
                Invoke(control, "HandleFeedback", Packet("AssemblyFeedback",
                    "{\"job_id\":\"" + id + "\",\"unit_id\":1,\"state\":\"PCB_PLACED\"}"));
                Assert.That(IntProperty(manager, "CompletedCount"), Is.EqualTo(1), "Duplicate placement must retain one board.");
                Invoke(control, "HandleFeedback", Packet("AssemblyFeedback",
                    "{\"job_id\":\"" + id + "\",\"unit_id\":99,\"state\":\"FAILED\"}"));
                Assert.That(terminal.Task.IsCompleted, Is.False, "Failure from another Unit must not end this request.");
                Invoke(control, "HandleFeedback", Packet("AssemblyFeedback",
                    "{\"job_id\":\"" + id + "\",\"unit_id\":1,\"state\":\"COMPLETED\"}"));
                Assert.That(terminal.Task.IsCompletedSuccessfully, Is.True);
                Assert.That(terminal.Task.Result, Is.Empty);
                Assert.That(IntProperty(manager, "CompletedCount"), Is.EqualTo(1), "Job completion must retain the board.");
                var nextPreview = (Array)Invoke(control, "BuildObservations", true);
                Assert.That(JsonUtility.ToJson(nextPreview.GetValue(0)), Is.EqualTo(JsonUtility.ToJson(preview.GetValue(0))),
                    "Next Job coordinates must not use completed board or attached parts.");
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(root);
            }
        }

        [TestCase(false)]
        [TestCase(true)]
        public void UnitLifecycleRetainsTenBoardsUntilNextJob(bool real)
        {
            var root = new GameObject("Unit lifecycle regression");
            root.SetActive(false);
            try
            {
                Transform Child(string name, Transform parent)
                {
                    var child = new GameObject(name).transform;
                    child.SetParent(parent, false);
                    return child;
                }
                var manager = root.AddComponent(RuntimeType("MainUnity.Static.ItemManager"));
                var realControl = root.AddComponent(RuntimeType("MainUnity.Runtime.Robot.Real.RealAssemblyScenarioControl"));
                Field(realControl, "itemManager").SetValue(realControl, manager);
                var prefab = Child("Prefab", root.transform);
                Child("Picker", prefab);
                var slot = Child("HBM-01", prefab);
                var point = Child("Supply", root.transform);
                var part = Child("PartPrefab", root.transform);
                var completed = Child("Completed", root.transform);
                Field(manager, "motherboardPrefab").SetValue(manager, prefab.gameObject);
                Field(manager, "spawnPoint").SetValue(manager, Child("Spawn", root.transform));
                Field(manager, "spawnRoot").SetValue(manager, root.transform);
                Field(manager, "completedRoot").SetValue(manager, completed);
                void Group(string fieldName, params (string Name, object Value)[] values)
                {
                    var field = Field(manager, fieldName);
                    var type = field.FieldType.GetElementType();
                    var group = Activator.CreateInstance(type);
                    foreach (var value in values) Field(group, value.Name).SetValue(group, value.Value);
                    var array = Array.CreateInstance(type, 1);
                    array.SetValue(group, 0);
                    field.SetValue(manager, array);
                }
                Group("assemblySlots", ("requiredItemType", "HBM"), ("slots", new[] { slot }));
                Group("itemGroups", ("itemType", "HBM"), ("items", new[] { point }), ("prefab", part.gameObject));
                string job = Guid.NewGuid().ToString();
                object entry = real ? realControl : manager;
                var boards = new List<Transform>();
                var parts = new List<Transform>();
                for (long unit = 1; unit <= 10; unit++)
                {
                    var board = (Transform)Invoke(entry, "BeginUnit", job, unit);
                    Assert.That(Invoke(entry, "BeginUnit", job, unit), Is.SameAs(board), "Duplicate start must be idempotent.");
                    Invoke(manager, "PrepareSupply");
                    var group = ((Array)Field(manager, "itemGroups").GetValue(manager)).GetValue(0);
                    var supplied = ((Transform[])Field(group, "RuntimeItems").GetValue(group))[0];
                    supplied.SetParent(board, true);
                    boards.Add(board);
                    parts.Add(supplied);
                    Invoke(entry, "CompleteUnit", job, unit);
                    Invoke(entry, "CompleteUnit", job, unit);
                    Assert.That(IntProperty(manager, "CompletedCount"), Is.EqualTo(unit));
                    for (int i = 0; i < boards.Count; i++)
                    {
                        Assert.That(boards[i].parent, Is.SameAs(completed));
                        Assert.That(parts[i].parent, Is.SameAs(boards[i]), "Later supply must not steal completed parts.");
                    }
                }
                Assert.That(completed.childCount, Is.EqualTo(10));
                Assert.That(Assert.Throws<TargetInvocationException>(() =>
                    Invoke(entry, "BeginUnit", "invalid", 11L)).InnerException, Is.TypeOf<InvalidOperationException>());
                Assert.That(completed.childCount, Is.EqualTo(10), "Rejected Job must preserve all completed boards.");
                Invoke(entry, "BeginUnit", Guid.NewGuid().ToString(), 11L);
                Assert.That(IntProperty(manager, "CompletedCount"), Is.Zero);
                Assert.That(boards.All(board => !board.gameObject.activeSelf), Is.True,
                    "Old boards must be hidden immediately while deferred Destroy is pending.");
            }
            finally { UnityEngine.Object.DestroyImmediate(root); }
        }

        [UnityTest]
        [Category("ExternalIntegration")]
        public IEnumerator JobsUiStartRunsTheFullMockStack()
        {
            LogAssert.Expect(LogType.Error, new System.Text.RegularExpressions.Regex(
                "Concave Mesh Colliders are not supported.*finger_right_joint",
                System.Text.RegularExpressions.RegexOptions.Singleline));
            LogAssert.Expect(LogType.Error, new System.Text.RegularExpressions.Regex(
                "Concave Mesh Colliders are not supported.*finger_left_joint",
                System.Text.RegularExpressions.RegexOptions.Singleline));
            SceneManager.LoadScene(ScenePath);
            yield return null;

            Component robotMaster = FindSceneComponent(
                RuntimeType("MainUnity.Runtime.Robot.RobotMaster"), "FR5");
            SetEnumField(robotMaster, "operatingMode", 0);
            Assert.That(Invoke(robotMaster, "Initialize"), Is.EqualTo(true),
                "RobotMaster could not initialize the Mock backend.");

            Component binder = FindSceneComponent(RuntimeType("MainUnity.UI.FR5RequestBinder"));
            yield return WaitForMainServer();

            Job[] before = null;
            yield return GetJobs(value => before = value);
            var existingIds = new HashSet<string>(
                (before ?? Array.Empty<Job>()).Select(job => job.job_id));

            Invoke(binder, "OnRegister");
            Job queuedJob = null;
            double registrationDeadline = Time.realtimeSinceStartupAsDouble + 15d;
            while (queuedJob == null && Time.realtimeSinceStartupAsDouble < registrationDeadline)
            {
                Job[] current = null;
                yield return GetJobs(value => current = value);
                queuedJob = (current ?? Array.Empty<Job>()).FirstOrDefault(job =>
                    !existingIds.Contains(job.job_id) && job.job_status == "PENDING");
                if (queuedJob == null)
                    yield return new WaitForSecondsRealtime(0.25f);
            }
            Assert.That(queuedJob, Is.Not.Null, "JOBS UI did not register a PENDING Job.");

            object binderJob = null;
            double uiDeadline = Time.realtimeSinceStartupAsDouble + 3d;
            while (binderJob == null && Time.realtimeSinceStartupAsDouble < uiDeadline)
            {
                binderJob = FindBinderJob(binder, queuedJob.job_id);
                if (binderJob == null)
                    yield return null;
            }
            Assert.That(binderJob, Is.Not.Null, "Registered Job was not loaded into the JOBS UI.");
            Invoke(binder, "StartJob", binderJob);

            object progress = GetProperty(robotMaster, "AssemblyProgress");
            object scenario = GetProperty(robotMaster, "Scenario");
            bool sawThreePlacements = false;
            bool sawGhost = false;
            double assemblyDeadline = Time.realtimeSinceStartupAsDouble + 1800d;
            while (Time.realtimeSinceStartupAsDouble < assemblyDeadline)
            {
                object latest = GetProperty(progress, "Latest");
                if (latest != null && StringProperty(latest, "JobId") == queuedJob.job_id)
                {
                    sawThreePlacements |= IntProperty(latest, "PlacedCount") >= 3;
                    sawGhost |= GameObject.Find("RobotGhost/Ghost")?.activeInHierarchy == true;
                }

                if (!(bool)GetProperty(scenario, "IsRunning") && latest != null)
                    break;
                yield return null;
            }

            Assert.That(sawThreePlacements, Is.True,
                "The Mock stack did not report the first three PLACED callbacks.");
            Assert.That(sawGhost, Is.True,
                "No Mock trajectory made the shared Ghost visible.");

            Job[] after = null;
            yield return GetJobs(value => after = value);
            Job completed = (after ?? Array.Empty<Job>()).FirstOrDefault(
                job => job.job_id == queuedJob.job_id);
            Assert.That(completed, Is.Not.Null);
            Assert.That(completed.job_status, Is.EqualTo("COMPLETED"),
                "The full Unity -> MainServer -> Sequencer -> mock_sim job did not complete.");
        }

        static IEnumerator WaitForMainServer()
        {
            using var request = UnityWebRequest.Get(MainServerUrl + "/api/v1/health");
            request.timeout = 5;
            yield return request.SendWebRequest();
            if (request.result != UnityWebRequest.Result.Success)
                Assert.Ignore(
                    "MainServer is unavailable. Start: ros2 launch mock_db_mvp launch_mock.launch.py");
        }

        static IEnumerator GetJobs(Action<Job[]> receive)
        {
            using var request = UnityWebRequest.Get(MainServerUrl + "/api/v1/jobs?limit=20");
            request.timeout = 5;
            yield return request.SendWebRequest();
            Assert.That(request.result, Is.EqualTo(UnityWebRequest.Result.Success),
                "MainServer jobs request failed: " + request.error);
            receive(JsonUtility.FromJson<JobListResponse>(request.downloadHandler.text)?.data ??
                Array.Empty<Job>());
        }

        static Type RuntimeType(string name) => Type.GetType(name + ", Assembly-CSharp", true);

        static Component FindSceneComponent(Type type, string objectName = null) =>
            Resources.FindObjectsOfTypeAll(type).OfType<Component>().First(component =>
                component.gameObject.scene.IsValid() &&
                (objectName == null || component.gameObject.name == objectName));

        static void SetEnumField(object target, string name, int value)
        {
            FieldInfo field = Field(target, name);
            field.SetValue(target, Enum.ToObject(field.FieldType, value));
        }

        static object FindBinderJob(object binder, string jobId)
        {
            Array jobs = (Array)Field(binder, "jobs").GetValue(binder);
            foreach (object job in jobs)
                if ((string)Field(job, "job_id").GetValue(job) == jobId)
                    return job;
            return null;
        }

        static object Invoke(object target, string name, params object[] arguments)
        {
            MethodInfo method = target.GetType().GetMethod(name,
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            Assert.That(method, Is.Not.Null, "Missing method: " + name);
            return method.Invoke(target, arguments);
        }

        static FieldInfo Field(object target, string name)
        {
            FieldInfo field = target.GetType().GetField(name,
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            Assert.That(field, Is.Not.Null, "Missing field: " + name);
            return field;
        }

        static object GetProperty(object target, string name)
        {
            if (target == null)
                return null;
            PropertyInfo property = target.GetType().GetProperty(name,
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            Assert.That(property, Is.Not.Null, "Missing property: " + name);
            return property.GetValue(target);
        }

        static string StringProperty(object target, string name) =>
            (string)GetProperty(target, name);

        static int IntProperty(object target, string name) =>
            (int)GetProperty(target, name);
    }
}
