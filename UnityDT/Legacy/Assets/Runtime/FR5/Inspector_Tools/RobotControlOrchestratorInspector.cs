#if UNITY_EDITOR
// FR5 관절 자세와 속도를 Inspector에서 확인하고 직접 제어합니다.

using System;
using FR5Mvp.RobotControl;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace FR5Mvp.InspectorTools
{
    [CustomEditor(typeof(RobotControlOrchestrator))]
    public sealed class RobotControlOrchestratorInspector : UnityEditor.Editor
    {
        public override void OnInspectorGUI()
        {
            DrawDefaultInspector();

            var controller = (RobotControlOrchestrator)target;
            JointController[] joints = controller.GetJoints();
            if (joints.Length == 0)
            {
                EditorGUILayout.HelpBox(
                    "Import the robot before using joint controls.", MessageType.Info);
                return;
            }

            DrawShadowControls(controller, joints);
            DrawTwinVelocityControls(controller, joints);
            if (Application.isPlaying)
                Repaint();
        }

        static void DrawShadowControls(
            RobotControlOrchestrator controller,
            JointController[] joints)
        {
            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Shadow Follow", EditorStyles.boldLabel);

            bool enabled = EditorGUILayout.Toggle(
                "Follow Every Frame", controller.ShadowFollowEnabled);
            if (enabled != controller.ShadowFollowEnabled)
                Change(controller, "Toggle FR5 Shadow Follow",
                    () => controller.SetShadowFollowEnabled(enabled));

            for (int i = 0; i < joints.Length; i++)
            {
                JointController joint = joints[i];
                float targetDegrees = EditorGUILayout.Slider(
                    $"{joint.JointName} Target (deg)",
                    controller.GetShadowTargetDegrees(i),
                    joint.LowerDegrees,
                    joint.UpperDegrees);
                if (!Mathf.Approximately(
                    targetDegrees, controller.GetShadowTargetDegrees(i)))
                {
                    int index = i;
                    Change(controller, "Set FR5 Shadow Target",
                        () => controller.SetShadowTargetDegrees(index, targetDegrees));
                }
                EditorGUILayout.LabelField("Actual", $"{joint.ActualDegrees:F2} deg");
            }

            EditorGUILayout.BeginHorizontal();
            if (GUILayout.Button("Capture Current"))
                Change(controller, "Capture FR5 Pose", controller.CaptureCurrentPose);
            if (GUILayout.Button("Apply Once"))
                Change(controller, "Apply FR5 Shadow Pose", controller.ApplyShadowPose);
            EditorGUILayout.EndHorizontal();
        }

        static void DrawTwinVelocityControls(
            RobotControlOrchestrator controller,
            JointController[] joints)
        {
            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Twin Joint Velocity", EditorStyles.boldLabel);

            bool hasPhysics = Array.TrueForAll(
                joints, joint => joint.HasArticulationBody);
            if (!hasPhysics)
                EditorGUILayout.HelpBox(
                    "Twin velocity requires Articulation Bodies.", MessageType.Info);
            else if (controller.ShadowFollowEnabled)
                EditorGUILayout.HelpBox(
                    "Velocity control is disabled while Shadow Follow is active.",
                    MessageType.Info);

            using (new EditorGUI.DisabledScope(
                !hasPhysics || controller.ShadowFollowEnabled))
            {
                for (int i = 0; i < joints.Length; i++)
                {
                    JointController joint = joints[i];
                    float maxVelocity = float.IsInfinity(
                        joint.MaxVelocityDegreesPerSecond)
                        ? 360f
                        : joint.MaxVelocityDegreesPerSecond;
                    float velocity = EditorGUILayout.Slider(
                        $"{joint.JointName} Target (deg/s)",
                        controller.GetTwinVelocityDegreesPerSecond(i),
                        -maxVelocity,
                        maxVelocity);
                    if (!Mathf.Approximately(
                        velocity,
                        controller.GetTwinVelocityDegreesPerSecond(i)))
                    {
                        int index = i;
                        Change(controller, "Set FR5 Twin Velocity",
                            () => controller.SetTwinVelocityDegreesPerSecond(
                                index, velocity));
                    }
                    EditorGUILayout.LabelField(
                        "Actual",
                        $"{joint.ActualVelocityDegreesPerSecond:F2} deg/s");
                }
            }

            using (new EditorGUI.DisabledScope(!hasPhysics))
                if (GUILayout.Button("Stop All Joints"))
                    Change(controller, "Stop FR5 Twin Motion",
                        controller.StopTwinMotion);
        }

        static void Change(
            RobotControlOrchestrator controller,
            string undoName,
            Action action)
        {
            Undo.RecordObject(controller, undoName);
            action();
            EditorUtility.SetDirty(controller);
            if (!Application.isPlaying && controller.gameObject.scene.IsValid())
                EditorSceneManager.MarkSceneDirty(controller.gameObject.scene);
            SceneView.RepaintAll();
        }
    }
}
#endif
