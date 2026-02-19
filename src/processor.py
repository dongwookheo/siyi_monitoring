import statistics
from collections import deque


class SignalProcessor:
    def __init__(self, window_size, num_channels=16, min_val=172, max_val=1811):
        self.num_channels = num_channels
        self.window_size = window_size
        self.min_val = min_val
        self.max_val = max_val
        self.mid_val = (min_val + max_val) // 2
        self.hist = [deque(maxlen=window_size) for _ in range(self.num_channels)]

    def apply_filter(self, raw_channels):
        for i in range(len(raw_channels)):
            if i < self.num_channels:
                self.hist[i].append(raw_channels[i])

        if len(self.hist[0]) < self.window_size:
            return None

        results = []
        for i in range(len(raw_channels)):
            results.append(int(statistics.median(self.hist[i])))
        return results

    def normalize(self, v: int) -> float:
        v = max(self.min_val, min(v, self.max_val))
        if v >= self.mid_val:
            return (v - self.mid_val) / (self.max_val - self.mid_val) * 100.0
        return (v - self.mid_val) / (self.mid_val - self.min_val) * 100.0
