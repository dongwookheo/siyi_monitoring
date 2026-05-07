# -*- coding: utf-8 -*-
import sys
import time
import queue
import threading
import copy
import tomli as tomllib
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from std_msgs.msg import String, Int32, Bool
from sensor_msgs.msg import Joy


from sbus_receiver import SBUSReceiver
from processor import SignalProcessor
from visualizer import SBUSVisualizer
from shared_sbus import SBUSSharedMemory

# SIYI RC Controller Channel Mapping
# ch1  = "R-Stick L/R"
# ch2  = "R-Stick U/D"
# ch3  = "L-Stick U/D"
# ch4  = "L-Stick L/R"
# ch5  = "Mode Switch (3/6 steps)"
# ch6  = "Left Dial / Left Top Button"
# ch7  = "Right Dial / Right Top Button"
# ch8  = "Left Bottom Button"
# ch9  = "Right Bottom Button"
# ch10 = "L-Switch H/M/L"
# ch11 = "R-Switch H/M/L"
# ch12 = "R1 Button"
# ch13 = "R2 Button"
# ch14 = "R3 Button"

# ch15 = "L1 Button"
# ch16 = "L2 Button"

# ch17 = "Left-Top Button"
# ch18 = "Right-Top Button"
# Default values: [992, 992, 992, 992, 192, 992, 992, 272, 272, 992, 992, 272, 272, 272, 272, 272]


class SIYIState:
    BUTTON_CHANNELS = {
        "l1": 14,
        "l2": 15,
        "r1": 11,
        "r2": 12,
        "r3": 13,
    }

    TRIGGER_VALUES = {
        "HIGH": 1712,
        "LOW": 272,
    }

    # SWITCH_VALUES = {
    #     "low": 192,
    #     "mid": 992,
    #     "high": 1792,
    # }

    def __init__(self):
        self.buttons = {name: False for name in self.BUTTON_CHANNELS}

        # self.modes = {
        #     "m1": False,
        #     "m2": False,
        #     "m3": False,
        #     "m4": False,
        #     "m5": False,
        #     "m6": False,
        # }

    def update_from_channels(self, channels: list[int]):
        if len(channels) < 16:
            return

        # buttons
        for name, ch_idx in self.BUTTON_CHANNELS.items():
            self.buttons[name] = channels[ch_idx] == self.TRIGGER_VALUES["HIGH"]


class SIYIInputHandler:
    """Handles SIYI controller input processing"""

    def __init__(self):
        self.pad = SIYIState()
        self.previous_pad = SIYIState()
        self.channels = [992] * 18

    def update_from_channels(self, channels: list[int]):
        self.previous_pad = copy.deepcopy(self.pad)
        self.pad.update_from_channels(channels)
        self.channels = channels.copy()

    def get_stick_value(self, channel_index: int, normalize=True) -> float:
        if channel_index >= len(self.channels):
            return 0.0

        raw_value = self.channels[channel_index]

        if normalize:
            return (raw_value - 992) / 720.0

        return raw_value

    def is_button_pressed(self, button_name: str) -> bool:
        return self.pad.buttons.get(button_name, False)

    def is_button_released(self, button_name: str) -> bool:
        return not self.pad.buttons.get(button_name, False)

    def is_button_just_pressed(self, button_name: str) -> bool:
        current = self.pad.buttons.get(button_name, False)
        previous = self.previous_pad.buttons.get(button_name, False)
        return current and not previous

    def is_button_just_released(self, button_name: str) -> bool:
        current = self.pad.buttons.get(button_name, False)
        previous = self.previous_pad.buttons.get(button_name, False)
        return not current and previous

    def is_mode(self, mode_name: str) -> bool:
        return self.pad.modes.get(mode_name, False)

    def is_mode_just_changed_to(self, mode_name: str) -> bool:
        current = self.pad.modes.get(mode_name, False)
        previous = self.previous_pad.modes.get(mode_name, False)
        return current and not previous

    def get_active_modes(self) -> list[str]:
        return [name for name, active in self.pad.modes.items() if active]


class RosInterface(Node):
    """ROS2 Node for SIYI Controller"""

    def __init__(self):
        super().__init__("siyi_controller_node")

        self.get_logger().info("SIYI Controller ROS2 Node Initialized")

        # Publishers
        self.event_pub = self.create_publisher(String, "/siyi_event", 10)
        self.joy_pub = self.create_publisher(Joy, "/joy", 10)
        self.job_cmd_pub = self.create_publisher(Int32, "/job_cmd", 10)

    def publish_event(self, event_msg: String):
        self.event_pub.publish(event_msg)

    def publish_joy(self, channels: list[int]):
        joy_msg = Joy()
        joy_msg.header.stamp = self.get_clock().now().to_msg()
        # joy_msg.axes = [0] * 6
        # joy_msg.axes[0] = channels[3]
        # joy_msg.axes[1] = channels[2]
        # joy_msg.axes[2] = channels[0]
        # joy_msg.axes[5] = channels[1]

        # 1712 (1) 992(0) 272(-1)
        # normalize to -1 ~ 1
        joy_msg.axes = [0.0] * 6
        joy_msg.axes[0] = (channels[3] - 992) / 720.0
        joy_msg.axes[1] = (channels[2] - 992) / 720.0
        joy_msg.axes[2] = (channels[0] - 992) / 720.0
        joy_msg.axes[5] = (channels[1] - 992) / 720.0

        joy_msg.buttons = [0] * 16
        joy_msg.buttons[0] = 1
        self.joy_pub.publish(joy_msg)


