#if UNITY_EDITOR
using FR5Mvp.PickPlace;
using UnityEditor;
using UnityEngine;

namespace FR5Mvp.InspectorTools
{
    [CustomEditor(typeof(PickPlaceOrchestrator))]
    public sealed class PickPlaceOrchestratorInspector : UnityEditor.Editor
    {
        public override void OnInspectorGUI()
        {
            DrawDefaultInspector();
            var workflow = (PickPlaceOrchestrator)target;

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Pick & Place", EditorStyles.boldLabel);
            EditorGUILayout.LabelField("State", workflow.State.ToString());
            if (!string.IsNullOrEmpty(workflow.LastError))
                EditorGUILayout.HelpBox(workflow.LastError, MessageType.Warning);
            EditorGUILayout.HelpBox(
                "Cross-feature Plan, Preview, Execute and Stop commands are exposed by " +
                "FR5SystemOrchestrator.",
                MessageType.Info);

            if (Application.isPlaying)
                Repaint();
        }
    }
}
#endif
