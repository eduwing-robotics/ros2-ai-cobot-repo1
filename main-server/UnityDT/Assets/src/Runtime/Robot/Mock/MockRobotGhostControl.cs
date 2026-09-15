using MainUnity.Runtime.Robot.Interface;
using MainUnity.Runtime.RobotGhost;
using RosMessageTypes.Trajectory;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Mock
{
    [DisallowMultipleComponent]
    public sealed class MockRobotGhostControl : MonoBehaviour, IRobotGhostControl
    {
        [SerializeField] string destinationTopic = "/twin_visual/movel_preview";

        ROSConnection connection;
        GhostMaster ghostMaster;
        bool subscribed;

        void OnDisable() => Unsubscribe();

        public bool Initialize(GhostMaster destination)
        {
            ghostMaster = destination;
            if (ghostMaster != null)
                return true;
            Debug.LogError("Assign the common GhostMaster.", this);
            return false;
        }

        public void SetActive(bool active)
        {
            enabled = active;
            if (active)
                Subscribe();
            else
                Unsubscribe();
        }

        void Subscribe()
        {
            if (subscribed || ghostMaster == null)
                return;
            if (string.IsNullOrWhiteSpace(destinationTopic))
            {
                Debug.LogError("Ghost destination topic is required.", this);
                return;
            }

            connection ??= ROSConnection.GetOrCreateInstance();
            connection.Subscribe<JointTrajectoryMsg>(destinationTopic, ReceiveDestination);
            subscribed = true;
        }

        void Unsubscribe()
        {
            if (!subscribed || connection == null)
                return;
            connection.Unsubscribe(destinationTopic);
            subscribed = false;
        }

        void ReceiveDestination(JointTrajectoryMsg trajectory)
        {
            if (ghostMaster.ShowDestination(trajectory))
                ghostMaster.SetVisible(true);
            else
                Debug.LogWarning("Mock Ghost rejected the destination trajectory.", this);
        }
    }
}
