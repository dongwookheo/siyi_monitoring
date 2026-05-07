from dataclasses import dataclass
from typing import Optional

import serial

SBUS_FRAME_LEN = 25  # SBUS 프레임의 고정 길이 (1바이트 시작, 22바이트 채널 데이터, 1바이트 플래그, 1바이트 종료)
SBUS_START_BYTE = 0x0F  # SBUS 프레임의 시작 바이트 (0x0F)
SBUS_END_BYTES = {
    0x00,  # 0x00: 정상 종료
    0x04,  # 0x04: 프레임 손실
    0x14,  # 0x14: 페일세이프
    # 0x24,  # 0x24: 프레임 손실 + 페일세이프
    # 0x34,  # 0x34: 프레임 손실 + 페일세이프 (일부 수신기에서 사용)
}  # SBUS 프레임의 유효한 종료 바이트 집합
SBUS_FRAME_LOST_FLAG = 0x04
SBUS_FAILSAFE_FLAG = 0x08


@dataclass
class SBUSFrame:
    """
    SBUS 프레임 클래스 - 16채널의 RC 수신기 데이터를 담고 있으며, 프레임 손실과 페일세이프 상태를 나타내는 플래그를 포함.
    """

    channels: list[int]  ### 16채널의 RC 수신기 데이터를 담는 리스트
    flags: int  ### 프레임 손실과 페일세이프 상태를 나타내는 플래그 (0x04: 프레임 손실, 0x08: 페일세이프)

    @property
    def frame_lost(self) -> bool:
        """프레임 손실 여부를 나타내는 속성 - flags의 0x04 비트가 설정되어 있으면 True, 그렇지 않으면 False를 반환."""
        return bool(self.flags & SBUS_FRAME_LOST_FLAG)

    @property
    def failsafe(self) -> bool:
        """페일세이프 상태 여부를 나타내는 속성 - flags의 0x08 비트가 설정되어 있으면 True, 그렇지 않으면 False를 반환."""
        return bool(self.flags & SBUS_FAILSAFE_FLAG)


def decode_channels(frame: bytes) -> SBUSFrame:
    """SBUS 프레임에서 16채널 데이터를 추출하여 SBUSFrame 객체로 반환하는 함수"""
    if len(frame) != SBUS_FRAME_LEN:
        raise ValueError(f"SBUS frame must be {SBUS_FRAME_LEN} bytes")

    b = frame
    channels = [0] * 16

    channels[0] = (b[1] | b[2] << 8) & 0x07FF
    channels[1] = (b[2] >> 3 | b[3] << 5) & 0x07FF
    channels[2] = (b[3] >> 6 | b[4] << 2 | b[5] << 10) & 0x07FF
    channels[3] = (b[5] >> 1 | b[6] << 7) & 0x07FF
    channels[4] = (b[6] >> 4 | b[7] << 4) & 0x07FF
    channels[5] = (b[7] >> 7 | b[8] << 1 | b[9] << 9) & 0x07FF
    channels[6] = (b[9] >> 2 | b[10] << 6) & 0x07FF
    channels[7] = (b[10] >> 5 | b[11] << 3) & 0x07FF
    channels[8] = (b[12] | b[13] << 8) & 0x07FF
    channels[9] = (b[13] >> 3 | b[14] << 5) & 0x07FF
    channels[10] = (b[14] >> 6 | b[15] << 2 | b[16] << 10) & 0x07FF
    channels[11] = (b[16] >> 1 | b[17] << 7) & 0x07FF
    channels[12] = (b[17] >> 4 | b[18] << 4) & 0x07FF
    channels[13] = (b[18] >> 7 | b[19] << 1 | b[20] << 9) & 0x07FF
    channels[14] = (b[20] >> 2 | b[21] << 6) & 0x07FF
    channels[15] = (b[21] >> 5 | b[22] << 3) & 0x07FF

    return SBUSFrame(channels=channels, flags=b[23])


class SBUSReceiver:
    """SBUS 수신기 클래스"""

    def __init__(self, port: str, baudrate: int = 100000, timeout: float = 0.0):
        """SBUS 수신기 초기화 - 시리얼 포트 설정 및 연결"""
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = serial.Serial(
            port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_TWO,
            timeout=timeout,
        )

    def get_latest_frame(self) -> Optional[bytes]:
        """시리얼 버퍼에서 최신 SBUS 프레임을 검색하여 반환하는 함수"""
        waiting = self.ser.in_waiting
        if waiting < SBUS_FRAME_LEN:
            return None

        data = self.ser.read(waiting)
        for i in range(len(data) - SBUS_FRAME_LEN, -1, -1):
            if data[i] != SBUS_START_BYTE:
                continue
            if data[i + 24] in SBUS_END_BYTES:
                return data[i : i + SBUS_FRAME_LEN]

        return None

    def read_latest(self) -> Optional[SBUSFrame]:
        """최신 SBUS 프레임을 읽어 SBUSFrame 객체로 반환하는 함수"""
        frame = self.get_latest_frame()
        if frame is None:
            return None
        return decode_channels(frame)

    def close(self) -> None:
        """시리얼 포트를 닫는 함수"""
        if self.ser and self.ser.is_open:
            self.ser.close()
