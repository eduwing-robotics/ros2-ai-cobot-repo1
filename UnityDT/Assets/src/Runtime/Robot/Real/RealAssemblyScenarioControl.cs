using System;
using System.Threading.Tasks;
using MainUnity.Runtime.Robot.Interface;
using MainUnity.Static;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Real
{
    /// <summary>Real 환경의 Scenario 명령을 ROS 작업 노드 경계로 전달한다.</summary>
    public sealed class RealAssemblyScenarioControl : MonoBehaviour, IRobotScenarioControl
    {
        [SerializeField] ItemManager itemManager;

        /// <summary>Backend가 확인한 Unit 투입을 공통 씬 객체 관리에 반영한다. 설비를 구동하지 않는다.</summary>
        public Transform BeginUnit(string jobId, long unitId)
        {
            if (itemManager == null)
                throw new InvalidOperationException("Assign the shared ItemManager.");
            return itemManager.BeginUnit(jobId, unitId);
        }

        /// <summary>Backend가 확인한 Unit 완료를 반영하고 기판과 장착 부품을 보존한다.</summary>
        public void CompleteUnit(string jobId, long unitId)
        {
            if (itemManager == null)
                throw new InvalidOperationException("Assign the shared ItemManager.");
            itemManager.CompleteUnit(jobId, unitId);
        }

        /// <summary>Real 조립 노드의 완료 계약이 연결되지 않아 실행 요청은 실패한다.</summary>
        public Task ExecuteAsync() =>
            Task.FromException(new NotSupportedException(
                "REAL assembly requires a configured ROS assembly node."));

        public Task ExecuteQueuedAsync(string jobId) => ExecuteAsync();

        public Task PauseAsync() =>
            Task.FromException(new NotSupportedException(
                "REAL pause requires the approved FAIRINO state feedback contract."));

        public Task ResumeAsync() =>
            Task.FromException(new NotSupportedException(
                "REAL resume requires the approved FAIRINO state feedback contract."));
    }
}
