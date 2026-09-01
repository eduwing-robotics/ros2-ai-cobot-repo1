"""Compatibility launch path for the AssemblySequencer-owned Mock stack."""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    package_share = get_package_share_directory("assembly_sequencer")
    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                f"{package_share}/launch/mock.launch.py"
            )
        ),
    ])
