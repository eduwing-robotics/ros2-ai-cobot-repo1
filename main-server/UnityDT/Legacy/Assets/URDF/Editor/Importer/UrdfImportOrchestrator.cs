#if UNITY_EDITOR
// FR5 URDF를 정해진 순서로 읽어 씬에 완성된 로봇 모델을 만듭니다.
// Import 과정은 에디터에서만 실행되며 씬에는 결과만 남깁니다.

using System;
using System.IO;
using FR5Mvp.RobotControl;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace FR5Mvp.UrdfImport
{
    /// <summary>FR5 URDF 파싱, 에셋 생성, 계층 구성과 제어 바인딩 순서를 조정합니다.</summary>
    public static class UrdfImportOrchestrator
    {
        internal const string GeneratedAssetDirectory = "Assets/Robots/FR5/Generated";
        const string RobotName = "FR5 Imported (URDF Articulation)";
        const string UrdfRelativePath = "URDF/Sources/FR5/urdf/fairino5_v6.urdf";
        const string PackageRootRelativePath = "URDF/Sources/FR5";
        const float DriveStiffness = 8000f;
        const float DriveDamping = 100f;
        static readonly Color RobotColor = new(0.82f, 0.9f, 0.96f, 1f);

        /// <summary>모든 Import 단계를 순서대로 실행하고 완성된 로봇을 반환합니다.</summary>
        public static GameObject ImportStatic(Transform host)
        {
            if (host == null)
                throw new ArgumentNullException(nameof(host));
            if (Application.isPlaying)
                throw new InvalidOperationException("URDF import is editor-only.");

            ClearImportedRobot(host);
            string urdfPath = Path.Combine(Application.dataPath, UrdfRelativePath);

            UrdfModel model = UrdfParser.Read(urdfPath);
            RobotAssetSet assets = RobotAssetImporter.Prepare(
                model,
                urdfPath,
                Path.Combine(Application.dataPath, PackageRootRelativePath),
                GeneratedAssetDirectory,
                RobotColor);
            RobotBuildResult robot = RobotHierarchyBuilder.Build(
                host, RobotName, model);
            RobotVisualBuilder.Apply(model, assets, robot);
            RobotCollisionBuilder.Apply(
                model, assets, robot, GeneratedAssetDirectory);
            RobotArticulationBuilder.Apply(
                model, robot, DriveStiffness, DriveDamping);
            RobotGripperBinder.Apply(model, robot);

            FR5SystemOrchestrator system = host.GetComponentInParent<FR5SystemOrchestrator>();
            system?.RefreshReferences();
            RobotControlOrchestrator controller = system != null
                ? system.RobotControl
                : host.GetComponent<RobotControlOrchestrator>();
            if (controller == null)
                controller = host.gameObject.AddComponent<RobotControlOrchestrator>();
            controller.SetImportedRoot(robot.Root);
            system?.RefreshReferences();

            EditorUtility.SetDirty(controller);
            EditorSceneManager.MarkSceneDirty(host.gameObject.scene);
            AssetDatabase.SaveAssets();
            return robot.Root;
        }

        /// <summary>같은 host 아래의 이전 정적 Import 결과만 제거합니다.</summary>
        public static void ClearImportedRobot(Transform host)
        {
            if (host == null)
                throw new ArgumentNullException(nameof(host));
            if (Application.isPlaying)
                throw new InvalidOperationException("URDF import is editor-only.");

            Transform imported = host.Find(RobotName);
            if (imported != null)
                UnityEngine.Object.DestroyImmediate(imported.gameObject);
            FR5SystemOrchestrator system = host.GetComponentInParent<FR5SystemOrchestrator>();
            system?.RefreshReferences();
            RobotControlOrchestrator controller = system != null
                ? system.RobotControl
                : host.GetComponent<RobotControlOrchestrator>();
            if (controller != null)
            {
                controller.SetImportedRoot(null);
                EditorUtility.SetDirty(controller);
            }
            system?.RefreshReferences();
            EditorSceneManager.MarkSceneDirty(host.gameObject.scene);
        }
    }
}
#endif
