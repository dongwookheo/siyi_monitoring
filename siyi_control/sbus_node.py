import threading
import time
from typing import Optional

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from std_msgs.msg import String

from siyi_control.mapping import (
    AxisMapping,
    ButtonMapping,
    ButtonStateTracker,
    JoyCalibration,
    build_joy_vectors,
    zero_joy,
)
from siyi_control.processor import SignalProcessor
from siyi_control.sbus import SBUSReceiver


class SiyiSbusNode(Node):
    """RC 채널 데이터 -> Joy 메시지 변환 노드"""

    def __init__(self):
        """노드 초기화"""
        super().__init__("siyi_controller")

        self._declare_parameters()
        self._load_parameters()

        self.joy_pub = self.create_publisher(Joy, self.joy_topic, 10)
        self.event_pub = self.create_publisher(String, self.event_topic, 10)

        self.receiver: Optional[SBUSReceiver] = None
        self.processor = SignalProcessor(window_size=self.filter_window_size)
        self.button_tracker = ButtonStateTracker(
            button_count=self.button_count,
            button_names=self.button_names_by_index,
        )

        self.last_input_time: Optional[float] = None
        self.next_connect_time = 0.0
        self.timed_out = False
        self.failsafe_active = False
        self.frame_lost_active = False
        self.running = True

        self._connect()
        self.data_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.data_thread.start()
        self.timeout_timer = self.create_timer(0.02, self._check_timeout)

    def _declare_parameters(self) -> None:
        """매개변수 선언 및 기본값 설정 함수"""
        self.declare_parameter("serial_port", "/dev/ttyUSB0")
        self.declare_parameter("serial_baudrate", 100000)
        self.declare_parameter("serial_timeout", 0.0)
        self.declare_parameter("idle_sleep_sec", 0.1)  # SBUS 수신 실패시 대기 시간
        self.declare_parameter("filter_window_size", 9)

        self.declare_parameter("joy_topic", "joy")
        self.declare_parameter("event_topic", "siyi_event")
        self.declare_parameter("publish_events", True)

        self.declare_parameter("axis_count", 6)
        self.declare_parameter("button_count", 16)
        self.declare_parameter("axis_indices", [0, 1, 2, 5])
        self.declare_parameter("axis_channels", [4, 3, 1, 2])
        self.declare_parameter("axis_scales", [1.0, 1.0, 1.0, 1.0])

        self.declare_parameter("joy_min_value", 272)
        self.declare_parameter("joy_mid_value", 992)
        self.declare_parameter("joy_max_value", 1712)
        self.declare_parameter("joy_deadband", 0.05)  # Joy 중앙 허용 오차 범위

        self.declare_parameter("button_indices", [0, 1, 2, 3, 4])
        self.declare_parameter("button_channels", [15, 16, 12, 13, 14])
        self.declare_parameter("button_names", ["l1", "l2", "r1", "r2", "r3"])
        self.declare_parameter("button_pressed_min", 1500)
        self.declare_parameter("button_pressed_mins", [0, 0, 0, 0, 0])
        self.declare_parameter("button_event_format", "semantic")

        self.declare_parameter("input_timeout_ms", 100.0)
        self.declare_parameter("reconnect_interval_sec", 1.0)  # 재연결 시도 간격
        self.declare_parameter("log_raw_channels", False)  # 원시 채널 로깅 여부

    def _load_parameters(self) -> None:
        self.serial_port = str(self.get_parameter("serial_port").value)
        self.serial_baudrate = int(self.get_parameter("serial_baudrate").value)
        self.serial_timeout = float(self.get_parameter("serial_timeout").value)
        self.idle_sleep_sec = max(
            0.0, float(self.get_parameter("idle_sleep_sec").value)
        )
        self.filter_window_size = int(self.get_parameter("filter_window_size").value)

        self.joy_topic = str(self.get_parameter("joy_topic").value)
        self.event_topic = str(self.get_parameter("event_topic").value)
        self.publish_events = bool(self.get_parameter("publish_events").value)

        self.axis_count = int(self.get_parameter("axis_count").value)
        self.button_count = int(self.get_parameter("button_count").value)
        self.axis_mappings = self._load_axis_mappings()
        self.button_pressed_min = int(self.get_parameter("button_pressed_min").value)
        self.button_mappings = self._load_button_mappings()
        self.button_names_by_index = {
            mapping.button: mapping.name
            for mapping in self.button_mappings
            if mapping.name
        }
        self.button_event_format = str(
            self.get_parameter("button_event_format").value
        ).lower()
        if self.button_event_format not in {"semantic", "indexed", "both"}:
            self.get_logger().warn(
                "Invalid button_event_format="
                f"{self.button_event_format!r}; falling back to 'semantic'"
            )
            self.button_event_format = "semantic"

        self.calibration = JoyCalibration(
            min_value=int(self.get_parameter("joy_min_value").value),
            mid_value=int(self.get_parameter("joy_mid_value").value),
            max_value=int(self.get_parameter("joy_max_value").value),
            deadband=float(self.get_parameter("joy_deadband").value),
        )
        self.input_timeout_sec = (
            float(self.get_parameter("input_timeout_ms").value) / 1000.0
        )
        self.reconnect_interval_sec = float(
            self.get_parameter("reconnect_interval_sec").value
        )
        self.log_raw_channels = bool(self.get_parameter("log_raw_channels").value)

    def _load_axis_mappings(self) -> list[AxisMapping]:
        indices = self._int_list_parameter("axis_indices")
        channels = self._int_list_parameter("axis_channels")
        scales = self._float_list_parameter("axis_scales")

        mappings = []
        for idx, axis in enumerate(indices):
            if idx >= len(channels):
                break
            scale = scales[idx] if idx < len(scales) else 1.0
            mappings.append(AxisMapping(axis=axis, channel=channels[idx], scale=scale))
        return mappings

    def _load_button_mappings(self) -> list[ButtonMapping]:
        indices = self._int_list_parameter("button_indices")
        channels = self._int_list_parameter("button_channels")
        names = self._str_list_parameter("button_names")
        pressed_mins = self._int_list_parameter("button_pressed_mins")

        mappings = []
        for idx, button in enumerate(indices):
            if idx >= len(channels):
                break
            name = names[idx] if idx < len(names) else ""
            pressed_min = (
                pressed_mins[idx]
                if idx < len(pressed_mins) and pressed_mins[idx] > 0
                else None
            )
            mappings.append(
                ButtonMapping(
                    button=button,
                    channel=channels[idx],
                    name=name,
                    pressed_min=pressed_min,
                )
            )
        return mappings

    def _int_list_parameter(self, name: str) -> list[int]:
        value = self.get_parameter(name).value
        return [int(item) for item in value]

    def _float_list_parameter(self, name: str) -> list[float]:
        value = self.get_parameter(name).value
        return [float(item) for item in value]

    def _str_list_parameter(self, name: str) -> list[str]:
        value = self.get_parameter(name).value
        return [str(item) for item in value]

    def _connect(self) -> None:
        now = self._now_sec()
        if now < self.next_connect_time:
            return

        try:
            self.receiver = SBUSReceiver(
                port=self.serial_port,
                baudrate=self.serial_baudrate,
                timeout=self.serial_timeout,
            )
            self.get_logger().info(f"Connected to SIYI SBUS on {self.serial_port}")
            self._publish_event("sbus_connected")
        except Exception as exc:
            self.receiver = None
            self.next_connect_time = now + self.reconnect_interval_sec
            self.get_logger().warn(f"Failed to open {self.serial_port}: {exc}")

    def _read_loop(self) -> None:
        while self.running and rclpy.ok():
            now = self._now_sec()

            if self.receiver is None:
                self._connect()
                time.sleep(self.idle_sleep_sec)
                continue

            try:
                frame = self.receiver.read_latest()
            except Exception as exc:
                self.get_logger().error(f"SBUS read failed: {exc}")
                self._close_receiver()
                self._publish_event("sbus_disconnected")
                time.sleep(self.idle_sleep_sec)
                continue

            if frame is None:
                time.sleep(self.idle_sleep_sec)
                continue

            self._process_frame(frame, now)

    def _process_frame(self, frame, now: float) -> None:
        if self.log_raw_channels:
            self.get_logger().info(f"channels={frame.channels} flags={frame.flags}")

        if frame.failsafe:
            if not self.failsafe_active:
                self.get_logger().warn("SBUS failsafe flag is active")
                self._publish_event("sbus_failsafe")
            self.failsafe_active = True
            self._publish_zero_joy()
            return

        if self.failsafe_active:
            self.get_logger().info("SBUS failsafe cleared")
            self._publish_event("sbus_failsafe_cleared")
            self.failsafe_active = False

        if frame.frame_lost and not self.frame_lost_active:
            self.get_logger().warn("SBUS frame_lost flag is active")
            self._publish_event("sbus_frame_lost")
        elif not frame.frame_lost and self.frame_lost_active:
            self._publish_event("sbus_frame_lost_cleared")
        self.frame_lost_active = frame.frame_lost

        self.last_input_time = now
        if self.timed_out:
            self.get_logger().info("SBUS input recovered")
            self._publish_event("sbus_input_recovered")
            self.timed_out = False

        filtered = self.processor.apply_filter(frame.channels)
        if filtered is None:
            return

        axes, buttons = build_joy_vectors(
            filtered,
            self.axis_mappings,
            self.button_mappings,
            self.calibration,
            self.axis_count,
            self.button_count,
            self.button_pressed_min,
        )
        self._publish_joy(axes, buttons)
        self._publish_button_events(self.button_tracker.update(buttons))

    def _check_timeout(self) -> None:
        self._handle_input_timeout(self._now_sec())

    def _handle_input_timeout(self, now: float) -> None:
        if self.last_input_time is None:
            return
        if now - self.last_input_time <= self.input_timeout_sec:
            return

        if not self.timed_out:
            self.get_logger().warn(
                f"SBUS input timeout after {self.input_timeout_sec:.3f}s"
            )
            self._publish_event("sbus_input_timeout")
            self.timed_out = True

        self._publish_zero_joy()

    def _publish_joy(self, axes: list[float], buttons: list[int]) -> None:
        msg = Joy()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.axes = axes
        msg.buttons = buttons
        self.joy_pub.publish(msg)

    def _publish_zero_joy(self) -> None:
        axes, buttons = zero_joy(self.axis_count, self.button_count)
        self._publish_joy(axes, buttons)
        self.button_tracker.reset()

    def _publish_button_events(self, events) -> None:
        for event in events:
            for text in self._button_event_texts(event):
                self._publish_event(text)

    def _button_event_texts(self, event) -> list[str]:
        indexed = f"button_{event.button}_{event.event_type}"
        semantic = f"{event.name}_{event.event_type}" if event.name else indexed

        if self.button_event_format == "indexed":
            return [indexed]
        if self.button_event_format == "both" and semantic != indexed:
            return [semantic, indexed]
        return [semantic]

    def _publish_event(self, text: str) -> None:
        if not self.publish_events:
            return
        msg = String()
        msg.data = text
        self.event_pub.publish(msg)

    def _close_receiver(self) -> None:
        if self.receiver is None:
            return
        try:
            self.receiver.close()
        finally:
            self.receiver = None
            self.next_connect_time = self._now_sec() + self.reconnect_interval_sec

    def _now_sec(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def destroy_node(self) -> bool:
        self.running = False
        if hasattr(self, "data_thread") and self.data_thread.is_alive():
            self.data_thread.join(timeout=1.0)
        self._close_receiver()
        return super().destroy_node()


def main(args: Optional[list[str]] = None) -> None:
    rclpy.init(args=args)
    node = SiyiSbusNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
