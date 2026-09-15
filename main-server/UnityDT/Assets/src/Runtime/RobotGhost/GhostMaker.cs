// 역할: Preview 전용 로봇 Prefab으로 실제 제어와 분리된 Ghost를 생성하고 표시한다.

using System;
using System.Collections.Generic;
using UnityEngine;

namespace MainUnity.Runtime.RobotGhost
{
    [DisallowMultipleComponent]
    public sealed class GhostMaker : MonoBehaviour
    {
        [SerializeField] GameObject ghostPrefab;
        [SerializeField] Transform ghostParent;
        [SerializeField] Material ghostMaterial;
        [SerializeField] GameObject ghostInstance;
        [Tooltip("MANUAL 미리보기에서 검사할 장애물입니다. 모든 항목이 연결되고 활성화되어야 요청할 수 있습니다.")]
        [SerializeField] internal Collider[] manualObstacles = Array.Empty<Collider>();

        static readonly int BaseColorId = Shader.PropertyToID("_BaseColor");
        static readonly int ColorId = Shader.PropertyToID("_Color");
        readonly List<Collider> manualColliders = new();
        MaterialPropertyBlock collisionProperties;
        GameObject configuredGhost;
        Renderer[] previewRenderers = Array.Empty<Renderer>();
        MaterialPropertyBlock[] normalProperties = Array.Empty<MaterialPropertyBlock>();
        Transform manualPreviewJoint;
        bool collisionVisual;

        internal Vector3 ManualPreviewPosition => manualPreviewJoint != null
            ? manualPreviewJoint.position
            : transform.position;

        internal int ManualObstacleSignature
        {
            get
            {
                unchecked
                {
                    int signature = manualObstacles == null ? -1 : manualObstacles.Length;
                    if (manualObstacles == null)
                        return signature;
                    foreach (Collider obstacle in manualObstacles)
                    {
                        signature = signature * 31 + (obstacle != null ? obstacle.GetInstanceID() : 0);
                        if (obstacle == null)
                            continue;
                        Bounds bounds = obstacle.bounds;
                        Transform obstacleTransform = obstacle.transform;
                        signature = signature * 31 + obstacle.enabled.GetHashCode();
                        signature = signature * 31 + obstacle.gameObject.activeInHierarchy.GetHashCode();
                        signature = signature * 31 + bounds.center.GetHashCode();
                        signature = signature * 31 + bounds.extents.GetHashCode();
                        signature = signature * 31 + obstacleTransform.position.GetHashCode();
                        signature = signature * 31 + obstacleTransform.rotation.GetHashCode();
                        signature = signature * 31 + obstacleTransform.lossyScale.GetHashCode();
                    }
                    return signature;
                }
            }
        }

        /// <summary>기존 Ghost를 반환하거나 Preview 전용 Prefab으로 새 Ghost를 생성한다.</summary>
        public GameObject GetOrCreateGhost()
        {
            if (ghostInstance != null)
            {
                ConfigurePreviewOnly(ghostInstance);
                return ghostInstance;
            }

            Transform parent = ghostParent != null ? ghostParent : transform;
            Transform existing = parent.Find("Ghost");
            if (existing != null)
            {
                ghostInstance = existing.gameObject;
                ConfigurePreviewOnly(ghostInstance);
                return ghostInstance;
            }

            if (ghostPrefab == null || ghostMaterial == null)
            {
                Debug.LogError("Assign a preview robot prefab and transparent Ghost material.", this);
                return null;
            }

            var staging = new GameObject("Ghost Creation");
            staging.SetActive(false);
            ghostInstance = Instantiate(ghostPrefab, staging.transform);
            ghostInstance.name = "Ghost";
            ConfigurePreviewOnly(ghostInstance);
            ghostInstance.transform.SetParent(parent, false);
            Destroy(staging);
            ghostInstance.SetActive(true);
            return ghostInstance;
        }

        /// <summary>Ghost를 생성한 뒤 표시 여부를 설정한다.</summary>
        public bool SetGhostVisible(bool visible)
        {
            GameObject ghost = GetOrCreateGhost();
            if (ghost == null)
                return false;
            ghost.SetActive(visible);
            return true;
        }

