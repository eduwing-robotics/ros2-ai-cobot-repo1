// 관절 하나에 위치와 속도 명령을 적용합니다.

using System;
using UnityEngine;

namespace FR5Mvp.RobotControl
{
    /// <summary>관절 명령을 Unity ArticulationBody drive에 적용합니다.</summary>
    [DisallowMultipleComponent]
    public sealed class JointDrive : MonoBehaviour
    {
        [SerializeField, HideInInspector] ArticulationBody articulationBody;
        [SerializeField, HideInInspector] float positionStiffness;
        [SerializeField, HideInInspector] float positionDamping;

        ArticulationBody Body => articulationBody != null
            ? articulationBody
            : articulationBody = GetComponent<ArticulationBody>();

        public bool IsBound => Body != null;
        public float ActualDegrees => Body != null && Body.dofCount > 0
            ? Body.jointPosition[0] * Mathf.Rad2Deg
            : 0f;
        public float ActualVelocityDegreesPerSecond => Body != null && Body.dofCount > 0
            ? Body.jointVelocity[0] * Mathf.Rad2Deg
            : 0f;

        public static JointDrive Attach(
            JointController joint,
            ArticulationBody body)
        {
            if (joint == null)
                throw new ArgumentNullException(nameof(joint));
            JointDrive drive = joint.GetComponent<JointDrive>();
            if (drive == null)
                drive = joint.gameObject.AddComponent<JointDrive>();
            drive.Bind(body);
            joint.UseDrive(drive);
            return drive;
        }

        void Bind(ArticulationBody body)
        {
            articulationBody = body != null
                ? body
                : throw new ArgumentNullException(nameof(body));
            ArticulationDrive drive = body.xDrive;
            positionStiffness = drive.stiffness;
            positionDamping = drive.damping;
        }

        public void SetPositionDegrees(float degrees)
        {
            ArticulationDrive drive = Body.xDrive;
            drive.stiffness = positionStiffness;
            drive.damping = positionDamping;
            drive.targetVelocity = 0f;
            drive.target = degrees;
            Body.xDrive = drive;
        }

        public void SetVelocityDegreesPerSecond(float degreesPerSecond)
        {
            ArticulationDrive drive = Body.xDrive;
            drive.stiffness = 0f;
            drive.damping = positionDamping;
            drive.targetVelocity = degreesPerSecond * Mathf.Deg2Rad;
            Body.xDrive = drive;
        }
    }
}
