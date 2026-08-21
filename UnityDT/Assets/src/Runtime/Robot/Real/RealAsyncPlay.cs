using System;
using System.Threading.Tasks;
using MainUnity.Runtime.Robot.Interface;
using UnityEngine;

namespace MainUnity.Runtime.Robot.Real
{
    /// <summary>Real 환경의 Scenario 명령을 ROS 작업 노드 경계로 전달한다.</summary>
    public sealed class RealAsyncPlay : MonoBehaviour, IRobotScenarioControl
    {
        /// <summary>TODO: Real 조립 노드의 작업 완료 callback 계약이 준비되면 구현한다.</summary>
        public Task ExecuteAsync() =>
            Task.FromException(new NotSupportedException(
                "REAL assembly requires a configured ROS assembly node."));
    }
}
