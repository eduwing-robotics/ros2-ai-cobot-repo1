using System;
using System.Threading.Tasks;
using UnityEngine;

namespace MainUnity.Runtime.ConveyBelt
{
    [DisallowMultipleComponent]
    public sealed class ConveyMock : MonoBehaviour
    {
        [Header("Objects")]
        [SerializeField] GameObject beltPlane;
        [SerializeField] GameObject pcb;
        [SerializeField] Transform assemblyStopPoint;
        [SerializeField] Transform inspectionStopPoint;

        [Header("Motion")]
        [SerializeField, InspectorName("Belt Speed (m/s)"), Min(0.01f)]
        float conveyorSpeed = 1f;
        [SerializeField, Min(0.1f)] float timeoutSeconds = 30f;

        Renderer beltRenderer;
        Material beltMaterial;
        Transform destination;
        string destinationName;
        TaskCompletionSource<bool> completion;
        float timeoutAt;
        bool moving;

        void Awake() => RefreshReferences();
        void OnValidate() => RefreshReferences();

        void OnDisable()
        {
            if (moving)
                CancelMovement();
        }

        void Update()
        {
            if (!moving)
                return;

            if (Time.time >= timeoutAt)
            {
                FailMovement(new TimeoutException(
                    $"Conveyor did not reach the {destinationName} stop point within {timeoutSeconds} seconds."));
                return;
            }

            float step = conveyorSpeed * Time.deltaTime;
            float remaining = destination.position.z - pcb.transform.position.z;
            if (remaining <= 0f)
            {
                CompleteMovement();
                return;
            }

            float distance = MoveDistance(remaining, step);
            pcb.transform.position += Vector3.forward * distance;
            MoveBeltTexture(distance);

            if (distance == remaining)
                CompleteMovement();
        }

        /// <summary>PCB를 조립 정지점까지 이동한다.</summary>
        public Task MoveBoardToAssemblyAsync() =>
            MoveToAsync(assemblyStopPoint, "assembly");

        /// <summary>PCB를 검사 정지점까지 이동한다.</summary>
        public Task MoveBoardToInspectionAsync() =>
            MoveToAsync(inspectionStopPoint, "inspection");

        /// <summary>Context Menu에서 조립 정지점까지 이동을 시작한다.</summary>
        [ContextMenu("Conveyor/Start")]
        public void StartConveyor()
        {
            try
            {
                StartMovement(assemblyStopPoint, "assembly", null);
            }
            catch (Exception exception)
            {
                Debug.LogException(exception, this);
            }
        }

        /// <summary>현재 컨베이어 동작을 즉시 정지한다.</summary>
        [ContextMenu("Conveyor/Stop")]
        public void StopConveyor()
        {
            if (moving)
                CancelMovement();
        }

        /// <summary>PCB가 현재 목표 정지점에 도달했으면 이동을 완료한다.</summary>
        [ContextMenu("Conveyor/Stop At Stop Point")]
        public void StopAtStopPoint()
        {
            if (!moving)
                return;

            if (destination.position.z - pcb.transform.position.z <= 0f)
                CompleteMovement();
        }

        /// <summary>정지점 직전과 일반 이동 거리 계산을 확인한다.</summary>
        [ContextMenu("Conveyor/Self Check")]
        void SelfCheck()
        {
            Debug.Assert(Mathf.Approximately(MoveDistance(0.05f, 0.1f), 0.05f));
            Debug.Assert(Mathf.Approximately(MoveDistance(1f, 0.1f), 0.1f));
        }

        Task MoveToAsync(Transform stopPoint, string stopPointName)
        {
            TaskCompletionSource<bool> moveCompletion = new();
            StartMovement(stopPoint, stopPointName, moveCompletion);
            return moveCompletion.Task;
        }

        void StartMovement(
            Transform stopPoint,
            string stopPointName,
            TaskCompletionSource<bool> moveCompletion)
        {
            RefreshReferences();

            if (!Application.isPlaying)
                throw new InvalidOperationException("Conveyor can only move in Play Mode.");
            if (moving)
                throw new InvalidOperationException("The conveyor is already moving.");
            if (stopPoint == null)
                throw new InvalidOperationException(
                    $"Assign the {stopPointName} conveyor stop point.");
            if (pcb == null || beltRenderer == null)
                throw new InvalidOperationException("Assign the belt Plane and PCB objects.");
            if (conveyorSpeed <= 0f)
                throw new InvalidOperationException("Set a positive conveyor speed.");
            if (timeoutSeconds <= 0f)
                throw new InvalidOperationException("Set a positive conveyor timeout.");

            beltMaterial = beltRenderer.material;
            destination = stopPoint;
            destinationName = stopPointName;
            completion = moveCompletion;
            timeoutAt = Time.time + timeoutSeconds;
            moving = true;
        }

        void CompleteMovement()
        {
            TaskCompletionSource<bool> moveCompletion = completion;
            ResetMovement();
            moveCompletion?.TrySetResult(true);
        }

        void CancelMovement()
        {
            TaskCompletionSource<bool> moveCompletion = completion;
            ResetMovement();
            moveCompletion?.TrySetCanceled();
        }

        void FailMovement(Exception exception)
        {
            TaskCompletionSource<bool> moveCompletion = completion;
            ResetMovement();
            moveCompletion?.TrySetException(exception);
            if (moveCompletion == null)
                Debug.LogException(exception, this);
        }

        void ResetMovement()
        {
            moving = false;
            destination = null;
            destinationName = null;
            completion = null;
        }

        void RefreshReferences()
        {
            beltRenderer = beltPlane == null ? null : beltPlane.GetComponent<Renderer>();
        }

        void MoveBeltTexture(float distance)
        {
            if (beltMaterial == null || distance == 0f)
                return;

            Vector3 size = beltRenderer.bounds.size;
            Vector2 scale = beltMaterial.mainTextureScale;
            if (size.z > 0f)
                beltMaterial.mainTextureOffset +=
                    Vector2.down * distance * scale.y / size.z;
        }

        static float MoveDistance(float remaining, float step) =>
            Mathf.Min(remaining, step);
    }
}
