from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    namespace = LaunchConfiguration("namespace")
    config_file = LaunchConfiguration("config_file")
    joy_topic = LaunchConfiguration("joy_topic")
    event_topic = LaunchConfiguration("event_topic")

    default_config_file = PathJoinSubstitution(
        [FindPackageShare("siyi_control"), "config", "siyi_control.yaml"]
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "namespace",
                default_value="",
                description="Optional ROS namespace for the SIYI controller node.",
            ),
            DeclareLaunchArgument(
                "config_file",
                default_value=default_config_file,
                description="Path to the SIYI controller parameter YAML.",
            ),
            DeclareLaunchArgument(
                "joy_topic",
                default_value="joy",
                description="Joy topic name. Relative by default, absolute allowed.",
            ),
            DeclareLaunchArgument(
                "event_topic",
                default_value="siyi_event",
                description="String event topic name. Relative by default.",
            ),
            Node(
                package="siyi_control",
                executable="sbus_node",
                name="siyi_controller",
                namespace=namespace,
                output="screen",
                parameters=[
                    config_file,
                    {
                        "joy_topic": joy_topic,
                        "event_topic": event_topic,
                    },
                ],
                respawn=True,
                respawn_delay=1.0,
            ),
        ]
    )
