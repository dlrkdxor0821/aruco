# ArUco 마커 인식 (UDP 방식)

`pinky_perception` 의 UDP 전송 패턴(`common/protocol.py`, `common/camera.py`)을
그대로 재사용한다. **Pi(client)가 CSI 카메라 프레임을 JPEG로 청크 분할해 UDP로 보내고,
server가 재조립 후 ArUco 마커를 검출해 결과(ID/꼭짓점)를 UDP로 회신**한다.
결과는 브라우저 MJPEG 프리뷰로 바로 확인한다.

## 파일
- `run_laptop.sh` — **노트북에서 실행.** 검출 서버를 띄우고, Pi에 알려줄 IP를 출력.
- `run_pi.sh` — **라즈베리파이에서 실행.** 카메라 캡처 → 송신 → 브라우저 프리뷰.
- `aruco_server.py` — UDP 검출 서버. JPEG 재조립 → ArUco 검출 → JSON 회신.
- `aruco_client.py` — Pi 카메라 캡처 → UDP 송신 → 결과 수신/표시 → 브라우저 프리뷰.
- `protocol.py` — UDP 프레이밍(pinky_perception 과 동일). 서버가 독립 실행되도록 둔 사본.
- `generate_marker.py` — 테스트용 마커 PNG 생성 (인쇄/화면 표시용).

## 실행 (역할이 나뉜 스크립트)
```bash
# ── 노트북(laptop) ──  먼저 서버를 띄운다. 출력되는 IP를 확인.
./run_laptop.sh

# ── 라즈베리파이(Pi) ──  위에서 본 노트북 IP를 넣어 실행.
./run_pi.sh <laptop-ip>

# ── 확인 ──  PC 브라우저에서 열기
#    http://<라즈베리파이-IP>:8090/
```

Pi 단독으로 확인하려면 같은 Pi에서 `./run_laptop.sh` 를 띄우고
`./run_pi.sh 127.0.0.1` 로 주면 된다 (ArUco는 가벼워 Pi 단독으로도 충분).

> 노트북에는 이 폴더(`aruco_server.py`, `protocol.py`)와 OpenCV만 있으면 된다.
> Pi 쪽 카메라는 `pinky_perception` 의 `common/camera.py`(picamera2)를 그대로 쓴다.

## 테스트 마커
```bash
python3 generate_marker.py --all 4 --dict DICT_6X6_250 --size 400
# markers/ 폴더의 PNG를 화면에 띄우거나 인쇄해 카메라에 보여준다
```

## 참고
- CSI 카메라(ov5647)는 OpenCV `VideoCapture`로는 검은 화면만 나와서
  반드시 picamera2(`common.camera.Camera(source="csi")`)를 거친다.
- 이 카메라는 보통 화면이 뒤집혀 `--rotate 180` 이 필요하다.
- 다른 마커 사전을 쓰려면 server/client 의 `--dict` 를 동일하게 맞춘다.
# aruco
# aruco
