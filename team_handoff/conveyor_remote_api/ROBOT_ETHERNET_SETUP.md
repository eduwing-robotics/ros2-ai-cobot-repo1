# TurtleBot 유선 경로 추가 절차

현재 노트북의 유선 포트는 `enp129s0=10.77.5.1/30`이고 Wi-Fi는
`wlo1=192.168.11.4/24`, 기본 경로 `192.168.11.1`을 유지하고 있다. 로봇의
Ethernet 포트에 `10.77.5.2/30`을 추가하면 두 장치 사이의 ROS/SSH 유선 경로를
검증할 수 있다. 이 절차는 Wi-Fi를 끄거나 Wi-Fi 기본 경로를 바꾸지 않는다.

현재 노트북에서 `musk@192.168.11.101` SSH는 호스트까지 도달하지만 등록된 키
인증이 거부되어 원격 적용을 완료하지 못했다. 아래 명령은 로봇의 로컬 콘솔에서
한 번 실행하거나, 인증이 복구된 뒤 SSH로 실행한다.

## 로봇 콘솔에서 확인

```bash
nmcli device status 2>/dev/null || true
ip -br link
ip -br addr
ip route
```

`TYPE`이 `ethernet`이고 `STATE`가 `disconnected`인 장치명을 확인한다(예:
`eth0` 또는 `enx...`). Wi-Fi 장치와 연결 이름은 그대로 둔다.

## NetworkManager 사용 시

아래의 `ETH_IF`만 앞 단계에서 확인한 실제 Ethernet 장치명으로 바꾼다.

```bash
ETH_IF=eth0
CON_NAME=KSMC-wired

if nmcli -t -f NAME con show | grep -Fxq "${CON_NAME}"; then
  sudo nmcli con mod "${CON_NAME}" \
    connection.interface-name "${ETH_IF}" \
    ipv4.method manual ipv4.addresses 10.77.5.2/30 \
    ipv4.never-default yes ipv6.method disabled \
    connection.autoconnect yes
else
  sudo nmcli con add type ethernet ifname "${ETH_IF}" con-name "${CON_NAME}" \
    ipv4.method manual ipv4.addresses 10.77.5.2/30 \
    ipv4.never-default yes ipv6.method disabled \
    connection.autoconnect yes
fi
sudo nmcli con up "${CON_NAME}"
```

`ipv4.never-default yes`가 로봇 Wi-Fi의 기본 경로를 보존한다. `nmcli radio
wifi off`, Wi-Fi 연결 삭제, `ip route del default`는 실행하지 않는다.

## 유선 연결과 Wi-Fi SSH 확인

노트북에서 다음을 실행한다.

```bash
ping -I enp129s0 -c 3 10.77.5.2
ssh -o BindAddress=10.77.5.1 musk@10.77.5.2 'hostname; ip -br addr; ip route'
ssh musk@192.168.11.101 'hostname'
```

첫 번째 SSH가 유선으로 성공하고 세 번째 SSH도 성공해야 한다. 세 번째가
성공하면 Wi-Fi를 유지한 상태에서 나중에 유선 SSH가 끊겨도 기존 관리 경로를
사용할 수 있다. 유선 주소가 응답하지 않으면 로봇 Ethernet 포트의 링크 LED,
케이블, `ETH_IF` 이름을 먼저 확인한다.

## ROS를 유선으로 검증

양쪽에서 ROS domain과 Fast DDS 프로파일을 동일하게 유지한 채 로봇 bringup을
재시작한다. 노트북에서 다음을 읽기 전용으로 확인한다.

```bash
ros2 topic info /cmd_vel -v
ros2 node info /turtlebot3_node
```

`/cmd_vel`의 TurtleBot subscriber가 보이면 유선 주소 경로가 ROS에 참여한
것이다. Wi-Fi 링크는 SSH를 위해 계속 켜 둔다. 유선 검증 전에는 Fast DDS
allowlist에서 Wi-Fi를 제거하지 않는다. 양쪽 유선 ROS가 확인된 뒤에도 SSH는
Wi-Fi 인터페이스와 별개로 유지된다.

노트북만 먼저 유선 전용 프로파일로 바꾸면 로봇이 아직 Wi-Fi에서만 ROS를
발견하는 동안 통신이 끊길 수 있다. 양쪽 주소와 `/cmd_vel` subscriber를 확인한
뒤에만 `config/fastdds_laptop_wired.xml`을 `KSMC_FASTDDS_PROFILE`로 지정하고,
ROS 카메라/ROI/서버를 재시작한다. 이 변경도 Wi-Fi 장치나 Wi-Fi SSH를 끄는
작업이 아니다.
