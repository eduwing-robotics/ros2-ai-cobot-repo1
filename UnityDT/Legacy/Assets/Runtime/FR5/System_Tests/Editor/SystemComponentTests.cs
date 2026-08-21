#if UNITY_EDITOR
using FR5Mvp.OperationView;
using FR5Mvp.PickPlace;
using FR5Mvp.RobotControl;
using FR5Mvp.RobotData;
using FR5Mvp.RosCommunication;
using FR5Mvp.SafetyMonitoring;
using NUnit.Framework;
using RosMessageTypes.Sensor;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace FR5Mvp.Tests
{
    public sealed class SystemComponentTests
    {
        [Test]
        public void TargetPlanningAndExecutionLifecycle()
        {
            var host = new GameObject("Pick Place Test");
            var workObject = new GameObject("Work Object");
            try
            {
                var target = host.AddComponent<TargetSelection>();
                var planning = host.AddComponent<MotionPlanning>();
                var execution = host.AddComponent<MotionExecution>();
                Assert.That(target.SelectObject(workObject.transform), Is.True);
                Assert.That(target.SetPickPose(
                    new Pose(Vector3.zero, Quaternion.identity)), Is.True);
                Assert.That(target.SetPlacePose(
                    new Pose(Vector3.one, Quaternion.identity)), Is.True);

                planning.PlanRequested += (_, _) => { };
                Assert.That(planning.Request(target.PickPose, target.PlacePose), Is.True);
                Assert.That(planning.State, Is.EqualTo(MotionPlanning.PlanState.Planning));

                RobotTrajectory trajectory = CreateTrajectory();
                Assert.That(planning.Accept(trajectory), Is.True);
                Assert.That(planning.HasValidPlan, Is.True);

                execution.ExecutionRequested += _ => { };
                Assert.That(execution.Execute(trajectory), Is.True);
                execution.Fail("previous failure");
                Assert.That(execution.State,
                    Is.EqualTo(MotionExecution.ExecutionState.Failed));
                execution.Clear();
                Assert.That(execution.State,
                    Is.EqualTo(MotionExecution.ExecutionState.Idle));
                Assert.That(execution.LastError, Is.Empty);
            }
            finally
            {
                Object.DestroyImmediate(workObject);
                Object.DestroyImmediate(host);
            }
        }

        [Test]
        public void SystemReportsWaitingAndStoppedStates()
        {
            var root = new GameObject("FR5 System Test");
            try
            {
                new GameObject("Model").transform.SetParent(root.transform);

                var control = new GameObject("Robot Control");
                control.transform.SetParent(root.transform);
                control.AddComponent<RobotControlOrchestrator>();

                var ros = new GameObject("ROS Communication");
                ros.transform.SetParent(root.transform);
                ros.AddComponent<SafetyMonitor>();
                ros.AddComponent<RosCommunicationOrchestrator>();
                ros.AddComponent<GripperCommandAdapter>();

                var work = new GameObject("Pick Place");
                work.transform.SetParent(root.transform);
                work.AddComponent<PickPlaceOrchestrator>();
                work.AddComponent<TrajectoryPreview>();
                work.AddComponent<PlanningAdapter>();
                work.AddComponent<ExecutionAdapter>();

                var system = root.AddComponent<FR5SystemOrchestrator>();
                system.RefreshReferences();

                Assert.That(system.IsConfigured, Is.True);
                Assert.That(system.State,
                    Is.EqualTo(FR5SystemOrchestrator.SystemState.WaitingForRos));

                system.StopAllMotion();
                Assert.That(system.State,
                    Is.EqualTo(FR5SystemOrchestrator.SystemState.Stopped));
            }
            finally
            {
                Object.DestroyImmediate(root);
            }
        }

        [Test]
        public void GripperStateReadsOnlyOneFiniteDriverJoint()
        {
            var message = new JointStateMsg
            {
                name = new[] { "j1", "finger_right_joint" },
                position = new[] { 0d, 0.021d }
            };

            Assert.That(
                RosCommunicationOrchestrator.TryReadGripperPosition(
                    message,
                    "finger_right_joint",
                    out float meters),
                Is.True);
            Assert.That(meters, Is.EqualTo(0.021f).Within(0.000001f));
        }

        [Test]
        public void SampleSceneHasNoMissingScripts()
        {
            SceneSetup[] previousSetup = EditorSceneManager.GetSceneManagerSetup();
            try
            {
                var scene = EditorSceneManager.OpenScene(
                    "Assets/Scenes/SampleScene.unity",
                    OpenSceneMode.Single);
                int missingCount = 0;
                foreach (GameObject root in scene.GetRootGameObjects())
                {
                    foreach (Transform item in root.GetComponentsInChildren<Transform>(true))
                    {
                        missingCount += GameObjectUtility
                            .GetMonoBehavioursWithMissingScriptCount(item.gameObject);
                    }
                }
                Assert.That(missingCount, Is.Zero);
            }
            finally
            {
                if (previousSetup.Length > 0)
                    EditorSceneManager.RestoreSceneManagerSetup(previousSetup);
                else
                    EditorSceneManager.NewScene(
                        NewSceneSetup.EmptyScene,
                        NewSceneMode.Single);
            }
        }

        static RobotTrajectory CreateTrajectory() =>
            new(
                "base_link",
                0,
                0,
                new[] { "j1" },
                new[]
                {
                    new RobotTrajectoryPoint(
                        new[] { 0d },
                        System.Array.Empty<double>(),
                        System.Array.Empty<double>(),
                        System.Array.Empty<double>(),
                        0d)
                });
    }
}
#endif
