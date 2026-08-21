using System;
using System.Collections.Generic;
using FR5Mvp.RobotControl;
using FR5Mvp.RobotData;
using UnityEngine;

namespace TWINMVP
{
    [AddComponentMenu("Robotics/TWIN MVP/Assembly Runner")]
    [DisallowMultipleComponent]
    public sealed class TwinMvpAssemblyRunner : MonoBehaviour
    {
        [Serializable]
        public sealed class PartJob
        {
            public string label;
            public Transform part;
            [Tooltip("Manual color/depth scan and grasp reference.")]
            public Transform scanPoint;
            public Transform placeTarget;
            public Transform wristOrientation;
            public Vector3 localGraspOffset;
        }

        enum Step
        {
            Idle, Scanning, ApproachPick, Pick, Lift,
            ApproachPlace, Place, Retreat, Complete, Error
        }

        [Header("MVP Components")]
        [SerializeField] TwinMvpDepthCameraPublisher depthCamera;
        [SerializeField] TwinMvpVisionAdapter vision;
        [SerializeField] TwinMvpMoveItAdapter moveIt;
        [SerializeField] RobotControlOrchestrator robot;
        [SerializeField] Transform wrist;
        [SerializeField] Transform carryAnchor;

        [Header("Pedestal -> Belt PCB")]
        [SerializeField] Transform sourceRoot;
        [SerializeField] Transform targetRoot;
        [SerializeField] PartJob[] jobs = Array.Empty<PartJob>();

        [Header("Calibration")]
        [SerializeField, Min(0f)] float graspHeight = 0.008f;
        [SerializeField, Min(0.01f)] float approachHeight = 0.08f;
        [SerializeField, Min(0.1f)] float scanTimeoutSeconds = 3f;
        [SerializeField, Min(0)] int currentIndex;

        Step step;
        float scanDeadline;
        bool runAll;
        Pose pickPose;
        Pose placePose;
        Transform originalParent;

        public int CurrentIndex => currentIndex;
        public string CurrentStep => step.ToString();
        public string LastError { get; private set; } = string.Empty;

        void OnEnable()
        {
            if (vision != null)
                vision.PointDetected += ReceivePoint;
            BindMoveIt(true);
        }

        void OnDisable()
        {
            if (vision != null)
                vision.PointDetected -= ReceivePoint;
            BindMoveIt(false);
        }

        void Update()
        {
            if (step == Step.Scanning && Time.unscaledTime > scanDeadline)
                Fail($"Vision timeout for part index {currentIndex}.");
        }

        public bool ScanAndAssemble(int index, bool continueWithAll = false)
        {
            if (!Application.isPlaying)
                return Reject("Enter Play Mode before starting assembly.");
            if (!TryGetJob(index, out PartJob job) || depthCamera == null || vision == null)
                return Reject("Install and configure the TWIN MVP Assembly Runner first.");

            currentIndex = index;
            runAll = continueWithAll;
            step = Step.Scanning;
            LastError = string.Empty;
            depthCamera.SetScanTarget(job.scanPoint);
            scanDeadline = Time.unscaledTime + scanTimeoutSeconds;
            Debug.Log($"TWIN MVP scanning {job.label}.", this);
            return true;
        }

        public bool AssembleFromKnownPoint(int index)
        {
            if (!Application.isPlaying)
                return Reject("Enter Play Mode before starting assembly.");
            if (!TryGetJob(index, out PartJob job))
                return false;
            currentIndex = index;
            runAll = false;
            return BeginAssembly(job, job.scanPoint.position);
        }

        void ReceivePoint(string label, Vector3 worldPoint)
        {
            if (step != Step.Scanning || !TryGetJob(currentIndex, out PartJob job) ||
                !string.Equals(label, job.label, StringComparison.OrdinalIgnoreCase))
                return;
            BeginAssembly(job, worldPoint);
        }

