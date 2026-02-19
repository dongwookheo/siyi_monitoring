import serial


class SBUSReceiver:
    def __init__(self, port, baudrate, timeout):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.frame_len = 25
        self.start_byte = 0x0F
        self.ser = serial.Serial(
            port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_TWO,
            timeout=timeout,
        )

    def get_latest_frame(self) -> bytes | None:
        waiting = self.ser.in_waiting
        if waiting < self.frame_len:
            return None

        data = self.ser.read(waiting)
        # 지연 방지를 위해 버퍼의 가장 마지막(최신) 프레임을 뒤에서부터 검색
        for i in range(len(data) - self.frame_len, -1, -1):
            if data[i] == self.start_byte:
                # 종료 바이트 검증 (표준 SBUS 규격 대응)
                if data[i + 24] in (0x00, 0x04, 0x14, 0x24, 0x34):
                    return data[i : i + self.frame_len]
        return None

    @staticmethod
    def decode_channels(frame: bytes):
        """
        25바이트 프레임에서 11비트씩 16개 채널을 파싱합니다.
        """
        b = frame
        ch = [0] * 16

        # 비트 연산을 통한 11비트 추출 (CH1 ~ CH16)
        ch[0] = (b[1] | b[2] << 8) & 0x07FF
        ch[1] = (b[2] >> 3 | b[3] << 5) & 0x07FF
        ch[2] = (b[3] >> 6 | b[4] << 2 | b[5] << 10) & 0x07FF
        ch[3] = (b[5] >> 1 | b[6] << 7) & 0x07FF
        ch[4] = (b[6] >> 4 | b[7] << 4) & 0x07FF
        raw_ch5 = (b[7] >> 7 | b[8] << 1 | b[9] << 9) & 0x07FF
        ch[5] = 1983 - raw_ch5
        ch[6] = (b[9] >> 2 | b[10] << 6) & 0x07FF
        ch[7] = (b[10] >> 5 | b[11] << 3) & 0x07FF
        ch[8] = (b[12] | b[13] << 8) & 0x07FF
        ch[9] = (b[13] >> 3 | b[14] << 5) & 0x07FF
        ch[10] = (b[14] >> 6 | b[15] << 2 | b[16] << 10) & 0x07FF
        ch[11] = (b[16] >> 1 | b[17] << 7) & 0x07FF
        ch[12] = (b[17] >> 4 | b[18] << 4) & 0x07FF
        ch[13] = (b[18] >> 7 | b[19] << 1 | b[20] << 9) & 0x07FF
        ch[14] = (b[20] >> 2 | b[21] << 6) & 0x07FF
        ch[15] = (b[21] >> 5 | b[22] << 3) & 0x07FF

        flags = b[23]

        return ch, flags

    def close(self):
        self.ser.close()
