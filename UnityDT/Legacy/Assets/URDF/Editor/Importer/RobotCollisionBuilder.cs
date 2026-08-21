// 각 로봇 부품에 충돌 영역을 만듭니다.
// 외형과 관절 움직임은 변경하지 않습니다.

using UnityEngine;

#if UNITY_EDITOR
using System.Collections.Generic;
using MeshProcess;
#endif

namespace FR5Mvp.UrdfImport
{
    internal static class RobotCollisionBuilder
    {
#if UNITY_EDITOR
        internal static void Apply(
            UrdfModel model,
            RobotAssetSet assets,
            RobotBuildResult robot,
            string outputDirectory)
        {
            foreach (UrdfLink link in model.Links.Values)
            {
                var collision = new GameObject(link.Name + "_collision");
                collision.transform.SetParent(robot.LinkTransforms[link.Name], false);
                collision.transform.localPosition =
                    RosUnityCoordinates.Position(link.CollisionOriginRos);
                collision.transform.localRotation =
                    RosUnityCoordinates.Rotation(link.CollisionRpyRos);

                UrdfGeometry geometry = link.CollisionGeometry;
                if (geometry.Type == UrdfGeometryType.Box)
                {
                    collision.AddComponent<BoxCollider>().size =
                        RosUnityCoordinates.Scale(geometry.BoxSizeRos);
                    continue;
                }
                if (geometry.Type == UrdfGeometryType.Cylinder)
                {
                    // ponytail: Unity CapsuleCollider는 길이가 지름보다 짧은 원판을 표현하지 못합니다.
                    // 정밀한 원통 접촉이 필요할 때만 primitive mesh collider로 교체합니다.
                    collision.AddComponent<BoxCollider>().size = new Vector3(
                        geometry.CylinderRadius * 2f,
                        geometry.CylinderLength,
                        geometry.CylinderRadius * 2f);
                    continue;
                }

                Mesh sourceMesh = assets.GetMesh(geometry.MeshFilename);
                collision.transform.localScale =
                    RosUnityCoordinates.Scale(geometry.MeshScaleRos);
                VHACD decomposer = collision.AddComponent<VHACD>();
                List<Mesh> convexMeshes = decomposer.GenerateConvexMeshes(sourceMesh);
                UnityEngine.Object.DestroyImmediate(decomposer);

                if (convexMeshes.Count == 1)
                {
                    MeshCollider collider = collision.AddComponent<MeshCollider>();
                    collider.sharedMesh = RobotAssetImporter.SaveCollisionMesh(
                        convexMeshes[0], outputDirectory, link.Name, 0);
                    collider.convex = true;
                    continue;
                }

                // ponytail: 여러 convex 조각의 self-contact 비용 대신 link당 box 하나를 사용합니다.
                foreach (Mesh convexMesh in convexMeshes)
                    UnityEngine.Object.DestroyImmediate(convexMesh);
                BoxCollider box = collision.AddComponent<BoxCollider>();
                box.center = sourceMesh.bounds.center;
                box.size = sourceMesh.bounds.size;
            }
        }
#endif
    }
}
