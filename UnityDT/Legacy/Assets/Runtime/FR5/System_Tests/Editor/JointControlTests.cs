#if UNITY_EDITOR
// FR5 Import, 관절 제어와 ROS 안전 동작이 함께 유지되는지 검증합니다.

using System;
using System.IO;
using System.Linq;
using System.Xml.Linq;
using FR5Mvp.RobotControl;
using FR5Mvp.RobotData;
using FR5Mvp.RosCommunication;
using FR5Mvp.SafetyMonitoring;
using FR5Mvp.UrdfImport;
using RosMessageTypes.Sensor;
using UnityEditor;
using UnityEngine;
using RobotJointDrive = FR5Mvp.RobotControl.JointDrive;

namespace FR5Mvp.Tests
{
    public static class JointControlTests
    {
        const float Tolerance = 0.0001f;

        [MenuItem("Tools/FR5 URDF Importer/Run Control Tests")]
        public static void Run()
        {
            TestShadowFollow();
            TestJointSerialization();
            TestTwinVelocity();
            TestManualPose();
            TestUrdfAssets();
            TestUrdfPhysicsImport();
            TestWatchdog();
            TestKinematicMirror();
            TestRosJointStateConversion();
            Debug.Log("FR5 joint control tests passed.");
        }

        static void TestShadowFollow()
        {
            var gameObject = new GameObject("shadow-test");
            try
            {
                var joint = gameObject.AddComponent<JointController>();
                joint.Configure("j1", Vector3.up, -90f, 90f, 1f);
                joint.FollowDegrees(120f);

                Near(90f, joint.ValueDegrees, "Shadow angle must respect the URDF limit.");
                Near(0f, Quaternion.Angle(
                    Quaternion.AngleAxis(90f, Vector3.up),
                    gameObject.transform.localRotation),
                    "Shadow pose must be applied immediately without physics.");
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(gameObject);
            }
        }

        static void TestJointSerialization()
        {
            var source = new GameObject("serialization-source");
            var restored = new GameObject("serialization-restored");
            try
            {
                Quaternion zeroRotation = Quaternion.Euler(10f, 20f, 30f);
                source.transform.localRotation = zeroRotation;
                var sourceJoint = source.AddComponent<JointController>();
                sourceJoint.Configure("j1", Vector3.up, -90f, 90f, 1.5f);
                sourceJoint.SetDegrees(25f);

                var restoredJoint = restored.AddComponent<JointController>();
                EditorJsonUtility.FromJsonOverwrite(
                    EditorJsonUtility.ToJson(sourceJoint), restoredJoint);

                if (restoredJoint.JointName != "j1")
                    throw new InvalidOperationException("Joint name must survive serialization.");
                Near(0f, Vector3.Angle(Vector3.up, restoredJoint.LocalAxis),
                    "Joint axis must survive serialization.");
                Near(-90f, restoredJoint.LowerDegrees,
                    "Lower limit must survive serialization.");
                Near(90f, restoredJoint.UpperDegrees,
                    "Upper limit must survive serialization.");
                Near(1.5f * Mathf.Rad2Deg, restoredJoint.MaxVelocityDegreesPerSecond,
                    "Velocity limit must survive serialization.");
                Near(25f, restoredJoint.ValueDegrees,
                    "Joint value must survive serialization.");

                restoredJoint.SetDegrees(30f);
                Near(0f, Quaternion.Angle(
                    zeroRotation * Quaternion.AngleAxis(30f, Vector3.up),
                    restored.transform.localRotation),
                    "Serialized zero rotation must still drive the correct pose.");
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(source);
                UnityEngine.Object.DestroyImmediate(restored);
            }
        }

