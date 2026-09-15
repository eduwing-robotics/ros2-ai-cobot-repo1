// 로봇 부품을 관절 순서대로 연결해 기본 구조를 만듭니다.
// 외형, 충돌 영역과 움직임은 만들지 않습니다.

using FR5Mvp.RobotControl;
using UnityEngine;

#if UNITY_EDITOR
using System;
using System.Collections.Generic;
#endif

namespace FR5Mvp.UrdfImport
{
    internal static class RobotHierarchyBuilder
    {
#if UNITY_EDITOR
        internal static RobotBuildResult Build(
            Transform parent,
            string robotName,
            UrdfModel model)
        {
            var root = new GameObject(robotName);
            root.transform.SetParent(parent, false);

            var linkTransforms = new Dictionary<string, Transform>(
                model.Links.Count, StringComparer.Ordinal)
            {
                [model.BaseLink] = root.transform
            };
            var jointTransforms = new Dictionary<string, Transform>(
                model.OrderedJoints.Count, StringComparer.Ordinal);
            var armJoints = new List<JointController>(6);

            foreach (UrdfJoint data in model.OrderedJoints)
            {
                Transform parentLink = linkTransforms[data.Parent];
                var pivot = new GameObject(data.Name).transform;
                pivot.SetParent(parentLink, false);
                pivot.localPosition = RosUnityCoordinates.Position(data.OriginRos);
                pivot.localRotation = RosUnityCoordinates.Rotation(data.RpyRos);

                if (data.Type == UrdfJointType.Revolute)
                {
                    JointController controller =
                        pivot.gameObject.AddComponent<JointController>();
                    controller.Configure(
                        data.Name,
                        -RosUnityCoordinates.Position(data.AxisRos),
                        data.LowerLimit,
                        data.UpperLimit,
                        data.Velocity);
                    armJoints.Add(controller);
                }

                jointTransforms.Add(data.Name, pivot);
                linkTransforms.Add(data.Child, pivot);
            }

            return new RobotBuildResult
            {
                Root = root,
                LinkTransforms = linkTransforms,
                JointTransforms = jointTransforms,
                Joints = armJoints.ToArray()
            };
        }
#endif
    }
}
