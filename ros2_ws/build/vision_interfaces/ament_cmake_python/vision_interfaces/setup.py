from setuptools import find_packages
from setuptools import setup

setup(
    name='vision_interfaces',
    version='0.1.0',
    packages=find_packages(
        include=('vision_interfaces', 'vision_interfaces.*')),
)
