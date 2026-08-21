using System;
using MainUnity.Runtime.ConveyBelt;
using MainUnity.Runtime.Robot.Interface;
using UnityEngine;

namespace MainUnity.Runtime.Scenario
{
    public sealed class Scenario : MonoBehaviour
    {
        [SerializeField] ConveyMock conveyBelt;

        IRobotScenarioControl robot;

        /// <summary>RobotMaster가 현재 Mock/Real Scenario 구현을 주입한다.</summary>
        public void Initialize(IRobotScenarioControl robot) =>
            this.robot = robot;

        /// <summary>상위 수준의 제품 이동과 조립 작업만 순서대로 실행한다.</summary>
        [ContextMenu("Run Scenario")]
        public async void Run()
        {
            if (robot == null || conveyBelt == null)
                throw new InvalidOperationException("Scenario dependencies are not initialized.");

            await conveyBelt.MoveBoardToAssemblyAsync();
            await robot.ExecuteAsync();
            await conveyBelt.MoveBoardToInspectionAsync();
            //await resultCheck
            //DB.Update
        }
    }
}
