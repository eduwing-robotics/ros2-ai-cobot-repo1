using System;
using System.Threading.Tasks;
using MainUnity.Runtime.Robot.Interface;
using UnityEngine;

namespace MainUnity.Runtime.Scenario
{
    public sealed class Scenario : MonoBehaviour
    {
        IRobotScenarioControl robot;
        bool running;

        public bool IsRunning => running;

        /// <summary>RobotMaster가 현재 Mock/Real Scenario 구현을 주입한다.</summary>
        public void Initialize(IRobotScenarioControl robot) =>
            this.robot = robot;

        /// <summary>상위 수준의 제품 이동과 조립 작업만 순서대로 실행한다.</summary>
        [ContextMenu("Run Scenario")]
        public async Task Run()
        {
            if (robot == null)
                throw new InvalidOperationException("Scenario dependencies are not initialized.");
            if (running)
                throw new InvalidOperationException("Scenario is already running.");

            running = true;
            try
            {
                await robot.ExecuteAsync();
            }
            finally
            {
                running = false;
            }
        }

        public Task PauseAsync()
        {
            if (!running || robot == null)
                throw new InvalidOperationException("Scenario is not running.");
            return robot.PauseAsync();
        }

        public Task ResumeAsync()
        {
            if (!running || robot == null)
                throw new InvalidOperationException("Scenario is not running.");
            return robot.ResumeAsync();
        }
    }
}
