#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace MainUnity.UrdfImport
{
    internal static class ObjectBuilder
    {
        internal static RobotBuildResult Build(Transform host, UrdfModel model)
        {
            ValidateHost(host);
            EnsureReplaceable(host, model.Name);

            var root = new GameObject(model.Name + " (Importing)");
            root.transform.SetParent(host, false);
            try
            {
                var links = new Dictionary<string, Transform>(
                    model.Links.Count, StringComparer.Ordinal)
                {
                    [model.BaseLink] = root.transform
                };
                var joints = new Dictionary<string, Transform>(
                    model.OrderedJoints.Count, StringComparer.Ordinal);

                foreach (UrdfJoint joint in model.OrderedJoints)
                {
                    var pivot = new GameObject(joint.Name).transform;
                    pivot.SetParent(links[joint.Parent], false);
                    pivot.localPosition = Ros2UnityCoordinate.Position(joint.OriginRos);
                    pivot.localRotation = Ros2UnityCoordinate.Rotation(joint.RpyRos);
                    joints.Add(joint.Name, pivot);
                    links.Add(joint.Child, pivot);
                }

                return new RobotBuildResult
                {
                    Root = root,
                    LinkTransforms = links,
                    JointTransforms = joints
                };
            }
            catch
            {
                UnityEngine.Object.DestroyImmediate(root);
                throw;
            }
        }

        internal static GameObject Commit(
            Transform host,
            RobotBuildResult robot,
            string robotName)
        {
            Transform previous = DirectChild(host, robotName);
            if (previous != null)
                UnityEngine.Object.DestroyImmediate(previous.gameObject);
            robot.Root.name = robotName;
            EditorUtility.SetDirty(robot.Root);
            EditorSceneManager.MarkSceneDirty(host.gameObject.scene);
            Selection.activeGameObject = robot.Root;
            return robot.Root;
        }

        internal static void Rollback(RobotBuildResult robot)
        {
            if (robot?.Root != null)
                UnityEngine.Object.DestroyImmediate(robot.Root);
        }

        static void ValidateHost(Transform host)
        {
            if (Application.isPlaying)
                throw new InvalidOperationException("URDF import is editor-only.");
            if (host == null)
                throw new ArgumentNullException(nameof(host), "Host is required.");
            if (EditorUtility.IsPersistent(host) || !host.gameObject.scene.IsValid())
                throw new ArgumentException(
                    "Host must be a Transform in an open Scene.",
                    nameof(host));
        }

        static void EnsureReplaceable(Transform host, string robotName)
        {
            Transform previous = DirectChild(host, robotName);
            if (previous != null && previous.GetComponent<ArticulationAttacher>() == null)
                throw new InvalidOperationException(
                    $"Host already contains an unrelated object named '{robotName}'.");
        }

        static Transform DirectChild(Transform parent, string name)
        {
            for (int i = 0; i < parent.childCount; i++)
            {
                Transform child = parent.GetChild(i);
                if (child.name == name)
                    return child;
            }
            return null;
        }
    }
}
#endif
