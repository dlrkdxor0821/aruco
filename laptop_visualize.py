#!/usr/bin/env python3
"""laptop 쪽: Pi 가 보낸 ArUco "정보"(JSON)를 받아 캔버스에 시각화.

이미지를 받지 않으므로, Pi 가 알려준 프레임 크기(w,h)만 한 빈 캔버스에 마커
테두리/방향 화살표/거리(빨간 글자)를 지금까지처럼 그려서 보여준다.

화면 창(cv2.imshow) 표시가 기본. 디스플레이가 없으면 --headless 로 프레임만
저장해 확인할 수 있다.

    python3 laptop_visualize.py                 # UDP 9000 수신, 창으로 표시 (q 종료)
    python3 laptop_visualize.py --port 9000
    python3 laptop_visualize.py --headless --frames 30 --save out.jpg   # 창 없이 확인
"""
import argparse
import json
import pathlib
import socket
import sys

import cv2
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from viz import draw_markers  # noqa: E402


def render(msg, bg=30):
    """수신한 메시지(dict)를 캔버스에 그려 BGR 이미지로 돌려준다."""
    w = int(msg.get("w", 640))
    h = int(msg.get("h", 480))
    canvas = np.full((h, w, 3), bg, np.uint8)
    dets = msg.get("detections", [])
    draw_markers(canvas, dets)
    cv2.putText(canvas, f'{msg.get("fps", 0):.1f} FPS (pi)  {len(dets)} marker  [laptop view]',
                (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2, cv2.LINE_AA)
    return canvas


def main():
    ap = argparse.ArgumentParser(description="laptop: Pi 정보 수신 + 시각화")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--headless", action="store_true", help="창 없이 (디스플레이 없을 때)")
    ap.add_argument("--frames", type=int, default=0, help="처리할 프레임 수 제한(0=무제한)")
    ap.add_argument("--save", default=None, help="마지막 프레임 저장 경로")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 * 1024 * 1024)
    sock.bind((args.host, args.port))
    sock.settimeout(2.0)
    print(f"[laptop-view] {args.host}:{args.port} 에서 Pi 정보 수신 대기 (q 종료)")

    last = None
    count = 0
    while True:
        try:
            data, _ = sock.recvfrom(65535)
        except socket.timeout:
            if not args.headless:
                wait = np.full((200, 520, 3), 30, np.uint8)
                cv2.putText(wait, "waiting for Pi...", (20, 110),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2, cv2.LINE_AA)
                cv2.imshow("ArUco (laptop view)", wait)
                if (cv2.waitKey(1) & 0xFF) in (ord("q"), 27):
                    break
            continue

        try:
            msg = json.loads(data.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue  # 손상/부분 패킷 무시

        frame = render(msg)
        last = frame
        count += 1

        if not args.headless:
            cv2.imshow("ArUco (laptop view)", frame)
            if (cv2.waitKey(1) & 0xFF) in (ord("q"), 27):
                break
        if args.frames and count >= args.frames:
            break

    sock.close()
    if not args.headless:
        cv2.destroyAllWindows()
    if args.save and last is not None:
        cv2.imwrite(args.save, last)
        print(f"[laptop-view] 저장: {args.save}")


if __name__ == "__main__":
    main()
