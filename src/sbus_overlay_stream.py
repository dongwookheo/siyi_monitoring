#!/usr/bin/env python3
import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib
import tomllib
from pathlib import Path
from shared_sbus import SBUSSharedMemory
from processor import SignalProcessor


class SBUSOverlayStream:
    def __init__(
        self,
        video_device="/dev/video4",
        rtsp_url="rtsp://localhost:8554/leftstream",
        config_path=None,
    ):
        # GStreamer 초기화
        Gst.init(None)

        self.video_device = video_device
        self.rtsp_url = rtsp_url

        # config.toml 읽기
        if config_path is None:
            script_location = Path(__file__).resolve()
            project_root = script_location.parent.parent
            config_path = project_root / "config.toml"

        if not config_path.exists():
            config_path = Path("config.toml")

        with open(config_path, "rb") as f:
            self.cfg = tomllib.load(f)

        # 공유 메모리에서 읽은 SBUS 데이터 저장
        self.sbus_channels = [0] * 16
        self.sbus_flags = 0

        # 공유 메모리 (main.py에서 쓴 필터링된 데이터 읽기)
        self.shared_mem = SBUSSharedMemory(create=False)

        # Signal Processor (normalize 함수만 사용)
        self.processor = SignalProcessor(window_size=self.cfg["filter"]["window_size"])

        # GStreamer 파이프라인 생성
        self.pipeline = None
        self.textoverlay = None
        self.create_pipeline()

    def create_pipeline(self):
        """GStreamer 파이프라인 생성"""
        pipeline_str = (
            f"v4l2src device={self.video_device} ! "
            "video/x-raw,width=640,height=480,framerate=30/1 ! "
            "videoconvert ! "
            'textoverlay name=overlay font-desc="Sans Bold 14" '
            "valignment=top halignment=left shaded-background=true ! "
            "videoconvert ! "
            "x264enc tune=zerolatency bitrate=500 speed-preset=ultrafast ! "
            f"rtspclientsink location={self.rtsp_url}"
        )

        self.pipeline = Gst.parse_launch(pipeline_str)
        self.textoverlay = self.pipeline.get_by_name("overlay")

        # 버스 메시지 처리
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)

    def on_message(self, bus, message):
        """GStreamer 버스 메시지 처리"""
        t = message.type
        if t == Gst.MessageType.EOS:
            print("End-of-stream")
            self.stop()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error: {err}, {debug}")
            self.stop()

    def update_overlay_text(self):
        """텍스트 오버레이 업데이트 (공유 메모리에서 읽은 필터링된 값)"""
        try:
            # 공유 메모리에서 main.py가 쓴 필터링된 데이터 읽기
            channels, flags = self.shared_mem.read()
            self.sbus_channels = channels
            self.sbus_flags = flags
        except Exception as e:
            print(f"공유 메모리 읽기 오류: {e}")
            # 오류 발생 시 이전 값 유지
            channels = self.sbus_channels
            flags = self.sbus_flags

        # SBUS 채널 값을 텍스트로 변환
        text_lines = ["=== SBUS (Filtered) ==="]

        # 주요 채널만 표시 (CH1~CH8) + 채널 이름 표시
        for i in range(8):
            ch_name = self.cfg["mapping"].get(f"ch{i+1}", f"CH{i+1}")
            value = channels[i]
            # normalize된 값도 표시 (%)
            normalized = self.processor.normalize(value)
            text_lines.append(f"{ch_name}: {value:4d} ({normalized:+6.1f}%)")

        # Failsafe 및 Frame Lost 플래그
        failsafe = "ON" if (flags & 0x08) else "OFF"
        frame_lost = "YES" if (flags & 0x04) else "NO"
        text_lines.append(f"Failsafe: {failsafe} | FrameLost: {frame_lost}")

        overlay_text = "\n".join(text_lines)

        # 텍스트 오버레이 업데이트
        if self.textoverlay:
            self.textoverlay.set_property("text", overlay_text)

        return True  # GLib.timeout_add에서 계속 호출되도록

    def start(self):
        """스트리밍 시작"""
        print("스트리밍 시작...")
        print(
            "공유 메모리에서 SBUS 데이터를 읽습니다. main.py가 실행 중인지 확인하세요."
        )

        # 공유 메모리 열기
        try:
            self.shared_mem.open()
        except RuntimeError as e:
            print(f"오류: {e}")
            print("먼저 main.py를 실행해주세요.")
            return

        # 파이프라인 시작
        self.pipeline.set_state(Gst.State.PLAYING)

        # 텍스트 업데이트 타이머 (100ms마다 공유 메모리 읽기)
        GLib.timeout_add(100, self.update_overlay_text)

        # 메인 루프 실행
        try:
            loop = GLib.MainLoop()
            loop.run()
        except KeyboardInterrupt:
            print("\n종료 중...")
            self.stop()

    def stop(self):
        """스트리밍 중지"""
        print("스트리밍 중지...")

        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)

        # 공유 메모리 닫기
        self.shared_mem.close()


def main():
    # 설정값 (필요시 수정)
    VIDEO_DEVICE = "/dev/video4"  # 카메라 장치
    RTSP_URL = "rtsp://localhost:8554/leftstream"  # RTSP 송출 주소
    # SBUS 설정은 config.toml에서 자동으로 읽어옵니다

    streamer = SBUSOverlayStream(video_device=VIDEO_DEVICE, rtsp_url=RTSP_URL)

    streamer.start()


if __name__ == "__main__":
    main()
