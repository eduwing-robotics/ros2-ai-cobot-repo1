// URDF의 로봇 모양 데이터를 Unity에서 사용할 수 있게 준비하고 저장합니다.
// 로봇 구조나 동작 기능은 만들지 않습니다.

using UnityEngine;

#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine.Rendering;
#endif

namespace FR5Mvp.UrdfImport
{
    internal static class RobotAssetImporter
    {
#if UNITY_EDITOR
        /// <summary>Import에 필요한 로봇 모양 데이터를 준비해 반환합니다.</summary>
        internal static RobotAssetSet Prepare(
            UrdfModel model,
            string urdfPath,
            string packageRoot,
            string outputDirectory,
            Color color)
        {
            EnsureFolder(outputDirectory);

            string[] filenames = model.Links.Values
                .SelectMany(link => new[]
                {
                    link.VisualGeometry,
                    link.CollisionGeometry
                })
                .Where(geometry => geometry.Type == UrdfGeometryType.Mesh)
                .Select(geometry => geometry.MeshFilename)
                .Distinct(StringComparer.Ordinal)
                .ToArray();
            var meshes = new Dictionary<string, Mesh>(
                filenames.Length, StringComparer.Ordinal);
            foreach (string filename in filenames)
            {
                Mesh loaded = LoadBinaryStl(
                    ResolveMeshPath(filename, urdfPath, packageRoot));
                meshes.Add(filename, SaveMesh(
                    $"{outputDirectory}/{Path.GetFileNameWithoutExtension(filename)}.asset",
                    loaded));
            }

            return new RobotAssetSet(
                SaveMaterial(outputDirectory, color),
                meshes);
        }

        /// <summary>URDF의 로봇 모양 경로를 실제 파일 경로로 바꿉니다.</summary>
        static string ResolveMeshPath(
            string filename,
            string urdfPath,
            string packageRoot)
        {
            const string packagePrefix = "package://";
            if (!filename.StartsWith(packagePrefix, StringComparison.Ordinal))
                return Path.GetFullPath(Path.Combine(
                    Path.GetDirectoryName(urdfPath) ?? string.Empty,
                    filename));

            string packagePath = filename.Substring(packagePrefix.Length);
            int separator = packagePath.IndexOf('/');
            if (separator < 0 || separator == packagePath.Length - 1)
                throw new InvalidDataException($"Invalid package URI: {filename}");
            string relative = packagePath.Substring(separator + 1)
                .Replace('/', Path.DirectorySeparatorChar);
            return Path.GetFullPath(Path.Combine(packageRoot, relative));
        }

        /// <summary>생성된 충돌 모양 데이터를 Generated 폴더에 저장합니다.</summary>
        internal static Mesh SaveCollisionMesh(
            Mesh mesh,
            string outputDirectory,
            string linkName,
            int index)
        {
            mesh.name = $"{linkName}_collision_{index}";
            return SaveMesh(
                $"{outputDirectory}/{linkName}_collision_{index}.asset",
                mesh);
        }

        static Mesh LoadBinaryStl(string path)
        {
            byte[] data = File.ReadAllBytes(path);
            if (data.Length < 84)
                throw new InvalidDataException($"STL is too short: {path}");

            uint triangleCount = BitConverter.ToUInt32(data, 80);
            long expectedLength = 84L + triangleCount * 50L;
            if (triangleCount == 0 || data.Length < expectedLength)
                throw new InvalidDataException($"Invalid binary STL: {path}");

            var vertices = new Vector3[triangleCount * 3];
            var triangles = new int[vertices.Length];
            for (int triangle = 0; triangle < triangleCount; triangle++)
            {
                int record = 84 + triangle * 50;
                int vertex = triangle * 3;
                vertices[vertex] = ReadVertex(data, record + 12);
                vertices[vertex + 1] = ReadVertex(data, record + 24);
                vertices[vertex + 2] = ReadVertex(data, record + 36);

                // ROS는 오른손 좌표계, Unity는 왼손 좌표계이므로 winding을 뒤집습니다.
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
            RosUnityCoordinates.Position(new Vector3(
                BitConverter.ToSingle(data, offset),
                BitConverter.ToSingle(data, offset + 4),
                BitConverter.ToSingle(data, offset + 8)));

        static Mesh SaveMesh(string path, Mesh loaded)
        {
            Mesh asset = AssetDatabase.LoadAssetAtPath<Mesh>(path);
            if (asset == null)
            {
                AssetDatabase.CreateAsset(loaded, path);
                return loaded;
            }

            EditorUtility.CopySerialized(loaded, asset);
            UnityEngine.Object.DestroyImmediate(loaded);
            EditorUtility.SetDirty(asset);
            return asset;
        }

        static Material SaveMaterial(string outputDirectory, Color color)
        {
            Shader shader = GraphicsSettings.currentRenderPipeline == null
                ? Shader.Find("Standard")
                : Shader.Find("Universal Render Pipeline/Lit");
            if (shader == null)
                throw new InvalidOperationException(
                    "No supported Built-in or URP Lit shader was found.");

            var loaded = new Material(shader)
            {
                name = "FR5UrdfMaterial",
                color = color
            };
            string path = $"{outputDirectory}/FR5UrdfMaterial.mat";
            Material asset = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (asset == null)
            {
                AssetDatabase.CreateAsset(loaded, path);
                return loaded;
            }

            EditorUtility.CopySerialized(loaded, asset);
            UnityEngine.Object.DestroyImmediate(loaded);
            EditorUtility.SetDirty(asset);
            return asset;
        }

        static void EnsureFolder(string path)
        {
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
#endif
    }
}
