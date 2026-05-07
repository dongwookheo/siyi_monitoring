import argparse
from contextlib import nullcontext
import logging
from pathlib import Path
import time

import yaml
from rich.live import Live

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
from siyi_control.visualizer import SBUSVisualizer


def make_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read SIYI SBUS input without ROS.")
    parser.add_argument("--config", type=Path, default=default_config_path())
    parser.add_argument("--port")
    parser.add_argument("--baudrate", type=int)
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--filter-window-size", type=int)
    parser.add_argument("--idle-sleep-sec", type=float)
    parser.add_argument("--input-timeout-ms", type=float)
    parser.add_argument("--raw", action="store_true", help="Print raw SBUS channels.")
    parser.add_argument("--ui", action="store_true", help="Show a rich live table.")
    return parser


def default_config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "siyi_control.yaml"


def load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"config file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return data.get("siyi_controller", {}).get("ros__parameters", {})


def make_axis_mappings(config: dict) -> list[AxisMapping]:
    indices = config.get("axis_indices", [0, 1, 2, 5])
    channels = config.get("axis_channels", [4, 3, 1, 2])
    scales = config.get("axis_scales", [1.0, 1.0, 1.0, 1.0])

    mappings = []
    for idx, axis in enumerate(indices):
        if idx >= len(channels):
            break
        scale = scales[idx] if idx < len(scales) else 1.0
        mappings.append(
            AxisMapping(axis=int(axis), channel=int(channels[idx]), scale=float(scale))
        )
    return mappings


def make_button_mappings(config: dict) -> list[ButtonMapping]:
    indices = config.get("button_indices", [0, 1, 2, 3, 4])
    channels = config.get("button_channels", [15, 16, 12, 13, 14])
    names = config.get("button_names", ["l1", "l2", "r1", "r2", "r3"])
    pressed_mins = config.get("button_pressed_mins", [])

    mappings = []
    for idx, button in enumerate(indices):
        if idx >= len(channels):
            break
        name = str(names[idx]) if idx < len(names) else ""
        pressed_min = (
            int(pressed_mins[idx])
            if idx < len(pressed_mins) and int(pressed_mins[idx]) > 0
            else None
        )
        mappings.append(
            ButtonMapping(
                button=int(button),
                channel=int(channels[idx]),
                name=name,
                pressed_min=pressed_min,
            )
        )
    return mappings


def get_config_value(config: dict, key: str, fallback):
    value = config.get(key, fallback)
    return fallback if value is None else value


def format_event_texts(event, event_format: str) -> list[str]:
    indexed = f"button_{event.button}_{event.event_type}"
    semantic = f"{event.name}_{event.event_type}" if event.name else indexed

    if event_format == "indexed":
        return [indexed]
    if event_format == "both" and semantic != indexed:
        return [semantic, indexed]
    return [semantic]


def format_events(events, event_format: str) -> str:
    if not events:
        return "-"
    return ", ".join(
        text for event in events for text in format_event_texts(event, event_format)
    )


def channel_names(config: dict) -> dict:
    return config.get("channel_names", {})


def main() -> None:
    args = make_arg_parser().parse_args()
    config = load_config(args.config)

    port = args.port or str(get_config_value(config, "serial_port", "/dev/ttyUSB0"))
    baudrate = args.baudrate or int(get_config_value(config, "serial_baudrate", 100000))
    timeout = (
        args.timeout
        if args.timeout is not None
        else float(get_config_value(config, "serial_timeout", 0.0))
    )
    filter_window_size = (
        args.filter_window_size
        if args.filter_window_size is not None
        else int(get_config_value(config, "filter_window_size", 9))
    )
    idle_sleep_sec = (
        args.idle_sleep_sec
        if args.idle_sleep_sec is not None
        else float(get_config_value(config, "idle_sleep_sec", 0.001))
    )
    input_timeout_ms = (
        args.input_timeout_ms
        if args.input_timeout_ms is not None
        else float(get_config_value(config, "input_timeout_ms", 100.0))
    )

    receiver = SBUSReceiver(
        port=port,
        baudrate=baudrate,
        timeout=timeout,
    )
    processor = SignalProcessor(window_size=filter_window_size)
    calibration = JoyCalibration(
        min_value=int(get_config_value(config, "joy_min_value", 272)),
        mid_value=int(get_config_value(config, "joy_mid_value", 992)),
        max_value=int(get_config_value(config, "joy_max_value", 1712)),
        deadband=float(get_config_value(config, "joy_deadband", 0.05)),
    )
    axis_mappings = make_axis_mappings(config)
    button_mappings = make_button_mappings(config)

    axis_count = int(get_config_value(config, "axis_count", 6))
    button_count = int(get_config_value(config, "button_count", 16))
    button_pressed_min = int(get_config_value(config, "button_pressed_min", 1500))
    button_names_by_index = {
        mapping.button: mapping.name for mapping in button_mappings if mapping.name
    }
    button_tracker = ButtonStateTracker(
        button_count=button_count,
        button_names=button_names_by_index,
    )
    button_event_format = str(
        get_config_value(config, "button_event_format", "semantic")
    ).lower()
    if button_event_format not in {"semantic", "indexed", "both"}:
        button_event_format = "semantic"
    input_timeout_sec = input_timeout_ms / 1000.0
    last_input_time = None
    timed_out = False
    visualizer = SBUSVisualizer(
        deadband_percent=float(get_config_value(config, "ui_deadband_percent", 6.0)),
        num_channels=16,
    )
    names = channel_names(config)

    print(f"Reading SBUS from {port}. Press Ctrl+C to exit.")

    try:
        live = Live(screen=False, auto_refresh=False) if args.ui else None
        with live if live is not None else nullcontext():
            while True:
                now = time.monotonic()
                frame = receiver.read_latest()

                if frame is None:
                    if (
                        last_input_time is not None
                        and now - last_input_time > input_timeout_sec
                    ):
                        if not timed_out:
                            axes, buttons = zero_joy(axis_count, button_count)
                            button_tracker.reset()
                            if not args.ui:
                                print(f"timeout -> axes={axes} buttons={buttons}")
                            timed_out = True
                    time.sleep(idle_sleep_sec)
                    continue

                last_input_time = now
                if timed_out:
                    if not args.ui:
                        print("input recovered")
                    timed_out = False

                if frame.failsafe:
                    axes, buttons = zero_joy(axis_count, button_count)
                    button_tracker.reset()
                    if not args.ui:
                        print(
                            f"failsafe flags={frame.flags} -> "
                            f"axes={axes} buttons={buttons}"
                        )
                    continue

                filtered = processor.apply_filter(frame.channels)
                if filtered is None:
                    continue

                axes, buttons = build_joy_vectors(
                    filtered,
                    axis_mappings,
                    button_mappings,
                    calibration,
                    axis_count,
                    button_count,
                    button_pressed_min,
                )
                events = button_tracker.update(buttons)

                if args.ui:
                    live.update(
                        visualizer.make_table(
                            filtered,
                            frame.flags,
                            processor,
                            names,
                        ),
                        refresh=True,
                    )
                    continue

                if args.raw:
                    print(f"raw={frame.channels} flags={frame.flags}")
                print(
                    f"axes={axes} buttons={buttons} "
                    f"frame_lost={frame.frame_lost} "
                    f"events={format_events(events, button_event_format)}"
                )

    except KeyboardInterrupt:
        pass
    finally:
        receiver.close()


if __name__ == "__main__":
    """사용법
    python3 sbus_cli.py --config path/to/siyi_control.yaml --ui
    """
    main()