        bool BeginAssembly(PartJob job, Vector3 detectedPoint)
        {
            if (moveIt == null || wrist == null || carryAnchor == null)
                return Reject("MoveIt, wrist3_link or TWINMVP_TCP is missing.");

            Vector3 pickTcp = detectedPoint +
                job.scanPoint.TransformVector(job.localGraspOffset) + Vector3.up * graspHeight;
            Quaternion rotation = job.wristOrientation != null
                ? job.wristOrientation.rotation
                : wrist.rotation;
            pickPose = WristPoseForTcp(pickTcp, rotation);
            placePose = WristPoseForTcp(
                job.placeTarget.position + Vector3.up * graspHeight, rotation);
            originalParent = job.part.parent;
            robot?.Gripper?.SetOpeningNormalized(1f);
            return Plan(Step.ApproachPick, Raised(pickPose));
        }

        Pose WristPoseForTcp(Vector3 tcpPosition, Quaternion wristRotation)
        {
            Vector3 localTcp = wrist.InverseTransformPoint(carryAnchor.position);
            return new Pose(tcpPosition - wristRotation * localTcp, wristRotation);
        }

        Pose Raised(Pose pose) =>
            new(pose.position + Vector3.up * approachHeight, pose.rotation);

        bool Plan(Step next, Pose target)
        {
            if (moveIt == null)
                return Reject("TWIN MVP MoveIt Adapter is missing.");
            step = next;
            moveIt.RequestPlan(target);
            Debug.Log($"TWIN MVP {jobs[currentIndex].label}: planning {step}.", this);
            return true;
        }

        void ReceivePlan(RobotTrajectory trajectory)
        {
            if (step != Step.Idle && step != Step.Complete && step != Step.Error)
                moveIt.Execute(trajectory);
        }

        void ReceiveExecutionCompleted()
        {
            switch (step)
            {
                case Step.ApproachPick:
                    Plan(Step.Pick, pickPose);
                    break;
                case Step.Pick:
                    AttachPart();
                    Plan(Step.Lift, Raised(pickPose));
                    break;
                case Step.Lift:
                    Plan(Step.ApproachPlace, Raised(placePose));
                    break;
                case Step.ApproachPlace:
                    Plan(Step.Place, placePose);
                    break;
                case Step.Place:
                    PlacePart();
                    Plan(Step.Retreat, Raised(placePose));
                    break;
                case Step.Retreat:
                    CompletePart();
                    break;
            }
        }

        void AttachPart()
        {
            PartJob job = jobs[currentIndex];
            foreach (Collider collider in job.part.GetComponentsInChildren<Collider>(true))
                collider.enabled = false;
            robot?.Gripper?.SetOpeningNormalized(0f);
            job.part.SetParent(carryAnchor, true);
            Debug.Log($"TWIN MVP picked {job.part.name}.", job.part);
        }

        void PlacePart()
        {
            PartJob job = jobs[currentIndex];
            job.part.SetParent(targetRoot != null ? targetRoot : originalParent, true);
            job.part.SetPositionAndRotation(job.placeTarget.position, job.placeTarget.rotation);
            EnableCollision(job.part.gameObject);
            robot?.Gripper?.SetOpeningNormalized(1f);
            Debug.Log($"TWIN MVP placed {job.part.name}; collision is active.", job.part);
        }

        void CompletePart()
        {
            step = Step.Complete;
            Debug.Log($"TWIN MVP completed {jobs[currentIndex].label} assembly.", this);
            if (runAll && currentIndex + 1 < jobs.Length)
                ScanAndAssemble(currentIndex + 1, true);
        }

        void EnableCollision(GameObject part)
        {
            Collider[] colliders = part.GetComponentsInChildren<Collider>(true);
            if (colliders.Length == 0)
                colliders = new Collider[] { AddBoundsCollider(part) };
            foreach (Collider collider in colliders)
                collider.enabled = true;

            TwinMvpPlacedPartCollision probe = part.GetComponent<TwinMvpPlacedPartCollision>();
            if (probe == null)
                probe = part.AddComponent<TwinMvpPlacedPartCollision>();
            probe.Configure(robot != null ? robot.transform.root : null);
        }

