"""Start the Real AssemblySequencer without MoveIt or ros2_control."""

import json
import os
from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.substitutions import EnvironmentVariable, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    config_path = Path(__file__).with_name(".env.real")
    environment = {}
    if config_path.exists():
        if config_path.stat().st_uid != os.getuid() or config_path.stat().st_mode & 0o077:
            raise RuntimeError(f"{config_path}: current-user ownership and chmod 600 are required")
        environment = json.loads(config_path.read_text())
        if not isinstance(environment, dict) or any(
            key not in {"MAIN_SERVER_DB_DSN", "PRODUCTION_DB_DSN", "DEFECT_IMAGE_ROOT", "VISION_BASE_URL", "KSMC_VISION_API_TOKEN"}
            or not isinstance(value, str) for key, value in environment.items()
        ):
            raise RuntimeError(f"{config_path}: invalid runtime environment")
    return LaunchDescription([
        *[SetEnvironmentVariable(key, EnvironmentVariable(key, default_value=value))
          for key, value in environment.items() if key != "MAIN_SERVER_DB_DSN"],
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
