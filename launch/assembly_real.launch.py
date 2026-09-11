"""Start the Real AssemblySequencer without MoveIt or ros2_control."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.substitutions import EnvironmentVariable, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    return LaunchDescription([
        SetEnvironmentVariable("ROS_DOMAIN_ID", "5"),
        SetEnvironmentVariable("ASSEMBLY_SEQUENCER_MODE", "real"),
        DeclareLaunchArgument("start_endpoint", default_value="true"),
        DeclareLaunchArgument("endpoint_ip", default_value="0.0.0.0"),
        DeclareLaunchArgument("endpoint_port", default_value="10000"),
        DeclareLaunchArgument("production_db_dsn", default_value=EnvironmentVariable("PRODUCTION_DB_DSN", default_value="")),
        SetEnvironmentVariable("PRODUCTION_DB_DSN", LaunchConfiguration("production_db_dsn")),
        Node(package="ros_tcp_endpoint", executable="default_server_endpoint", name="UnityEndpoint", output="screen",
             condition=IfCondition(LaunchConfiguration("start_endpoint")),
             parameters=[{"ROS_IP": LaunchConfiguration("endpoint_ip"),
                          "ROS_TCP_PORT": ParameterValue(LaunchConfiguration("endpoint_port"), value_type=int)}]),
        Node(package="assembly_sequencer", executable="sequencer_node", name="assembly_sequencer_real", output="screen"),
    ])