        static void TestTwinVelocity()
        {
            var root = new GameObject("velocity-root");
            var child = new GameObject("velocity-test");
            try
            {
                root.AddComponent<ArticulationBody>().immovable = true;
                child.transform.SetParent(root.transform);
                ArticulationBody body = child.AddComponent<ArticulationBody>();
                body.jointType = ArticulationJointType.RevoluteJoint;
                body.twistLock = ArticulationDofLock.LimitedMotion;
                ArticulationDrive initialDrive = body.xDrive;
                initialDrive.stiffness = 8000f;
                initialDrive.damping = 100f;
                body.xDrive = initialDrive;

                var joint = child.AddComponent<JointController>();
                joint.Configure("j1", Vector3.right, -180f, 180f, 1f);
                RobotJointDrive.Attach(joint, body);
                if (!child.TryGetComponent(out RobotJointDrive _))
                    throw new InvalidOperationException(
                        "Articulation control must be owned by JointDrive.");
                joint.SetVelocityDegreesPerSecond(180f);

                Near(Mathf.Rad2Deg, joint.TargetVelocityDegreesPerSecond,
                    "Twin velocity must respect the URDF rad/s limit.");
                Near(1f, body.xDrive.targetVelocity,
                    "Angular drive velocity must be written in rad/s.");
                Near(0f, body.xDrive.stiffness,
                    "Velocity control must disable the position spring.");

                joint.SetDegrees(30f);
                Near(8000f, body.xDrive.stiffness,
                    "Position control must restore its drive stiffness.");
                Near(0f, body.xDrive.targetVelocity,
                    "Position control must clear the velocity target.");
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(root);
            }
        }

        static void TestManualPose()
        {
            var root = new GameObject("manual-pose-test");
            var child = new GameObject("manual-pose-joint");
            try
            {
                child.transform.SetParent(root.transform);
                var joint = child.AddComponent<JointController>();
                joint.Configure("j1", Vector3.up, -180f, 180f, 1f);
                var controller = root.AddComponent<RobotControlOrchestrator>();
                controller.SetImportedRoot(root);

                controller.SetShadowFollowEnabled(true);
                controller.ApplyManualPose(new[] { 15f });
                if (controller.ShadowFollowEnabled)
                    throw new InvalidOperationException(
                        "Manual Apply must disable ROS shadow following.");
                Near(15f, controller.GetShadowTargetDegrees(0),
                    "Manual Apply must set the requested joint target.");

                controller.SetTwinVelocityDegreesPerSecond(0, 10f);
                controller.ApplyManualPose(new[] { 0f });
                Near(0f, controller.GetTwinVelocityDegreesPerSecond(0),
                    "Manual Apply must stop Twin velocity control.");
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(root);
            }
        }

