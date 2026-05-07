import statistics
from collections import deque
from typing import Optional


class SignalProcessor:
    """SBUS 채널 데이터를 필터링하고 정규화하는 클래스"""

    def __init__(
        self,
        window_size: int,
        num_channels: int = 16,
        min_val: int = 172,
        max_val: int = 1811,
    ):
        """필터링을 위한 버퍼 크기와 SBUS 채널의 최소/최대값을 설정하는 생성자"""
        if window_size < 1:
            raise ValueError("window_size must be >= 1")

        self.num_channels = num_channels
        self.window_size = window_size
        self.min_val = min_val
        self.max_val = max_val
        self.mid_val = (min_val + max_val) // 2
        self.hist = [deque(maxlen=window_size) for _ in range(num_channels)]

    def apply_filter(self, raw_channels: list[int]) -> Optional[list[int]]:
        """SBUS 채널 데이터에 필터를 적용하는 메서드"""
        for idx, value in enumerate(raw_channels[: self.num_channels]):
            self.hist[idx].append(value)

        if len(self.hist[0]) < self.window_size:
            return None

        return [int(statistics.median(hist)) for hist in self.hist]

    def normalize_percent(self, value: int) -> float:
        """SBUS 채널 값을 퍼센트로 정규화하는 메서드"""
        value = max(self.min_val, min(value, self.max_val))
        if value >= self.mid_val:
            return (value - self.mid_val) / (self.max_val - self.mid_val) * 100.0
        return (value - self.mid_val) / (self.mid_val - self.min_val) * 100.0
