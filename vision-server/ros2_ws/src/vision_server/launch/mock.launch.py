from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    scenario = LaunchConfiguration('scenario')
    return LaunchDescription([
        DeclareLaunchArgument(
            'scenario',
            default_value='pass',
            description='pass, missing_hbm, extra_gpu, low_score_hbm, or unknown',
        ),
        Node(
            package='vision_server',
            executable='vision_mock',
            name='vision_mock',
            output='screen',
            parameters=[{'scenario': scenario}],
        ),
        Node(
            package='vision_server',
            executable='assembly_inspector',
            name='assembly_inspector',
            output='screen',
            parameters=[{'auto': True}],
        ),
    ])
