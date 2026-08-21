// 역할: Preview 전용 로봇 Prefab으로 실제 제어와 분리된 Ghost를 생성하고 표시한다.

using System;
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

        /// <summary>기존 Ghost를 반환하거나 Preview 전용 Prefab으로 새 Ghost를 생성한다.</summary>
        public GameObject GetOrCreateGhost()
        {
            if (ghostInstance != null)
                return ghostInstance;

            Transform parent = ghostParent != null ? ghostParent : transform;
            Transform existing = parent.Find("Ghost");
            if (existing != null)
            {
                ghostInstance = existing.gameObject;
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

        void ConfigurePreviewOnly(GameObject ghost)
        {
            foreach (MonoBehaviour behaviour in ghost.GetComponentsInChildren<MonoBehaviour>(true))
                behaviour.enabled = false;
            foreach (Collider collider in ghost.GetComponentsInChildren<Collider>(true))
                collider.enabled = false;
            foreach (ArticulationBody body in ghost.GetComponentsInChildren<ArticulationBody>(true))
            {
                body.useGravity = false;
                if (body.isRoot)
                    body.immovable = true;
            }
            foreach (Renderer renderer in ghost.GetComponentsInChildren<Renderer>(true))
            {
                Material[] materials = renderer.sharedMaterials;
                Array.Fill(materials, ghostMaterial);
                renderer.sharedMaterials = materials;
            }
        }
    }
}
