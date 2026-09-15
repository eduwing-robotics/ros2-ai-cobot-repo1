// 각 로봇 부품에 URDF 외형을 배치합니다.
// 충돌 영역과 움직임은 만들지 않습니다.

using UnityEngine;

#if UNITY_EDITOR
using System;
using UnityEngine.Rendering;
#endif

namespace FR5Mvp.UrdfImport
{
    internal static class RobotVisualBuilder
    {
#if UNITY_EDITOR
        internal static void Apply(
            UrdfModel model,
            RobotAssetSet assets,
            RobotBuildResult robot)
        {
            foreach (UrdfLink link in model.Links.Values)
            {
                GameObject visual = CreateGeometry(link.VisualGeometry, assets);
                visual.name = link.Name;
                visual.transform.SetParent(robot.LinkTransforms[link.Name], false);
                visual.transform.localPosition =
                    RosUnityCoordinates.Position(link.VisualOriginRos);
                visual.transform.localRotation =
                    RosUnityCoordinates.Rotation(link.VisualRpyRos);

                MeshRenderer renderer = visual.GetComponent<MeshRenderer>();
                renderer.sharedMaterial = assets.Material;
                bool opaque = assets.Material.color.a >= 1f;
                renderer.shadowCastingMode =
                    opaque ? ShadowCastingMode.On : ShadowCastingMode.Off;
                renderer.receiveShadows = opaque;
            }
        }

        static GameObject CreateGeometry(
            UrdfGeometry geometry,
            RobotAssetSet assets)
        {
            if (geometry.Type == UrdfGeometryType.Mesh)
            {
                var visual = new GameObject();
                visual.AddComponent<MeshFilter>().sharedMesh =
                    assets.GetMesh(geometry.MeshFilename);
                visual.AddComponent<MeshRenderer>();
                visual.transform.localScale =
                    RosUnityCoordinates.Scale(geometry.MeshScaleRos);
                return visual;
            }

            PrimitiveType primitive = geometry.Type == UrdfGeometryType.Box
                ? PrimitiveType.Cube
                : PrimitiveType.Cylinder;
            GameObject result = GameObject.CreatePrimitive(primitive);
            UnityEngine.Object.DestroyImmediate(result.GetComponent<Collider>());
            result.transform.localScale = geometry.Type == UrdfGeometryType.Box
                ? RosUnityCoordinates.Scale(geometry.BoxSizeRos)
                : new Vector3(
                    geometry.CylinderRadius * 2f,
                    geometry.CylinderLength * 0.5f,
                    geometry.CylinderRadius * 2f);
            return result;
        }
#endif
    }
}