class RosSpinThread(threading.Thread):
    """Thread to spin ROS node"""

    def __init__(self, node):
        super().__init__(daemon=True)
        self.node = node
        self.running = True
        self.executor = MultiThreadedExecutor()  # to do list
        self.executor.add_node(self.node)

    def run(self):
        """Spin the ROS executor"""
        while self.running and rclpy.ok():
            self.executor.spin_once(timeout_sec=0.1)

    def stop(self):
        """Stop the thread"""
        self.running = False
        self.executor.shutdown()


class SIYIController:
    """Main controller class for SIYI RC integration with ROS2"""

    def __init__(self):
        self.connected = False
        self.running = True

        self.load_cfg()

        self.receiver = SBUSReceiver(**self.cfg["serial"])
        self.processor = SignalProcessor(window_size=self.cfg["filter"]["window_size"])

        self.input_handler = SIYIInputHandler()

        self.ros_node = RosInterface()

        self.ros_thread = RosSpinThread(self.ros_node)
        self.ros_thread.start()

        self.event_queue = queue.Queue()

        # Start threads
        self.data_thread = threading.Thread(target=self.load_data, daemon=True)
        self.data_thread.start()

        self.publish_thread = threading.Thread(target=self.publish_events, daemon=True)
        self.publish_thread.start()

        self.ros_node.get_logger().info("SIYI Controller initialized successfully")

    def load_cfg(self):
        """Load configuration from config.toml"""
        script_location = Path(__file__).resolve()
        project_root = script_location.parent.parent
        config_path = project_root / "config.toml"

        if not config_path.exists():
            config_path = Path("config.toml")
            if not config_path.exists():
                raise FileNotFoundError("config.toml file not found")

        with open(config_path, "rb") as f:
            self.cfg = tomllib.load(f)

    def load_data(self):
        while self.running:
            try:
                frame = self.receiver.get_latest_frame()
                if frame is not None:
                    raw_ch, flags = self.receiver.decode_channels(frame)
                    print(f"Raw Channels: {raw_ch}, Flags: {flags}")
                    if not (flags & 0x0C):  # Quality Check
                        filtered = self.processor.apply_filter(raw_ch)

                        if filtered is not None:
                            self.input_handler.update_from_channels(filtered)
                            self.process_button_events()
                            self.ros_node.publish_joy(filtered)

            except Exception as e:
                self.ros_node.get_logger().error(f"Error in data loop: {e}")
                time.sleep(0.1)

    def process_button_events(self):
        """Process button press/release events and generate ROS events"""

        if self.input_handler.is_button_just_pressed("r1"):
            event = String()
            event.data = "R1 pressed - Example Event"
            self.event_queue.put(event)

        # R2 button - Example: Servo Off
        if self.input_handler.is_button_just_pressed("r2"):
            event = String()
            event.data = "R2 pressed - Example Event"
            self.event_queue.put(event)

        # L1 button - Example: Emergency Stop
        if self.input_handler.is_button_just_pressed("l1"):
            cmd = Int32()
            cmd.data = 2
            self.ros_node.job_cmd_pub.publish(cmd)
            event = String()
            event.data = "L1 pressed - Emergency Stop"
            self.event_queue.put(event)

    def publish_events(self):
        while self.running:
            try:
                event = self.event_queue.get(timeout=0.1)
                self.ros_node.publish_event(event)
            except queue.Empty:
                continue
            except Exception as e:
                self.ros_node.get_logger().error(f"Error publishing event: {e}")

    def stop(self):
        self.ros_node.get_logger().info("Stopping SIYI Controller...")
        self.running = False

        # Stop threads
        if self.data_thread.is_alive():
            self.data_thread.join(timeout=1.0)
        if self.publish_thread.is_alive():
            self.publish_thread.join(timeout=1.0)

        # Stop ROS thread
        self.ros_thread.stop()
        self.ros_thread.join(timeout=1.0)

        self.ros_node.get_logger().info("SIYI Controller stopped")


def main():
    """Main entry point"""
    rclpy.init()

    controller = None

    try:
        controller = SIYIController()
        print("SIYI Controller started. Press Ctrl+C to exit.")

        # Keep main thread alive
        while rclpy.ok():
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        if controller is not None:
            controller.stop()
        rclpy.shutdown()
        sys.exit(0)


if __name__ == "__main__":
    main()
