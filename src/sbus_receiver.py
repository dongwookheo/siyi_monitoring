import serial

class SBUSReceiver:
    def __init__(self, port, baudrate, timeout):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.frame_len = 25
        self.start_byte = 0x0F
        self.ser = serial.Serial(
            port, baudrate=baudrate, bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_EVEN, stopbits=serial.STOPBITS_TWO,
            timeout=timeout
        )

    def get_latest_frame(self) -> bytes | None:
        waiting = self.ser.in_waiting
        if waiting < self.frame_len:
            return None
        
        data = self.ser.read(waiting)
        for i in range(len(data) - self.frame_len, -1, -1):
            if data[i] == self.start_byte:
                if data[i + 24] in (0x00, 0x04, 0x14, 0x24, 0x34):
                    return data[i : i + self.frame_len]
        return None

    @staticmethod
    def decode_channels(frame: bytes):
        b = frame
        ch = [0] * 16
        ch[0] = (b[1] | b[2] << 8) & 0x07FF
        ch[1] = (b[2] >> 3 | b[3] << 5) & 0x07FF
        ch[2] = (b[3] >> 6 | b[4] << 2 | b[5] << 10) & 0x07FF
        ch[3] = (b[5] >> 1 | b[6] << 7) & 0x07FF
        # 4~15 채널은 필요시 추가 구현 가능
        flags = b[23]
        return ch, flags

    def close(self):
        self.ser.close()