        static BoxCollider AddBoundsCollider(GameObject part)
        {
            Renderer[] renderers = part.GetComponentsInChildren<Renderer>(true);
            Bounds bounds = renderers.Length == 0
                ? new Bounds(part.transform.position, Vector3.one * 0.01f)
                : renderers[0].bounds;
            for (int i = 1; i < renderers.Length; i++)
                bounds.Encapsulate(renderers[i].bounds);

            BoxCollider collider = part.AddComponent<BoxCollider>();
            collider.center = part.transform.InverseTransformPoint(bounds.center);
            Vector3 scale = part.transform.lossyScale;
            collider.size = new Vector3(
                bounds.size.x / Mathf.Max(Mathf.Abs(scale.x), 0.0001f),
                bounds.size.y / Mathf.Max(Mathf.Abs(scale.y), 0.0001f),
                bounds.size.z / Mathf.Max(Mathf.Abs(scale.z), 0.0001f));
            return collider;
        }

        bool TryGetJob(int index, out PartJob job)
        {
            job = index >= 0 && index < jobs.Length ? jobs[index] : null;
            if (job != null && !string.IsNullOrWhiteSpace(job.label) && job.part != null &&
                job.scanPoint != null && job.placeTarget != null)
                return true;
            return Reject($"Part job {index} is incomplete.");
        }

        void BindMoveIt(bool bind)
        {
            if (moveIt == null)
                return;
            if (bind)
            {
                moveIt.PlanReceived += ReceivePlan;
                moveIt.PlanFailed += Fail;
                moveIt.ExecutionCompleted += ReceiveExecutionCompleted;
                moveIt.ExecutionFailed += Fail;
            }
            else
            {
                moveIt.PlanReceived -= ReceivePlan;
                moveIt.PlanFailed -= Fail;
                moveIt.ExecutionCompleted -= ReceiveExecutionCompleted;
                moveIt.ExecutionFailed -= Fail;
            }
        }

        bool Reject(string error)
        {
            Fail(error);
            return false;
        }

        void Fail(string error)
        {
            LastError = error;
            step = Step.Error;
            Debug.LogWarning(error, this);
        }

        [ContextMenu("TWIN MVP/Install And Auto Configure Scene")]
        void InstallAndAutoConfigure()
        {
            GameObject cameraObject = GameObject.Find("Depth Cam");
            if (cameraObject == null)
            {
                Reject("The scene does not contain 'Depth Cam'.");
                return;
            }

            depthCamera = cameraObject.GetComponent<TwinMvpDepthCameraPublisher>();
            if (depthCamera == null)
                depthCamera = cameraObject.AddComponent<TwinMvpDepthCameraPublisher>();
            vision = cameraObject.GetComponent<TwinMvpVisionAdapter>();
            if (vision == null)
                vision = cameraObject.AddComponent<TwinMvpVisionAdapter>();
            vision.UseCameraFrame(cameraObject.transform);

            moveIt = GetComponent<TwinMvpMoveItAdapter>();
            if (moveIt == null)
                moveIt = gameObject.AddComponent<TwinMvpMoveItAdapter>();
            robot = FindFirstObjectByType<RobotControlOrchestrator>();
            wrist = FindTransform("wrist3_link");
            if (robot == null || robot.Gripper == null || wrist == null)
            {
                Reject("FR5 robot, gripper or wrist3_link was not found.");
                return;
            }

            carryAnchor = EnsureCarryAnchor(robot.Gripper);
            moveIt.UsePlanningFrame(FindPlanningFrame(wrist));
            ConfigurePlateJobs();
            Debug.Log($"TWIN MVP configured {jobs.Length} pedestal parts and PCB targets.", this);
        }

        void ConfigurePlateJobs()
        {
            Transform first = GameObject.Find("PLATE")?.transform;
            Transform second = GameObject.Find("PLATE (1)")?.transform;
            Transform pedestal = GameObject.Find("item_Place")?.transform;
            if (first == null || second == null || pedestal == null)
            {
                Reject("PLATE, PLATE (1), or item_Place was not found.");
                return;
            }

            sourceRoot = DistanceToPcb(first, pedestal.position) <
                DistanceToPcb(second, pedestal.position) ? first : second;
            targetRoot = sourceRoot == first ? second : first;
            var configured = new List<PartJob>();
            foreach (Transform source in sourceRoot)
            {
                if (source.name.Equals("PCB", StringComparison.OrdinalIgnoreCase))
                {
                    source.gameObject.SetActive(false);
                    continue;
                }

                Transform target = FindDirectChild(targetRoot, source.name);
                if (target == null)
                    continue;
                target.gameObject.SetActive(false);
                configured.Add(new PartJob
                {
                    label = LabelFor(source.name),
                    part = source,
                    scanPoint = source,
                    placeTarget = target
                });
            }
            configured.Sort((a, b) => LabelOrder(a.label).CompareTo(LabelOrder(b.label)));
            jobs = configured.ToArray();
            Transform targetPcb = FindDirectChild(targetRoot, "PCB");
            if (targetPcb != null)
                targetPcb.gameObject.SetActive(true);
        }

