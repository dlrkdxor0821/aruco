# ArUco 마커 인식 (Pi 검출 → 정보만 전송 → laptop 시각화)

**Pi 가 카메라 프레임에서 ArUco 를 직접 검출**하고, 추출한 마커 정보(id·꼭짓점·거리·yaw)만
작은 JSON(수백 바이트)으로 laptop 에 UDP 전송한다. **이미지/프레임은 보내지 않는다.**
laptop 은 그 정보를 받아 캔버스에 테두리·방향 화살표·거리(빨간 글자)를 그려 보여준다.
→ 대역폭이 작아(한 프레임 ≈ 0.4KB) WiFi 손실로 인한 끊김이 거의 없다.

## 파일 (현재 구조)
- `run_pi.sh` — **라즈베리파이에서 실행.** 카메라 캡처 → ArUco 검출 → 정보만 송신.
- `run_laptop.sh` — **노트북에서 실행.** 정보 수신 → 화면 창에 시각화.
- `pi_detect_send.py` — Pi: 검출 후 마커 정보 JSON 을 UDP 로 전송.
- `laptop_visualize.py` — laptop: JSON 수신 → 캔버스에 그려 cv2 창으로 표시.
- `aruco_server.py` — `ArucoDetector`(검출+자세추정) 정의. Pi 가 import 해서 씀.
- `viz.py` — 그리기 공용 함수(테두리/화살표/빨간 글자). 양쪽이 공유.
- `calibrate_camera.py` — Pi 에서 체커보드로 정확 보정 → `calib.npz`.
- `generate_marker.py` — 테스트용 마커 PNG 생성.

## 실행
```bash
# ── 노트북(laptop) ──  먼저 뷰어를 띄운다. 출력되는 IP를 확인.
./run_laptop.sh

# ── 라즈베리파이(Pi) ──  위에서 본 노트북 IP + 마커 실제 크기(m).
MARKER=0.08 ./run_pi.sh <laptop-ip>
```
노트북 화면 창에 마커 박스·방향 화살표·거리/yaw(빨간 글자)가 실시간 표시된다(q 종료).

> 노트북에는 이 폴더(`laptop_visualize.py`, `viz.py`)와 OpenCV/numpy만 있으면 된다
> (카메라가 없으니 pinky_perception 불필요). Pi 쪽 카메라만 `pinky_perception` 의
> `common/camera.py`(picamera2)를 쓴다.

### 다른 모드 (참고)
- `detect_pi.py` / `run_pi_solo.sh` — Pi 단독: 검출도 표시도 Pi 에서, 브라우저로 확인.
- `aruco_client.py` — (구) Pi 가 프레임을 보내고 서버가 검출하던 방식.

## 테스트 마커
```bash
python3 generate_marker.py --all 4 --dict DICT_6X6_250 --size 400
# markers/ 폴더의 PNG를 화면에 띄우거나 인쇄해 카메라에 보여준다
```

## 거리·방향(자세) 표시
Pi 가 `solvePnP`로 각 마커의 거리(m)·yaw(도)를 추정해 정보에 담아 보내고,
laptop 이 마커 옆에 **빨간 글자**로 표시하며 **방향 화살표**(빨강 X·초록 Y·파랑 Z=정면)를 그린다.

- **마커 실제 크기를 반드시 맞춰야** 거리가 맞다: `MARKER=0.08 ./run_pi.sh <ip>` (8cm).
- 보정 파일이 없으면 화각으로 근사하며, 거리 앞에 `~`가 붙는다(대략값).
- **정확한 거리**가 필요하면 Pi에서 체커보드 1회 보정 (검출이 Pi 에서 일어나므로 보정도 Pi 에):
  ```bash
  # Pi 에서 (실제 쓸 카메라/해상도로)
  python3 calibrate_camera.py --cols 9 --rows 6 --square 0.025
  #  → calib.npz 생성. 그대로 Pi 에서
  CALIB=calib.npz MARKER=0.08 ./run_pi.sh <laptop-ip>
  ```

## 참고
- CSI 카메라(ov5647)는 OpenCV `VideoCapture`로는 검은 화면만 나와서
  반드시 picamera2(`common.camera.Camera(source="csi")`)를 거친다.
- 이 카메라는 보통 화면이 뒤집혀 `--rotate 180` 이 필요하다.
- 다른 마커 사전을 쓰려면 server/client 의 `--dict` 를 동일하게 맞춘다.
# aruco
# aruco
