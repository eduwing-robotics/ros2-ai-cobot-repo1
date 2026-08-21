// 역할: 선택된 상태 소스와 상태 관리자, 그리퍼 상태 컴포넌트의 이벤트 연결을 오케스트레이션한다.

using MainUnity.Runtime.Robot.Interface;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Status
{
    [DisallowMultipleComponent]
    public sealed class RobotStatusMaster : MonoBehaviour
    {
        [SerializeField] GripperSubscriber gripperSubscriber;
        [SerializeField] RobotStatusManager statusManager;

        IRobotStateSource stateSource;
        bool bound;

        public RobotStatusManager StatusManager => statusManager;

        /// <summary>공통 그리퍼 상태 컴포넌트다. UI는 씬을 뒤지지 말고 이 경로로 받는다.</summary>
        public GripperSubscriber Gripper => gripperSubscriber;

        void Awake() => RefreshReferences();
        void OnEnable()
        {
            RefreshReferences();
            Bind();
        }
        void OnDisable() => Unbind();
        void OnValidate() => RefreshReferences();

        /// <summary>RobotMaster가 선택한 상태 소스를 연결한다.</summary>
        public void Initialize(IRobotStateSource selectedStateSource)
        {
            if (ReferenceEquals(stateSource, selectedStateSource))
                return;
            Unbind();
            stateSource = selectedStateSource;
            if (isActiveAndEnabled)
                Bind();
        }

        /// <summary>같은 오브젝트와 자식 계층에서 공통 상태 컴포넌트 참조를 다시 찾는다.</summary>
        public void RefreshReferences()
        {
            if (gripperSubscriber == null)
                gripperSubscriber = GetComponentInChildren<GripperSubscriber>(true);
            if (statusManager == null)
                statusManager = GetComponentInChildren<RobotStatusManager>(true);
        }

        void Bind()
        {
            if (bound || stateSource == null)
                return;
            if (statusManager != null) stateSource.StateReceived += statusManager.ApplyState;
            if (statusManager != null) stateSource.ErrorReceived += statusManager.ReportError;
            if (gripperSubscriber != null) stateSource.StateReceived += gripperSubscriber.ApplyState;
            bound = true;
            stateSource.StartSubscription();
        }

        void Unbind()
        {
            if (!bound || stateSource == null)
                return;
            if (statusManager != null) stateSource.StateReceived -= statusManager.ApplyState;
            if (statusManager != null) stateSource.ErrorReceived -= statusManager.ReportError;
            if (gripperSubscriber != null) stateSource.StateReceived -= gripperSubscriber.ApplyState;
            stateSource.StopSubscription();
            bound = false;
        }

        /// <summary>현재 로봇 상태가 새 명령을 받을 수 있는지 상태 관리자에 확인한다.</summary>
        public bool CanAcceptCommand(out string reason)
        {
            if (statusManager != null)
                return statusManager.CanAcceptCommand(out reason);
            reason = "RobotStatusManager is not assigned.";
            return false;
        }
    }
}
