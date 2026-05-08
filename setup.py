from glob import glob
from setuptools import find_packages, setup

package_name = "siyi_control"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/config", glob("config/*.yaml")),
        (f"share/{package_name}/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="hdwook",
    maintainer_email="hdwook@todo.todo",
    description="Minimal ROS2 wrapper for SIYI SBUS controller input.",
    license="TODO",
    entry_points={
        "console_scripts": [
            "sbus_node = siyi_control.sbus_node:main",
            "sbus_cli = siyi_control.sbus_cli:main",
        ],
    },
)
