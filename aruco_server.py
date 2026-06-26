#!/usr/bin/env python3
"""ArUco UDP 검출 서버.

pinky_perception 의 UDP 전송 방식(common/protocol.py)을 그대로 재사용한다.
동작: 청크로 쪼개져 오는 JPEG 프레임을 재조립 → ArUco 마커 검출 →
검출 결과(JSON: 마커 ID와 네 꼭짓점 좌표)를 보낸 쪽으로 UDP 회신.

    python3 aruco_server.py --port 9000 --dict DICT_6X6_250

클라이언트(라즈베리파이): aruco_client.py 참고.
"""
import argparse
import json
import pathlib
import socket
import sys
import time

import cv2
import numpy as np

# UDP 프레이밍(pinky_perception 과 동일 방식)을 같은 폴더의 사본에서 가져온다.
# → laptop(서버)은 pinky_perception 저장소 없이 이 폴더만으로 실행된다.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from protocol import Reassembler, encode_result  # noqa: E402

ARUCO_DICTS = {
    "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
    "DICT_4X4_100": cv2.aruco.DICT_4X4_100,
    "DICT_4X4_250": cv2.aruco.DICT_4X4_250,
    "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
    "DICT_5X5_100": cv2.aruco.DICT_5X5_100,
    "DICT_6X6_50": cv2.aruco.DICT_6X6_50,
    "DICT_6X6_250": cv2.aruco.DICT_6X6_250,
    "DICT_7X7_50": cv2.aruco.DICT_7X7_50,
    "DICT_ARUCO_ORIGINAL": cv2.aruco.DICT_ARUCO_ORIGINAL,
}


