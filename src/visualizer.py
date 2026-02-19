from rich.table import Table
from rich.panel import Panel
from rich.text import Text


class SBUSVisualizer:
    def __init__(self, deadband=6.0, num_channels=16):
        self.num_channels = num_channels
        self.deadband = deadband

    def flags_text(self, flags: int) -> str:
        frame_lost = (flags & 0x04) != 0
        failsafe = (flags & 0x08) != 0
        return f"FRAME_LOST={'YES' if frame_lost else 'NO'} | FAILSAFE={'YES' if failsafe else 'NO'}"

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
        if ch_idx == 4 or "Mode switch" in name:
            if val > 1500:
                return "[bold green]M3[/]"  # 1792 부근
            if val > 500:
                return "[bold yellow]M2[/]"  # 872 부근 (중간값)
            return "[bold red]M1[/]"

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

            is_analog = i < 4 or (5 <= i <= 8)

            status = self.get_status_display(val, name, processor, ch_idx=i)
            direction = (
                self.get_direction_icon(processor.normalize(val), name)
                if is_analog
                else "-"
            )

            table.add_row(f"{i+1:02d}", name, f"{val:>4}", status, direction)

        return table