        internal bool TryCheckManualCollision(out string reason)
        {
            GameObject ghost = GetOrCreateGhost();
            if (ghost == null || ghostMaterial == null || !ghost.activeInHierarchy ||
                manualColliders.Count == 0)
            {
                reason = "Ghost 충돌 형상이 준비되지 않았습니다.";
                return false;
            }
            if (manualObstacles == null || manualObstacles.Length == 0)
            {
                reason = "검사할 장애물이 연결되지 않았습니다.";
                return false;
            }

            // 누락된 장애물을 건너뛰면 미검사 경로를 통과로 오인하게 된다.
            // 실행 요청 전까지 Inspector에 지정한 전체 장애물이 유효해야 한다.
            foreach (Collider obstacle in manualObstacles)
            {
                if (obstacle == null || !obstacle.enabled || !obstacle.gameObject.activeInHierarchy ||
                    obstacle.transform.IsChildOf(ghost.transform) ||
                    (obstacle is MeshCollider mesh && mesh.sharedMesh == null))
                {
                    reason = "검사 대상 장애물이 누락되었거나 비활성 상태입니다.";
                    return false;
                }
            }

            foreach (Collider collider in manualColliders)
            {
                if (collider == null || !collider.enabled || !collider.isTrigger ||
                    !collider.gameObject.activeInHierarchy)
                {
                    reason = "Ghost의 Trigger 충돌 형상이 비활성 상태입니다.";
                    return false;
                }
                foreach (Collider obstacle in manualObstacles)
                {
                    // Trigger는 물리 반발을 만들지 않는다. Ghost의 현재 월드 자세를
                    // 명시적으로 검사하므로 자식 Articulation의 콜백 전달에 의존하지 않는다.
                    bool collision = Physics.ComputePenetration(collider,
                        collider.transform.position, collider.transform.rotation,
                        obstacle, obstacle.transform.position, obstacle.transform.rotation,
                        out _, out _);
                    // 비볼록 벽 메시의 뒷면은 침투 검사에서 빠질 수 있다. 경계 상자도
                    // 겹치면 접촉 가능성을 배제할 수 없으므로 보수적으로 거절한다.
                    bool uncertainContact = obstacle is MeshCollider mesh && !mesh.convex &&
                        collider.bounds.Intersects(obstacle.bounds);
                    if (collision || uncertainContact)
                    {
                        reason = $"{obstacle.name} 충돌 · {collider.name}";
                        return false;
                    }
                }
            }

            reason = string.Empty;
            return true;
        }

        internal void SetManualCollisionVisual(bool collision)
        {
            if (collisionVisual == collision)
                return;
            collisionVisual = collision;
            collisionProperties ??= new MaterialPropertyBlock();
            Color color = ghostMaterial != null && ghostMaterial.HasProperty(BaseColorId)
                ? ghostMaterial.GetColor(BaseColorId)
                : new Color(0f, 0.8f, 1f, 0.3f);
            color.r = 1f;
            color.g = 0.08f;
            color.b = 0.08f;

            for (int i = 0; i < previewRenderers.Length; i++)
            {
                Renderer renderer = previewRenderers[i];
                if (renderer == null)
                    continue;
                if (!collision)
                {
                    renderer.SetPropertyBlock(normalProperties[i]);
                    continue;
                }
                renderer.GetPropertyBlock(collisionProperties);
                collisionProperties.SetColor(BaseColorId, color);
                collisionProperties.SetColor(ColorId, color);
                renderer.SetPropertyBlock(collisionProperties);
            }
        }

        void ConfigurePreviewOnly(GameObject ghost)
        {
            if (configuredGhost == ghost || ghostMaterial == null)
                return;

            manualColliders.Clear();
            manualPreviewJoint = null;
            foreach (MonoBehaviour behaviour in ghost.GetComponentsInChildren<MonoBehaviour>(true))
                behaviour.enabled = false;
            foreach (Collider collider in ghost.GetComponentsInChildren<Collider>(true))
            {
                ArticulationBody body = collider.GetComponentInParent<ArticulationBody>(true);
                bool supportedShape = collider is BoxCollider || collider is SphereCollider ||
                    collider is CapsuleCollider ||
                    (collider is MeshCollider mesh && mesh.convex && mesh.sharedMesh != null);
                bool previewShape = body != null && body.transform.IsChildOf(ghost.transform) &&
                    supportedShape;
                collider.enabled = false;
                if (!previewShape)
                    continue;
                collider.isTrigger = true;
                collider.enabled = true;
                manualColliders.Add(collider);
            }
            foreach (ArticulationBody body in ghost.GetComponentsInChildren<ArticulationBody>(true))
            {
                body.useGravity = false;
                if (body.isRoot)
                    body.immovable = true;
                if (string.Equals(body.name, "j6", StringComparison.OrdinalIgnoreCase))
                    manualPreviewJoint = body.transform;
            }
            int previewLayer = LayerMask.NameToLayer("TransparentFX");
            previewRenderers = ghost.GetComponentsInChildren<Renderer>(true);
            normalProperties = new MaterialPropertyBlock[previewRenderers.Length];
            for (int i = 0; i < previewRenderers.Length; i++)
            {
                Renderer renderer = previewRenderers[i];
                renderer.gameObject.layer = previewLayer;
                Material[] materials = renderer.sharedMaterials;
                Array.Fill(materials, ghostMaterial);
                renderer.sharedMaterials = materials;
                normalProperties[i] = new MaterialPropertyBlock();
                renderer.GetPropertyBlock(normalProperties[i]);
            }
            collisionVisual = false;
            configuredGhost = ghost;
        }
    }
}
