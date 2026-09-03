from glob import glob
from setuptools import find_packages, setup


package_name = 'vision_server'


setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'README.md']),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/models', glob('models/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Project Team',
    maintainer_email='project@example.com',
    description='AI/Vision server for the assembly cell',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'camera_manager = vision_server.camera_manager:main',
            'part_detector = vision_server.part_detector:main',
            'assembly_inspector = vision_server.assembly_inspector:main',
            'conveyor_roi = vision_server.conveyor_roi:main',
            'conveyor_controller = vision_server.conveyor_controller:main',
            'vision_mock = vision_server.vision_mock:main',
            'orchestration_action_server = vision_server.orchestration_action_server:main',
        ],
    },
)
