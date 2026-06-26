#!/usr/bin/env python3
"""ArUco UDP 클라이언트 (라즈베리파이 쪽).

pinky_perception 의 preview_client.py / camera.py / protocol.py 패턴을 그대로 따른다.
동작: CSI 카메라(picamera2)로 프레임 캡처 → JPEG 인코딩 → UDP 청크 전송 →
서버(aruco_server.py)에서 받은 검출 결과(마커 ID/꼭짓점)를 프레임에 그려서
브라우저로 MJPEG 스트리밍 → PC 브라우저에서 잘 보이는지 바로 확인 가능.

    # 1) 검출 서버 실행 (PC 또는 같은 Pi)
    python3 aruco_server.py --port 9000

    # 2) Pi 에서 클라이언트 실행
    python3 aruco_client.py --host <server-ip> --source csi --rotate 180

그 다음 PC 브라우저에서  http://<라즈베리파이-IP>:8090/  열기.

서버 없이 Pi 단독으로 확인하려면 같은 Pi 에서 aruco_server.py 를 띄우고
--host 127.0.0.1 로 주면 된다 (ArUco 는 가벼워서 Pi 단독으로도 충분).
"""
import argparse
import json
import pathlib
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2

# UDP 프레이밍은 같은 폴더의 사본에서 (pinky_perception 과 동일 방식)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from protocol import encode_frame, decode_result  # noqa: E402

# 카메라(CSI/picamera2)는 pinky_perception 의 검증된 Camera 를 그대로 쓴다 (Pi 전용)
PERCEPTION_ROOT = pathlib.Path("/home/pinky/leekt/pinky_perception/perception")
sys.path.insert(0, str(PERCEPTION_ROOT))
from common.camera import Camera  # noqa: E402
from viz import draw_markers  # noqa: E402

_latest = {"jpeg": None}
_lock = threading.Lock()
_stop = threading.Event()


def capture_loop(args):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_addr = (args.host, args.udp_port)
    enc = [int(cv2.IMWRITE_JPEG_QUALITY), args.quality]
    src = int(args.source) if args.source.isdigit() else args.source
    print(f"[aruco-client] -> server {args.host}:{args.udp_port}")

    with Camera(src, width=args.width, height=args.height, rotate=args.rotate,
                hflip=args.hflip, vflip=args.vflip) as cam:
        t_prev = time.perf_counter()
        i = 0
        while not _stop.is_set():
            frame = cam.read()
            ok, buf = cv2.imencode(".jpg", frame, enc)
            if not ok:
                continue

            # 서버로 청크 전송 후 같은 frame_id 의 결과 수신
            for dg in encode_frame(i, buf.tobytes()):
                sock.sendto(dg, server_addr)
            sock.settimeout(1.0)
            dets = []
            try:
                while True:
                    data, _ = sock.recvfrom(65535)
                    fid, payload = decode_result(data)
                    if fid == (i & 0xFFFFFFFF):
                        dets = json.loads(payload.decode()).get("detections", [])
                        break
            except socket.timeout:
                pass
            i += 1

            draw_markers(frame, dets)
            now = time.perf_counter()
            fps = 1.0 / (now - t_prev) if now > t_prev else 0.0
            t_prev = now
            cv2.putText(frame, f"{fps:4.1f} FPS  {len(dets)} marker", (8, 26),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)
            ok, out = cv2.imencode(".jpg", frame, enc)
            if ok:
                with _lock:
                    _latest["jpeg"] = out.tobytes()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path not in ("/", "/stream"):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            while not _stop.is_set():
                with _lock:
                    jpg = _latest["jpeg"]
                if jpg is None:
                    time.sleep(0.05)
                    continue
                self.wfile.write(
                    b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                    + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
                time.sleep(1.0 / self.server.max_fps)
        except (BrokenPipeError, ConnectionResetError):
            pass


def main():
    ap = argparse.ArgumentParser(description="ArUco UDP 클라이언트 (Pi 카메라)")
    ap.add_argument("--host", required=True, help="aruco_server.py 가 도는 IP")
    ap.add_argument("--udp-port", type=int, default=9000)
    ap.add_argument("--source", default="csi",
                    help="'csi'=Pi 카메라, 숫자=USB 웹캠 인덱스")
    ap.add_argument("--rotate", type=int, default=180, choices=[0, 90, 180, 270],
                    help="화면 방향 보정 (이 카메라는 보통 180)")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--hflip", action="store_true")
    ap.add_argument("--vflip", action="store_true")
    ap.add_argument("--port", type=int, default=8090, help="브라우저 프리뷰 포트")
    ap.add_argument("--quality", type=int, default=80)
    ap.add_argument("--max-fps", type=float, default=30.0, dest="max_fps")
    args = ap.parse_args()

    worker = threading.Thread(target=capture_loop, args=(args,), daemon=True)
    worker.start()

    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    server.max_fps = args.max_fps
    print(f"[aruco-client] 브라우저에서 http://<이-Pi-IP>:{args.port}/ 열기")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _stop.set()
        server.shutdown()


if __name__ == "__main__":
    main()
