// Unity 메뉴에서 FR5 Import와 제거 명령을 시작합니다.
// 실제 작업 순서는 UrdfImportOrchestrator에 맡깁니다.

using System;
using FR5Mvp.UrdfImport;
using UnityEditor;
using UnityEngine;

namespace FR5Mvp.Editor
{
    /// <summary>FR5 URDF 가져오기와 제거를 Unity 메뉴 명령으로 노출합니다.</summary>
    public static class UrdfImporterMenu
    {
        [MenuItem("Tools/FR5 URDF Importer/Import Scene Robot")]
        static void ImportSceneRobot()
        {
            FR5SystemOrchestrator system = FindSystemOrchestrator();
            system.RefreshReferences();
            UrdfImportOrchestrator.ImportStatic(RequiredModelRoot(system));
        }

        [MenuItem("Tools/FR5 URDF Importer/Clear Scene Robot")]
        static void ClearSceneRobot()
        {
            FR5SystemOrchestrator system = FindSystemOrchestrator();
            system.RefreshReferences();
            UrdfImportOrchestrator.ClearImportedRobot(RequiredModelRoot(system));
        }

        static FR5SystemOrchestrator FindSystemOrchestrator() =>
            UnityEngine.Object.FindFirstObjectByType<FR5SystemOrchestrator>() ??
            throw new InvalidOperationException(
                "No FR5SystemOrchestrator exists in the active Scene.");

        static Transform RequiredModelRoot(FR5SystemOrchestrator system) =>
            system.ModelRoot != null
                ? system.ModelRoot
                : throw new InvalidOperationException(
                    "FR5SystemOrchestrator requires a Model child.");
    }
}