        static void TestUrdfPhysicsImport()
        {
            var host = new GameObject("urdf-physics-test");
            host.transform.position = new Vector3(100f, 100f, 100f);
            try
            {
                GameObject importedRoot = UrdfImportOrchestrator.ImportStatic(host.transform);
                RobotControlOrchestrator controller = host.GetComponent<RobotControlOrchestrator>();
                JointController[] joints = controller.GetJoints();
                GripperController gripper = importedRoot
                    .GetComponentInChildren<GripperController>();
                ArticulationBody rootBody = importedRoot.GetComponent<ArticulationBody>();
                ArticulationBody firstJointBody = joints[0].GetComponent<ArticulationBody>();
                ArticulationBody[] bodies = importedRoot
                    .GetComponentsInChildren<ArticulationBody>();
                Collider[] colliders = importedRoot.GetComponentsInChildren<Collider>();
                Material material = importedRoot
                    .GetComponentInChildren<MeshRenderer>().sharedMaterial;

                if (rootBody == null || !rootBody.immovable)
                    throw new InvalidOperationException("The URDF base must be an immovable articulation body.");
                if (firstJointBody == null)
                    throw new InvalidOperationException("URDF joints must have articulation bodies.");
                if (joints.Length != 6 || bodies.Length != 7)
                    throw new InvalidOperationException(
                        "Import must keep the stable base plus six arm bodies.");
                if (gripper == null || !gripper.IsBound)
                    throw new InvalidOperationException(
                        "The gripper mimic controller must be bound after physics import.");
                Near(1.6185f, rootBody.mass, "Base mass must come from the URDF.");
                Near(4.64f, firstJointBody.mass, "Link mass must come from the URDF.");
                Near(150f, firstJointBody.xDrive.forceLimit,
                    "Joint effort must become the drive force limit.");
                Near(3.15f, firstJointBody.maxJointVelocity,
                    "Joint velocity must become the articulation joint velocity limit.");
                string expectedShader = UnityEngine.Rendering.GraphicsSettings
                    .currentRenderPipeline == null
                    ? "Standard"
                    : "Universal Render Pipeline/Lit";
                if (material.shader.name != expectedShader)
                    throw new InvalidOperationException(
                        $"Robot material must use {expectedShader}, got {material.shader.name}.");
                if (colliders.Length != 11)
                    throw new InvalidOperationException(
                        "Each URDF link must have one collider. Got " + colliders.Length + ".");
                if (Array.Exists(colliders, collider =>
                        collider is MeshCollider mesh && (!mesh.convex || mesh.sharedMesh == null)))
                    throw new InvalidOperationException("FR5 mesh colliders must be non-empty and convex.");
                if (!Array.Exists(colliders, collider => collider is BoxCollider))
                    throw new InvalidOperationException(
                        "Complex collision meshes must fall back to a stable box collider.");
                if (Quaternion.Angle(Quaternion.identity, firstJointBody.inertiaTensorRotation) < 0.01f)
                    throw new InvalidOperationException("Full URDF inertia must set a principal-axis rotation.");
                if (!UnityEngine.Physics.GetIgnoreCollision(colliders[0], colliders[1]))
                    throw new InvalidOperationException("Imported FR5 links must ignore self-collision.");

                Vector3 driverClosed = gripper.DriverJaw.localPosition;
                Vector3 followerClosed = gripper.FollowerJaw.localPosition;
                gripper.SetOpeningMeters(0.01f);
                Near(0.01f,
                    Vector3.Distance(driverClosed, gripper.DriverJaw.localPosition),
                    "The gripper driver must receive the requested opening.");
                Near(0.01f,
                    Vector3.Distance(followerClosed, gripper.FollowerJaw.localPosition),
                    "The mimic finger must follow the driver.");
                gripper.SetOpeningMeters(0f);

                SimulationMode previousMode = UnityEngine.Physics.simulationMode;
                try
                {
                    UnityEngine.Physics.simulationMode = SimulationMode.Script;
                    UnityEngine.Physics.SyncTransforms();
                    for (int step = 0; step < 100; step++)
                        UnityEngine.Physics.Simulate(0.01f);
                    float maximumDrift = joints.Max(joint => Mathf.Abs(joint.ActualDegrees));
                    if (!float.IsFinite(maximumDrift) || maximumDrift > 1f)
                        throw new InvalidOperationException(
                            "Zero ROS pose must remain stable for one second. Drift: " +
                            maximumDrift + " degrees.");
                }
                finally
                {
                    UnityEngine.Physics.simulationMode = previousMode;
                }
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(host);
            }
        }

        static void TestUrdfAssets()
        {
            string urdfPath = Path.Combine(
                Application.dataPath, "URDF/Sources/FR5/urdf/fairino5_v6.urdf");
            XDocument document = XDocument.Load(urdfPath);
            if (document.Descendants("origins").Any())
                throw new InvalidOperationException("URDF contains an invalid <origins> element.");

            if (document.Descendants("link").Count() != 11 ||
                document.Descendants("joint").Count() != 10)
                throw new InvalidOperationException(
                    "The FR5 gripper URDF must contain eleven links and ten joints.");

            string packageRoot = Path.Combine(Application.dataPath, "URDF/Sources/FR5");
            foreach (XElement mesh in document.Descendants("mesh"))
            {
                string filename = mesh.Attribute("filename")?.Value;
                if (string.IsNullOrEmpty(filename) ||
                    !filename.StartsWith("package://fairino_description/"))
                    throw new InvalidOperationException($"Invalid FR5 package URI: {filename}");
                string relative = filename.Substring(
                    "package://fairino_description/".Length);
                if (!File.Exists(Path.Combine(packageRoot, relative)))
                    throw new FileNotFoundException("URDF mesh is missing.", filename);
            }
        }

