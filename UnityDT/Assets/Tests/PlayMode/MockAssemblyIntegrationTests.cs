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
        public void CommandsRejectStaleStateBeforeUpdateAndAcceptFreshRecovery()
        {
            var root = new GameObject("Command freshness regression");
            root.SetActive(false);
            try
            {
                var status = root.AddComponent(RuntimeType("MainUnity.Runtime.Robot.Status.RobotStatusManager"));
                var frameType = RuntimeType("MainUnity.Runtime.Robot.Status.RobotStatusFrame");
                var constructor = frameType.GetConstructors(BindingFlags.Instance | BindingFlags.NonPublic).Single();
                object[] args = constructor.GetParameters().Select(parameter =>
                    parameter.ParameterType.IsValueType ? Activator.CreateInstance(parameter.ParameterType) : null).ToArray();
                args[0] = new float[6];
                args[8] = (byte)1; // robotMotionDone: an idle frame must still expire.
                Field(status, "staleAfterSeconds").SetValue(status, 0.5f);
                object[] commandArgs = { null };
                Assert.That(Invoke(status, "CanAcceptCommand", commandArgs), Is.False);
                Assert.That(GetProperty(status, "ErrorLabel").ToString(), Is.EqualTo("Connection"));

                args[args.Length - 1] = Time.realtimeSinceStartupAsDouble;
                Invoke(status, "ApplyState", constructor.Invoke(args));
                Assert.That(Invoke(status, "CanAcceptCommand", commandArgs), Is.True);
                Field(status, "lastReceiveTimeSeconds").SetValue(status, Time.realtimeSinceStartupAsDouble - 0.6d);
                // No Update runs on this inactive object: the command boundary must reject it itself.
                Assert.That(Invoke(status, "CanAcceptCommand", commandArgs), Is.False);
                Assert.That(GetProperty(status, "ErrorLabel").ToString(), Is.EqualTo("Timeout"));
                Assert.That(commandArgs[0], Does.Contain("older than"));

                args[args.Length - 1] = Time.realtimeSinceStartupAsDouble;
                Invoke(status, "ApplyState", constructor.Invoke(args));
                Assert.That(Invoke(status, "CanAcceptCommand", commandArgs), Is.True);
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(root);
            }
        }

        [Test]
        public void UiGripperShowsFeedbackWithoutInferringGraspAndBlanksStaleValues()
        {
            var root = new GameObject("UI feedback truthfulness regression");
            root.SetActive(false);
            try
            {
                var status = root.AddComponent(RuntimeType("MainUnity.Runtime.Robot.Status.RobotStatusManager"));
                var gripper = root.AddComponent(RuntimeType("MainUnity.Runtime.Robot.Status.GripperSubscriber"));
                var constructor = RuntimeType("MainUnity.Runtime.Robot.Status.RobotStatusFrame")
                    .GetConstructors(BindingFlags.Instance | BindingFlags.NonPublic).Single();
                object[] args = constructor.GetParameters().Select(parameter =>
                    parameter.ParameterType.IsValueType ? Activator.CreateInstance(parameter.ParameterType) : null).ToArray();
                args[0] = new float[6];
                args[8] = (byte)1;
                args[11] = (byte)40;
                args[12] = true;
                foreach (string name in new[] { "FR5RunBinder", "FR5ManualBinder" })
                {
                    var binder = root.AddComponent(RuntimeType("MainUnity.UI." + name));
                    var value = new UnityEngine.UIElements.Label();
                    var state = new UnityEngine.UIElements.Label();
                    Field(binder, "statusManager").SetValue(binder, status);
                    Field(binder, "gripper").SetValue(binder, gripper);
                    Field(binder, "gripperValue").SetValue(binder, value);
                    Field(binder, "gripperText").SetValue(binder, state);
                    args[args.Length - 1] = Time.realtimeSinceStartupAsDouble;
                    var frame = constructor.Invoke(args);
                    Invoke(status, "ApplyState", frame);
                    Invoke(gripper, "ApplyState", frame);
                    Invoke(binder, "RefreshGripper");
                    Assert.That(value.text, Is.EqualTo(name == "FR5RunBinder" ? "40 %" : "40"));
                    Assert.That(state.text, Is.EqualTo("파지 미확인"));
                    Field(status, "lastReceiveTimeSeconds").SetValue(status, Time.realtimeSinceStartupAsDouble - 1d);
                    Invoke(binder, "RefreshGripper");
                    Assert.That(value.text, Is.EqualTo("—"));
                    Assert.That(state.text, Is.EqualTo("—"));
                }
            }
            finally { UnityEngine.Object.DestroyImmediate(root); }
        }

        [Test]
        public void UiProgressUsesReceivedStepCountInsteadOfSceneSlots()
        {
            var root = new GameObject("UI progress truthfulness regression");
            root.SetActive(false);
            try
            {
                var binder = root.AddComponent(RuntimeType("MainUnity.UI.FR5RunBinder"));
                var label = new UnityEngine.UIElements.Label();
                Field(binder, "progressCount").SetValue(binder, label);
                Field(binder, "planTotal").SetValue(binder, 25);
                var frameType = RuntimeType("MainUnity.Runtime.Robot.Assembly.AssemblyProgressFrame");
                var stateType = RuntimeType("MainUnity.Runtime.Robot.Assembly.AssemblyState");
                var frame = Activator.CreateInstance(frameType, "test", "recipe", Enum.Parse(stateType, "Placed"),
                    3, 10, 3, "HBM", "HBM-03", "", "", Time.realtimeSinceStartupAsDouble);
                Invoke(binder, "RefreshProgressHeader", frame, 3);
                Assert.That(label.text, Is.EqualTo("3 / 10"));
                Invoke(binder, "RefreshProgressHeader", null, 0);
                Assert.That(label.text, Is.EqualTo("진행 수량 미확인"));
            }
            finally { UnityEngine.Object.DestroyImmediate(root); }
        }

        [UnityTest]
        public IEnumerator PausedTimePreservesBudgetAndTimeoutRetainsTracking()
        {
            var root = new GameObject("Assembly timeout regression");
            root.SetActive(false);
            try
            {
                var control = root.AddComponent(RuntimeType("MainUnity.Runtime.Robot.Mock.MockAssemblyScenarioControl"));
                var scenario = root.AddComponent(RuntimeType("MainUnity.Runtime.Scenario.Scenario"));
                Invoke(scenario, "Initialize", control);
                var terminal = new System.Threading.Tasks.TaskCompletionSource<string>();
                Field(control, "terminal").SetValue(control, terminal);
                Field(control, "activeJobId").SetValue(control, "tracked-job");
                Field(control, "awaitingExecution").SetValue(control, true);
                Field(control, "completionTimeoutSeconds").SetValue(control, 0.15f);
                var clock = (System.Diagnostics.Stopwatch)Field(control, "executionClock").GetValue(control);
                Type stateType = RuntimeType("MainUnity.Runtime.Robot.Assembly.AssemblyState");
                void Report(string state) => Invoke(control, "Report", Enum.Parse(stateType, state), null, null);
                Report("Paused");
                var wait = (System.Threading.Tasks.Task)Invoke(control, "WaitForCompletionAsync", terminal.Task);
                yield return new WaitForSecondsRealtime(0.2f);
                Assert.That(wait.IsCompleted, Is.False, "Confirmed pause must not spend timeout budget.");
                Report("Started");
                yield return new WaitForSecondsRealtime(0.05f);
                Report("Paused");
                double used = clock.Elapsed.TotalSeconds;
                yield return new WaitForSecondsRealtime(0.2f);
                Assert.That(clock.Elapsed.TotalSeconds, Is.EqualTo(used).Within(0.005));
                Assert.That(wait.IsCompleted, Is.False);
                Report("Started");
                double deadline = Time.realtimeSinceStartupAsDouble + 2;
                while (!wait.IsCompleted && Time.realtimeSinceStartupAsDouble < deadline)
                    yield return null;
                Assert.That(wait.IsFaulted, Is.True);
                Assert.That(wait.Exception.InnerException, Is.TypeOf<TimeoutException>());
                // The caller releases its wait, while equipment remains active until terminal feedback.
                Field(control, "awaitingExecution").SetValue(control, false);
                Assert.That(GetProperty(scenario, "IsRunning"), Is.True);
                var retry = (System.Threading.Tasks.Task)Invoke(scenario, "Run");
                Assert.That(retry.IsFaulted, Is.True);
                Assert.That(retry.Exception.InnerException, Is.TypeOf<InvalidOperationException>());
                Invoke(control, "CompleteActive", string.Empty);
                Assert.That(GetProperty(scenario, "IsRunning"), Is.False);
                Assert.That(Field(control, "activeJobId").GetValue(control), Is.EqualTo(string.Empty));
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(root);
            }
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
                Invoke(binder, "SetFilter", "ALL");
                string response = "{\"data\":[" + JsonUtility.ToJson(job) + "]}";
                Invoke(binder, "ApplyJobsResponse", response);
                var existingRow = list[0];
                Invoke(binder, "ApplyJobsResponse", response);
                Assert.That(list[0], Is.SameAs(existingRow), "Unchanged polling must retain rendered rows.");
                Invoke(binder, "SetJobError", "조회 실패");
                Invoke(binder, "ApplyJobsResponse", response);
                Assert.That(Text("queryState"), Does.Not.Contain("실패"));
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
                Assert.That(source.text, Is.EqualTo("영상 수신 대기"));
            }
            finally { UnityEngine.Object.DestroyImmediate(root); }
        }

        [Test]
        public void QualityDistinguishesMissingInspectionsFromZeroDefects()
        {
            var root = new GameObject("Quality truthfulness regression");
            root.SetActive(false);
            try
            {
                var binder = root.AddComponent(RuntimeType("MainUnity.UI.FR5QualityBinder"));
                var visual = new UnityEngine.UIElements.VisualElement();
                var empty = new UnityEngine.UIElements.VisualElement { name = "pareto-empty" };
                visual.Add(empty);
                Field(binder, "root").SetValue(binder, visual);
                var rateType = binder.GetType().GetNestedType("SlotRate", BindingFlags.NonPublic);
                var rates = Array.CreateInstance(rateType, 1);
                var rate = JsonUtility.FromJson("{\"part_id\":\"HBM\",\"inspected_quantity\":0,\"defective_quantity\":0}", rateType);
                rates.SetValue(rate, 0);
                Field(binder, "rates").SetValue(binder, rates);
                Invoke(binder, "Rebuild");
                Assert.That(((UnityEngine.UIElements.Label)empty[0][1]).text, Does.Contain("검사 이력 없음"));
                Field(rate, "inspected_quantity").SetValue(rate, 10);
                Invoke(binder, "Rebuild");
                Assert.That(((UnityEngine.UIElements.Label)empty[0][1]).text, Does.Contain("10건 중 기록된 불량 0건"));
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
                Field(calibration, "baseLink").SetValue(calibration, root.transform);
                var binding = ((Array)Field(calibration, "prefabBindings").GetValue(calibration)).GetValue(0);
                var template = new GameObject("Calibration template");
                template.transform.SetParent(root.transform);
                Field(binding, "prefab").SetValue(binding, template);
                ((IDictionary)Field(calibration, "bindingsByType").GetValue(calibration)).Add("black_block", binding);
                const string preparing = "{\"schema\":\"fr5.tray.unity_state/v1\",\"valid\":false}";
                const string applied = "{\"schema\":\"fr5.tray.unity_state/v1\",\"valid\":true," +
                    "\"sequence\":7,\"registration_state\":\"TRACKING\",\"coordinate_frame\":\"base_link\"," +
                    "\"position_units\":\"mm\",\"parts\":[{\"id\":\"retained\",\"part_type\":\"black_block\",\"instance_index\":1,\"base_xyz_mm\":[1,2,3],\"angle_base_deg\":0}]}";
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
                var part = (GameObject)((IDictionary)Field(calibration, "instancesById").GetValue(calibration))["retained"];
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
        public void BoardCalibrationPreservesUnitOwnershipAndRejectsPartialObservations()
        {
            var root = new GameObject("Board calibration regression");
            root.SetActive(false);
            var uiRoot = new GameObject("Board calibration UI regression");
            uiRoot.SetActive(false);
            try
            {
                Transform Child(string name)
                {
                    var child = new GameObject(name).transform;
                    child.SetParent(root.transform, false);
                    return child;
                }
                var owner = root.AddComponent(RuntimeType("MainUnity.Static.ItemManager"));
                Transform prefab = Child("Board prefab");
                prefab.localScale = Vector3.one * 0.01f;
                var picker = new GameObject("Picker").transform;
                picker.SetParent(prefab, false);
                Transform[] targets = Enumerable.Range(1, 25).Select(i =>
                {
                    var slot = new GameObject("SLOT-" + i).transform;
                    slot.SetParent(prefab, false);
                    slot.localPosition = new Vector3(i, 0f, 0f);
                    return slot;
                }).ToArray();
                Type groupType = owner.GetType().GetNestedType("AssemblySlot");
                object group = Activator.CreateInstance(groupType);
                Field(group, "slots").SetValue(group, targets);
                Field(group, "requiredItemType").SetValue(group, "GPU");
                Array groups = Array.CreateInstance(groupType, 1);
                groups.SetValue(group, 0);
                Field(owner, "assemblySlots").SetValue(owner, groups);
                Field(owner, "motherboardPrefab").SetValue(owner, prefab.gameObject);
                Transform spawn = Child("Spawn");
                spawn.position = new Vector3(5f, 6f, 7f);
                Field(owner, "spawnPoint").SetValue(owner, spawn);
                Field(owner, "spawnRoot").SetValue(owner, Child("Current boards"));
                Field(owner, "completedRoot").SetValue(owner, Child("Completed boards"));
                Transform origin = Child("ROS origin");
                origin.SetPositionAndRotation(new Vector3(1f, 2f, 3f), Quaternion.Euler(0f, 30f, 0f));
                var calibration = root.AddComponent(RuntimeType("MainUnity.Runtime.Camera.BoardPartCalibrator"));
                Field(calibration, "baseLink").SetValue(calibration, origin);
                Field(calibration, "itemManager").SetValue(calibration, owner);
                Vector3 offset = new Vector3(0.01f, 0.02f, 0.03f);
                Field(calibration, "modelPositionOffsetMeters").SetValue(calibration, offset);
                Field(calibration, "modelRotationOffsetDegrees").SetValue(calibration, new Vector3(0f, -90f, 0f));
                string rows = string.Join(",", Enumerable.Range(1, 25).Select(i =>
                    "{\"slot_code\":\"SLOT-" + i + "\",\"board_position_m\":[0.1,0.2,0.3]," +
                    "\"board_orientation_xyzw\":[0,0,0,2],\"nominal_board_position_m\":[9,9,9]}"));
                string Payload(long sequence, long frame, string content = null, string publisher = "camera-a") =>
                    "{\"schema\":\"fr5.board.unity_state/v1\",\"valid\":true,\"stable\":true," +
                    "\"publisher_id\":\"" + publisher + "\",\"sequence\":" + sequence +
                    ",\"timestamp_ros_ns\":" + frame + ",\"published_ros_ns\":" + (frame + 100000000) +
                    ",\"coordinate_frame\":\"base_link\",\"position_units\":\"m\"," +
                    "\"product_code\":\"printed_semiconductor_package_board\",\"product_version\":\"assembly-r1\"," +
                    "\"calibration_id\":\"calibration-" + frame + "\",\"board_pose\":{\"position_m\":[1,2,3]," +
                    "\"orientation_xyzw\":[0,0,0.7071067811865475,0.7071067811865476]},\"slots\":[" + (content ?? rows) + "]}";
                MethodInfo receive = calibration.GetType().GetMethod("ReceiveState", BindingFlags.Instance | BindingFlags.NonPublic);
                void Receive(string json)
                {
                    object message = Activator.CreateInstance(receive.GetParameters()[0].ParameterType);
                    Field(message, "data").SetValue(message, json);
                    receive.Invoke(calibration, new[] { message });
                }
                string State() => GetProperty(calibration, "Progress").ToString();
                // Synchronous test: destroy before Start can subscribe to the live ROS network.
                root.SetActive(true);
                Receive(Payload(-1, 8000000000));
                Assert.That(State(), Is.EqualTo("Rejected"));
                Receive(Payload(0, 9000000000));
                Assert.That(State(), Is.EqualTo("Waiting"));
                Receive(Payload(1, 10000000000, rows.Replace("SLOT-25", "UNKNOWN")));
                Assert.That(State(), Is.EqualTo("Rejected"));
                Assert.That(GetProperty(owner, "ObservationBoard"), Is.Null, "Malformed observations must not create a board.");
                Assert.That(prefab.position, Is.EqualTo(Vector3.zero), "No Unit must never modify the prefab.");
                Receive(Payload(2, 11000000000));
                Assert.That(State(), Is.EqualTo("Applied"));
                Transform observed = (Transform)GetProperty(owner, "ObservationBoard");
                Assert.That(observed, Is.Not.Null);
                Assert.That(GetProperty(owner, "CurrentBoard"), Is.Null, "Observation must not fabricate a Unit.");
                Assert.That(GetProperty(owner, "JobId"), Is.Null);
                Vector3 observedPosition = observed.position;
                string jobId = Guid.NewGuid().ToString();
                Transform first = (Transform)Invoke(owner, "BeginUnit", jobId, 1L);
                Assert.That(first, Is.SameAs(observed), "Unit start must reuse the observed PCB.");
                Assert.That(Invoke(owner, "BeginUnit", jobId, 1L), Is.SameAs(first));
                Assert.That(first.parent.childCount, Is.EqualTo(1), "Repeated Unit start must not duplicate the PCB.");
                Assert.That(first.position, Is.EqualTo(observedPosition), "Unit binding must retain calibrated placement.");
                Transform firstSlot = first.Find("SLOT-1");
                Transform parent = first.parent;
                Receive(Payload(3, 12000000000));
                Assert.That(State(), Is.EqualTo("Applied"));
                Quaternion boardRotation = origin.rotation * Quaternion.Euler(0f, -90f, 0f);
                Vector3 boardPosition = origin.TransformPoint(new Vector3(-2f, 3f, 1f));
                Assert.That(Vector3.Distance(first.position, boardPosition + boardRotation * offset), Is.LessThan(1e-5f));
                Assert.That(Quaternion.Angle(first.rotation, boardRotation * Quaternion.Euler(0f, -90f, 0f)), Is.LessThan(0.01f));
                Assert.That(Vector3.Distance(firstSlot.position, boardPosition + boardRotation * new Vector3(-0.2f, 0.3f, 0.1f)), Is.LessThan(1e-5f));
                Assert.That(Quaternion.Angle(firstSlot.rotation, boardRotation), Is.LessThan(0.01f));
                Assert.That(first.localScale, Is.EqualTo(Vector3.one * 0.01f));
                Assert.That(first.parent, Is.SameAs(parent));
                Assert.That(first.childCount, Is.EqualTo(26), "Reuse the existing 25 slots; do not generate anchors.");
                object savedDisplay = Invoke(calibration, "CaptureDisplay");
                Assert.That(savedDisplay, Is.Not.Null);
                var restoredCalibration = Child("Restored board calibration").gameObject.AddComponent(calibration.GetType());
                Field(restoredCalibration, "baseLink").SetValue(restoredCalibration, origin);
                Field(restoredCalibration, "itemManager").SetValue(restoredCalibration, owner);
                Vector3 savedBoardPosition = first.position, savedSlotPosition = firstSlot.localPosition;
                first.position += Vector3.one;
                firstSlot.localPosition += Vector3.one;
                Assert.That(Invoke(restoredCalibration, "TryRestoreDisplay", savedDisplay), Is.True);
                Assert.That(Vector3.Distance(first.position, savedBoardPosition), Is.LessThan(1e-5f));
                Assert.That(firstSlot.localPosition, Is.EqualTo(savedSlotPosition));
                Assert.That((double)GetProperty(restoredCalibration, "LastAppliedTime"), Is.EqualTo(-1d));
                Assert.That(GetProperty(owner, "JobId"), Is.EqualTo(jobId));
                Field(savedDisplay, "UnitId").SetValue(savedDisplay, 2L);
                Assert.That(Invoke(restoredCalibration, "TryRestoreDisplay", savedDisplay), Is.False);
                Assert.That(GetProperty(owner, "UnitId"), Is.EqualTo(1L));
                Field(savedDisplay, "UnitId").SetValue(savedDisplay, 1L);
                var savedSlots = (IList)Field(savedDisplay, "Slots").GetValue(savedDisplay);
                savedSlots.RemoveAt(24);
                Assert.That(Invoke(restoredCalibration, "TryRestoreDisplay", savedDisplay), Is.False);
                // Avoid a second calibrator owning this board for the rest of the test.
                Field(restoredCalibration, "itemManager").SetValue(restoredCalibration, null);
                UnityEngine.Object.DestroyImmediate(restoredCalibration);
                Vector3 retainedBoard = first.position, retainedSlot = firstSlot.position;
                double appliedAt = (double)GetProperty(calibration, "LastAppliedTime");
                Receive(Payload(3, 13000000000));
                Receive(Payload(4, 12000000000));
                Assert.That((double)GetProperty(calibration, "LastAppliedTime"), Is.EqualTo(appliedAt));
                long sequence = 5;
                foreach (string invalid in new[]
                {
                    Payload(sequence++, 14000000000).Replace("[1,2,3]", "[1,2]"),
                    Payload(sequence++, 14000000000).Replace("[1,2,3]", "[1e100,2,3]"),
                    Payload(sequence++, 14000000000).Replace("[0,0,0,2]", "[0,0,0,0]"),
                    Payload(sequence++, 14000000000, rows.Replace("SLOT-25", "SLOT-1")),
                    Payload(sequence++, 14000000000, rows.Replace("SLOT-25", "UNKNOWN")),
                    Payload(sequence++, 14000000000).Replace("14100000000", "18000000000"),
                    Payload(sequence++, 14000000000).Replace("\"m\"", "\"mm\""),
                    Payload(sequence++, 14000000000).Replace("assembly-r1", "wrong-product"),
                    "{}"
                })
                {
                    Receive(invalid);
                    Assert.That(State(), Is.EqualTo("Rejected"));
                    Assert.That(first.position, Is.EqualTo(retainedBoard));
                    Assert.That(firstSlot.position, Is.EqualTo(retainedSlot));
                    Assert.That((double)GetProperty(calibration, "LastAppliedTime"), Is.EqualTo(appliedAt));
                }
                Receive(Payload(sequence++, 15000000000).Replace("\"valid\":true", "\"valid\":false"));
                Assert.That(State(), Is.EqualTo("Preparing"));
                Receive(Payload(sequence++, 16000000000));
                Assert.That(State(), Is.EqualTo("Applied"));
                Field(calibration, "<LastAppliedTime>k__BackingField").SetValue(calibration, Time.realtimeSinceStartupAsDouble - 4d);
                Invoke(calibration, "Update");
                Assert.That(State(), Is.EqualTo("Preparing"));
                Assert.That(StringProperty(calibration, "ProgressDetail"), Does.Contain("이전 배치 유지"));
                Receive(Payload(sequence++, 17000000000));
                Assert.That(State(), Is.EqualTo("Applied"));
                ((Behaviour)calibration).enabled = false;
                Receive(Payload(sequence++, 18000000000));
                Assert.That(State(), Is.EqualTo("Waiting"));
                ((Behaviour)calibration).enabled = true;
                Receive(Payload(sequence++, 19000000000));
                Assert.That(State(), Is.EqualTo("Waiting"));
                Receive(Payload(sequence++, 20000000000));
                Assert.That(State(), Is.EqualTo("Applied"));
                Receive(Payload(0, 1000000000, publisher: "camera-b"));
                Assert.That(State(), Is.EqualTo("Waiting"));
                Receive(Payload(1, 2000000000, publisher: "camera-b"));
                Assert.That(State(), Is.EqualTo("Applied"), "Publisher restart must accept new sequences and frames.");
                retainedBoard = first.position;
                retainedSlot = firstSlot.position;
                Invoke(owner, "CompleteUnit", jobId, 1L);
                Receive(Payload(2, 2500000000, publisher: "camera-b"));
                Receive(Payload(3, 2600000000, publisher: "camera-b"));
                Assert.That(GetProperty(owner, "ObservationBoard"), Is.Null);
                Assert.That(parent.childCount, Is.EqualTo(0), "Post-completion observations must not duplicate the completed PCB.");
                Assert.That(StringProperty(calibration, "ProgressDetail"), Does.Contain("다음 Unit"));
                Transform second = (Transform)Invoke(owner, "BeginUnit", jobId, 2L);
                Receive(Payload(4, 3000000000, publisher: "camera-b"));
                Assert.That(State(), Is.EqualTo("Waiting"));
                Assert.That(second.position, Is.EqualTo(spawn.position));
                Assert.That(GetProperty(calibration, "CalibrationId"), Is.Null);
                Receive(Payload(5, 3000000000, publisher: "camera-b"));
                Assert.That(second.position, Is.EqualTo(spawn.position));
                Receive(Payload(6, 4000000000, publisher: "camera-b"));
                Assert.That(State(), Is.EqualTo("Applied"));
                Assert.That(first.position, Is.EqualTo(retainedBoard), "Completed boards must remain untouched.");
                Assert.That(firstSlot.position, Is.EqualTo(retainedSlot));
                Assert.That(IntProperty(owner, "CompletedCount"), Is.EqualTo(1));
                Invoke(owner, "DiscardCurrentUnit");
                Invoke(calibration, "Update");
                Assert.That(State(), Is.EqualTo("Waiting"));
                Assert.That((double)GetProperty(calibration, "LastAppliedTime"), Is.EqualTo(-1d));
                Receive(Payload(7, 5000000000, publisher: "camera-b"));
                Receive(Payload(8, 6000000000, publisher: "camera-b"));
                Transform recoveredObservation = (Transform)GetProperty(owner, "ObservationBoard");
                Assert.That(recoveredObservation, Is.Not.Null, "Discarded Units must allow observation-only recovery.");
                Assert.That(GetProperty(owner, "CurrentBoard"), Is.Null);
                Transform smoothedSlot = recoveredObservation.Find("SLOT-1");
                Vector3 startPosition = recoveredObservation.position;
                Vector3 startSlotPosition = smoothedSlot.position;
                Vector3 movement = origin.TransformVector(Vector3.forward);
                Receive(Payload(9, 7000000000, publisher: "camera-b").Replace("[1,2,3]", "[2,2,3]"));
                Assert.That(recoveredObservation.position, Is.EqualTo(startPosition), "New observations update the target without snapping the display.");
                double targetReceivedAt = (double)GetProperty(calibration, "LastAppliedTime");
                float halfTimeStep = 1f - Mathf.Exp(-0.1f / 0.2f);
                Invoke(calibration, "ApplyDisplayPose", halfTimeStep);
                Invoke(calibration, "ApplyDisplayPose", halfTimeStep);
                float fraction = 1f - Mathf.Exp(-1f);
                Assert.That(Vector3.Distance(recoveredObservation.position, startPosition + movement * fraction), Is.LessThan(1e-5f));
                Assert.That(Vector3.Distance(smoothedSlot.position, startSlotPosition + movement * fraction), Is.LessThan(1e-5f));
                Assert.That((double)GetProperty(calibration, "LastAppliedTime"), Is.EqualTo(targetReceivedAt), "Rendering must not refresh observation age.");
                Invoke(calibration, "ApplyDisplayPose", 1f);
                Quaternion startRotation = recoveredObservation.rotation;
                Receive(Payload(10, 8000000000, publisher: "camera-b")
                    .Replace("[1,2,3]", "[2,2,3]")
                    .Replace("[0,0,0.7071067811865475,0.7071067811865476]", "[0,0,0,1]"));
                Assert.That(Quaternion.Angle(recoveredObservation.rotation, startRotation), Is.LessThan(0.001f));
                Invoke(calibration, "ApplyDisplayPose", 0.5f);
                Quaternion modelCorrection = Quaternion.Euler(0f, -90f, 0f);
                Quaternion expectedRotation = Quaternion.Slerp(startRotation, origin.rotation * modelCorrection, 0.5f);
                Assert.That(Quaternion.Angle(recoveredObservation.rotation, expectedRotation), Is.LessThan(0.01f));
                Quaternion displayedOrigin = recoveredObservation.rotation * Quaternion.Inverse(modelCorrection);
                Vector3 expectedSlot = recoveredObservation.position + displayedOrigin * (new Vector3(-0.2f, 0.3f, 0.1f) - offset);
                Assert.That(Vector3.Distance(smoothedSlot.position, expectedSlot), Is.LessThan(1e-5f), "Rotating PCB and slots must share the same displayed coordinate frame.");
                Assert.That(Quaternion.Angle(smoothedSlot.rotation, displayedOrigin), Is.LessThan(0.01f));
                Vector3 frozen = recoveredObservation.position;
                Quaternion frozenRotation = recoveredObservation.rotation;
                Receive(Payload(11, 9000000000, publisher: "camera-b").Replace("\"valid\":true", "\"valid\":false"));
                Invoke(calibration, "Update");
                Assert.That(recoveredObservation.position, Is.EqualTo(frozen));
                Assert.That(recoveredObservation.rotation, Is.EqualTo(frozenRotation), "Invalid observations must freeze pending interpolation.");
                Receive(Payload(12, 10000000000, publisher: "camera-b"));
                Field(calibration, "<LastAppliedTime>k__BackingField").SetValue(calibration, Time.realtimeSinceStartupAsDouble - 4d);
                Invoke(calibration, "Update");
                Assert.That(recoveredObservation.position, Is.EqualTo(frozen));
                Assert.That(recoveredObservation.rotation, Is.EqualTo(frozenRotation), "Stale input must freeze the last displayed pose.");
                ((Behaviour)calibration).enabled = false;
                Assert.That(recoveredObservation.gameObject.activeSelf, Is.False, "Mode changes must not leave an orphan preview.");
                Assert.That(GetProperty(owner, "ObservationBoard"), Is.Null);

                var master = uiRoot.AddComponent(RuntimeType("MainUnity.UI.UIMaster"));
                Field(master, "observedBoardCalibration").SetValue(master, calibration);
                Invoke(master, "OnBoardCalibrationChanged");
                Assert.That(((IList)Field(master, "Events").GetValue(master)).Count, Is.EqualTo(1));
                var binder = uiRoot.AddComponent(RuntimeType("MainUnity.UI.FR5RunBinder"));
                foreach (string field in new[] { "calibrationState", "calibrationDetail", "calibrationAge" })
                    Field(binder, field).SetValue(binder, new UnityEngine.UIElements.Label());
                Invoke(binder, "RefreshCalibration");
                Assert.That(((UnityEngine.UIElements.Label)Field(binder, "calibrationState").GetValue(binder)).text, Does.Contain("기판"));
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

                // Domain reload loses the nonserialized supply array while
                // its scene objects survive. Recovery must not duplicate them.
                Transform orphanedSupply = item2;
                Field(supplyGroup, "RuntimeItems").SetValue(supplyGroup, null);
                Invoke(control, "ResetVisualization", true);
                Assert.That(orphanedSupply.gameObject.activeSelf, Is.False,
                    "Recovery must remove existing supply even after runtime references are lost.");
                Assert.That(root.transform.Cast<Transform>().Count(t =>
                    t.name == "HBM" && t.gameObject.activeSelf), Is.EqualTo(2));
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

        [UnityTest]
        public IEnumerator RealMoveDoesNotSendAfterTimeoutOrStatusFailure()
        {
            var rosType = AppDomain.CurrentDomain.GetAssemblies()
                .Select(assembly => assembly.GetType("Unity.Robotics.ROSTCPConnector.ROSConnection"))
                .First(type => type != null);
            var singleton = rosType.GetField("_instance", BindingFlags.Static | BindingFlags.NonPublic);
            object previousConnection = singleton.GetValue(null);
            foreach (string outcome in new[] { "timeout", "status", "success" })
            {
                var root = new GameObject("Real move regression " + outcome);
                root.SetActive(false);
                try
                {
                    // 비활성 연결은 소켓을 열지 않는다. 응답은 이 테스트의 대기 요청에만 주입한다.
                    var ros = root.AddComponent(rosType);
                    singleton.SetValue(null, ros);
                    const string service = "/test/real_move";
                    rosType.GetMethod("RegisterRosService", new[] {
                        typeof(string), typeof(string), typeof(string), typeof(int?)
                    }).Invoke(ros, new object[] {
                        service, "fairino_msgs/RemoteCmdInterface", "fairino_msgs/RemoteCmdInterface", null
                    });
                    var control = root.AddComponent(RuntimeType("MainUnity.Runtime.Robot.Real.RealRobotControl"));
                    var status = root.AddComponent(RuntimeType("MainUnity.Runtime.Robot.Status.RobotStatusManager"));
                    Field(control, "statusManager").SetValue(control, status);
                    Field(control, "serviceName").SetValue(control, service);
                    Field(control, "completionTimeoutSeconds").SetValue(control, outcome == "timeout" ? 0.1f : 5f);
                    void State(string state, string error) => Invoke(status, "SetStatus",
                        Enum.Parse(RuntimeType("MainUnity.Runtime.Robot.Status.RobotRunState"), state),
                        Enum.Parse(RuntimeType("MainUnity.Runtime.Robot.Status.RobotErrorLabel"), error), "test status");
                    State("Idle", "None");
                    int firstServiceId = (int)Field(ros, "m_NextSrvID").GetValue(ros);
                    var waiting = (IDictionary)Field(ros, "m_ServicesWaiting").GetValue(ros);
                    void Reply()
                    {
                        Assert.That(waiting.Count, Is.EqualTo(1));
                        object id = waiting.Keys.Cast<object>().Single();
                        object pauser = waiting[id];
                        waiting.Remove(id);
                        object response = Activator.CreateInstance(RuntimeType("RosMessageTypes.Fairino.RemoteCmdInterfaceResponse"));
                        Field(response, "cmd_res").SetValue(response, "0");
                        object serializer = Field(ros, "m_MessageSerializer").GetValue(ros);
                        Invoke(serializer, "Clear");
                        Invoke(serializer, "SerializeMessage", response);
                        Invoke(pauser, "Resume", Invoke(serializer, "GetBytes"));
                    }
                    var request = (System.Threading.Tasks.Task)Invoke(control, "RequestMoveAsync",
                        true, Vector3.zero, Vector3.zero);
                    Assert.That(waiting.Count, Is.EqualTo(1), "CARTPoint must precede MoveJ.");
                    if (outcome == "status") State("Error", "EmergencyStop");
                    if (outcome != "success")
                    {
                        float deadline = Time.realtimeSinceStartup + 2f;
                        while (!request.IsCompleted && Time.realtimeSinceStartup < deadline) yield return null;
                        Assert.That(request.IsFaulted, Is.True);
                        Assert.That(request.Exception.InnerException, outcome == "timeout"
                            ? Is.TypeOf<TimeoutException>() : Is.TypeOf<InvalidOperationException>());
                        Assert.That(Field(control, "requestInFlight").GetValue(control), Is.False);
                        State("Idle", "None");
                        Reply();
                        yield return new WaitForSecondsRealtime(0.1f);
                        Assert.That(Field(ros, "m_NextSrvID").GetValue(ros), Is.EqualTo(firstServiceId + 1),
                            "Late CARTPoint success must not send MoveJ, even after status recovery.");
                        Assert.That(waiting.Count, Is.Zero);
                    }
                    else
                    {
                        Reply();
                        float deadline = Time.realtimeSinceStartup + 2f;
                        while (waiting.Count == 0 && Time.realtimeSinceStartup < deadline) yield return null;
                        Assert.That(Field(ros, "m_NextSrvID").GetValue(ros), Is.EqualTo(firstServiceId + 2));
                        Reply();
                        yield return null;
                        Assert.That(request.IsCompleted, Is.False, "Acceptance alone is not motion completion.");
                        State("Running", "None");
                        State("Idle", "None");
                        while (!request.IsCompleted && Time.realtimeSinceStartup < deadline) yield return null;
                        Assert.That(request.IsCompletedSuccessfully, Is.True);
                    }
                }
                finally
                {
                    singleton.SetValue(null, previousConnection);
                    UnityEngine.Object.DestroyImmediate(root);
                }
            }
        }

#if UNITY_EDITOR
        [TestCase("sk_hynix 1")]
        [TestCase("cap_small")]
        [TestCase("yellowBar")]
        [TestCase("cap_Big")]
        [TestCase("nvidia")]
        [TestCase("BlackBox")]
        public void GripperSnapCentersImportedGeometryAndPreservesScale(string prefabName)
        {
            var root = new GameObject("Offline snap geometry");
            root.SetActive(false);
            try
            {
                var receiver = root.AddComponent(RuntimeType("MainUnity.Runtime.Camera.TrayPartCalibrator"));
                var tcp = new GameObject("Scaled TCP").transform;
                tcp.SetParent(root.transform, false);
                tcp.localScale = Vector3.one * 0.005f;
                tcp.SetPositionAndRotation(new Vector3(0.3f, 0.4f, -0.5f), Quaternion.Euler(8f, 70f, 175f));
                Field(receiver, "measuredGripper").SetValue(receiver, tcp);
                var prefab = UnityEditor.AssetDatabase.LoadAssetAtPath<GameObject>("Assets/prefab/" + prefabName + ".prefab");
                Assert.That(prefab, Is.Not.Null);
                var part = UnityEngine.Object.Instantiate(prefab, root.transform).transform;
                part.rotation = tcp.rotation * Quaternion.Euler(173f, 86f, 3f);
                Vector3 scale = part.lossyScale;
                Invoke(receiver, "SnapToGripper", part);
                var renderers = part.GetComponentsInChildren<Renderer>();
                Bounds bounds = renderers[0].bounds;
                foreach (var renderer in renderers.Skip(1)) bounds.Encapsulate(renderer.bounds);
                Assert.That(Vector3.Distance(bounds.center, tcp.position), Is.LessThan(1e-5f));
                Assert.That(Vector3.Distance(part.lossyScale, scale), Is.LessThan(1e-5f));
                Assert.That(Quaternion.Angle(part.localRotation, Quaternion.Euler(180f, 90f, 0f)), Is.LessThan(0.05f));
            }
            finally { UnityEngine.Object.DestroyImmediate(root); }
        }
#endif


        // Recorded VRM-01 events from 2026-09-10; adversarial variants below are synthetic.
        [TestCase("normal")]
        [TestCase("ambiguous")]
        [TestCase("unverified")]
        [TestCase("wrong_observation")]
        [TestCase("release_first")]
        [TestCase("other_place")]
        [TestCase("reverse_phase")]
        [TestCase("stale_snapshot")]
        [TestCase("plain_failure")]
        [TestCase("rejected_request")]
        [TestCase("observation_dropout")]
        [TestCase("restore_placed")]
        [TestCase("restore_held")]
        [TestCase("restore_released")]
        [TestCase("restore_corrupt")]
        [TestCase("restore_tray")]
        [TestCase("restore_server_changed")]
        [TestCase("restore_recovery_required")]
        [TestCase("candidate_registration")]
        [TestCase("candidate_restored")]
        [TestCase("candidate_missing")]
        [TestCase("candidate_evicted")]
        [TestCase("candidate_late")]
        [TestCase("candidate_other_execution")]
        [TestCase("candidate_repeated")]
        [TestCase("candidate_part_limit")]
        public void IdleRobotCallbacksPreserveIdentityAndNeverRequireProduction(string variant)
        {
            Transform Child(string name, Transform parent)
            {
                var child = new GameObject(name).transform;
                child.SetParent(parent);
                return child;
            }
            var root = new GameObject("Offline callback replay");
            root.SetActive(false);
            try
            {
                var calibration = root.AddComponent(RuntimeType("MainUnity.Runtime.Camera.TrayPartCalibrator"));
                var boardCalibration = root.AddComponent(RuntimeType("MainUnity.Runtime.Camera.BoardPartCalibrator"));
                Transform gripper = Child("Measured gripper", root.transform);
                Transform board = Child("Observed board", root.transform);
                Child("VRM-01", board);
                Field(boardCalibration, "currentBoard").SetValue(boardCalibration, board);
                Field(boardCalibration, "<LastAppliedTime>k__BackingField").SetValue(boardCalibration, 1d);
                Component boardOwner = null;
                if (variant == "restore_placed")
                {
                    boardOwner = Child("Board owner", root.transform).gameObject.AddComponent(RuntimeType("MainUnity.Static.ItemManager"));
                    Child("Picker", board);
                    var targets = new List<Transform> { board.Find("VRM-01") };
                    for (int i = 2; i <= 25; i++) targets.Add(Child("SLOT-" + i, board));
                    Type groupType = boardOwner.GetType().GetNestedType("AssemblySlot");
                    object group = Activator.CreateInstance(groupType);
                    Field(group, "slots").SetValue(group, targets.ToArray());
                    Field(group, "requiredItemType").SetValue(group, "VRM");
                    Array groups = Array.CreateInstance(groupType, 1);
                    groups.SetValue(group, 0);
                    Field(boardOwner, "assemblySlots").SetValue(boardOwner, groups);
                    var boardPrefab = UnityEngine.Object.Instantiate(board.gameObject, root.transform);
                    Field(boardOwner, "motherboardPrefab").SetValue(boardOwner, boardPrefab);
                    Field(group, "slots").SetValue(group, targets.Select(slot => boardPrefab.transform.Find(slot.name)).ToArray());
                    Field(boardOwner, "spawnPoint").SetValue(boardOwner, root.transform);
                    Field(boardOwner, "spawnRoot").SetValue(boardOwner, root.transform);
                    Field(boardOwner, "completedRoot").SetValue(boardOwner, Child("Completed", root.transform));
                    Field(boardOwner, "observedBoard").SetValue(boardOwner, board);
                    Field(boardCalibration, "baseLink").SetValue(boardCalibration, root.transform);
                    Field(boardCalibration, "itemManager").SetValue(boardCalibration, boardOwner);
                    Field(boardCalibration, "<DisplayId>k__BackingField").SetValue(boardCalibration, Guid.NewGuid().ToString());
                    root.SetActive(true);
                }
                Invoke(calibration, "InitializeAttachments", gripper, boardCalibration);
                var part = GameObject.CreatePrimitive(PrimitiveType.Cube);
                part.name = "Recorded source";
                gripper.localScale = Vector3.one * 0.005f;
                part.transform.SetParent(root.transform);
                part.transform.position = new Vector3(1f, 2f, 3f);
                string source = "black_block:8881a668-32d6-436e-8a04-6beefd4d74eb";
                string registration = "022111f9-b745-4d62-ab14-70bb7a6b8b71:5";
                string observation = "022111f9-b745-4d62-ab14-70bb7a6b8b71:5:1789014788812035400";
                ((IDictionary)Field(calibration, "instancesById").GetValue(calibration)).Add(source, part);
                ((IDictionary)Field(calibration, "instanceRegistrations").GetValue(calibration)).Add(source, registration);
                ((IDictionary)Field(calibration, "instanceTypes").GetValue(calibration)).Add(source, "black_block");
                Field(calibration, "registration").SetValue(calibration, registration);
                ((HashSet<(string, string, string)>)Field(calibration, "observations").GetValue(calibration)).Add((registration, observation, source));
                // Supply a validated, exact observation for the initial Pick. Later
                // assertions exercise the live ReceiveState path and bounded history.
                var sourceBinding = ((Array)Field(calibration, "prefabBindings").GetValue(calibration)).GetValue(0);
                Field(sourceBinding, "prefab").SetValue(sourceBinding, part);
                var poseType = calibration.GetType().GetNestedType("PartPose", BindingFlags.NonPublic);
                object originalPose = Activator.CreateInstance(poseType);
                Field(originalPose, "Id").SetValue(originalPose, source);
                Field(originalPose, "Binding").SetValue(originalPose, sourceBinding);
                Field(originalPose, "Position").SetValue(originalPose, part.transform.position);
                Field(originalPose, "Rotation").SetValue(originalPose, Quaternion.identity);
                var candidatePoses = (IList)Activator.CreateInstance(typeof(List<>).MakeGenericType(poseType));
                candidatePoses.Add(originalPose);
                ((IDictionary)Field(calibration, "candidates").GetValue(calibration)).Add((registration, observation), candidatePoses);
                ((Queue<(string, string)>)Field(calibration, "candidateOrder").GetValue(calibration)).Enqueue((registration, observation));
                Field(calibration, "candidatePartCount").SetValue(calibration, 1);
                string start = @"{""job_id"":""0bf5780c-d6bf-4d01-b949-1365c6614164"",""operation_id"":""96488522-5d89-4b70-a046-44db144ea3f3"",""action"":""robot.pick"",""phase"":""01_pre_pick_safe_vertical"",""event"":""PHASE_STARTED"",""error_code"":"""",""message"":""{\""source_id\"": \""black_block:8881a668-32d6-436e-8a04-6beefd4d74eb\"", \""tray_registration_id\"": \""022111f9-b745-4d62-ab14-70bb7a6b8b71:5\"", \""source_observation_id\"": \""022111f9-b745-4d62-ab14-70bb7a6b8b71:5:1789014788812035400\"", \""source_cycle_id\"": \""20260910-133247\"", \""plan_sha256\"": \""bb9ca7b86cbf41ef1a4575f4070b0cf41d4421b9544aa53613ab593bbd4e5340\"", \""schema\"": \""fr5.robot_event_context/v1\"", \""part_id\"": \""VRM\"", \""source_index\"": 1, \""slot_code\"": \""VRM-01\"", \""order\"": 14, \""attachment_binding_valid\"": true, \""server_instance_id\"": \""7184ba72-ca00-4b70-bbc0-7d35bfc9bb1f\"", \""event_sequence\"": 592}""}";
                string grasp = @"{""job_id"":""0bf5780c-d6bf-4d01-b949-1365c6614164"",""operation_id"":""96488522-5d89-4b70-a046-44db144ea3f3"",""action"":""robot.pick"",""phase"":""GRASP"",""event"":""PHASE_COMPLETED"",""error_code"":"""",""message"":""{\""source_id\"": \""black_block:8881a668-32d6-436e-8a04-6beefd4d74eb\"", \""tray_registration_id\"": \""022111f9-b745-4d62-ab14-70bb7a6b8b71:5\"", \""source_observation_id\"": \""022111f9-b745-4d62-ab14-70bb7a6b8b71:5:1789014788812035400\"", \""source_cycle_id\"": \""20260910-133247\"", \""plan_sha256\"": \""bb9ca7b86cbf41ef1a4575f4070b0cf41d4421b9544aa53613ab593bbd4e5340\"", \""schema\"": \""fr5.robot_event_context/v1\"", \""part_id\"": \""VRM\"", \""source_index\"": 1, \""slot_code\"": \""VRM-01\"", \""order\"": 14, \""attachment_binding_valid\"": true, \""feedback\"": {\""phase\"": \""GRASP\"", \""target_position\"": 24.0, \""actual_position\"": 24.0, \""grip_motion_done\"": 1, \""gripper_feedback_valid\"": true, \""robot_motion_done\"": 1, \""gripperfaultnum\"": 0, \""grippererro\"": 0, \""state_sequence\"": 90089, \""observed_unix\"": 1789015307.7152622, \""controller_object_detected\"": true, \""physical_holding_verified\"": false, \""continuous_feedback_verified\"": true}, \""server_instance_id\"": \""7184ba72-ca00-4b70-bbc0-7d35bfc9bb1f\"", \""event_sequence\"": 605}""}";
                string release = @"{""job_id"":""0bf5780c-d6bf-4d01-b949-1365c6614164"",""operation_id"":""ec91a09c-0f2c-4e1c-b733-9f6c19952398"",""action"":""robot.place"",""phase"":""RELEASE"",""event"":""PHASE_COMPLETED"",""error_code"":"""",""message"":""{\""source_id\"": \""black_block:8881a668-32d6-436e-8a04-6beefd4d74eb\"", \""tray_registration_id\"": \""022111f9-b745-4d62-ab14-70bb7a6b8b71:5\"", \""source_observation_id\"": \""022111f9-b745-4d62-ab14-70bb7a6b8b71:5:1789014788812035400\"", \""source_cycle_id\"": \""20260910-133247\"", \""plan_sha256\"": \""bb9ca7b86cbf41ef1a4575f4070b0cf41d4421b9544aa53613ab593bbd4e5340\"", \""schema\"": \""fr5.robot_event_context/v1\"", \""part_id\"": \""VRM\"", \""source_index\"": 1, \""slot_code\"": \""VRM-01\"", \""order\"": 14, \""attachment_binding_valid\"": true, \""feedback\"": {\""phase\"": \""RELEASE\"", \""target_position\"": 28.0, \""actual_position\"": 28.0, \""grip_motion_done\"": 1, \""gripper_feedback_valid\"": true, \""robot_motion_done\"": 1, \""gripperfaultnum\"": 0, \""grippererro\"": 0, \""state_sequence\"": 92284, \""observed_unix\"": 1789015329.6652358, \""controller_object_detected\"": true, \""physical_holding_verified\"": false, \""continuous_feedback_verified\"": true}, \""server_instance_id\"": \""7184ba72-ca00-4b70-bbc0-7d35bfc9bb1f\"", \""event_sequence\"": 629}""}";
                void Receive(string data) => Invoke(calibration, "ProcessRobotEvent", data);
                if (variant == "release_first")
                {
                    Receive(release);
                    Assert.That(part.transform.parent, Is.EqualTo(root.transform));
                    Assert.That(StringProperty(calibration, "RobotDetail"), Does.Contain("미확인"));
                    return;
                }
                if (variant == "wrong_observation")
                {
                    Receive(start.Replace(observation, "unknown-observation"));
                    Receive(grasp);
                    Assert.That(part.transform.parent, Is.EqualTo(root.transform));
                    return;
                }
                if (variant == "observation_dropout" || variant.StartsWith("candidate_", StringComparison.Ordinal))
                {
                    Field(calibration, "baseLink").SetValue(calibration, root.transform);
                    var binding = ((Array)Field(calibration, "prefabBindings").GetValue(calibration)).GetValue(0);
                    Field(binding, "prefab").SetValue(binding, part);
                    ((IDictionary)Field(calibration, "bindingsByType").GetValue(calibration)).Add("black_block", binding);
                    var method = calibration.GetType().GetMethod("ReceiveState", BindingFlags.Instance | BindingFlags.NonPublic);
                    void Tray(int sequence, string reg, string obs, string parts)
                    {
                        var message = Activator.CreateInstance(method.GetParameters()[0].ParameterType);
                        string json = "{\"schema\":\"fr5.tray.unity_state/v1\",\"valid\":true,\"sequence\":" + sequence +
                            ",\"registration_state\":\"TRACKING\",\"coordinate_frame\":\"base_link\",\"position_units\":\"mm\",\"tray_registration_id\":\"" + reg +
                            "\",\"source_observation_id\":\"" + obs + "\",\"parts\":" + parts + "}";
                        Field(message, "data").SetValue(message, json);
                        method.Invoke(calibration, new[] { message });
                    }
                    root.SetActive(true); // Synchronous test ends before Start/ROS subscription.
                    string observed = "[{\"id\":\"" + source + "\",\"part_type\":\"black_block\",\"instance_index\":1,\"base_xyz_mm\":[1000,2000,3000],\"angle_base_deg\":0}]";
                    if (variant.StartsWith("candidate_", StringComparison.Ordinal))
                    {
                        ((IDictionary)Field(calibration, "candidates").GetValue(calibration)).Clear();
                        ((Queue<(string, string)>)Field(calibration, "candidateOrder").GetValue(calibration)).Clear();
                        Field(calibration, "candidatePartCount").SetValue(calibration, 0);
                        Field(calibration, "registration").SetValue(calibration, registration + ":old");
                        ((IDictionary)Field(calibration, "instanceRegistrations").GetValue(calibration))[source] = registration + ":old";
                        ((HashSet<(string, string, string)>)Field(calibration, "observations").GetValue(calibration)).Clear();
                        if (variant == "candidate_restored") Field(calibration, "hasUnverifiedRestoredLayout").SetValue(calibration, true);
                        // FLU (3,-1,2)m maps to the existing world pose (1,2,3)m.
                        string executionPose = observed.Replace("1000,2000,3000", "3000,-1000,2000");
                        if (variant != "candidate_missing") Tray(1, registration, observation, executionPose);
                        if (variant == "candidate_repeated")
                            Tray(2, registration, observation, executionPose.Replace("3000", "9000"));
                        int frames = variant == "candidate_evicted" ? 1024 : variant == "candidate_part_limit" ? 950 : 1;
                        string newerParts = observed.Replace("1000", "9000");
                        if (variant == "candidate_part_limit")
                            newerParts = "[" + string.Join(",", Enumerable.Range(0, 35).Select(index =>
                                newerParts.Trim('[', ']').Replace(source, source + ":" + index))) + "]";
                        for (int i = 0; i < frames; i++)
                            Tray(i + 3, registration + ":new", "new-observation-" + i, newerParts);
                        Assert.That(((IDictionary)Field(calibration, "candidates").GetValue(calibration)).Count, Is.LessThanOrEqualTo(1024));
                        Assert.That((int)Field(calibration, "candidatePartCount").GetValue(calibration), Is.LessThanOrEqualTo(32768));
                        part.transform.position = Vector3.zero;
                        if (variant == "candidate_late")
                        {
                            Receive(grasp);
                            Receive(start.Replace("01_pre_pick_safe_vertical", "06_post_grasp_lift_50mm_vertical"));
                            Assert.That(part.transform.position, Is.EqualTo(Vector3.zero));
                            Assert.That(((IDictionary)Field(calibration, "attachments").GetValue(calibration)).Count, Is.Zero);
                            return;
                        }
                        Receive(start);
                        if (variant is "candidate_missing" or "candidate_evicted" or "candidate_part_limit")
                        {
                            Receive(grasp);
                            Assert.That(part.transform.parent, Is.EqualTo(root.transform));
                            Assert.That(part.transform.position, Is.EqualTo(Vector3.zero));
                            Assert.That(((IDictionary)Field(calibration, "attachments").GetValue(calibration)).Count, Is.Zero);
                            return;
                        }
                        Assert.That(Vector3.Distance(part.transform.position, new Vector3(1f, 2f, 3f)), Is.LessThan(0.00001f), "Use the execution observation, never the newest detection.");
                        Assert.That(Field(calibration, "registration").GetValue(calibration), Is.EqualTo(registration));
                        Assert.That((bool)Field(calibration, "hasUnverifiedRestoredLayout").GetValue(calibration), Is.False);
                        Receive(start);
                        Assert.That(((IDictionary)Field(calibration, "attachments").GetValue(calibration)).Count, Is.EqualTo(1));
                        if (variant == "candidate_other_execution")
                        {
                            string other = start.Replace("0bf5780c-d6bf-4d01-b949-1365c6614164", "11111111-1111-4111-8111-111111111111").Replace(source, "other-source");
                            Receive(other);
                            Assert.That(StringProperty(calibration, "RobotDetail"), Does.Contain("다른 실행"));
                            Assert.That(Vector3.Distance(part.transform.position, new Vector3(1f, 2f, 3f)), Is.LessThan(0.00001f));
                            Assert.That(((IDictionary)Field(calibration, "attachments").GetValue(calibration)).Count, Is.EqualTo(1));
                            return;
                        }
                    }
                    else
                    {
                        Tray(1, registration, observation, observed);
                        Vector3 original = part.transform.position;
                        Tray(2, registration, observation + ":empty", "[]");
                        Assert.That(part.activeSelf, Is.True, "valid TRACKING with zero detections is not removal.");
                        Assert.That(StringProperty(calibration, "ProgressDetail"), Does.Contain("이전 배치 유지"));
                        Tray(3, registration, observation + ":partial", observed.Replace(source, "other-source"));
                        Assert.That(part.activeSelf, Is.True, "Partial observation must preserve absent source.");
                        Tray(4, registration + ":new", "new-observation", observed.Replace("1000", "9000"));
                        Assert.That(part.transform.position, Is.EqualTo(original));
                        Assert.That(Field(calibration, "registration").GetValue(calibration), Is.EqualTo(registration));
                        Assert.That(StringProperty(calibration, "ProgressDetail"), Does.Contain("등록 세대 변경"));
                        // The original execution's recorded frame is still accepted after newer detector frames.
                        part.transform.position = new Vector3(1f, 2f, 3f);
                    }
                }
                Receive(start);
                // Detection updates must not delete a reserved or held source.
                var apply = calibration.GetType().GetMethod("Apply", BindingFlags.Instance | BindingFlags.NonPublic);
                object emptyPoses = Activator.CreateInstance(apply.GetParameters()[0].ParameterType);
                apply.Invoke(calibration, new[] { emptyPoses });
                Assert.That(part.activeSelf, Is.True);
                if (variant == "ambiguous") grasp = grasp.Replace("attachment_binding_valid\\\": true", "attachment_binding_valid\\\": false");
                if (variant == "unverified") grasp = grasp.Replace("continuous_feedback_verified\\\": true", "continuous_feedback_verified\\\": false");
                if (variant == "reverse_phase")
                {
                    // A later nonterminal phase must not discard an unseen GRASP.
                    Receive(grasp.Replace("GRASP", "LIFT").Replace("605", "606"));
                }
                Receive(grasp);
                if (variant is "ambiguous" or "unverified")
                {
                    Assert.That(part.transform.parent, Is.EqualTo(root.transform));
                    Assert.That(StringProperty(calibration, "RobotDetail"), Does.Contain("미확인"));
                    return;
                }
                Assert.That(part.transform.parent, Is.EqualTo(gripper));
                Assert.That(Vector3.Distance(part.transform.position, gripper.position), Is.LessThan(0.00001f));
                Assert.That(Vector3.Distance(part.transform.lossyScale, Vector3.one), Is.LessThan(0.00001f));
                Assert.That(Vector3.Dot(part.transform.up, gripper.up), Is.LessThan(-0.9999f));
                gripper.position += Vector3.right;
                Vector3 heldPosition = part.transform.position;
                Receive(grasp);
                Assert.That(part.transform.position, Is.EqualTo(heldPosition));
                apply.Invoke(calibration, new[] { emptyPoses });
                Assert.That(part.activeSelf, Is.True);
                if (variant.StartsWith("restore_", StringComparison.Ordinal))
                {
                    string path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "unity-recovery-" + Guid.NewGuid() + ".json");
                    Component restored = null;
                    try
                    {
                        Field(calibration, "baseLink").SetValue(calibration, root.transform);
                        Field(calibration, "storagePath").SetValue(calibration, path);
                        if (variant == "restore_tray") ((IDictionary)Field(calibration, "attachments").GetValue(calibration)).Clear();
                        if (variant == "restore_placed") Receive(release);
                        Invoke(calibration, "SaveLayout");
                        Invoke(calibration, "SaveLayout"); // Exercise atomic replacement and backup.
                        Assert.That(System.IO.File.Exists(path + ".bak"), Is.True);
                        if (variant == "restore_corrupt") System.IO.File.WriteAllText(path, "invalid json");
                        restored = Child("Restored receiver", root.transform).gameObject.AddComponent(calibration.GetType());
                        Field(restored, "baseLink").SetValue(restored, root.transform);
                        Field(restored, "storagePath").SetValue(restored, path);
                        var binding = ((Array)Field(restored, "prefabBindings").GetValue(restored)).GetValue(0);
                        Field(binding, "prefab").SetValue(binding, part);
                        ((IDictionary)Field(restored, "bindingsByType").GetValue(restored)).Add("black_block", binding);
                        Invoke(restored, "InitializeAttachments", gripper, boardCalibration);
                        if (variant == "restore_placed")
                        {
                            Field(boardOwner, "observedBoard").SetValue(boardOwner, null);
                            Field(boardCalibration, "currentBoard").SetValue(boardCalibration, null);
                            Field(boardCalibration, "<DisplayId>k__BackingField").SetValue(boardCalibration, null);
                        }
                        Invoke(restored, "RestoreLayout");
                        var restoredPart = (GameObject)((IDictionary)Field(restored, "instancesById").GetValue(restored))[source];
                        Assert.That(restoredPart, Is.Not.Null);
                        Assert.That(restoredPart.transform.parent, Is.EqualTo(restored.transform), "Saved poses remain detached until verified.");
                        Assert.That(StringProperty(restored, "SyncDetail"), Does.Contain("확인 중"));
                        if (variant == "restore_tray")
                        {
                            Assert.That(((IDictionary)Field(restored, "attachments").GetValue(restored)).Count, Is.Zero);
                            Assert.That(restoredPart.transform.position, Is.EqualTo(part.transform.position));
                            return;
                        }
                        Vector3 savedRelative = part.transform.localPosition;
                        gripper.position += Vector3.up * 2f;
                        string state = variant is "restore_released" or "restore_placed" ? "placed" : "attached";
                        string snapshot = "{\"schema\":\"fr5.robot_api_status/v1\",\"recovery_required\":false,\"state_fresh\":true,\"event_context\":{\"server_instance_id\":\"7184ba72-ca00-4b70-bbc0-7d35bfc9bb1f\",\"event_sequence\":606,\"attachments\":[{" +
                            "\"source_id\":\"" + source + "\",\"tray_registration_id\":\"" + registration + "\",\"source_observation_id\":\"" + observation + "\"," +
                            "\"job_id\":\"0bf5780c-d6bf-4d01-b949-1365c6614164\",\"operation_id\":\"96488522-5d89-4b70-a046-44db144ea3f3\",\"server_instance_id\":\"7184ba72-ca00-4b70-bbc0-7d35bfc9bb1f\"," +
                            "\"slot_code\":\"VRM-01\",\"state\":\"" + state + "\",\"event_sequence\":606,\"uncertain\":false,\"attachment_binding_valid\":true," +
                            "\"plan_sha256\":\"bb9ca7b86cbf41ef1a4575f4070b0cf41d4421b9544aa53613ab593bbd4e5340\",\"source_cycle_id\":\"20260910-133247\"}]}}";
                        if (variant == "restore_placed") snapshot = snapshot.Replace("96488522-5d89-4b70-a046-44db144ea3f3", "ec91a09c-0f2c-4e1c-b733-9f6c19952398").Replace("606", "629");
                        if (variant == "restore_server_changed") snapshot = snapshot.Replace("7184ba72-ca00-4b70-bbc0-7d35bfc9bb1f", "11111111-1111-4111-8111-111111111111");
                        if (variant == "restore_recovery_required") snapshot = snapshot.Replace("\"recovery_required\":false", "\"recovery_required\":true");
                        Invoke(restored, "ReconcileSnapshot", snapshot);
                        if (variant is "restore_released" or "restore_server_changed" or "restore_recovery_required")
                        {
                            Assert.That(restoredPart.transform.parent, Is.EqualTo(restored.transform));
                            Assert.That(StringProperty(restored, "SyncDetail"), Does.Contain("미확인"));
                        }
                        else if (variant == "restore_placed")
                        {
                            Transform recoveredBoard = (Transform)GetProperty(boardOwner, "ObservationBoard");
                            Assert.That(recoveredBoard, Is.Not.Null, StringProperty(restored, "StorageDetail") + " / " + StringProperty(restored, "SyncDetail"));
                            Assert.That(recoveredBoard, Is.Not.SameAs(board));
                            Assert.That(restoredPart.transform.parent, Is.EqualTo(recoveredBoard));
                            Assert.That(Vector3.Distance(restoredPart.transform.localPosition, savedRelative), Is.LessThan(1e-5f));
                            Vector3 before = restoredPart.transform.position;
                            recoveredBoard.position += Vector3.right;
                            Assert.That(Vector3.Distance(restoredPart.transform.position, before + Vector3.right), Is.LessThan(1e-5f));
                            Assert.That((Transform)GetProperty(boardOwner, "CurrentBoard") == null, Is.True);
                        }
                        else
                        {
                            Assert.That(restoredPart.transform.parent, Is.EqualTo(gripper));
                            Assert.That(restoredPart.transform.localPosition, Is.EqualTo(savedRelative));
                            Assert.That(StringProperty(restored, "SyncDetail"), Does.Contain("대조 완료"));
                            Invoke(restored, "ProcessRobotEvent", grasp);
                            Assert.That(restoredPart.transform.localPosition, Is.EqualTo(savedRelative));
                        }
                        return;
                    }
                    finally
                    {
                        Field(calibration, "storagePath").SetValue(calibration, null);
                        if (restored != null) Field(restored, "storagePath").SetValue(restored, null);
                        foreach (string suffix in new[] { "", ".tmp", ".bak" }) System.IO.File.Delete(path + suffix);
                    }
                }
                if (variant == "other_place")
                {
                    Receive(release.Replace("RELEASE", "APPROACH").Replace("629", "628"));
                    Receive(release.Replace("ec91a09c-0f2c-4e1c-b733-9f6c19952398", "11111111-1111-4111-8111-111111111111"));
                    Assert.That(part.transform.parent, Is.EqualTo(gripper));
                    Assert.That(StringProperty(calibration, "RobotDetail"), Does.Contain("미확인"));
                    return;
                }
                if (variant is "plain_failure" or "rejected_request")
                {
                    string kind = variant == "plain_failure" ? "OPERATION_FAILED" : "REQUEST_REJECTED";
                    Receive("{\"job_id\":\"0bf5780c-d6bf-4d01-b949-1365c6614164\",\"event\":\"" + kind +
                        "\",\"action\":\"robot.place\",\"message\":\"plain failure\"}");
                    Receive(release);
                    Assert.That(part.transform.parent, Is.EqualTo(variant == "plain_failure" ? gripper : board));
                    return;
                }
                if (variant == "stale_snapshot")
                {
                    Invoke(calibration, "ReconcileSnapshot", "{\"schema\":\"fr5.robot_api_status/v1\",\"state_fresh\":true,\"event_context\":{\"attachments\":[]}}");
                    Receive(release);
                    Assert.That(part.transform.parent, Is.EqualTo(gripper));
                    Assert.That(StringProperty(calibration, "RobotDetail"), Does.Contain("미확인"));
                    return;
                }
                Receive(release);
                Assert.That(part.transform.parent, Is.EqualTo(board));
                Assert.That(part.transform.position, Is.EqualTo(heldPosition));
                Receive(grasp.Replace("605", "650"));
                Receive(release);
                Assert.That(part.transform.parent, Is.EqualTo(board), "A late GRASP cannot reattach a placed part.");
                apply.Invoke(calibration, new[] { emptyPoses });
                Assert.That(part.activeSelf, Is.True);
                Assert.That(StringProperty(calibration, "RobotDetail"), Does.Contain("placed"));
            }
            finally { UnityEngine.Object.DestroyImmediate(root); }
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
