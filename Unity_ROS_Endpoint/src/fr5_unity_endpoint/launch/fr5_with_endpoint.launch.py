from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    endpoint_ip = LaunchConfiguration("endpoint_ip")
    endpoint_port = LaunchConfiguration("endpoint_port")
    moveit_share = get_package_share_directory("fr5_moveit_mvp")

    return LaunchDescription(
        [
            DeclareLaunchArgument("endpoint_ip", default_value="0.0.0.0"),
            DeclareLaunchArgument("endpoint_port", default_value="10000"),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    f"{moveit_share}/launch/fr5_mvp.launch.py"
                )
            ),
            Node(
                package="ros_tcp_endpoint",
                executable="default_server_endpoint",
                name="UnityEndpoint",
                output="screen",
                parameters=[
                    {"ROS_IP": endpoint_ip},
                    {
                        "ROS_TCP_PORT": ParameterValue(
                            endpoint_port, value_type=int
                        )
                    },
                ],
            ),
        ]
    )
