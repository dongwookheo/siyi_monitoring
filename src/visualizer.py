from rich.table import Table
from rich.panel import Panel
from rich.text import Text
import re


class SBUSVisualizer:
    def __init__(self, deadband=6.0, num_channels=16, min_val=172, max_val=1811):
        self.num_channels = num_channels
        self.deadband = deadband
        self.min_val = min_val
        self.max_val = max_val

    def flags_text(self, flags: int) -> str:
        frame_lost = (flags & 0x04) != 0
        failsafe = (flags & 0x08) != 0
        return f"FRAME_LOST={'YES' if frame_lost else 'NO'} | FAILSAFE={'YES' if failsafe else 'NO'}"

    def parse_mode_steps(self, name: str) -> int:
        """이름에서 모드 개수 파싱. 예: 'Mode Switch (6)' -> 6"""
        match = re.search(r"\((\d+)\)", name)
        return int(match.group(1)) if match else 3  # 기본값 3

    def get_mode_display(self, val: int, steps: int) -> str:
        """동적으로 모드 단계 표시 (3단계 또는 6단계 등)"""
        # 색상 팔레트 (steps 개수만큼 사용)
        colors = ["red", "dark_orange3", "yellow", "green", "cyan", "magenta"]

        # 각 단계의 크기 계산
        step_size = (self.max_val - self.min_val) / steps

        # 현재 값이 어느 단계에 속하는지 계산
        mode_idx = min(int((val - self.min_val) / step_size), steps - 1)

        color = colors[mode_idx % len(colors)]
        mode_label = f"M{mode_idx + 1}"

        return f"[bold {color}]{mode_label}[/]"

    def is_analog_control(self, name: str) -> bool:
        """이름 기반으로 아날로그 컨트롤 여부 판단"""
        # 디지털 타입 키워드 체크
        digital_keywords = ["Button", "Switch", "Mode Switch", "Mode switch"]
        if any(keyword in name for keyword in digital_keywords):
            return False

        # 아날로그 타입 키워드 체크
        analog_keywords = ["Stick", "Dial", "Rocker"]
        return any(keyword in name for keyword in analog_keywords)

    def get_direction_icon(self, percent: float, name: str):
        """방향에 따른 아이콘 및 색상 (UP/RIGHT: Green, DOWN/LEFT: Red)"""
        # 이름에 L/R 또는 Dial이 포함되면 좌우 화살표, 아니면 상하 화살표
        is_horizontal = any(x in name for x in ["L/R", "Dial", "Rocker(L/R)"])

        if percent > self.deadband:
            icon = "▶" if is_horizontal else "▲"
            return f"[bold green]{icon}[/]"
        if percent < -self.deadband:
            icon = "◀" if is_horizontal else "▼"
            return f"[bold red]{icon}[/]"
        return "■"

    def get_status_display(self, val: int, name: str, processor, ch_idx=None):
        """매핑된 컨트롤 성격에 따라 상태 출력"""
        # Mode Switch - 동적으로 단계 수 인식
        if "Mode Switch" in name or "Mode switch" in name:
            steps = self.parse_mode_steps(name)
            return self.get_mode_display(val, steps)

        # 1. 3단 스위치 (H/M/L) - 872와 992 모두 대응 가능한 임계값 적용
        if "H/M/L" in name or "Switch" in name:
            if val > 1500:
                return "[bold green]HIGH[/]"
            if val > 500:
                return "[bold yellow]MID [/]"
            return "[bold red]LOW[/]"

        # 2. 버튼 (PUSH/IDLE)
        if "Button" in name:
            return "[bold cyan]PUSH[/]" if val > 1300 else "IDLE"

        # 3. 아날로그 (Stick, Dial, Rocker)
        pct = processor.normalize(val)
        return f"{pct:>6.1f}%"

    def make_ui(self, ch, flags, processor, mapping):
        table = Table(
            title="SIYI UniRC 7 실시간 모니터링",
            show_lines=True,
            caption=self.flags_text(flags),
            expand=True,
        )

        table.add_column("CH", justify="center", width=4)
        table.add_column("컨트롤 명칭", justify="left", width=22)
        table.add_column("RAW", justify="right", width=6)
        table.add_column("상태 / 정규화", justify="center", width=15)
        table.add_column("방향", justify="center", width=8)

        for i in range(self.num_channels):
            ch_key = f"ch{i+1}"
            name = mapping.get(ch_key, f"AUX {i+1}")
            val = ch[i]

            # 이름 기반으로 아날로그 여부 판단 (채널 번호가 아닌!)
            is_analog = self.is_analog_control(name)

            status = self.get_status_display(val, name, processor, ch_idx=i)
            direction = (
                self.get_direction_icon(processor.normalize(val), name)
                if is_analog
                else "-"
            )

            table.add_row(f"{i+1:02d}", name, f"{val:>4}", status, direction)

        return table
