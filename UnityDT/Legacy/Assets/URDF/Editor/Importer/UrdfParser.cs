// URDF를 읽고 로봇 부품과 관절 순서를 확인해 Import 데이터로 바꿉니다.
// 로봇 오브젝트는 만들지 않습니다.

using UnityEngine;

#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Xml.Linq;
#endif

namespace FR5Mvp.UrdfImport
{
    internal static class UrdfParser
    {
#if UNITY_EDITOR
        internal static UrdfModel Read(string path)
        {
            XElement robot = XDocument.Load(path).Root ??
                throw new InvalidOperationException($"URDF has no root element: {path}");
            XElement[] linkElements = robot.Elements("link").ToArray();
            List<UrdfJoint> jointList = robot.Elements("joint")
                .Select(ParseJoint)
                .ToList();

            Dictionary<string, UrdfLink> links = linkElements.ToDictionary(
                element => Required(element, "name"),
                ParseLink,
                StringComparer.Ordinal);
            Dictionary<string, UrdfJoint> joints = jointList.ToDictionary(
                joint => joint.Name,
                StringComparer.Ordinal);

            if (jointList.Count(joint => joint.Type == UrdfJointType.Revolute) != 6)
                throw new InvalidOperationException(
                    "FR5 URDF must contain exactly six revolute arm joints.");

            string baseLink = links.Keys.Single(name =>
                !jointList.Any(joint => joint.Child == name));
            Validate(links, joints);

            return new UrdfModel
            {
                BaseLink = baseLink,
                Links = links,
                OrderedJoints = OrderJoints(baseLink, jointList)
            };
        }

