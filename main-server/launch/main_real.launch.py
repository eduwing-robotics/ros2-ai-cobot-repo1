"""Start MainServer and its defect-report worker in Real mode."""

import json
import os
from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, SetEnvironmentVariable
from launch.substitutions import EnvironmentVariable, FindExecutable, LaunchConfiguration, PythonExpression


def generate_launch_description():
    config_path = Path(__file__).with_name(".env.real")
    environment = {}
    if config_path.exists():
        if config_path.stat().st_uid != os.getuid() or config_path.stat().st_mode & 0o077:
            raise RuntimeError(f"{config_path}: current-user ownership and chmod 600 are required")
        environment = json.loads(config_path.read_text())
        if not isinstance(environment, dict) or any(
            key not in {"MAIN_SERVER_DB_DSN", "PRODUCTION_DB_DSN", "DEFECT_IMAGE_ROOT"}
            or not isinstance(value, str) for key, value in environment.items()
        ):
            raise RuntimeError(f"{config_path}: invalid runtime environment")
    return LaunchDescription([
        *[SetEnvironmentVariable(key, EnvironmentVariable(key, default_value=value))
          for key, value in environment.items() if key in {"MAIN_SERVER_DB_DSN", "DEFECT_IMAGE_ROOT"}],
        SetEnvironmentVariable("ROS_DOMAIN_ID", "5"),
        SetEnvironmentVariable("MAIN_SERVER_MODE", "real"),
        DeclareLaunchArgument("main_server_db_dsn", default_value=EnvironmentVariable("MAIN_SERVER_DB_DSN", default_value="")),
        DeclareLaunchArgument("main_server_script", default_value="MAIN_SERVER/server.py"),
        DeclareLaunchArgument("defect_report_script", default_value="MAIN_SERVER/generate_defect_reports.py"),
        DeclareLaunchArgument("defect_mail_enabled", default_value=EnvironmentVariable("DEFECT_MAIL_ENABLED", default_value="false")),
        ExecuteProcess(
            cmd=[FindExecutable(name="python3"), LaunchConfiguration("main_server_script")],
            additional_env={"MAIN_SERVER_MODE": "real", "MAIN_SERVER_DB_DSN": LaunchConfiguration("main_server_db_dsn")},
            output="screen",
        ),
        ExecuteProcess(
            cmd=[FindExecutable(name="python3"), LaunchConfiguration("defect_report_script"), "--watch", "--mode",
                 PythonExpression(["'email' if '", LaunchConfiguration("defect_mail_enabled"), "'.lower() in ('true', '1') else 'local'"])],
            additional_env={"MAIN_SERVER_MODE": "real", "MAIN_SERVER_DB_DSN": LaunchConfiguration("main_server_db_dsn")},
            output="screen",
        ),
    ])
