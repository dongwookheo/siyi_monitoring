import time
import tomllib
from pathlib import Path
from rich.live import Live
from rich.table import Table
from sbus_receiver import SBUSReceiver
from processor import SignalProcessor
from visualizer import SBUSVisualizer

def main():
    script_location = Path(__file__).resolve()
    project_root = script_location.parent.parent
    config_path = project_root / "config.toml"

    if not config_path.exists():
        config_path = Path("config.toml")
        if not config_path.exists():
            print(f"config.toml 파일을 찾을 수 없음")
            return

    with open(config_path, "rb") as f:
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