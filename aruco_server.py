#!/usr/bin/env python3
"""ArUco UDP 검출 서버.

pinky_perception 의 UDP 전송 방식(common/protocol.py)을 그대로 재사용한다.
동작: 청크로 쪼개져 오는 JPEG 프레임을 재조립 → ArUco 마커 검출 →
검출 결과(JSON: 마커 ID와 네 꼭짓점 좌표)를 보낸 쪽으로 UDP 회신.

    python3 aruco_server.py --port 9000 --dict DICT_4X4_50

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
    """JPEG/이미지에서 ArUco 마커를 찾아 [{id, corners}] 리스트로 돌려준다."""

    def __init__(self, dict_name="DICT_4X4_50"):
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

    def detect(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if self._new_api:
            corners, ids, _ = self.detector.detectMarkers(gray)
        else:
            corners, ids, _ = cv2.aruco.detectMarkers(
                gray, self._dict, parameters=self._params)
        out = []
        if ids is not None:
            for marker_id, c in zip(ids.flatten(), corners):
                pts = c.reshape(4, 2)
                out.append({
                    "id": int(marker_id),
                    "corners": pts.tolist(),
                    "center": pts.mean(axis=0).tolist(),
                })
        return out


def main():
    ap = argparse.ArgumentParser(description="ArUco UDP 검출 서버")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--dict", default="DICT_4X4_50", choices=list(ARUCO_DICTS))
    args = ap.parse_args()

    detector = ArucoDetector(args.dict)

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
