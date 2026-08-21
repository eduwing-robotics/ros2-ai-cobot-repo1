#if UNITY_EDITOR
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace FR5Mvp.InspectorTools
{
    [CustomEditor(typeof(FR5SystemOrchestrator))]
    public sealed class SystemOrchestratorInspector : UnityEditor.Editor
    {
        public override void OnInspectorGUI()
        {
            DrawDefaultInspector();
            var system = (FR5SystemOrchestrator)target;

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("FR5 System", EditorStyles.boldLabel);
            EditorGUILayout.LabelField("State", system.State.ToString());
            if (!string.IsNullOrEmpty(system.LastError))
                EditorGUILayout.HelpBox(system.LastError, MessageType.Warning);

            if (GUILayout.Button("Refresh References"))
            {
                Undo.RecordObject(system, "Refresh FR5 System References");
                system.RefreshReferences();
                EditorUtility.SetDirty(system);
                if (system.gameObject.scene.IsValid())
                    EditorSceneManager.MarkSceneDirty(system.gameObject.scene);
            }

            using (new EditorGUI.DisabledScope(!Application.isPlaying))
            {
                EditorGUILayout.BeginHorizontal();
                if (GUILayout.Button("Plan")) system.PlanPickPlace();
                if (GUILayout.Button("Preview")) system.PreviewPickPlace();
                if (GUILayout.Button("Execute")) system.ExecutePickPlace();
                EditorGUILayout.EndHorizontal();

                EditorGUILayout.BeginHorizontal();
                if (GUILayout.Button("Cancel")) system.CancelPickPlace();
                if (GUILayout.Button("Stop Motion")) system.StopAllMotion();
                EditorGUILayout.EndHorizontal();

                EditorGUILayout.BeginHorizontal();
                if (GUILayout.Button("Open Gripper")) system.OpenGripper();
                if (GUILayout.Button("Close Gripper")) system.CloseGripper();
                EditorGUILayout.EndHorizontal();
            }

            if (Application.isPlaying)
                Repaint();
        }
    }
}
#endif
