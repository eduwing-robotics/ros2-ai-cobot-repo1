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
        public void UiStatusRecoveryAndSessionEventsRemainConsistent()
        {
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
                Invoke(control, "CaptureInitialSceneState");

                slot2.name = "HBM-01";
                Assert.That(Assert.Throws<TargetInvocationException>(() =>
                    Invoke(control, "BuildObservations")).InnerException,
                    Is.TypeOf<InvalidOperationException>());
                slot2.name = "HBM-02";
                Array observations = (Array)Invoke(control, "BuildObservations");
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
                Assert.That(item1.position, Is.EqualTo(slot1.position));
                Assert.That(item1.parent, Is.SameAs(board));
                Assert.That(item2.parent, Is.SameAs(root.transform));

                Invoke(control, "ResetVisualization", true);
                object snapshot = Packet("AssemblySnapshot",
                    "{\"available\":true,\"active\":true," +
                    "\"job_id\":\"12345678-1234-5678-1234-567812345678\"," +
                    "\"recipe_version\":\"assembly-r1\",\"state\":\"PAUSED\"," +
                    "\"placed_count\":1,\"placed_slot_codes\":[\"HBM-01\"]," +
                    "\"expected_step_count\":2,\"held_step_order\":2," +
                    "\"held_part_id\":\"HBM\",\"held_slot_code\":\"HBM-02\"}");
                Invoke(control, "RestoreSnapshot", snapshot, observations);
                Assert.That(item1.position, Is.EqualTo(slot1.position));
                Assert.That(Field(control, "heldItem").GetValue(control), Is.SameAs(item2));
                Field(snapshot, "placed_slot_codes").SetValue(snapshot, new[] { "UNKNOWN" });
                Assert.That(Assert.Throws<TargetInvocationException>(() =>
                    Invoke(control, "ValidateSnapshot", snapshot, observations)).InnerException,
                    Is.TypeOf<InvalidOperationException>());
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(root);
            }
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
