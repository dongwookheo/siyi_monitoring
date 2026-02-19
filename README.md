# SIYI Monitoring
이 프로젝트는 SIYI UniRC7를 위한 통합 모니터링 솔루션입니다.
조종기의 SBUS 채널 데이터를 실시간으로 디코딩하고, mediamtx를 통한 영상 스트리밍을 통합합니다.

## 데이터 및 영상 흐름
<img width="500" height="300" alt="Image" src="https://github.com/user-attachments/assets/d61082c5-1718-4a1c-b046-b7765e0a8286" />

1. 영상 획득 (Video Input):
    - **카메라(Camera)**가 USB 또는 HDMI를 통해 PC에 직접 연결됩니다.
    - PC는 카메라로부터 고화질 영상을 직접 수신합니다.
2. 영상 전송 및 피드백 (Video Feedback):
    - PC에서 처리된 영상 신호는 연결된 **에어 유닛(Air Unit)**으로 전달됩니다.
    - 에어 유닛은 이 신호를 무선 링크를 통해 UniRC 7 조종기로 송신합니다.
    - 사용자는 WebRTC 주소로 접속하여, 조종기의 화면을 통해 실시간 영상을 확인합니다.
3. 조종 신호 및 디코딩 (Control & SBUS Decoding):
    - 사용자가 조종기를 조작하면 제어 신호가 무선으로 에어 유닛에 도달합니다.
    - 에어 유닛은 이 신호를 SBUS 형식으로 PC에 전달합니다.
    - PC에서 실행 중인 `sbus_receiver.py`가 이 신호를 실시간으로 **디코딩(Decoding)**하여 CLI에 표시합니다.

## 의존성 설치 및 실행
본 프로젝트는 영상 전송 및 중계를 위해 mediamtx를 서버로 활용합니다.

1. Repository clone
   ```bash
   git clone https://github.com/dongwookheo/siyi_monitoring.git
   ```

2. 가상환경 설정
    ```bash
    conda env create -f environment.yml
    conda activate siyi_monitoring
    pip install -e .
    ```

2. MediaMTX 설치 및 환경 설정
    - 제공된 스크립트를 사용하여 서버를 준비합니다.
    - 이 과정에서, `wget`이 미설치되어 있다면, `apt` 를 통해 설치됩니다.
    - USB 포트를 통해 연결된 `USB-to-TTL` 장치에 권한을 추가합니다 (예시에서는 `/dev/ttyUSB0).
    ```bash
    chmod +x script/install_mediamtx.sh
    chmod +x script/write_mediamtx_config.sh
    chmod 666 /dev/ttyUSB0
    ```

3. 실행  
    a. PC 실행
    - MediaMTX 서버 실행  
        ```
        ./thirdparty/mediamtx/mediamtx
        ```
    - Gstreamer를 활용한 영상 송신  
        ```
        gst-launch-1.0 v4l2src device=/dev/video4 ! video/x-raw,width=640,height=480,framerate=30/1 !  videoconvert !  x264enc tune=zerolatency bitrate=500 speed-preset=ultrafast !  rtspclientsink location=rtsp://localhost:8554/mystream
        ```
        - 설치가 안됐다면,
            ```bash
            sudo apt update
            sudo apt install gstreamer1.0-tools gstreamer1.0-plugins-* libgstreamer1.0-dev
            ```
    - 디코더 실행  
        ```
        sbus-run
        ```
    b. 조종기 실행
    - Web browser에서, Web RTC 서비스 주소 접속 (본 예시에서는`http://192.168.144.30:8889/mystream`) 접속
