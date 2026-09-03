"""Start the Mock AIO and MainServer against the same mock database."""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    GroupAction,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import EnvironmentVariable, FindExecutable, LaunchConfiguration


def generate_launch_description():
    sequencer_share = get_package_share_directory("assembly_sequencer")
    production_dsn = LaunchConfiguration("production_db_dsn")

    return LaunchDescription([
        DeclareLaunchArgument("endpoint_ip", default_value="0.0.0.0"),
        DeclareLaunchArgument("endpoint_port", default_value="10000"),
        DeclareLaunchArgument("start_delay", default_value="5"),
        DeclareLaunchArgument("inspection_fail_probability", default_value="0.2"),
        DeclareLaunchArgument("random_seed", default_value="-1"),
        DeclareLaunchArgument(
            "production_db_dsn",
            default_value=EnvironmentVariable("PRODUCTION_DB_DSN", default_value=""),
        ),
        DeclareLaunchArgument(
            "main_server_db_dsn",
            default_value=EnvironmentVariable("MAIN_SERVER_DB_DSN", default_value=""),
        ),
        DeclareLaunchArgument(
            "main_server_script",
            default_value=EnvironmentVariable(
                "MAIN_SERVER_SCRIPT", default_value="MAIN_SERVER/server.py"
            ),
        ),
        GroupAction(scoped=True, actions=[
            SetEnvironmentVariable("PRODUCTION_DB_DSN", production_dsn),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    f"{sequencer_share}/launch/mock.launch.py"
                ),
                launch_arguments={
                    "endpoint_ip": LaunchConfiguration("endpoint_ip"),
                    "endpoint_port": LaunchConfiguration("endpoint_port"),
                    "start_delay": LaunchConfiguration("start_delay"),
                    "inspection_fail_probability": LaunchConfiguration(
                        "inspection_fail_probability"
                    ),
                    "random_seed": LaunchConfiguration("random_seed"),
                }.items(),
            ),
        ]),
        ExecuteProcess(
            cmd=[FindExecutable(name="python3"), LaunchConfiguration("main_server_script")],
            additional_env={
                "MAIN_SERVER_MODE": "mock",
                "MAIN_SERVER_DB_DSN": LaunchConfiguration("main_server_db_dsn"),
            },
            output="screen",
        ),
    ])
