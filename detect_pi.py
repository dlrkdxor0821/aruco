#!/usr/bin/env python3
"""라즈베리파이 단독 ArUco 인식 (검출 주체 = Pi).

노트북/UDP 없이 Pi가 직접: CSI 카메라 캡처 → ArUco 검출(+거리/방향) → 화면 표시.
네트워크 왕복이 없으니 WiFi 패킷 손실로 인한 끊김이 사라진다.

결과 보기 두 가지:
  - 브라우저 프리뷰(기본): http://<Pi-IP>:8090/  (디스플레이 없어도 됨)
  - 터미널 로그: --log  (프레임마다 id/거리/yaw 출력)

    python3 detect_pi.py --marker-size 0.08
    python3 detect_pi.py --marker-size 0.08 --calib calib.npz   # 정확 거리
    python3 detect_pi.py --log                                  # 터미널에도 값 출력
"""
import argparse
import pathlib
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np

# 검출+자세추정 로직(ArucoDetector)과 그리기(draw_markers)를 그대로 재사용
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from aruco_server import ArucoDetector, ARUCO_DICTS  # noqa: E402
from viz import draw_markers  # noqa: E402

# 카메라(CSI/picamera2)는 pinky_perception 의 Camera 사용
PERCEPTION_ROOT = pathlib.Path("/home/pinky/leekt/pinky_perception/perception")
sys.path.insert(0, str(PERCEPTION_ROOT))
from common.camera import Camera  # noqa: E402

_latest = {"jpeg": None}
_lock = threading.Lock()
_stop = threading.Event()


def capture_loop(args):
    K = dist = None
    if args.calib:
        data = np.load(args.calib)
        K, dist = data["camera_matrix"], data["dist_coeffs"]
        print(f"[calib] {args.calib} 로 정확 자세추정")
    else:
        print(f"[calib] 보정 없음 → 화각 {args.hfov}° 근사 (거리는 대략값)")

    detector = ArucoDetector(args.dict, marker_size=args.marker_size,
                             camera_matrix=K, dist_coeffs=dist, hfov_deg=args.hfov)
    enc = [int(cv2.IMWRITE_JPEG_QUALITY), args.quality]
    src = int(args.source) if str(args.source).isdigit() else args.source
    print(f"[detect-pi] '{args.dict}' 로 Pi 단독 검출 시작 (마커 {args.marker_size}m)")

    with Camera(src, width=args.width, height=args.height, rotate=args.rotate,
                hflip=args.hflip, vflip=args.vflip) as cam:
        t_prev = time.perf_counter()
        while not _stop.is_set():
            frame = cam.read()
            dets = detector.detect(frame)        # ← Pi 가 직접 검출
            draw_markers(frame, dets)

            now = time.perf_counter()
            fps = 1.0 / (now - t_prev) if now > t_prev else 0.0
            t_prev = now
            cv2.putText(frame, f"{fps:4.1f} FPS  {len(dets)} marker [pi]", (8, 26),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)

            if args.log:
                if dets:
                    for d in dets:
                        msg = f"id={d['id']}"
                        if "distance_m" in d:
                            msg += f" dist={d['distance_m']:.2f}m yaw={d['yaw_deg']:.0f}"
                        print(f"[detect-pi] {msg}")
                else:
                    print("[detect-pi] no marker")

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
    ap = argparse.ArgumentParser(description="라즈베리파이 단독 ArUco 인식")
    ap.add_argument("--dict", default="DICT_6X6_250", choices=list(ARUCO_DICTS))
    ap.add_argument("--marker-size", type=float, default=0.05,
                    help="마커 한 변 실제 길이(m). 거리/방향 추정에 필요")
    ap.add_argument("--calib", default=None, help="카메라 보정 .npz (없으면 화각 근사)")
    ap.add_argument("--hfov", type=float, default=54.0, help="보정 없을 때 수평화각(도)")
    ap.add_argument("--source", default="csi", help="'csi' 또는 USB 인덱스 숫자")
    ap.add_argument("--rotate", type=int, default=180, choices=[0, 90, 180, 270])
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--hflip", action="store_true")
    ap.add_argument("--vflip", action="store_true")
    ap.add_argument("--port", type=int, default=8090, help="브라우저 프리뷰 포트")
    ap.add_argument("--quality", type=int, default=80)
    ap.add_argument("--max-fps", type=float, default=30.0, dest="max_fps")
    ap.add_argument("--log", action="store_true", help="프레임마다 값을 터미널에 출력")
    args = ap.parse_args()

    worker = threading.Thread(target=capture_loop, args=(args,), daemon=True)
    worker.start()

    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    server.max_fps = args.max_fps
    pi_ip = "<이-Pi-IP>"
    print(f"[detect-pi] 브라우저에서 http://{pi_ip}:{args.port}/ 열기")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _stop.set()
        server.shutdown()


if __name__ == "__main__":
    main()
