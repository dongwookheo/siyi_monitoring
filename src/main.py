import time
import tomllib
from rich.live import Live
from rich.table import Table
from sbus_receiver import SBUSReceiver
from processor import SignalProcessor
from visualizer import SBUSVisualizer

def main():
    with open("config.toml", "rb") as f:
        cfg = tomllib.load(f)

    receiver = SBUSReceiver(**cfg["serial"])
    processor = SignalProcessor(window_size=cfg["filter"]["window_size"])
    visualizer = SBUSVisualizer(deadband=cfg["filter"]["deadband"])
    
    refresh_dt = 1.0 / cfg["ui"]["refresh_hz"]
    last_render = 0

    try:
        with Live(screen=False, auto_refresh=False) as live:
            while True:
                frame = receiver.get_latest_frame()
                if frame:
                    raw_ch, flags = receiver.decode_channels(frame)
                    
                    if not (flags & 0x0C): # Quality Check
                        filtered = processor.apply_filter(raw_ch)
                        
                        if filtered:
                            now = time.time()
                            if now - last_render >= refresh_dt:
                                panel, table = visualizer.make_ui(filtered, flags, processor)
                                
                                combined = Table.grid(expand=True)
                                combined.add_row(panel)
                                combined.add_row(table)
                                live.update(combined, refresh=True)
                                last_render = now
                
                time.sleep(0.001)
    except KeyboardInterrupt:
        pass
    finally:
        receiver.close()

if __name__ == "__main__":
    main()