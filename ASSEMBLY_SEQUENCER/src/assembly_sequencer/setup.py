from glob import glob

from setuptools import find_packages, setup


PACKAGE_NAME = "assembly_sequencer"


setup(
    name=PACKAGE_NAME,
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{PACKAGE_NAME}"]),
        (f"share/{PACKAGE_NAME}", ["package.xml"]),
        (f"share/{PACKAGE_NAME}/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="codlab",
    maintainer_email="codlab@example.com",
    description="Independent Mock/Real assembly orchestration and DB writer.",
    license="Proprietary",
    entry_points={
        "console_scripts": [
            "mock_node = assembly_sequencer.mock_node:main",
        ],
    },
)
