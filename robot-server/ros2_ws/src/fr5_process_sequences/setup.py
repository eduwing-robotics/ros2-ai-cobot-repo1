from setuptools import find_packages, setup


package_name = "fr5_process_sequences"

setup(
    name=package_name,
    version="0.2.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Lucas",
    maintainer_email="lucas@example.com",
    description="Fail-closed Real robot operation backend for the FR5 cell.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "real_robot_api = fr5_process_sequences.real_ros_node:main",
            "real_precision_targets = fr5_process_sequences.real_vision_adapter:main",
        ],
    },
)