        static UrdfLink ParseLink(XElement element)
        {
            string name = Required(element, "name");
            XElement visual = element.Element("visual") ??
                throw new InvalidOperationException($"Missing visual data for {name}.");
            XElement collision = element.Element("collision") ??
                throw new InvalidOperationException($"Missing collision data for {name}.");

            var link = new UrdfLink
            {
                Name = name,
                VisualGeometry = ParseGeometry(visual, name, "visual"),
                VisualOriginRos = Vector(visual.Element("origin"), "xyz", Vector3.zero),
                VisualRpyRos = Vector(visual.Element("origin"), "rpy", Vector3.zero),
                CollisionGeometry = ParseGeometry(collision, name, "collision"),
                CollisionOriginRos =
                    Vector(collision.Element("origin"), "xyz", Vector3.zero),
                CollisionRpyRos =
                    Vector(collision.Element("origin"), "rpy", Vector3.zero)
            };

            XElement inertial = element.Element("inertial");
            if (inertial == null)
                return link;

            XElement inertia = inertial.Element("inertia") ??
                throw new InvalidOperationException($"Missing inertia tensor for {name}.");
            link.HasInertial = true;
            link.Mass = Number(inertial.Element("mass"), "value");
            link.CenterOfMassRos = Vector(inertial.Element("origin"), "xyz", Vector3.zero);
            link.InertialRpyRos = Vector(inertial.Element("origin"), "rpy", Vector3.zero);
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

        static UrdfGeometry ParseGeometry(
            XElement owner,
            string linkName,
            string role)
        {
            XElement geometry = owner.Element("geometry") ??
                throw new InvalidOperationException(
                    $"Missing {role} geometry for {linkName}.");
            XElement mesh = geometry.Element("mesh");
            if (mesh != null)
                return new UrdfGeometry
                {
                    Type = UrdfGeometryType.Mesh,
                    MeshFilename = Required(mesh, "filename"),
                    MeshScaleRos = Vector(mesh, "scale", Vector3.one)
                };

            XElement box = geometry.Element("box");
            if (box != null)
                return new UrdfGeometry
                {
                    Type = UrdfGeometryType.Box,
                    BoxSizeRos = Vector(box, "size")
                };

            XElement cylinder = geometry.Element("cylinder");
            if (cylinder != null)
                return new UrdfGeometry
                {
                    Type = UrdfGeometryType.Cylinder,
                    CylinderRadius = Number(cylinder, "radius"),
                    CylinderLength = Number(cylinder, "length")
                };

            throw new NotSupportedException(
                $"Unsupported {role} geometry for link '{linkName}'.");
        }

        static UrdfJoint ParseJoint(XElement element)
        {
            string name = Required(element, "name");
            UrdfJointType type = Required(element, "type") switch
            {
                "fixed" => UrdfJointType.Fixed,
                "revolute" => UrdfJointType.Revolute,
                "prismatic" => UrdfJointType.Prismatic,
                string value => throw new NotSupportedException(
                    $"Unsupported joint type '{value}' for '{name}'.")
            };

            var joint = new UrdfJoint
            {
                Name = name,
                Type = type,
                Parent = Required(element.Element("parent"), "link"),
                Child = Required(element.Element("child"), "link"),
                OriginRos = Vector(element.Element("origin"), "xyz", Vector3.zero),
                RpyRos = Vector(element.Element("origin"), "rpy", Vector3.zero)
            };
            if (type == UrdfJointType.Fixed)
                return joint;

            XElement limit = element.Element("limit") ??
                throw new InvalidOperationException($"Missing joint limit for {name}.");
            XElement dynamics = element.Element("dynamics");
            float unit = type == UrdfJointType.Revolute ? Mathf.Rad2Deg : 1f;
            joint.AxisRos = Vector(element.Element("axis"), "xyz").normalized;
            joint.LowerLimit = Number(limit, "lower") * unit;
            joint.UpperLimit = Number(limit, "upper") * unit;
            joint.Effort = Number(limit, "effort");
            joint.Velocity = Number(limit, "velocity");
            joint.Damping = Number(dynamics, "damping", 0f);
            joint.Friction = Number(dynamics, "friction", 0f);

            XElement mimic = element.Element("mimic");
            if (mimic != null)
            {
                joint.MimicJoint = Required(mimic, "joint");
                joint.MimicMultiplier = Number(mimic, "multiplier", 1f);
                joint.MimicOffset = Number(mimic, "offset", 0f) * unit;
            }
            return joint;
        }

        static void Validate(
            Dictionary<string, UrdfLink> links,
            Dictionary<string, UrdfJoint> joints)
        {
            foreach (UrdfLink link in links.Values)
                if (link.HasInertial &&
                    (link.Mass <= 0f || link.InertiaDiagonalRos.x <= 0f ||
                     link.InertiaDiagonalRos.y <= 0f ||
                     link.InertiaDiagonalRos.z <= 0f))
                    throw new InvalidOperationException(
                        $"Invalid mass or inertia for link '{link.Name}'.");

            var children = new HashSet<string>(StringComparer.Ordinal);
            foreach (UrdfJoint joint in joints.Values)
            {
                if (!links.ContainsKey(joint.Parent) ||
                    !links.ContainsKey(joint.Child) ||
                    !children.Add(joint.Child))
                    throw new InvalidOperationException(
                        $"Invalid parent/child data for joint '{joint.Name}'.");
                if (joint.Type != UrdfJointType.Fixed &&
                    (joint.AxisRos.sqrMagnitude < 0.99f ||
                     joint.LowerLimit >= joint.UpperLimit))
                    throw new InvalidOperationException(
                        $"Invalid axis or limit for joint '{joint.Name}'.");
                if (joint.MimicJoint != null &&
                    (!joints.TryGetValue(joint.MimicJoint, out UrdfJoint source) ||
                     source.Type != joint.Type))
                    throw new InvalidOperationException(
                        $"Invalid mimic source for joint '{joint.Name}'.");
            }
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
                    if (!reachedJoints.Contains(joint.Name) &&
                        reachedLinks.Contains(joint.Parent))
                    {
                        ordered.Add(joint);
                        reachedJoints.Add(joint.Name);
                        reachedLinks.Add(joint.Child);
                    }
                if (ordered.Count == before)
                    throw new InvalidOperationException(
                        "URDF joints must form one connected tree without cycles.");
            }
            return ordered;
        }

        static string Required(XElement element, string attribute) =>
            element?.Attribute(attribute)?.Value ??
            throw new InvalidOperationException(
                $"Missing URDF attribute '{attribute}'.");

        static float Number(
            XElement element,
            string attribute,
            float fallback = float.NaN)
        {
            string text = element?.Attribute(attribute)?.Value;
            if (text != null)
                return float.Parse(
                    text, NumberStyles.Float, CultureInfo.InvariantCulture);
            if (!float.IsNaN(fallback))
                return fallback;
            throw new InvalidOperationException(
                $"Missing URDF numeric attribute '{attribute}'.");
        }

        static Vector3 Vector(
            XElement element,
            string attribute,
            Vector3? fallback = null)
        {
            string text = element?.Attribute(attribute)?.Value;
            if (text == null)
            {
                if (fallback.HasValue)
                    return fallback.Value;
                throw new InvalidOperationException(
                    $"Missing URDF attribute '{attribute}'.");
            }

            string[] values = text.Split(
                new[] { ' ', '\t', '\r', '\n' },
                StringSplitOptions.RemoveEmptyEntries);
            if (values.Length != 3)
                throw new FormatException(
                    $"URDF vector '{attribute}' must have three values.");
            return new Vector3(
                float.Parse(values[0], CultureInfo.InvariantCulture),
                float.Parse(values[1], CultureInfo.InvariantCulture),
                float.Parse(values[2], CultureInfo.InvariantCulture));
        }
#endif
    }
}