class ArucoDetector:
    """JPEG/이미지에서 ArUco 마커를 찾아 [{id, corners, ...자세}] 리스트로 돌려준다.

    marker_size(마커 한 변, m) 가 주어지면 solvePnP 로 자세를 추정해
    거리(m)와 3축 방향(이미지 좌표로 투영한 점)을 함께 돌려준다.
    카메라 보정(camera_matrix/dist_coeffs)이 없으면 화각(hfov)으로 근사 K 를 만든다.
    """

    def __init__(self, dict_name="DICT_6X6_250", marker_size=None,
                 camera_matrix=None, dist_coeffs=None, hfov_deg=54.0):
        dict_id = ARUCO_DICTS[dict_name]
        # OpenCV 버전에 따라 aruco API 가 다르다 (4.7+ 신 API vs 구 API).
        if hasattr(cv2.aruco, "ArucoDetector"):  # OpenCV >= 4.7
            aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
            self.detector = cv2.aruco.ArucoDetector(
                aruco_dict, cv2.aruco.DetectorParameters())
            self._new_api = True
        else:  # OpenCV < 4.7 (구 API)
            if hasattr(cv2.aruco, "getPredefinedDictionary"):
                self._dict = cv2.aruco.getPredefinedDictionary(dict_id)
            else:
                self._dict = cv2.aruco.Dictionary_get(dict_id)
            self._params = cv2.aruco.DetectorParameters_create()
            self._new_api = False

        self.marker_size = marker_size
        self.hfov_deg = hfov_deg
        self.K = camera_matrix
        self.dist = dist_coeffs if dist_coeffs is not None else np.zeros((5, 1))
        self._approx_K = camera_matrix is None  # 보정 파일 없으면 화각으로 추정
        # 마커 좌표계 기준 네 꼭짓점 (중심이 원점, 마커는 X-Y 평면, Z=평면 바깥/정면)
        if marker_size:
            s = marker_size / 2.0
            self._objp = np.array([[-s, s, 0], [s, s, 0],
                                   [s, -s, 0], [-s, -s, 0]], dtype=np.float32)

    def _ensure_K(self, w, h):
        """보정 파일이 없을 때 이미지 크기 + 화각으로 근사 카메라 행렬 생성."""
        if self.K is not None:
            return
        f = (w / 2.0) / np.tan(np.deg2rad(self.hfov_deg) / 2.0)
        self.K = np.array([[f, 0, w / 2.0],
                           [0, f, h / 2.0],
                           [0, 0, 1]], dtype=np.float64)

    def detect(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if self._new_api:
            corners, ids, _ = self.detector.detectMarkers(gray)
        else:
            corners, ids, _ = cv2.aruco.detectMarkers(
                gray, self._dict, parameters=self._params)
        out = []
        if ids is None:
            return out

        do_pose = self.marker_size is not None
        if do_pose:
            self._ensure_K(img.shape[1], img.shape[0])

        for marker_id, c in zip(ids.flatten(), corners):
            pts = c.reshape(4, 2)
            d = {
                "id": int(marker_id),
                "corners": pts.tolist(),
                "center": pts.mean(axis=0).tolist(),
            }
            if do_pose:
                ok, rvec, tvec = cv2.solvePnP(
                    self._objp, pts.astype(np.float32), self.K, self.dist,
                    flags=cv2.SOLVEPNP_IPPE_SQUARE)
                if ok:
                    L = self.marker_size  # 축 길이 = 마커 한 변
                    axis3d = np.float32([[0, 0, 0], [L, 0, 0],
                                         [0, L, 0], [0, 0, L]])
                    axis2d, _ = cv2.projectPoints(
                        axis3d, rvec, tvec, self.K, self.dist)
                    R, _ = cv2.Rodrigues(rvec)
                    # 마커가 향하는 방향(정면 = 마커의 +Z)과 정면 대비 기울기
                    yaw = float(np.degrees(np.arctan2(R[1, 0], R[0, 0])))
                    d["distance_m"] = round(float(np.linalg.norm(tvec)), 3)
                    d["yaw_deg"] = round(yaw, 1)
                    d["axes_2d"] = axis2d.reshape(-1, 2).tolist()  # [원점, X끝, Y끝, Z끝]
                    d["approx"] = self._approx_K  # 근사 보정 여부
            out.append(d)
        return out


def main():
    ap = argparse.ArgumentParser(description="ArUco UDP 검출 서버")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--dict", default="DICT_6X6_250", choices=list(ARUCO_DICTS))
    ap.add_argument("--marker-size", type=float, default=0.05,
                    help="마커 한 변 실제 길이(m). 거리/방향 추정에 필요 (기본 0.05=5cm)")
    ap.add_argument("--calib", default=None,
                    help="카메라 보정 .npz 경로(camera_matrix, dist_coeffs). "
                         "없으면 --hfov 로 근사 (거리는 대략값)")
    ap.add_argument("--hfov", type=float, default=54.0,
                    help="보정 파일이 없을 때 쓸 수평화각(도). ov5647 표준렌즈 ≈54")
    args = ap.parse_args()

    K = dist = None
    if args.calib:
        data = np.load(args.calib)
        K, dist = data["camera_matrix"], data["dist_coeffs"]
        print(f"[calib] {args.calib} 로 정확 자세추정")
    else:
        print(f"[calib] 보정 파일 없음 → 화각 {args.hfov}° 로 근사 (거리는 대략값)")

    detector = ArucoDetector(args.dict, marker_size=args.marker_size,
                             camera_matrix=K, dist_coeffs=dist, hfov_deg=args.hfov)
    print(f"[pose] 마커 크기 {args.marker_size} m 로 거리/방향 추정")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
    sock.bind((args.host, args.port))
    sock.settimeout(1.0)
    reasm = Reassembler()
    print(f"[aruco-udp] '{args.dict}' 로 {args.host}:{args.port} 에서 수신 대기")

    while True:
        try:
            data, addr = sock.recvfrom(65535)
        except socket.timeout:
            continue
        except KeyboardInterrupt:
            break
        res = reasm.push(data)
        if res is None:
            continue
        frame_id, jpeg = res
        img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            continue
        t0 = time.perf_counter()
        dets = detector.detect(img)
        infer_ms = (time.perf_counter() - t0) * 1000
        payload = json.dumps(
            {"detections": dets, "server_infer_ms": round(infer_ms, 2)}
        ).encode()
        sock.sendto(encode_result(frame_id, payload), addr)

    sock.close()


if __name__ == "__main__":
    main()