        static void TestWatchdog()
        {
            var host = new GameObject("watchdog-test");
            try
            {
                UrdfImportOrchestrator.ImportStatic(host.transform);
                RobotControlOrchestrator controller = host.GetComponent<RobotControlOrchestrator>();
                SafetyMonitor watchdog = host.AddComponent<SafetyMonitor>();
                watchdog.Configure(controller.GetJointSpecifications());
                watchdog.StopRequested += controller.StopAllMotion;
                watchdog.TimeoutSeconds = 0.2f;
                watchdog.InterpolationSeconds = 0.1f;
                string[] names = { "j1", "j2", "j3", "j4", "j5", "j6" };
                float[] pose = { 10f, 10f, 10f, 10f, 10f, 10f };
                string[] wrongOrder = { "j2", "j1", "j3", "j4", "j5", "j6" };

                if (watchdog.SubmitJointState(wrongOrder, pose, 1d))
                    throw new InvalidOperationException("Watchdog must reject wrong joint order.");
                pose[0] = 999f;
                if (watchdog.SubmitJointState(names, pose, 1d))
                    throw new InvalidOperationException("Watchdog must reject out-of-range degrees.");

                pose[0] = 10f;
                if (!watchdog.SubmitJointState(names, pose, 1d))
                    throw new InvalidOperationException(
                        "Valid state rejected: " + watchdog.LastError);
                double receivedAt = watchdog.LastReceiveTimeSeconds;
                controller.FollowJointState(
                    pose, watchdog.InterpolationSeconds, receivedAt);
                controller.TickJointState(receivedAt + 0.05d);
                Near(5f, controller.GetShadowTargetDegrees(0),
                    "Watchdog must interpolate incoming joint states.", 0.01f);

                if (!watchdog.SubmitJointState(names, pose, 2d))
                    throw new InvalidOperationException("A high-rate sample must remain valid.");
                controller.FollowJointState(
                    pose, watchdog.InterpolationSeconds, receivedAt + 0.05d);
                controller.TickJointState(receivedAt + 0.1d);
                Near(7.5f, controller.GetShadowTargetDegrees(0),
                    "High-rate samples must not restart interpolation.", 0.01f);
                Near(7.5f, controller.GetJoints()[0].GetComponent<ArticulationBody>().xDrive.target,
                    "ROS following must update the drive target.", 0.01f);
                if (watchdog.SubmitJointState(names, pose, 2d))
                    throw new InvalidOperationException("Watchdog must reject duplicate timestamps.");
                if (!watchdog.SubmitJointState(names, pose, 0d))
                    throw new InvalidOperationException("A reset ROS clock must start a new timestamp epoch.");

                receivedAt = watchdog.LastReceiveTimeSeconds;
                watchdog.Tick(receivedAt + 0.21d);
                if (!watchdog.IsTimedOut || controller.ShadowFollowEnabled)
                    throw new InvalidOperationException(
                        "Watchdog timeout must disable shadow following.");
                Near(8000f, controller.GetJoints()[0].GetComponent<ArticulationBody>().xDrive.stiffness,
                    "Watchdog timeout must hold the current position.");
                if (!watchdog.SubmitJointState(names, pose, 0d) || !watchdog.IsHealthy)
                    throw new InvalidOperationException("A fresh state must recover the watchdog.");
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(host);
            }
        }

