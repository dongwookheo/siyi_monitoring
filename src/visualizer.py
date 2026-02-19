from rich.table import Table
from rich.panel import Panel
from rich.text import Text

class SBUSVisualizer:
    def __init__(self, deadband=6.0):
        self.deadband = deadband

    def flags_text(self, flags: int) -> str:
        ch17 = (flags & 0x01) != 0
        ch18 = (flags & 0x02) != 0
        frame_lost = (flags & 0x04) != 0
        failsafe = (flags & 0x08) != 0
        return f"CH17={'ON' if ch17 else 'OFF'} | CH18={'ON' if ch18 else 'OFF'} | FRAME_LOST={'YES' if frame_lost else 'NO'} | FAILSAFE={'YES' if failsafe else 'NO'}"

    def axis_direction(self, percent: float, pos_label="+", neg_label="-"):
        if percent > self.deadband:
            return "▶" if pos_label == "RIGHT" else "▲" if pos_label == "UP" else pos_label
        if percent < -self.deadband:
            return "◀" if neg_label == "LEFT" else "▼" if neg_label == "DOWN" else neg_label
        return "■"

    def describe_stick(self, lr_pct, ud_pct, stick_name):
        lr = "오른쪽" if lr_pct > self.deadband else "왼쪽" if lr_pct < -self.deadband else "중립"
        ud = "위" if ud_pct > self.deadband else "아래" if ud_pct < -self.deadband else "중립"
        return f"{stick_name}: 좌우={lr}, 상하={ud}"

    def make_ui(self, ch, flags, processor):
        # 정규화 계산
        pcts = [processor.normalize(v) for v in ch[:4]]
        
        # 아이콘 결정
        icons = [
            self.axis_direction(pcts[0], "RIGHT", "LEFT"),
            self.axis_direction(pcts[1], "UP", "DOWN"),
            self.axis_direction(pcts[2], "UP", "DOWN"),
            self.axis_direction(pcts[3], "RIGHT", "LEFT"),
        ]

        # 테이블 생성 시 열 너비를 명시적으로 지정할 수도 있습니다.
        table = Table(title="SBUS 조이스틱 해석 (CH1~CH4)", show_lines=True)
        table.add_column("채널", justify="center", width=6)
        table.add_column("매핑", justify="left", width=20)
        table.add_column("RAW", justify="right", width=8)  # 열 너비 자체를 고정
        table.add_column("정규화(%)", justify="right", width=12)
        table.add_column("방향", justify="center", width=6)

        labels = ["오른쪽 스틱 좌/우", "오른쪽 스틱 상/하", "왼쪽 스틱 상/하", "왼쪽 스틱 좌/우"]
        for i in range(4):
            # {:>4} : 4자리 공간을 확보하고 오른쪽(>)으로 정렬
            raw_value_fixed = f"{ch[i]:>4}" 
            
            table.add_row(
                f"CH{i+1}", 
                labels[i], 
                raw_value_fixed, 
                f"{pcts[i]:6.1f}", 
                icons[i]
            )
        # 요약 패널 생성
        summary = Text()
        summary.append(self.describe_stick(pcts[0], pcts[1], "오른쪽 스틱"), style="bold")
        summary.append("\n")
        summary.append(self.describe_stick(pcts[3], pcts[2], "왼쪽 스틱"), style="bold")
        summary.append("\n\n")
        summary.append("FLAGS: " + self.flags_text(flags))

        return Panel.fit(summary, title="현재 조작(한글 요약)"), table