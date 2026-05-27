from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    namespace = LaunchConfiguration("namespace")
    config_file = LaunchConfiguration("config_file")
    joy_topic = LaunchConfiguration("joy_topic")
    event_topic = LaunchConfiguration("event_topic")
    cmd_vel_topic = LaunchConfiguration("cmd_vel_topic")
    require_enable_button = LaunchConfiguration("require_enable_button")
    enable_button = LaunchConfiguration("enable_button")
    axis_linear_x = LaunchConfiguration("axis_linear_x")
    axis_angular_z = LaunchConfiguration("axis_angular_z")
    scale_linear_x = LaunchConfiguration("scale_linear_x")
    scale_angular_z = LaunchConfiguration("scale_angular_z")

    sbus_launch = PathJoinSubstitution(
        [FindPackageShare("siyi_control"), "launch", "sbus.launch.py"]
    )
    default_config_file = PathJoinSubstitution(
        [FindPackageShare("siyi_control"), "config", "siyi_control.yaml"]
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "namespace",
                default_value="",
                description="Optional ROS namespace for the SIYI controller stack.",
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
            DeclareLaunchArgument(
                "cmd_vel_topic",
                default_value="cmd_vel",
                description="Twist command topic name. Relative by default.",
            ),
            DeclareLaunchArgument(
                "require_enable_button",
                default_value="true",
                description="Whether teleop_twist_joy requires an enable button.",
            ),
            DeclareLaunchArgument(
                "enable_button",
                default_value="0",
                description="Joy button index that enables cmd_vel publishing.",
            ),
            DeclareLaunchArgument(
                "axis_linear_x",
                default_value="1",
                description="Joy axis index mapped to Twist linear.x.",
            ),
            DeclareLaunchArgument(
                "axis_angular_z",
                default_value="0",
                description="Joy axis index mapped to Twist angular.z yaw.",
            ),
            DeclareLaunchArgument(
                "scale_linear_x",
                default_value="0.5",
                description="Maximum linear.x speed when the selected axis is full scale.",
            ),
            DeclareLaunchArgument(
                "scale_angular_z",
                default_value="1.0",
                description="Maximum angular.z speed when the selected axis is full scale.",
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(sbus_launch),
                launch_arguments={
                    "namespace": namespace,
                    "config_file": config_file,
                    "joy_topic": joy_topic,
                    "event_topic": event_topic,
                }.items(),
            ),
            Node(
                package="teleop_twist_joy",
                executable="teleop_node",
                name="siyi_cmd_vel",
                namespace=namespace,
                output="screen",
                remappings=[
                    ("joy", joy_topic),
                    ("cmd_vel", cmd_vel_topic),
                ],
                parameters=[
                    {
                        "require_enable_button": ParameterValue(
                            require_enable_button, value_type=bool
                        ),
                        "enable_button": ParameterValue(enable_button, value_type=int),
                        "axis_linear.x": ParameterValue(
                            axis_linear_x, value_type=int
                        ),
                        "scale_linear.x": ParameterValue(
                            scale_linear_x, value_type=float
                        ),
                        "axis_angular.yaw": ParameterValue(
                            axis_angular_z, value_type=int
                        ),
                        "scale_angular.yaw": ParameterValue(
                            scale_angular_z, value_type=float
                        ),
                    }
                ],
                respawn=True,
                respawn_delay=1.0,
            ),
        ]
    )
