import re

from rich.table import Table

from siyi_control.mapping import (
    JoyCalibration,
    ModeSwitchMapping,
    decode_mode_switch,
    normalize_axis,
)

TRIANGLE_UP = "\u25b2"
TRIANGLE_DOWN = "\u25bc"
TRIANGLE_LEFT = "\u25c0"
TRIANGLE_RIGHT = "\u25b6"


class SBUSVisualizer:
    """SBUS 채널 데이터를 콘솔에 시각적으로 표시하는 클래스"""

    def __init__(
        self,
        deadband_percent: float | None = None,
        num_channels: int = 16,
        calibration: JoyCalibration | None = None,
        mode_switch_mappings: list[ModeSwitchMapping] | None = None,
    ):
        """시각화에 사용할 데드밴드 퍼센트와 표시할 채널 수를 설정하는 생성자"""
        self.calibration = calibration or JoyCalibration()
        self.deadband_percent = (
            self.calibration.deadband * 100.0
            if deadband_percent is None
            else deadband_percent
        )
        self.num_channels = num_channels
        self.mode_switch_mappings = mode_switch_mappings or []

    def make_table(self, channels: list[int], flags: int, processor, names: dict):
        """SBUS 채널 데이터와 플래그를 받아서 콘솔에 표시할 테이블을 생성하는 함수"""
        table = Table(
            title="SIYI SBUS Monitoring",
            show_lines=True,
            caption=self._flags_text(flags),
            expand=True,
        )
        table.add_column("CH", justify="center", width=4)
        table.add_column("Name", justify="left", width=24)
        table.add_column("RAW", justify="right", width=6)
        table.add_column("Status", justify="center", width=16)
        table.add_column("Direction", justify="center", width=8)

        for idx in range(min(self.num_channels, len(channels))):
            name = names.get(f"ch{idx + 1}", f"CH{idx + 1}")
            value = channels[idx]
            percent = self._normalize_percent(value)
            status = self._status(value, percent, name, idx + 1)
            direction = self._direction(percent, name) if self._is_analog(name) else "-"

            table.add_row(
                f"{idx + 1:02d}",
                name,
                f"{value:>4}",
                status,
                direction,
            )

        return table

    def _normalize_percent(self, value: int) -> float:
        """Joy 보정값을 기준으로 SBUS 채널 값을 퍼센트로 정규화한다."""
        return normalize_axis(value, self.calibration) * 100.0

    def _flags_text(self, flags: int) -> str:
        """SBUS 프레임의 플래그 상태를 텍스트로 표현하는 함수"""
        frame_lost = "YES" if flags & 0x04 else "NO"
        failsafe = "YES" if flags & 0x08 else "NO"
        return f"FRAME_LOST={frame_lost} | FAILSAFE={failsafe}"

    def _status(self, value: int, percent: float, name: str, channel: int) -> str:
        """SBUS 채널의 상태를 텍스트로 표현하는 함수"""
        if "Mode Switch" in name or "Mode switch" in name:
            return self._mode_status(value, channel, name)

        if "H/M/L" in name or "Switch" in name:
            if value > 1500:
                return "[bold green]HIGH[/]"
            if value > 500:
                return "[bold yellow]MID[/]"
            return "[bold red]LOW[/]"

        if "Button" in name:
            return "[bold cyan]PUSH[/]" if value > 1300 else "IDLE"

        return f"{percent:>6.1f}%"

    def _mode_status(self, value: int, channel: int, name: str) -> str:
        """Mode switch의 상태를 텍스트로 표현하는 함수"""
        colors = ["red", "dark_orange3", "yellow", "green", "cyan", "magenta"]
        for mapping in self.mode_switch_mappings:
            if mapping.channel != channel:
                continue
            step = decode_mode_switch(value, mapping)
            if step is None:
                return "-"
            step_index = mapping.steps.index(step)
            color = colors[step_index % len(colors)]
            label = step.name.upper() if step.name else f"M{step_index + 1}"
            return f"[bold {color}]{label}[/]"
        match = re.search(r"\((\d+)\)", name)
        steps = int(match.group(1)) if match else 3
        value = max(172, min(value, 1811))
        step_size = (1811 - 172) / steps
        mode_idx = min(int((value - 172) / step_size), steps - 1)
        color = colors[mode_idx % len(colors)]
        return f"[bold {color}]M{mode_idx + 1}[/]"

    def _is_analog(self, name: str) -> bool:
        """채널 이름에서 아날로그 입력 여부를 판단하는 함수"""
        if any(keyword in name for keyword in ["Button", "Switch", "Mode switch"]):
            return False
        return any(keyword in name for keyword in ["Stick", "Dial", "Rocker"])

    def _direction(self, percent: float, name: str) -> str:
        """채널의 방향을 텍스트로 표현하는 함수"""
        is_horizontal = any(x in name for x in ["L/R", "Dial", "Rocker(L/R)"])
        is_left_dial = "Left Dial" in name

        if percent > self.deadband_percent:
            if is_left_dial:
                return f"[bold green]{TRIANGLE_LEFT}[/]"
            return (
                f"[bold green]{TRIANGLE_RIGHT}[/]"
                if is_horizontal
                else f"[bold green]{TRIANGLE_UP}[/]"
            )

        if percent < -self.deadband_percent:
            if is_left_dial:
                return f"[bold red]{TRIANGLE_RIGHT}[/]"
            return (
                f"[bold red]{TRIANGLE_LEFT}[/]"
                if is_horizontal
                else f"[bold red]{TRIANGLE_DOWN}[/]"
            )

        return "-"
