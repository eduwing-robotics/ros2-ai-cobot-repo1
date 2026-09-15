#if UNITY_EDITOR
using System;
using UnityEditor;
using UnityEngine;

namespace MainUnity.UrdfImport
{
    public sealed class UrdfImporter : EditorWindow
    {
        const string DefaultUrdfPath =
            "Assets/URDF/Sources/FR5/urdf/fairino5_v6.urdf";
        const string DefaultPackageRoot = "Assets/URDF/Sources/FR5";
        const string DefaultOutputDirectory = "Assets/URDF_Importer/Generated";

        [SerializeField] Transform host;
        [SerializeField] string urdfPath = DefaultUrdfPath;
        [SerializeField] string packageRoot = DefaultPackageRoot;
        [SerializeField] string outputDirectory = DefaultOutputDirectory;
        [SerializeField, Min(0f)] float driveStiffness = 8000f;
        [SerializeField, Min(0f)] float driveDamping = 100f;
        Vector2 scroll;

        [MenuItem("Tools/URDF Importer")]
        static void OpenWindow()
        {
            UrdfImporter window = GetWindow<UrdfImporter>("URDF Importer");
            window.minSize = new Vector2(460f, 300f);
            window.Show();
        }

        void OnEnable()
        {
            if (host == null && Selection.activeTransform != null)
                host = Selection.activeTransform;
            urdfPath = string.IsNullOrWhiteSpace(urdfPath) ? DefaultUrdfPath : urdfPath;
            packageRoot = string.IsNullOrWhiteSpace(packageRoot)
                ? DefaultPackageRoot
                : packageRoot;
            outputDirectory = string.IsNullOrWhiteSpace(outputDirectory)
                ? DefaultOutputDirectory
                : outputDirectory;
        }

        void OnGUI()
        {
            scroll = EditorGUILayout.BeginScrollView(scroll);
            EditorGUILayout.LabelField("Static URDF Import", EditorStyles.boldLabel);
            EditorGUILayout.HelpBox(
                "ROS 통신 없이 URDF를 Scene의 Articulation 로봇으로 생성합니다. Host 아래의 같은 robot name 결과는 성공 후 교체됩니다.",
                MessageType.Info);
            host = (Transform)EditorGUILayout.ObjectField(
                "Host",
                host,
                typeof(Transform),
                true);
            urdfPath = EditorGUILayout.TextField("URDF Path", urdfPath);
            packageRoot = EditorGUILayout.TextField("Package Root", packageRoot);
            outputDirectory = EditorGUILayout.TextField("Output Directory", outputDirectory);
            driveStiffness = EditorGUILayout.FloatField("Drive Stiffness", driveStiffness);
            driveDamping = EditorGUILayout.FloatField("Drive Damping", driveDamping);
            EditorGUILayout.Space();

            using (new EditorGUI.DisabledScope(Application.isPlaying))
            {
                if (GUILayout.Button("Import URDF", GUILayout.Height(32f)))
                {
                    try
                    {
                        Import(host, urdfPath, packageRoot, outputDirectory);
                    }
                    catch (Exception exception)
                    {
                        Debug.LogException(exception);
                        EditorUtility.DisplayDialog(
                            "URDF Import 실패",
                            exception.Message,
                            "확인");
                    }
                }
            }
            EditorGUILayout.EndScrollView();
        }

        public GameObject Import(
            Transform targetHost,
            string sourceUrdfPath,
            string sourcePackageRoot,
            string targetOutputDirectory)
        {
            RobotAssets assets = null;
            RobotBuildResult robot = null;
            try
            {
                UrdfModel model = UrdfReader.Read(sourceUrdfPath);
                robot = ObjectBuilder.Build(targetHost, model);
                assets = MeshAttacher.Attach(robot, model, sourcePackageRoot);
                ArticulationAttacher.Apply(
                    robot,
                    model,
                    Mathf.Max(0f, driveStiffness),
                    Mathf.Max(0f, driveDamping));
                GripperAttacher.Apply(robot, model);
                MeshAttacher.Export(assets, robot.Root, targetOutputDirectory);
                AssetDatabase.SaveAssets();
                return ObjectBuilder.Commit(targetHost, robot, model.Name);
            }
            catch
            {
                ObjectBuilder.Rollback(robot);
                MeshAttacher.DisposeTransient(assets);
                throw;
            }
        }
    }
}
#endif
