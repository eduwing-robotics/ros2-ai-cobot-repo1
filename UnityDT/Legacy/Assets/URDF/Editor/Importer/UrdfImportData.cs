#if UNITY_EDITOR
// URDF Import 단계 사이에 전달되는 링크, 관절과 에셋 정보를 정의합니다.
// 파일 읽기나 씬 생성은 수행하지 않습니다.

using System;
using FR5Mvp.RobotControl;
using System.Collections.Generic;
using UnityEngine;

namespace FR5Mvp.UrdfImport
{
    internal enum UrdfGeometryType
    {
        Mesh,
        Box,
        Cylinder
    }

    internal enum UrdfJointType
    {
        Fixed,
        Revolute,
        Prismatic
    }

    /// <summary>mesh, box, cylinder 중 하나의 URDF geometry입니다.</summary>
    internal sealed class UrdfGeometry
    {
        internal UrdfGeometryType Type;
        internal string MeshFilename;
        internal Vector3 MeshScaleRos = Vector3.one;
        internal Vector3 BoxSizeRos;
        internal float CylinderRadius;
        internal float CylinderLength;
    }

    /// <summary>URDF link 하나에서 외형, 충돌, 물리 단계가 사용하는 값입니다.</summary>
    internal sealed class UrdfLink
    {
        internal string Name;
        internal bool HasInertial;
        internal float Mass;
        internal Vector3 CenterOfMassRos;
        internal Vector3 InertiaDiagonalRos;
        internal Vector3 InertiaOffDiagonalRos;
        internal Vector3 InertialRpyRos;
        internal UrdfGeometry VisualGeometry;
        internal Vector3 VisualOriginRos;
        internal Vector3 VisualRpyRos;
        internal UrdfGeometry CollisionGeometry;
        internal Vector3 CollisionOriginRos;
        internal Vector3 CollisionRpyRos;
    }

    /// <summary>URDF joint 하나에서 계층, 물리, 그리퍼 단계가 사용하는 값입니다.</summary>
    internal sealed class UrdfJoint
    {
        internal string Name;
        internal UrdfJointType Type;
        internal string Parent;
        internal string Child;
        internal Vector3 OriginRos;
        internal Vector3 RpyRos;
        internal Vector3 AxisRos;

        // Revolute는 degree, prismatic은 meter 단위입니다. Fixed에는 사용하지 않습니다.
        internal float LowerLimit;
        internal float UpperLimit;
        internal float Effort;
        internal float Velocity;
        internal float Damping;
        internal float Friction;

        internal string MimicJoint;
        internal float MimicMultiplier = 1f;
        internal float MimicOffset;
    }

    /// <summary>파싱된 링크와 순서가 정해진 관절을 함께 보관합니다.</summary>
    internal sealed class UrdfModel
    {
        internal string BaseLink;
        internal Dictionary<string, UrdfLink> Links;
        internal List<UrdfJoint> OrderedJoints;
    }

    /// <summary>Asset 단계가 준비한 공용 Material과 mesh 참조입니다.</summary>
    internal sealed class RobotAssetSet
    {
        readonly Dictionary<string, Mesh> meshes;

        internal RobotAssetSet(Material material, Dictionary<string, Mesh> meshes)
        {
            Material = material;
            this.meshes = meshes;
        }

        internal Material Material { get; }

        internal Mesh GetMesh(string urdfFilename) =>
            meshes.TryGetValue(urdfFilename, out Mesh mesh)
                ? mesh
                : throw new InvalidOperationException(
                    $"Prepared mesh is missing: {urdfFilename}");
    }

    /// <summary>Hierarchy 단계가 한 번 만든 link/joint 매핑을 뒤 단계에 전달합니다.</summary>
    internal sealed class RobotBuildResult
    {
        internal GameObject Root;
        internal Dictionary<string, Transform> LinkTransforms;
        internal Dictionary<string, Transform> JointTransforms;
        internal JointController[] Joints;
    }
}
#endif