        static void TestKinematicMirror()
        {
            var host = new GameObject("kinematic-mirror-test");
            try
            {
                UrdfImportOrchestrator.ImportStatic(host.transform);
                RobotControlOrchestrator controller = host.GetComponent<RobotControlOrchestrator>();
                SafetyMonitor watchdog = host.AddComponent<SafetyMonitor>();
                watchdog.Configure(controller.GetJointSpecifications());
                watchdog.InterpolationSeconds = 0.05f;

                var serialized = new SerializedObject(controller);
                serialized.FindProperty("kinematicMirror").boolValue = true;
                serialized.ApplyModifiedPropertiesWithoutUndo();

                string[] names = { "j1", "j2", "j3", "j4", "j5", "j6" };
                float[] pose = { 20f, 0f, 0f, 0f, 0f, 0f };
                if (!watchdog.SubmitJointState(names, pose, 1d))
                    throw new InvalidOperationException(watchdog.LastError);
                double receivedAt = watchdog.LastReceiveTimeSeconds;
                controller.FollowJointState(
                    pose, watchdog.InterpolationSeconds, receivedAt);
                controller.TickJointState(receivedAt + 0.025d);

                ArticulationBody body = controller.GetJoints()[0]
                    .GetComponent<ArticulationBody>();
                Near(10f, controller.GetJoints()[0].ActualDegrees,
                    "Kinematic mirror must interpolate the ROS pose.", 0.01f);
                controller.TickJointState(receivedAt + 0.075d);
                Near(20f, controller.GetJoints()[0].ActualDegrees,
                    "Kinematic mirror must reach the ROS pose.", 0.01f);
                Near(0f, body.xDrive.stiffness,
                    "Kinematic mirror must disable the position spring.");

                serialized.Update();
                serialized.FindProperty("kinematicMirror").boolValue = false;
                serialized.ApplyModifiedPropertiesWithoutUndo();
                controller.ApplyShadowPose();
                Near(8000f, body.xDrive.stiffness,
                    "Disabling kinematic mirror must restore the position spring.");
                Near(20f, body.xDrive.target,
                    "Physics follow must resume from the mirrored pose.", 0.01f);
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(host);
            }
        }

        static void TestRosJointStateConversion()
        {
            var host = new GameObject("ros-joint-state-test");
            try
            {
                UrdfImportOrchestrator.ImportStatic(host.transform);
                RobotControlOrchestrator controller = host.GetComponent<RobotControlOrchestrator>();
                SafetyMonitor watchdog = host.AddComponent<SafetyMonitor>();
                watchdog.Configure(controller.GetJointSpecifications());
                watchdog.InterpolationSeconds = 0f;
                var message = new JointStateMsg
                {
                    name = new[] { "j3", "j1", "j6", "j2", "j5", "j4" },
                    position = new[] { 0.3d, 0.1d, 0.6d, 0.2d, 0.5d, 0.4d }
                };

                var degrees = new float[6];
                if (!RosCommunicationOrchestrator.TryConvertArmState(
                        message, 1d, degrees, out double timestamp, out string error))
                    throw new InvalidOperationException(error);
                if (!watchdog.SubmitJointState(
                        new[] { "j1", "j2", "j3", "j4", "j5", "j6" },
                        degrees,
                        timestamp))
                    throw new InvalidOperationException(watchdog.LastError);
                controller.FollowJointState(
                    degrees, watchdog.InterpolationSeconds, watchdog.LastReceiveTimeSeconds);
                controller.TickJointState(watchdog.LastReceiveTimeSeconds);

                if (!watchdog.IsHealthy)
                    throw new InvalidOperationException(
                        $"Valid ROS joint state rejected: {watchdog.LastError}");
                Near(0.1f * Mathf.Rad2Deg, controller.GetShadowTargetDegrees(0),
                    "ROS joints must be ordered by name.");
                Near(0.6f * Mathf.Rad2Deg, controller.GetShadowTargetDegrees(5),
                    "ROS radians must become degrees.");
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(host);
            }
        }

        static void Near(
            float expected,
            float actual,
            string message,
            float tolerance = Tolerance)
        {
            if (Mathf.Abs(expected - actual) > tolerance)
                throw new InvalidOperationException($"{message} Expected {expected}, got {actual}.");
        }
    }
}
#endif
