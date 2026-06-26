#!/usr/bin/env python3
"""laptop 쪽: Pi 가 보낸 카메라 "영상 + 마커 값"을 받아 실제 영상 위에 시각화하고,
브라우저로 볼 수 있게 MJPEG 스트리밍한다.

Pi 가 한 프레임마다 [마커 값 JSON] + [JPEG 영상] 을 청크 UDP(protocol.py)로 보낸다.
여기서 재조립 → 영상 디코딩 → 값(테두리/방향 화살표/거리 빨간 글자) 오버레이 →
http://<laptop-IP>:8090/ 로 스트리밍 → 브라우저에서 확인.

    python3 laptop_visualize.py                 # UDP 9000 수신, 브라우저 8090
    python3 laptop_visualize.py --udp-port 9000 --port 8090
"""
import argparse
import json
import pathlib
import socket
import struct
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from viz import draw_markers  # noqa: E402
from protocol import Reassembler  # noqa: E402

_latest = {"jpeg": None}
_lock = threading.Lock()
_stop = threading.Event()


def unpack_payload(payload):
    """[uint32 json_len][json][jpeg] → (meta dict, jpeg bytes)."""
    n = struct.unpack("!I", payload[:4])[0]
    meta = json.loads(payload[4:4 + n].decode())
    jpeg = payload[4 + n:]
    return meta, jpeg


def recv_loop(args):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
    sock.bind((args.host, args.udp_port))
    sock.settimeout(1.0)
    reasm = Reassembler()
    enc = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
    print(f"[laptop-view] {args.host}:{args.udp_port} 에서 Pi 영상+값 수신 대기")

    while not _stop.is_set():
        try:
            data, _ = sock.recvfrom(65535)
        except socket.timeout:
            continue
        res = reasm.push(data)
        if res is None:
            continue  # 아직 미완성 / 손상·지연 패킷
        _frame_id, payload = res
        try:
            meta, jpeg = unpack_payload(payload)
        except (struct.error, UnicodeDecodeError, json.JSONDecodeError):
            continue
        frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            continue

        dets = meta.get("detections", [])
        draw_markers(frame, dets)  # 실제 영상 위에 오버레이
        cv2.putText(frame, f'{meta.get("fps", 0):.1f} FPS (pi)  {len(dets)} marker  [laptop view]',
                    (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2, cv2.LINE_AA)
        ok, buf = cv2.imencode(".jpg", frame, enc)
        if ok:
            with _lock:
                _latest["jpeg"] = buf.tobytes()
    sock.close()


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
    ap = argparse.ArgumentParser(description="laptop: Pi 영상+값 수신 + 브라우저 시각화")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--udp-port", type=int, default=9000, help="Pi 가 보내는 UDP 포트")
    ap.add_argument("--port", type=int, default=8090, help="브라우저 미리보기 포트")
    ap.add_argument("--max-fps", type=float, default=30.0, dest="max_fps")
    args = ap.parse_args()

    worker = threading.Thread(target=recv_loop, args=(args,), daemon=True)
    worker.start()

    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    server.max_fps = args.max_fps
    ip = socket.gethostbyname(socket.gethostname())
    print(f"[laptop-view] 브라우저에서 http://{ip}:{args.port}/  (또는 http://localhost:{args.port}/)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _stop.set()
        server.shutdown()


if __name__ == "__main__":
    main()
