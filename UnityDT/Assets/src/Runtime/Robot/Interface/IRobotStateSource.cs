// 역할: Mock과 실제 FAIRINO 상태 수신 구현이 제공해야 하는 공통 계약을 정의한다.

using System;
using MainUnity.Runtime.Robot.Status;

namespace MainUnity.Runtime.Robot.Interface
{
    /// <summary>
    /// ROS 토픽과 메시지 형식에 관계없이 로봇 상태를 공통 형식으로 전달한다.
    /// RobotStatusFrame의 선형 위치·거리는 mm, 회전은 deg 단위를 사용한다.
    /// </summary>
    public interface IRobotStateSource
    {
        /// <summary>검증과 변환이 완료된 최신 로봇 상태를 전달한다.</summary>
        event Action<RobotStatusFrame> StateReceived;

        /// <summary>연결 또는 수신 데이터 오류를 전달한다.</summary>
        event Action<RobotErrorLabel, string> ErrorReceived;

        /// <summary>선택된 상태 소스의 구독을 시작한다.</summary>
        bool StartSubscription();

        /// <summary>현재 상태 소스의 구독을 중단한다.</summary>
        void StopSubscription();
    }
}
