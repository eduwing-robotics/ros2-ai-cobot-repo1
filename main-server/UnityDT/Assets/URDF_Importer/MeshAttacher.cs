#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using MeshProcess;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace MainUnity.UrdfImport
{
    internal static class MeshAttacher
    {
        internal static RobotAssets Prepare(
            UrdfModel model,
            string packageRoot)
        {
            packageRoot = ProjectPath(packageRoot);
            if (string.IsNullOrWhiteSpace(packageRoot) || !Directory.Exists(packageRoot))
                throw new DirectoryNotFoundException(
                    $"URDF package root was not found: {packageRoot}");

            var assets = new RobotAssets();
            string[] filenames = model.Links.Values
                .SelectMany(link => new[] { link.VisualGeometry, link.CollisionGeometry })
                .Where(geometry => geometry.Type == UrdfGeometryType.Mesh)
                .Select(geometry => geometry.MeshFilename)
                .Distinct(StringComparer.Ordinal)
                .OrderBy(filename => filename, StringComparer.Ordinal)
                .ToArray();
            foreach (string filename in filenames)
                assets.Meshes.Add(
                    filename,
                    LoadBinaryStl(ResolveMeshPath(filename, model.SourcePath, packageRoot)));

            Shader shader = GraphicsSettings.currentRenderPipeline == null
                ? Shader.Find("Standard")
                : Shader.Find("Universal Render Pipeline/Lit");
            if (shader == null)
                throw new InvalidOperationException("No supported Lit shader was found.");
            foreach (Color color in model.Links.Values
                         .Select(link => link.VisualColor)
                         .GroupBy(ColorKey)
                         .Select(group => group.First()))
            {
                var material = new Material(shader)
                {
                    name = $"UrdfMaterial_{ColorKey(color)}",
                    color = color
                };
                assets.Materials.Add(ColorKey(color), material);
            }
            return assets;
        }

        internal static RobotAssets Attach(
            RobotBuildResult robot,
            UrdfModel model,
            string packageRoot)
        {
            RobotAssets assets = Prepare(model, packageRoot);
            try
            {
                ApplyVisualsAndCollisions(robot, model, assets);
                return assets;
            }
            catch
            {
                DisposeTransient(assets);
                throw;
            }
        }

        internal static void ApplyVisualsAndCollisions(
            RobotBuildResult robot,
            UrdfModel model,
            RobotAssets assets)
        {
            foreach (UrdfLink link in model.Links.Values)
            {
                ApplyVisual(link, robot.LinkTransforms[link.Name], assets);
                ApplyCollision(link, robot.LinkTransforms[link.Name], assets);
            }
        }

        internal static void Export(
            RobotAssets assets,
            GameObject robot,
            string outputDirectory)
        {
            outputDirectory = AssetDirectory(outputDirectory);
            EnsureAssetDirectory(outputDirectory);
            var replacements = new Dictionary<UnityEngine.Object, UnityEngine.Object>();
            int index = 0;
            foreach (KeyValuePair<string, Mesh> pair in assets.Meshes
                         .OrderBy(pair => pair.Key, StringComparer.Ordinal))
            {
                string name = Path.GetFileNameWithoutExtension(pair.Key);
                Mesh saved = SaveAsset(
                    pair.Value,
                    $"{outputDirectory}/visual_{index++:00}_{SafeName(name)}.asset");
                replacements[pair.Value] = saved;
            }

            for (int i = 0; i < assets.CollisionMeshes.Count; i++)
            {
                Mesh mesh = assets.CollisionMeshes[i];
                Mesh saved = SaveAsset(
                    mesh,
                    $"{outputDirectory}/collision_{i:00}_{SafeName(mesh.name)}.asset");
                replacements[mesh] = saved;
            }

            foreach (KeyValuePair<string, Material> pair in assets.Materials)
            {
                Material saved = SaveAsset(
                    pair.Value,
                    $"{outputDirectory}/material_{pair.Key}.mat");
                replacements[pair.Value] = saved;
            }

            foreach (MeshFilter filter in robot.GetComponentsInChildren<MeshFilter>(true))
                if (filter.sharedMesh != null &&
                    replacements.TryGetValue(filter.sharedMesh, out UnityEngine.Object mesh))
                    filter.sharedMesh = (Mesh)mesh;
            foreach (MeshCollider collider in robot.GetComponentsInChildren<MeshCollider>(true))
                if (collider.sharedMesh != null &&
                    replacements.TryGetValue(collider.sharedMesh, out UnityEngine.Object mesh))
                    collider.sharedMesh = (Mesh)mesh;
            foreach (Renderer renderer in robot.GetComponentsInChildren<Renderer>(true))
                if (renderer.sharedMaterial != null &&
                    replacements.TryGetValue(renderer.sharedMaterial, out UnityEngine.Object material))
                    renderer.sharedMaterial = (Material)material;

            foreach (UnityEngine.Object source in replacements.Keys)
                DestroyIfTransient(source);
        }

        internal static void DisposeTransient(RobotAssets assets)
        {
            if (assets == null)
                return;
            foreach (Mesh mesh in assets.Meshes.Values.Concat(assets.CollisionMeshes))
                DestroyIfTransient(mesh);
            foreach (Material material in assets.Materials.Values)
                DestroyIfTransient(material);
        }

        internal static string ColorKey(Color color)
        {
            Color32 value = color;
            return $"{value.r:X2}{value.g:X2}{value.b:X2}{value.a:X2}";
        }

        static void ApplyVisual(UrdfLink link, Transform parent, RobotAssets assets)
        {
            GameObject visual = CreateVisualGeometry(link.VisualGeometry, assets);
            visual.name = link.Name + "_visual";
            visual.transform.SetParent(parent, false);
            visual.transform.localPosition =
                Ros2UnityCoordinate.Position(link.VisualOriginRos);
            visual.transform.localRotation =
                Ros2UnityCoordinate.Rotation(link.VisualRpyRos);

            MeshRenderer renderer = visual.GetComponent<MeshRenderer>();
            renderer.sharedMaterial = assets.GetMaterial(link.VisualColor);
            bool opaque = link.VisualColor.a >= 1f;
            renderer.shadowCastingMode = opaque
                ? ShadowCastingMode.On
                : ShadowCastingMode.Off;
            renderer.receiveShadows = opaque;
        }

        static GameObject CreateVisualGeometry(UrdfGeometry geometry, RobotAssets assets)
        {
            if (geometry.Type == UrdfGeometryType.Mesh)
            {
                var visual = new GameObject();
                visual.AddComponent<MeshFilter>().sharedMesh =
                    assets.GetMesh(geometry.MeshFilename);
                visual.AddComponent<MeshRenderer>();
                visual.transform.localScale =
                    Ros2UnityCoordinate.Scale(geometry.MeshScaleRos);
                return visual;
            }

            PrimitiveType primitive = geometry.Type == UrdfGeometryType.Box
                ? PrimitiveType.Cube
                : PrimitiveType.Cylinder;
            GameObject result = GameObject.CreatePrimitive(primitive);
            UnityEngine.Object.DestroyImmediate(result.GetComponent<Collider>());
            result.transform.localScale = geometry.Type == UrdfGeometryType.Box
                ? Ros2UnityCoordinate.Scale(geometry.BoxSizeRos)
                : new Vector3(
                    geometry.CylinderRadius * 2f,
                    geometry.CylinderLength * 0.5f,
                    geometry.CylinderRadius * 2f);
            return result;
        }

        static void ApplyCollision(UrdfLink link, Transform parent, RobotAssets assets)
        {
            var collision = new GameObject(link.Name + "_collision");
            collision.transform.SetParent(parent, false);
            collision.transform.localPosition =
                Ros2UnityCoordinate.Position(link.CollisionOriginRos);
            collision.transform.localRotation =
                Ros2UnityCoordinate.Rotation(link.CollisionRpyRos);

            UrdfGeometry geometry = link.CollisionGeometry;
            if (geometry.Type == UrdfGeometryType.Box)
            {
                collision.AddComponent<BoxCollider>().size =
                    Ros2UnityCoordinate.Scale(geometry.BoxSizeRos);
                return;
            }
            if (geometry.Type == UrdfGeometryType.Cylinder)
            {
                float diameter = geometry.CylinderRadius * 2f;
                if (geometry.CylinderLength >= diameter)
                {
                    CapsuleCollider capsule = collision.AddComponent<CapsuleCollider>();
                    capsule.direction = 1;
                    capsule.radius = geometry.CylinderRadius;
                    capsule.height = geometry.CylinderLength;
                }
                else
                {
                    // Unity capsule cannot represent a cylinder shorter than its diameter.
                    collision.AddComponent<BoxCollider>().size = new Vector3(
                        diameter, geometry.CylinderLength, diameter);
                    Debug.LogWarning(
                        $"'{link.Name}' cylinder collision uses a bounds box because it is shorter than its diameter.",
                        collision);
                }
                return;
            }

            Mesh source = assets.GetMesh(geometry.MeshFilename);
            Mesh scaled = ScaleCollisionMesh(
                source,
                Ros2UnityCoordinate.Scale(geometry.MeshScaleRos),
                link.Name);
            try
            {
                VHACD decomposer = collision.AddComponent<VHACD>();
                List<Mesh> convexMeshes;
                try
                {
                    convexMeshes = decomposer.GenerateConvexMeshes(scaled);
                }
                finally
                {
                    UnityEngine.Object.DestroyImmediate(decomposer);
                }

                if (convexMeshes == null || convexMeshes.Count == 0)
                {
                    AddBoundsCollider(collision, scaled);
                    Debug.LogWarning(
                        $"VHACD returned no collision mesh for '{link.Name}'; using its bounds.",
                        collision);
                    return;
                }

                for (int i = 0; i < convexMeshes.Count; i++)
                {
                    Mesh convex = convexMeshes[i];
                    convex.name = $"{link.Name}_{i}";
                    assets.CollisionMeshes.Add(convex);
                    MeshCollider collider = collision.AddComponent<MeshCollider>();
                    collider.sharedMesh = convex;
                    collider.convex = true;
                }
            }
            catch (Exception exception)
            {
                AddBoundsCollider(collision, scaled);
                Debug.LogWarning(
                    $"VHACD failed for '{link.Name}'; using its bounds. {exception.Message}",
                    collision);
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(scaled);
            }
        }

        static Mesh ScaleCollisionMesh(Mesh source, Vector3 scale, string name)
        {
            Vector3[] vertices = source.vertices;
            for (int i = 0; i < vertices.Length; i++)
                vertices[i] = Vector3.Scale(vertices[i], scale);
            int[] triangles = source.triangles;
            if (scale.x * scale.y * scale.z < 0f)
                for (int i = 0; i < triangles.Length; i += 3)
                    (triangles[i + 1], triangles[i + 2]) =
                        (triangles[i + 2], triangles[i + 1]);

            var result = new Mesh
            {
                name = name + "_collision_source",
                indexFormat = IndexFormat.UInt32,
                vertices = vertices,
                triangles = triangles
            };
            result.RecalculateNormals();
            result.RecalculateBounds();
            return result;
        }

        static void AddBoundsCollider(GameObject target, Mesh mesh)
        {
            BoxCollider box = target.AddComponent<BoxCollider>();
            box.center = mesh.bounds.center;
            box.size = mesh.bounds.size;
        }

        static string ResolveMeshPath(
            string filename,
            string urdfPath,
            string packageRoot)
        {
            const string prefix = "package://";
            string path;
            if (!filename.StartsWith(prefix, StringComparison.Ordinal))
            {
                path = Path.GetFullPath(Path.Combine(
                    Path.GetDirectoryName(urdfPath) ?? string.Empty,
                    filename));
            }
            else
            {
                string packagePath = filename.Substring(prefix.Length);
                int separator = packagePath.IndexOf('/');
                if (separator < 0 || separator == packagePath.Length - 1)
                    throw new InvalidDataException($"Invalid package URI: {filename}");
                string relative = packagePath.Substring(separator + 1)
                    .Replace('/', Path.DirectorySeparatorChar);
                string root = Path.GetFullPath(packageRoot).TrimEnd(
                    Path.DirectorySeparatorChar,
                    Path.AltDirectorySeparatorChar);
                path = Path.GetFullPath(Path.Combine(root, relative));
                if (!path.StartsWith(
                        root + Path.DirectorySeparatorChar,
                        StringComparison.Ordinal))
                    throw new InvalidDataException(
                        $"Package URI escapes the selected package root: {filename}");
            }

            if (!File.Exists(path))
                throw new FileNotFoundException($"URDF mesh was not found: {filename}", path);
            return path;
        }

        static Mesh LoadBinaryStl(string path)
        {
            byte[] data = File.ReadAllBytes(path);
            if (data.Length < 84)
                throw new InvalidDataException($"STL is too short: {path}");
            uint triangleCount = BitConverter.ToUInt32(data, 80);
            long expectedLength = 84L + triangleCount * 50L;
            if (triangleCount == 0 || data.Length < expectedLength || triangleCount > 5_000_000)
                throw new InvalidDataException($"Invalid binary STL: {path}");

            var vertices = new Vector3[checked((int)triangleCount * 3)];
            var triangles = new int[vertices.Length];
            for (int triangle = 0; triangle < triangleCount; triangle++)
            {
                int record = 84 + triangle * 50;
                int vertex = triangle * 3;
                vertices[vertex] = ReadVertex(data, record + 12);
                vertices[vertex + 1] = ReadVertex(data, record + 24);
                vertices[vertex + 2] = ReadVertex(data, record + 36);
                triangles[vertex] = vertex;
                triangles[vertex + 1] = vertex + 2;
                triangles[vertex + 2] = vertex + 1;
            }

            var mesh = new Mesh
            {
                name = Path.GetFileNameWithoutExtension(path),
                indexFormat = IndexFormat.UInt32,
                vertices = vertices,
                triangles = triangles
            };
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            return mesh;
        }

        static Vector3 ReadVertex(byte[] data, int offset) =>
            Ros2UnityCoordinate.Position(new Vector3(
                BitConverter.ToSingle(data, offset),
                BitConverter.ToSingle(data, offset + 4),
                BitConverter.ToSingle(data, offset + 8)));

        static T SaveAsset<T>(T loaded, string path) where T : UnityEngine.Object
        {
            T asset = AssetDatabase.LoadAssetAtPath<T>(path);
            if (asset == null)
            {
                AssetDatabase.CreateAsset(loaded, path);
                return loaded;
            }
            EditorUtility.CopySerialized(loaded, asset);
            EditorUtility.SetDirty(asset);
            return asset;
        }

        static string ProjectPath(string path)
        {
            if (string.IsNullOrWhiteSpace(path))
                throw new ArgumentException("Path is required.", nameof(path));
            if (Path.IsPathRooted(path))
                return Path.GetFullPath(path);
            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ??
                throw new InvalidOperationException("Unity project root was not found.");
            return Path.GetFullPath(Path.Combine(projectRoot, path));
        }

        static string AssetDirectory(string path)
        {
            string fullPath = ProjectPath(path).TrimEnd(
                Path.DirectorySeparatorChar,
                Path.AltDirectorySeparatorChar);
            string assetsRoot = Path.GetFullPath(Application.dataPath).TrimEnd(
                Path.DirectorySeparatorChar,
                Path.AltDirectorySeparatorChar);
            if (!fullPath.Equals(assetsRoot, StringComparison.Ordinal) &&
                !fullPath.StartsWith(
                    assetsRoot + Path.DirectorySeparatorChar,
                    StringComparison.Ordinal))
                throw new ArgumentException(
                    "Output directory must be inside Assets.",
                    nameof(path));
            string relative = fullPath.Substring(assetsRoot.Length)
                .TrimStart(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
                .Replace((char)92, (char)47);
            return string.IsNullOrEmpty(relative) ? "Assets" : "Assets/" + relative;
        }

        static void EnsureAssetDirectory(string path)
        {
            path = path.Replace('\\', '/').TrimEnd('/');
            if (path != "Assets" && !path.StartsWith("Assets/", StringComparison.Ordinal))
                throw new ArgumentException("Output directory must be inside Assets.", nameof(path));
            string[] parts = path.Split('/');
            string current = parts[0];
            for (int i = 1; i < parts.Length; i++)
            {
                string next = $"{current}/{parts[i]}";
                if (!AssetDatabase.IsValidFolder(next))
                    AssetDatabase.CreateFolder(current, parts[i]);
                current = next;
            }
        }

        static string SafeName(string value)
        {
            foreach (char invalid in Path.GetInvalidFileNameChars())
                value = value.Replace(invalid, '_');
            return value.Replace('/', '_').Replace('\\', '_');
        }

        static void DestroyIfTransient(UnityEngine.Object value)
        {
            if (value != null && !AssetDatabase.Contains(value))
                UnityEngine.Object.DestroyImmediate(value);
        }
    }
}
#endif
