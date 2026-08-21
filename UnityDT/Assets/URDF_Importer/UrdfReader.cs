#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Xml;
using System.Xml.Linq;
using UnityEngine;

namespace MainUnity.UrdfImport
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

    internal sealed class UrdfGeometry
    {
        internal UrdfGeometryType Type;
        internal string MeshFilename;
        internal Vector3 MeshScaleRos = Vector3.one;
        internal Vector3 BoxSizeRos;
        internal float CylinderRadius;
        internal float CylinderLength;
    }

    internal sealed class UrdfLink
    {
        internal string Name;
        internal UrdfGeometry VisualGeometry;
        internal Vector3 VisualOriginRos;
        internal Vector3 VisualRpyRos;
        internal Color VisualColor;
        internal UrdfGeometry CollisionGeometry;
        internal Vector3 CollisionOriginRos;
        internal Vector3 CollisionRpyRos;
        internal bool HasInertial;
        internal float Mass;
        internal Vector3 CenterOfMassRos;
        internal Vector3 InertialRpyRos;
        internal Vector3 InertiaDiagonalRos;
        internal Vector3 InertiaOffDiagonalRos;
    }

    internal sealed class UrdfJoint
    {
        internal string Name;
        internal UrdfJointType Type;
        internal string Parent;
        internal string Child;
        internal Vector3 OriginRos;
        internal Vector3 RpyRos;
        internal Vector3 AxisRos;
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

    internal sealed class UrdfModel
    {
        internal string Name;
        internal string SourcePath;
        internal string BaseLink;
        internal Dictionary<string, UrdfLink> Links;
        internal List<UrdfJoint> OrderedJoints;
    }

    internal sealed class RobotAssets
    {
        internal readonly Dictionary<string, Mesh> Meshes =
            new(StringComparer.Ordinal);
        internal readonly Dictionary<string, Material> Materials =
            new(StringComparer.Ordinal);
        internal readonly List<Mesh> CollisionMeshes = new();

        internal Mesh GetMesh(string filename) => Meshes.TryGetValue(filename, out Mesh mesh)
            ? mesh
            : throw new InvalidOperationException($"Mesh was not prepared: {filename}");

        internal Material GetMaterial(Color color) =>
            Materials[MeshAttacher.ColorKey(color)];
    }

    internal sealed class RobotBuildResult
    {
        internal GameObject Root;
        internal Dictionary<string, Transform> LinkTransforms;
        internal Dictionary<string, Transform> JointTransforms;
    }

    internal static class UrdfReader
    {
        static readonly Color DefaultColor = new(0.82f, 0.9f, 0.96f, 1f);

        internal static UrdfModel Read(string path)
        {
            if (string.IsNullOrWhiteSpace(path))
                throw new ArgumentException("URDF path is required.", nameof(path));
            path = ProjectPath(path);
            if (!File.Exists(path))
                throw new FileNotFoundException("URDF file was not found.", path);

            var settings = new XmlReaderSettings
            {
                DtdProcessing = DtdProcessing.Prohibit,
                XmlResolver = null
            };
            XDocument document;
            using (XmlReader reader = XmlReader.Create(path, settings))
                document = XDocument.Load(reader, LoadOptions.SetLineInfo);

            XElement robot = document.Root;
            if (robot == null || robot.Name.LocalName != "robot")
                throw new InvalidDataException("URDF root element must be <robot>.");

            string robotName = Required(robot, "name");
            var links = new Dictionary<string, UrdfLink>(StringComparer.Ordinal);
            foreach (XElement element in robot.Elements("link"))
            {
                UrdfLink link = ParseLink(element);
                if (!links.TryAdd(link.Name, link))
                    throw Error(element, $"Duplicate link '{link.Name}'.");
            }

            var joints = new List<UrdfJoint>();
            var jointNames = new HashSet<string>(StringComparer.Ordinal);
            foreach (XElement element in robot.Elements("joint"))
            {
                UrdfJoint joint = ParseJoint(element);
                if (!jointNames.Add(joint.Name))
                    throw Error(element, $"Duplicate joint '{joint.Name}'.");
                joints.Add(joint);
            }

            ValidateFr5(links, joints);
            string baseLink = FindBaseLink(links, joints);
            List<UrdfJoint> ordered = OrderJoints(baseLink, joints);
            return new UrdfModel
            {
                Name = robotName,
                SourcePath = path,
                BaseLink = baseLink,
                Links = links,
                OrderedJoints = ordered
            };
        }

        static UrdfLink ParseLink(XElement element)
        {
            string name = Required(element, "name");
            XElement visual = element.Element("visual") ??
                throw Error(element, $"Link '{name}' has no visual element.");
            XElement collision = element.Element("collision") ??
                throw Error(element, $"Link '{name}' has no collision element.");
            XElement visualOrigin = visual.Element("origin");
            XElement collisionOrigin = collision.Element("origin");

            var link = new UrdfLink
            {
                Name = name,
                VisualGeometry = ParseGeometry(visual, name, "visual"),
                VisualOriginRos = Vector(visualOrigin, "xyz", Vector3.zero),
                VisualRpyRos = Vector(visualOrigin, "rpy", Vector3.zero),
                VisualColor = ParseColor(visual),
                CollisionGeometry = ParseGeometry(collision, name, "collision"),
                CollisionOriginRos = Vector(collisionOrigin, "xyz", Vector3.zero),
                CollisionRpyRos = Vector(collisionOrigin, "rpy", Vector3.zero)
            };

            XElement inertial = element.Element("inertial");
            if (inertial == null)
                return link;

            XElement inertia = inertial.Element("inertia") ??
                throw Error(inertial, $"Link '{name}' has no inertia tensor.");
            XElement inertialOrigin = inertial.Element("origin");
            link.HasInertial = true;
            link.Mass = Number(inertial.Element("mass"), "value");
            link.CenterOfMassRos = Vector(inertialOrigin, "xyz", Vector3.zero);
            link.InertialRpyRos = Vector(inertialOrigin, "rpy", Vector3.zero);
            link.InertiaDiagonalRos = new Vector3(
                Number(inertia, "ixx"),
                Number(inertia, "iyy"),
                Number(inertia, "izz"));
            link.InertiaOffDiagonalRos = new Vector3(
                Number(inertia, "ixy"),
                Number(inertia, "ixz"),
                Number(inertia, "iyz"));
            return link;
        }

        static UrdfGeometry ParseGeometry(XElement owner, string link, string role)
        {
            XElement geometry = owner.Element("geometry") ??
                throw Error(owner, $"Link '{link}' has no {role} geometry.");
            XElement mesh = geometry.Element("mesh");
            if (mesh != null)
            {
                Vector3 scale = Vector(mesh, "scale", Vector3.one);
                if (Mathf.Approximately(scale.x * scale.y * scale.z, 0f))
                    throw Error(mesh, $"Link '{link}' has a zero mesh scale.");
                return new UrdfGeometry
                {
                    Type = UrdfGeometryType.Mesh,
                    MeshFilename = Required(mesh, "filename"),
                    MeshScaleRos = scale
                };
            }

            XElement box = geometry.Element("box");
            if (box != null)
            {
                Vector3 size = Vector(box, "size");
                if (size.x <= 0f || size.y <= 0f || size.z <= 0f)
                    throw Error(box, $"Link '{link}' has an invalid box size.");
                return new UrdfGeometry
                {
                    Type = UrdfGeometryType.Box,
                    BoxSizeRos = size
                };
            }

            XElement cylinder = geometry.Element("cylinder");
            if (cylinder != null)
            {
                float radius = Number(cylinder, "radius");
                float length = Number(cylinder, "length");
                if (radius <= 0f || length <= 0f)
                    throw Error(cylinder, $"Link '{link}' has invalid cylinder dimensions.");
                return new UrdfGeometry
                {
                    Type = UrdfGeometryType.Cylinder,
                    CylinderRadius = radius,
                    CylinderLength = length
                };
            }

            throw Error(geometry, $"Link '{link}' uses unsupported {role} geometry.");
        }

        static UrdfJoint ParseJoint(XElement element)
        {
            string name = Required(element, "name");
            UrdfJointType type = Required(element, "type") switch
            {
                "fixed" => UrdfJointType.Fixed,
                "revolute" => UrdfJointType.Revolute,
                "prismatic" => UrdfJointType.Prismatic,
                string value => throw Error(element,
                    $"Joint '{name}' uses unsupported type '{value}'.")
            };
            XElement origin = element.Element("origin");
            var joint = new UrdfJoint
            {
                Name = name,
                Type = type,
                Parent = Required(element.Element("parent"), "link"),
                Child = Required(element.Element("child"), "link"),
                OriginRos = Vector(origin, "xyz", Vector3.zero),
                RpyRos = Vector(origin, "rpy", Vector3.zero)
            };
            if (type == UrdfJointType.Fixed)
                return joint;

            XElement limit = element.Element("limit") ??
                throw Error(element, $"Joint '{name}' has no limit element.");
            XElement dynamics = element.Element("dynamics");
            joint.AxisRos = Vector(element.Element("axis"), "xyz").normalized;
            joint.LowerLimit = Number(limit, "lower");
            joint.UpperLimit = Number(limit, "upper");
            joint.Effort = Number(limit, "effort");
            joint.Velocity = Number(limit, "velocity");
            joint.Damping = Number(dynamics, "damping", 0f);
            joint.Friction = Number(dynamics, "friction", 0f);

            XElement mimic = element.Element("mimic");
            if (mimic != null)
            {
                joint.MimicJoint = Required(mimic, "joint");
                joint.MimicMultiplier = Number(mimic, "multiplier", 1f);
                joint.MimicOffset = Number(mimic, "offset", 0f);
            }
            return joint;
        }

        static void ValidateFr5(
            Dictionary<string, UrdfLink> links,
            List<UrdfJoint> joints)
        {
            if (links.Count == 0)
                throw new InvalidDataException("URDF has no links.");
            if (joints.Count(joint => joint.Type == UrdfJointType.Revolute) != 6)
                throw new InvalidDataException("FR5 URDF requires exactly six revolute joints.");

            UrdfJoint[] prismatic = joints
                .Where(joint => joint.Type == UrdfJointType.Prismatic)
                .ToArray();
            if (prismatic.Length != 2 ||
                prismatic.Count(joint => !string.IsNullOrEmpty(joint.MimicJoint)) != 1)
                throw new InvalidDataException(
                    "FR5 gripper requires two prismatic joints and one mimic joint.");

            var children = new HashSet<string>(StringComparer.Ordinal);
            var jointByName = joints.ToDictionary(joint => joint.Name, StringComparer.Ordinal);
            foreach (UrdfLink link in links.Values)
            {
                if (link.HasInertial &&
                    (link.Mass <= 0f || link.InertiaDiagonalRos.x <= 0f ||
                     link.InertiaDiagonalRos.y <= 0f || link.InertiaDiagonalRos.z <= 0f))
                    throw new InvalidDataException(
                        $"Link '{link.Name}' has invalid mass or inertia values.");
            }

            foreach (UrdfJoint joint in joints)
            {
                if (!links.ContainsKey(joint.Parent) || !links.ContainsKey(joint.Child) ||
                    !children.Add(joint.Child))
                    throw new InvalidDataException(
                        $"Joint '{joint.Name}' has invalid parent/child links.");
                if (joint.Type != UrdfJointType.Fixed &&
                    (joint.AxisRos.sqrMagnitude < 0.99f ||
                     joint.LowerLimit >= joint.UpperLimit ||
                     joint.Effort <= 0f || joint.Velocity <= 0f))
                    throw new InvalidDataException(
                        $"Joint '{joint.Name}' has invalid axis, limits, effort, or velocity.");
                if (!string.IsNullOrEmpty(joint.MimicJoint) &&
                    (!jointByName.TryGetValue(joint.MimicJoint, out UrdfJoint source) ||
                     source.Type != joint.Type || source.Name == joint.Name))
                    throw new InvalidDataException(
                        $"Joint '{joint.Name}' has an invalid mimic source.");
            }
        }

        static string FindBaseLink(
            Dictionary<string, UrdfLink> links,
            List<UrdfJoint> joints)
        {
            var children = new HashSet<string>(
                joints.Select(joint => joint.Child), StringComparer.Ordinal);
            string[] roots = links.Keys.Where(link => !children.Contains(link)).ToArray();
            if (roots.Length != 1)
                throw new InvalidDataException("URDF must contain exactly one base link.");
            return roots[0];
        }

        static List<UrdfJoint> OrderJoints(string baseLink, List<UrdfJoint> joints)
        {
            var ordered = new List<UrdfJoint>(joints.Count);
            var reachedLinks = new HashSet<string>(StringComparer.Ordinal) { baseLink };
            var reachedJoints = new HashSet<string>(StringComparer.Ordinal);
            while (ordered.Count < joints.Count)
            {
                int before = ordered.Count;
                foreach (UrdfJoint joint in joints)
                {
                    if (reachedJoints.Contains(joint.Name) || !reachedLinks.Contains(joint.Parent))
                        continue;
                    ordered.Add(joint);
                    reachedJoints.Add(joint.Name);
                    reachedLinks.Add(joint.Child);
                }
                if (ordered.Count == before)
                    throw new InvalidDataException(
                        "URDF joints must form one connected tree without cycles.");
            }
            return ordered;
        }

        static Color ParseColor(XElement visual)
        {
            string rgba = visual.Element("material")?.Element("color")?
                .Attribute("rgba")?.Value;
            if (string.IsNullOrWhiteSpace(rgba))
                return DefaultColor;
            float[] values = Values(rgba, 4, "rgba");
            return new Color(values[0], values[1], values[2], values[3]);
        }

        static string Required(XElement element, string attribute) =>
            element?.Attribute(attribute)?.Value ??
            throw Error(element, $"Missing URDF attribute '{attribute}'.");

        static float Number(XElement element, string attribute, float fallback = float.NaN)
        {
            string text = element?.Attribute(attribute)?.Value;
            if (text != null && float.TryParse(
                    text, NumberStyles.Float, CultureInfo.InvariantCulture, out float value) &&
                !float.IsNaN(value) && !float.IsInfinity(value))
                return value;
            if (!float.IsNaN(fallback))
                return fallback;
            throw Error(element, $"Invalid or missing numeric attribute '{attribute}'.");
        }

        static Vector3 Vector(XElement element, string attribute, Vector3? fallback = null)
        {
            string text = element?.Attribute(attribute)?.Value;
            if (string.IsNullOrWhiteSpace(text))
            {
                if (fallback.HasValue)
                    return fallback.Value;
                throw Error(element, $"Missing URDF vector '{attribute}'.");
            }
            float[] values = Values(text, 3, attribute);
            return new Vector3(values[0], values[1], values[2]);
        }

        static float[] Values(string text, int count, string name)
        {
            string[] parts = text.Split(
                new[] { ' ', '\t', '\r', '\n' },
                StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length != count)
                throw new FormatException($"URDF '{name}' requires {count} values.");
            var values = new float[count];
            for (int i = 0; i < count; i++)
                if (!float.TryParse(parts[i], NumberStyles.Float,
                        CultureInfo.InvariantCulture, out values[i]) ||
                    (float.IsNaN(values[i]) || float.IsInfinity(values[i])))
                    throw new FormatException($"URDF '{name}' contains an invalid number.");
            return values;
        }

        static string ProjectPath(string path)
        {
            if (Path.IsPathRooted(path))
                return Path.GetFullPath(path);
            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ??
                throw new InvalidOperationException("Unity project root was not found.");
            return Path.GetFullPath(Path.Combine(projectRoot, path));
        }

        static Exception Error(XElement element, string message)
        {
            if (element is IXmlLineInfo line && line.HasLineInfo())
                return new InvalidDataException($"{message} (line {line.LineNumber})");
            return new InvalidDataException(message);
        }
    }
}
#endif
