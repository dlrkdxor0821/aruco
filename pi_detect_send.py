#!/usr/bin/env python3
"""Pi 쪽: 카메라에서 ArUco 를 직접 검출하고, 카메라 "영상 + 마커 값"을 laptop 으로 UDP 전송.

- Pi 에서는 아무 화면도 띄우지 않는다 (영상은 laptop 에서만 본다).
- 검출은 Pi 가 한다. 한 프레임마다 [마커 값 JSON] + [JPEG 영상] 을 하나로 묶어
  pinky_perception 의 청크 UDP 방식(protocol.py)으로 보낸다.
- laptop 의 laptop_visualize.py 가 받아서 실제 영상 위에 시각화한다.

    python3 pi_detect_send.py --host <laptop-ip> --marker-size 0.08
    python3 pi_detect_send.py --host <laptop-ip> --marker-size 0.08 --calib calib.npz
    python3 pi_detect_send.py --host <laptop-ip> --log
"""
import argparse
import json
import pathlib
import socket
import struct
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from aruco_server import ArucoDetector, ARUCO_DICTS  # noqa: E402
from protocol import encode_frame  # noqa: E402

PERCEPTION_ROOT = pathlib.Path("/home/pinky/leekt/pinky_perception/perception")
sys.path.insert(0, str(PERCEPTION_ROOT))
from common.camera import Camera  # noqa: E402


def pack_payload(dets, jpeg, fps, frame_id):
    """[uint32 json_len][json bytes][jpeg bytes] 로 묶는다. laptop 이 다시 분리."""
    meta = json.dumps({"fps": round(fps, 1), "frame_id": frame_id,
                       "detections": dets}).encode()
    return struct.pack("!I", len(meta)) + meta + jpeg


def main():
    ap = argparse.ArgumentParser(description="Pi 검출 + 영상/값 UDP 송신")
    ap.add_argument("--host", required=True, help="laptop(뷰어) IP")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--dict", default="DICT_6X6_250", choices=list(ARUCO_DICTS))
    ap.add_argument("--marker-size", type=float, default=0.05,
                    help="마커 한 변 실제 길이(m). 거리/방향 추정에 필요")
    ap.add_argument("--calib", default=None, help="카메라 보정 .npz (없으면 화각 근사)")
    ap.add_argument("--hfov", type=float, default=54.0, help="보정 없을 때 수평화각(도)")
    ap.add_argument("--source", default="csi")
    ap.add_argument("--rotate", type=int, default=180, choices=[0, 90, 180, 270])
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--hflip", action="store_true")
    ap.add_argument("--vflip", action="store_true")
    ap.add_argument("--quality", type=int, default=80, help="JPEG 품질")
    ap.add_argument("--log", action="store_true", help="프레임마다 값을 터미널에 출력")
    args = ap.parse_args()

    K = dist = None
    if args.calib:
        data = np.load(args.calib)
        K, dist = data["camera_matrix"], data["dist_coeffs"]
        print(f"[calib] {args.calib} 로 정확 자세추정")
    else:
        print(f"[calib] 보정 없음 → 화각 {args.hfov}° 근사 (거리는 대략값)")

    detector = ArucoDetector(args.dict, marker_size=args.marker_size,
                             camera_matrix=K, dist_coeffs=dist, hfov_deg=args.hfov)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    addr = (args.host, args.port)
    enc = [int(cv2.IMWRITE_JPEG_QUALITY), args.quality]
    src = int(args.source) if str(args.source).isdigit() else args.source
    print(f"[pi-send] '{args.dict}' 검출 → {addr} 로 영상+값 전송 (마커 {args.marker_size}m)")

    with Camera(src, width=args.width, height=args.height, rotate=args.rotate,
                hflip=args.hflip, vflip=args.vflip) as cam:
        t_prev = time.perf_counter()
        fps = 0.0
        i = 0
        while True:
            frame = cam.read()
            now = time.perf_counter()
            fps = 0.9 * fps + 0.1 * (1.0 / max(now - t_prev, 1e-6))
            t_prev = now

            dets = detector.detect(frame)                  # ← Pi 가 직접 검출
            ok, buf = cv2.imencode(".jpg", frame, enc)
            if not ok:
                continue
            payload = pack_payload(dets, buf.tobytes(), fps, i)
            for dg in encode_frame(i, payload):            # 영상+값을 청크로 전송
                sock.sendto(dg, addr)

            if args.log:
                if dets:
                    for d in dets:
                        s = f"id={d['id']}"
                        if "distance_m" in d:
                            s += f" dist={d['distance_m']:.2f}m yaw={d['yaw_deg']:.0f}"
                        print(f"[pi-send] {s}")
                else:
                    print("[pi-send] no marker")
            i += 1


if __name__ == "__main__":
    main()