        static float DistanceToPcb(Transform root, Vector3 point)
        {
            Transform pcb = FindDirectChild(root, "PCB");
            return pcb == null ? float.PositiveInfinity : Vector3.Distance(pcb.position, point);
        }

        static Transform FindDirectChild(Transform root, string childName)
        {
            foreach (Transform child in root)
                if (child.name.Equals(childName, StringComparison.OrdinalIgnoreCase))
                    return child;
            return null;
        }

        static string LabelFor(string partName)
        {
            string value = partName.ToLowerInvariant();
            if (value.StartsWith("chip")) return "chip";
            if (value.StartsWith("led")) return "led";
            if (value.StartsWith("tantal")) return "tantal";
            if (value.StartsWith("sot")) return "sot";
            if (value.StartsWith("pinheader")) return "pinheader";
            return "cond";
        }

        static int LabelOrder(string label) => label switch
        {
            "chip" => 0,
            "led" => 1,
            "tantal" => 2,
            "sot" => 3,
            "pinheader" => 4,
            _ => 5
        };

        static Transform FindTransform(string objectName)
        {
            foreach (Transform value in FindObjectsByType<Transform>(
                FindObjectsInactive.Include, FindObjectsSortMode.None))
                if (value.name.Equals(objectName, StringComparison.OrdinalIgnoreCase))
                    return value;
            return null;
        }

        static Transform FindPlanningFrame(Transform tip)
        {
            Transform value = tip;
            while (value.parent != null && !value.name.StartsWith("FR5 Imported"))
                value = value.parent;
            return value.parent != null ? value.parent : tip.root;
        }

        static Transform EnsureCarryAnchor(GripperController gripper)
        {
            Transform existing = gripper.transform.Find("TWINMVP_TCP");
            if (existing != null)
                return existing;
            var anchor = new GameObject("TWINMVP_TCP").transform;
            anchor.SetParent(gripper.transform, true);
            anchor.position = (gripper.DriverJaw.position + gripper.FollowerJaw.position) * 0.5f;
            anchor.rotation = gripper.transform.rotation;
            return anchor;
        }

        [ContextMenu("TWIN MVP/Run First Part With Vision")]
        void RunFirstWithVision() => ScanAndAssemble(0);

        [ContextMenu("TWIN MVP/Run All Parts With Vision")]
        void RunAllWithVision() => ScanAndAssemble(0, true);

        [ContextMenu("TWIN MVP/Run First Part (Skip Vision)")]
        void RunFirstWithoutVision() => AssembleFromKnownPoint(0);

        [ContextMenu("TWIN MVP/Validate Scenario")]
        void ValidateScenario()
        {
            bool valid = depthCamera != null && vision != null && moveIt != null &&
                robot != null && wrist != null && carryAnchor != null && jobs.Length > 0;
            for (int i = 0; i < jobs.Length; i++)
                valid &= jobs[i] != null && jobs[i].part != null &&
                    jobs[i].scanPoint != null && jobs[i].placeTarget != null;
            Debug.Assert(valid, "TWIN MVP assembly references are incomplete.", this);
        }

        [ContextMenu("TWIN MVP/Run Local Pose Check")]
        void RunLocalPoseCheck()
        {
            if (!TryGetJob(currentIndex, out PartJob job) || wrist == null || carryAnchor == null)
                return;
            Vector3 desired = job.scanPoint.position + Vector3.up * graspHeight;
            Pose pose = WristPoseForTcp(desired, wrist.rotation);
            Vector3 reconstructed = pose.position + pose.rotation *
                wrist.InverseTransformPoint(carryAnchor.position);
            Debug.Assert(Vector3.Distance(desired, reconstructed) < 0.0001f,
                "TCP-to-wrist pose conversion failed.", this);
        }
    }
}
