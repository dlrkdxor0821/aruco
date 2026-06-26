"""ArUco 검출 결과를 프레임/캔버스에 그리는 공용 함수.

Pi(클라이언트)와 laptop(뷰어) 양쪽에서 import 한다. 카메라 등 무거운 의존성이
없어야 noteebook(laptop)에서도 그대로 쓸 수 있다.

검출 dict 한 개 형식 (aruco_server.ArucoDetector.detect 가 만드는 것):
    {id, corners[4][2], center[2],
     distance_m?, yaw_deg?, axes_2d?[4][2], approx?}
"""
import cv2
import numpy as np

RED = (0, 0, 255)  # BGR


def draw_markers(frame, dets):
    """테두리(초록) + 방향 화살표(X빨강·Y초록·Z파랑=정면) + 마커 옆 빨간 글자."""
    for d in dets:
        pts = np.array(d["corners"], dtype=np.int32)
        cv2.polylines(frame, [pts], isClosed=True, color=(0, 255, 0), thickness=2)

        # 자세가 있으면 3축 화살표
        if "axes_2d" in d:
            o, ax, ay, az = (tuple(map(int, p)) for p in d["axes_2d"])
            cv2.arrowedLine(frame, o, ax, (0, 0, 255), 2, tipLength=0.2)   # X
            cv2.arrowedLine(frame, o, ay, (0, 255, 0), 2, tipLength=0.2)   # Y
            cv2.arrowedLine(frame, o, az, (255, 0, 0), 3, tipLength=0.25)  # Z=정면

        # 마커 바로 옆에 빨간 글자로 id/거리/방향
        x_text = int(pts[:, 0].max()) + 6
        y_text = int(pts[:, 1].min()) + 14
        lines = [f'id={d["id"]}']
        if "distance_m" in d:
            tag = "~" if d.get("approx") else ""  # 근사 보정이면 ~ 표시
            lines.append(f'{tag}{d["distance_m"]:.2f} m')
            lines.append(f'yaw {d["yaw_deg"]:.0f}deg')
        for i, t in enumerate(lines):
            cv2.putText(frame, t, (x_text, y_text + i * 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, RED, 2, cv2.LINE_AA)
