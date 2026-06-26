#!/usr/bin/env python3
"""ChArUco 보드(아루코 마커 체커보드)로 카메라 내부보정(intrinsic)을 구해 calib.npz 저장.
== 라즈베리파이(Pi)에서, 실제로 쓸 카메라/해상도로 실행 ==

일반 체스보드(calibrate_camera.py)보다 가림/부분 노출에 강해 더 정확하다.
generate_charuco.py 로 뽑은 보드를 그대로 쓰면 되고, 보드 파라미터
(--squares-x/-y, --square, --marker, --dict)를 인쇄한 보드와 똑같이 맞춰야 한다.

준비물: generate_charuco.py 기본값 보드 = 5x7 칸, 칸 3.5cm(0.035m),
       마커 2.6cm(0.026m), DICT_4X4_50. (인쇄 후 자로 칸 크기 확인!)

사용법(라이브):
    python3 calibrate_charuco.py --source csi --rotate 180 \
        --squares-x 5 --squares-y 7 --square 0.035 --marker 0.026
    # 보드를 여러 각도/거리로 천천히 보여준다. SPACE=캡처, c=계산/저장, q=취소

디스플레이가 없으면 --headless 로 자동 수집:
    python3 calibrate_charuco.py --headless --need 20 --square 0.035 --marker 0.026
"""
import argparse
import pathlib
import sys
import time

import cv2
import numpy as np

PERCEPTION_ROOT = pathlib.Path("/home/pinky/leekt/pinky_perception/perception")
sys.path.insert(0, str(PERCEPTION_ROOT))
from common.camera import Camera  # noqa: E402

ARUCO_DICTS = {
    "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
    "DICT_5X5_100": cv2.aruco.DICT_5X5_100,
    "DICT_6X6_250": cv2.aruco.DICT_6X6_250,
}


def main():
    ap = argparse.ArgumentParser(description="ChArUco 카메라 보정")
    ap.add_argument("--source", default="csi")
    ap.add_argument("--rotate", type=int, default=180, choices=[0, 90, 180, 270])
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    # 아래 보드 인자는 인쇄한 ChArUco 보드와 반드시 일치시킬 것
    ap.add_argument("--dict", default="DICT_4X4_50", choices=list(ARUCO_DICTS))
    ap.add_argument("--squares-x", type=int, default=5, help="가로 칸 수")
    ap.add_argument("--squares-y", type=int, default=7, help="세로 칸 수")
    ap.add_argument("--square", type=float, default=0.035, help="한 칸 길이(m)")
    ap.add_argument("--marker", type=float, default=0.026, help="마커 길이(m)")
    ap.add_argument("--min-corners", type=int, default=6,
                    help="한 장 채택에 필요한 최소 ChArUco 코너 수")
    ap.add_argument("--need", type=int, default=20, help="모을 샘플 수")
    ap.add_argument("--headless", action="store_true", help="창 없이 자동 수집")
    ap.add_argument("--interval", type=float, default=0.7,
                    help="headless 에서 캡처 간 최소 간격(초)")
    ap.add_argument("--out", default="calib.npz")
    args = ap.parse_args()

    dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICTS[args.dict])
    board = cv2.aruco.CharucoBoard_create(
        args.squares_x, args.squares_y, args.square, args.marker, dictionary)
    det_params = cv2.aruco.DetectorParameters_create()

    all_corners, all_ids = [], []
    src = int(args.source) if str(args.source).isdigit() else args.source
    last_cap = 0.0
    print(f"[calib] ChArUco {args.squares_x}x{args.squares_y}, 칸 {args.square} m, "
          f"마커 {args.marker} m, {args.dict}. 목표 {args.need} 장.")

    with Camera(src, width=args.width, height=args.height, rotate=args.rotate) as cam:
        gray = None
        while len(all_corners) < args.need:
            frame = cam.read()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            m_corners, m_ids, _ = cv2.aruco.detectMarkers(
                gray, dictionary, parameters=det_params)

            ch_n, ch_corners, ch_ids = 0, None, None
            if m_ids is not None and len(m_ids) > 0:
                ch_n, ch_corners, ch_ids = cv2.aruco.interpolateCornersCharuco(
                    m_corners, m_ids, gray, board)

            now = time.perf_counter()
            take = False
            usable = ch_n is not None and ch_n >= args.min_corners
            if args.headless:
                take = usable and (now - last_cap) > args.interval
            else:
                if m_ids is not None and len(m_ids) > 0:
                    cv2.aruco.drawDetectedMarkers(frame, m_corners, m_ids)
                if usable:
                    cv2.aruco.drawDetectedCornersCharuco(
                        frame, ch_corners, ch_ids, (0, 255, 0))
                msg = (f"{len(all_corners)}/{args.need}  corners={ch_n or 0}  "
                       f"SPACE=capture c=calc q=quit")
                cv2.putText(frame, msg, (8, 24),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.imshow("calib_charuco", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("[calib] 취소")
                    return
                if key == ord("c"):
                    break
                take = usable and key == ord(" ")

            if take:
                all_corners.append(ch_corners)
                all_ids.append(ch_ids)
                last_cap = now
                print(f"[calib] 캡처 {len(all_corners)}/{args.need} "
                      f"(코너 {ch_n})")

        if not args.headless:
            cv2.destroyAllWindows()

        if len(all_corners) < 5:
            print("[calib] 샘플이 너무 적습니다. 중단.")
            return

        img_size = gray.shape[::-1]
        rms, K, dist, _, _ = cv2.aruco.calibrateCameraCharuco(
            all_corners, all_ids, board, img_size, None, None)
        np.savez(args.out, camera_matrix=K, dist_coeffs=dist,
                 image_size=np.array(img_size))
        print(f"[calib] 완료. 재투영 오차(RMS)={rms:.3f} px  → {args.out}")
        print(f"[calib] fx={K[0,0]:.1f} fy={K[1,1]:.1f} "
              f"cx={K[0,2]:.1f} cy={K[1,2]:.1f}")
        print("[calib] 이 calib.npz 를 서버(노트북)로 복사해 "
              "aruco_server.py --calib calib.npz 로 쓰세요.")


if __name__ == "__main__":
    main()
