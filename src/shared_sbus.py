#!/usr/bin/env python3
"""
SBUS 데이터를 위한 공유 메모리 유틸리티

main.py에서 필터링된 SBUS 데이터를 공유 메모리에 쓰면,
다른 프로세스(예: 스트리밍)에서 읽어서 사용할 수 있습니다.
"""
import struct
from multiprocessing import shared_memory
from typing import Optional


class SBUSSharedMemory:
    """SBUS 데이터 공유 메모리 관리"""

    SHARED_NAME = "sbus_data"
    # 16 channels (int16) + flags (uint8) + padding = 34 bytes
    # struct format: 16 signed shorts (h) + 1 unsigned char (B) + padding
    STRUCT_FORMAT = "16hBx"  # 16*2 + 1 + 1(padding) = 34 bytes
    MEMORY_SIZE = struct.calcsize(STRUCT_FORMAT)

    def __init__(self, create: bool = False):
        """
        Args:
            create: True면 공유 메모리 생성 (writer), False면 기존 메모리 접근 (reader)
        """
        self.create = create
        self.shm: Optional[shared_memory.SharedMemory] = None

    def open(self):
        """공유 메모리 열기"""
        try:
            if self.create:
                # 기존 메모리가 있으면 먼저 정리
                try:
                    existing = shared_memory.SharedMemory(name=self.SHARED_NAME)
                    existing.close()
                    existing.unlink()
                except FileNotFoundError:
                    pass

                # 새로 생성
                self.shm = shared_memory.SharedMemory(
                    create=True, size=self.MEMORY_SIZE, name=self.SHARED_NAME
                )
                # 초기값으로 0 채우기
                self.shm.buf[:] = bytes(self.MEMORY_SIZE)
            else:
                # 기존 메모리 열기
                self.shm = shared_memory.SharedMemory(name=self.SHARED_NAME)
        except FileNotFoundError:
            raise RuntimeError(
                f"공유 메모리 '{self.SHARED_NAME}'를 찾을 수 없습니다. "
                "main.py가 먼저 실행되어 있는지 확인하세요."
            )

    def write(self, channels: list[int], flags: int):
        """
        필터링된 SBUS 데이터를 공유 메모리에 쓰기

        Args:
            channels: 16개 채널 값 (0~2047)
            flags: SBUS 플래그 (failsafe, frame lost 등)
        """
        if self.shm is None:
            raise RuntimeError("공유 메모리가 열려있지 않습니다.")

        # 16개 채널만 사용 (나머지는 버림)
        data = struct.pack(self.STRUCT_FORMAT, *channels[:16], flags)
        self.shm.buf[: self.MEMORY_SIZE] = data

    def read(self) -> tuple[list[int], int]:
        """
        공유 메모리에서 SBUS 데이터 읽기

        Returns:
            (channels, flags): 16개 채널 값과 플래그
        """
        if self.shm is None:
            raise RuntimeError("공유 메모리가 열려있지 않습니다.")

        data = bytes(self.shm.buf[: self.MEMORY_SIZE])
        unpacked = struct.unpack(self.STRUCT_FORMAT, data)
        channels = list(unpacked[:16])
        flags = unpacked[16]
        return channels, flags

    def close(self):
        """공유 메모리 닫기"""
        if self.shm:
            self.shm.close()
            if self.create:
                # writer만 unlink
                self.shm.unlink()
            self.shm = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# 간단한 테스트
if __name__ == "__main__":
    import time

    # Writer 예제
    print("공유 메모리 Writer 테스트...")
    with SBUSSharedMemory(create=True) as writer:
        for i in range(10):
            channels = [1000 + i * 10] * 16
            flags = i % 2
            writer.write(channels, flags)
            print(f"Write: ch[0]={channels[0]}, flags={flags}")
            time.sleep(0.5)

    print("\n공유 메모리 Reader 테스트는 다른 터미널에서 실행하세요:")
    print(
        "python3 -c 'from shared_sbus import SBUSSharedMemory; "
        "import time; shm = SBUSSharedMemory(create=False); shm.open(); "
        "[print(shm.read()) or time.sleep(0.1) for _ in range(10)]'"
    )
