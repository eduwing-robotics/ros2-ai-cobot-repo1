"""Start MainServer and its defect-report worker in Mock mode."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, SetEnvironmentVariable
from launch.substitutions import EnvironmentVariable, FindExecutable, LaunchConfiguration, PythonExpression


def generate_launch_description():
    return LaunchDescription([
        SetEnvironmentVariable("ROS_DOMAIN_ID", "42"),
        SetEnvironmentVariable("MAIN_SERVER_MODE", "mock"),
        DeclareLaunchArgument("main_server_db_dsn", default_value=EnvironmentVariable("MAIN_SERVER_DB_DSN", default_value="")),
        DeclareLaunchArgument("main_server_script", default_value="MAIN_SERVER/server.py"),
        DeclareLaunchArgument("defect_report_script", default_value="MAIN_SERVER/generate_defect_reports.py"),
        DeclareLaunchArgument("defect_mail_enabled", default_value=EnvironmentVariable("DEFECT_MAIL_ENABLED", default_value="false")),
        ExecuteProcess(
            cmd=[FindExecutable(name="python3"), LaunchConfiguration("main_server_script")],
            additional_env={"MAIN_SERVER_MODE": "mock", "MAIN_SERVER_DB_DSN": LaunchConfiguration("main_server_db_dsn")},
            output="screen",
        ),
        ExecuteProcess(
            cmd=[FindExecutable(name="python3"), LaunchConfiguration("defect_report_script"), "--watch", "--mode",
                 PythonExpression(["'email' if '", LaunchConfiguration("defect_mail_enabled"), "'.lower() in ('true', '1') else 'local'"])],
            additional_env={"MAIN_SERVER_MODE": "mock", "MAIN_SERVER_DB_DSN": LaunchConfiguration("main_server_db_dsn")},
            output="screen",
        ),
    ])
