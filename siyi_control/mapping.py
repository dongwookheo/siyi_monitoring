from dataclasses import dataclass


@dataclass
class AxisMapping:
    """조이스틱 axes와 SBUS 채널 간의 매핑을 정의하는 데이터 클래스"""

    axis: int  ### 조이스틱의 축 번호 (예: 0, 1, 2 등)
    channel: int  ### SBUS 채널 번호 (1부터 시작)
    scale: float = 1.0  ### 축 값에 적용할 스케일링 팩터 (양수)


@dataclass
class ButtonMapping:
    """조이스틱 버튼과 SBUS 채널 간의 매핑을 정의하는 데이터 클래스"""

    button: int  ### 조이스틱의 버튼 번호 (예: 0, 1, 2 등)
    channel: int  ### SBUS 채널 번호 (1부터 시작)
    name: str = ""  ### 버튼의 의미론적 이름 (예: l1, r1 등)
    pressed_min: int | None = None  ### 버튼별 pressed 판정 임계값


@dataclass
class ButtonEvent:
    """버튼 상태 변화 이벤트"""

    button: int
    event_type: str
    name: str = ""


@dataclass
class JoyCalibration:
    """조이스틱 axes의 보정 정보를 담는 데이터 클래스"""

    min_value: int = 272  ### SBUS 채널의 최소값
    mid_value: int = 992  ### SBUS 채널의 중간값
    max_value: int = 1712  ### SBUS 채널의 최대값
    deadband: float = 0.05  ### 조이스틱이 중앙에 있을 때의 허용 오차 범위


def normalize_axis(value: int, calibration: JoyCalibration) -> float:
    """SBUS 채널 값을 정규화하는 함수"""
    value = max(calibration.min_value, min(value, calibration.max_value))

    if value >= calibration.mid_value:
        denom = calibration.max_value - calibration.mid_value
        normalized = (value - calibration.mid_value) / denom if denom else 0.0
    else:
        denom = calibration.mid_value - calibration.min_value
        normalized = (value - calibration.mid_value) / denom if denom else 0.0

    normalized = max(-1.0, min(normalized, 1.0))
    if abs(normalized) < calibration.deadband:
        return 0.0
    return normalized


def build_joy_vectors(
    channels: list[int],
    axis_mappings: list[AxisMapping],
    button_mappings: list[ButtonMapping],
    calibration: JoyCalibration,
    axis_count: int,
    button_count: int,
    button_pressed_min: int,
) -> tuple[list[float], list[int]]:
    """SBUS 채널 데이터를 조이스틱 axes와 버튼 상태로 변환하는 함수"""
    axes = [0.0] * axis_count
    buttons = [0] * button_count

    for mapping in axis_mappings:
        if mapping.axis < 0 or mapping.axis >= axis_count:
            continue
        channel_idx = mapping.channel - 1
        if channel_idx < 0 or channel_idx >= len(channels):
            continue
        axes[mapping.axis] = (
            normalize_axis(channels[channel_idx], calibration) * mapping.scale
        )

    for mapping in button_mappings:
        if mapping.button < 0 or mapping.button >= button_count:
            continue
        channel_idx = mapping.channel - 1
        if channel_idx < 0 or channel_idx >= len(channels):
            continue
        pressed_min = (
            mapping.pressed_min
            if mapping.pressed_min is not None
            else button_pressed_min
        )
        buttons[mapping.button] = int(channels[channel_idx] >= pressed_min)

    return axes, buttons


class ButtonStateTracker:
    """버튼의 이전/현재 상태를 비교해 rising/falling edge를 찾는 클래스"""

    PRESSED = "pressed"
    RELEASED = "released"

    def __init__(self, button_count: int, button_names: dict[int, str] | None = None):
        self.previous_buttons = [0] * button_count
        self.button_names = button_names or {}

    def update(self, buttons: list[int]) -> list[ButtonEvent]:
        events = []

        for idx, current in enumerate(buttons):
            previous = (
                self.previous_buttons[idx] if idx < len(self.previous_buttons) else 0
            )

            if previous == 0 and current == 1:
                events.append(
                    ButtonEvent(
                        button=idx,
                        event_type=self.PRESSED,
                        name=self.button_names.get(idx, ""),
                    )
                )
            elif previous == 1 and current == 0:
                events.append(
                    ButtonEvent(
                        button=idx,
                        event_type=self.RELEASED,
                        name=self.button_names.get(idx, ""),
                    )
                )

        self.previous_buttons = buttons.copy()
        return events

    def reset(self) -> None:
        self.previous_buttons = [0] * len(self.previous_buttons)


def zero_joy(axis_count: int, button_count: int) -> tuple[list[float], list[int]]:
    """조이스틱 axes와 버튼 상태를 모두 0으로 초기화하는 함수"""
    return [0.0] * axis_count, [0] * button_count
