#!/usr/bin/env python3
"""Pi 쪽: 카메라 프레임에서 ArUco 를 직접 검출하고 "정보만" laptop 으로 UDP 전송.

이미지/프레임은 보내지 않는다. Pi 가 검출까지 끝내고, 추출한 마커 정보
(id, 꼭짓점, 거리, yaw, 축 투영점)를 작은 JSON 한 덩어리로 보낸다.
→ 대역폭이 매우 작아 WiFi 손실로 인한 끊김이 거의 없다.

laptop 에서는 laptop_visualize.py 가 이 JSON 을 받아 시각화한다.

    python3 pi_detect_send.py --host <laptop-ip> --marker-size 0.08
    python3 pi_detect_send.py --host <laptop-ip> --marker-size 0.08 --calib calib.npz
    python3 pi_detect_send.py --host <laptop-ip> --log
"""
import argparse
import json
import pathlib
import socket
import sys
import time

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from aruco_server import ArucoDetector, ARUCO_DICTS  # noqa: E402

PERCEPTION_ROOT = pathlib.Path("/home/pinky/leekt/pinky_perception/perception")
sys.path.insert(0, str(PERCEPTION_ROOT))
from common.camera import Camera  # noqa: E402


def build_message(detector, frame, frame_id, fps):
    """프레임을 검출해 전송할 JSON 메시지(dict)를 만든다. (카메라 없이도 테스트 가능)"""
    dets = detector.detect(frame)
    h, w = frame.shape[:2]
    return {
        "frame_id": frame_id,
        "w": int(w), "h": int(h),     # laptop 이 캔버스 크기를 알도록
        "fps": round(fps, 1),
        "detections": dets,           # id/corners/center/distance_m/yaw_deg/axes_2d
    }


def main():
    ap = argparse.ArgumentParser(description="Pi 단독 검출 + 정보만 UDP 송신")
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
    src = int(args.source) if str(args.source).isdigit() else args.source
    print(f"[pi-send] '{args.dict}' 검출 → {addr} 로 정보 전송 (마커 {args.marker_size}m)")

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

            msg = build_message(detector, frame, i, fps)
            sock.sendto(json.dumps(msg).encode(), addr)  # 이미지 없이 정보만

            if args.log:
                ds = msg["detections"]
                if ds:
                    for d in ds:
                        s = f"id={d['id']}"
                        if "distance_m" in d:
                            s += f" dist={d['distance_m']:.2f}m yaw={d['yaw_deg']:.0f}"
                        print(f"[pi-send] {s}")
                else:
                    print("[pi-send] no marker")
            i += 1


if __name__ == "__main__":
    main()
