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
