#!/usr/bin/env python3
"""체커보드로 카메라 내부보정(intrinsic) 값을 구해 calib.npz 로 저장한다.
== 라즈베리파이(Pi)에서, 실제로 쓸 카메라/해상도로 실행 ==

정확한 거리/방향(자세) 추정을 하려면 이 보정이 필요하다. 보정 없이도 서버는
화각(--hfov)으로 근사하지만, 거리값은 대략값이다.

준비물: 체커보드(예: A4에 인쇄한 9x6 내부코너 격자). --cols/--rows 는
       "내부 코너" 개수(검은/흰 칸 경계 교차점)이고 칸 수보다 1 적다.
       --square 는 한 칸 실제 길이(m).

사용법:
    python3 calibrate_camera.py --source csi --rotate 180 --cols 9 --rows 6 --square 0.025
    # 체커보드를 여러 각도/거리로 천천히 움직이며 보여준다. 인식되면 자동 캡처.
    # SPACE=수동 캡처, c=보정 계산 후 저장, q=취소

디스플레이가 없으면 --headless 로 자동 수집:
    python3 calibrate_camera.py --headless --need 20 --cols 9 --rows 6 --square 0.025
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


def main():
    ap = argparse.ArgumentParser(description="체커보드 카메라 보정")
    ap.add_argument("--source", default="csi")
    ap.add_argument("--rotate", type=int, default=180, choices=[0, 90, 180, 270])
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--cols", type=int, default=9, help="체커보드 내부코너 가로 개수")
    ap.add_argument("--rows", type=int, default=6, help="체커보드 내부코너 세로 개수")
    ap.add_argument("--square", type=float, default=0.025, help="한 칸 길이(m)")
    ap.add_argument("--need", type=int, default=20, help="모을 샘플 수")
    ap.add_argument("--headless", action="store_true", help="창 없이 자동 수집")
    ap.add_argument("--interval", type=float, default=0.7,
                    help="headless 에서 캡처 간 최소 간격(초)")
    ap.add_argument("--out", default="calib.npz")
    args = ap.parse_args()

    pattern = (args.cols, args.rows)
    # 보드 좌표계의 3D 점 (z=0 평면), 실제 칸 길이 반영
    objp = np.zeros((args.rows * args.cols, 3), np.float32)
    objp[:, :2] = np.mgrid[0:args.cols, 0:args.rows].T.reshape(-1, 2)
    objp *= args.square
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    objpoints, imgpoints = [], []
    src = int(args.source) if str(args.source).isdigit() else args.source
    last_cap = 0.0
    print(f"[calib] {pattern} 내부코너, 칸 {args.square} m. 목표 {args.need} 장.")

    with Camera(src, width=args.width, height=args.height, rotate=args.rotate) as cam:
        gray = None
        while len(objpoints) < args.need:
            frame = cam.read()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            found, corners = cv2.findChessboardCorners(
                gray, pattern,
                cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE)

            now = time.perf_counter()
            take = False
            if args.headless:
                take = found and (now - last_cap) > args.interval
            else:
                if found:
                    cv2.drawChessboardCorners(frame, pattern, corners, found)
                cv2.putText(frame, f"{len(objpoints)}/{args.need}  SPACE=capture c=calc q=quit",
                            (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.imshow("calib", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("[calib] 취소")
                    return
                if key == ord("c"):
                    break
                take = found and key == ord(" ")

            if take:
                refined = cv2.cornerSubPix(
                    gray, corners, (11, 11), (-1, -1), criteria)
                objpoints.append(objp.copy())
                imgpoints.append(refined)
                last_cap = now
                print(f"[calib] 캡처 {len(objpoints)}/{args.need}")

        if not args.headless:
            cv2.destroyAllWindows()

        if len(objpoints) < 5:
            print("[calib] 샘플이 너무 적습니다. 중단.")
            return

        rms, K, dist, _, _ = cv2.calibrateCamera(
            objpoints, imgpoints, gray.shape[::-1], None, None)
        np.savez(args.out, camera_matrix=K, dist_coeffs=dist,
                 image_size=np.array(gray.shape[::-1]))
        print(f"[calib] 완료. 재투영 오차(RMS)={rms:.3f} px  → {args.out}")
        print(f"[calib] fx={K[0,0]:.1f} fy={K[1,1]:.1f} cx={K[0,2]:.1f} cy={K[1,2]:.1f}")
        print("[calib] 이 calib.npz 를 서버(노트북)로 복사해 "
              "aruco_server.py --calib calib.npz 로 쓰세요.")


if __name__ == "__main__":
    main()
