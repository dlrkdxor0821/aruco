#!/usr/bin/env python3
"""테스트용 ArUco 마커 이미지를 생성/저장하는 스크립트.

사용 예:
    python3 generate_marker.py --id 0                 # ID 0 마커 한 장 저장
    python3 generate_marker.py --id 23 --size 600     # 600px 크기
    python3 generate_marker.py --all 5                # ID 0~4 한꺼번에 저장

저장된 PNG 를 화면에 띄우거나 인쇄해서 카메라에 보여주면 됩니다.
"""
import argparse

import cv2

ARUCO_DICTS = {
    "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
    "DICT_5X5_100": cv2.aruco.DICT_5X5_100,
    "DICT_6X6_250": cv2.aruco.DICT_6X6_250,
}


def parse_args():
    p = argparse.ArgumentParser(description="ArUco 마커 이미지 생성")
    p.add_argument("--dict", default="DICT_6X6_250", choices=list(ARUCO_DICTS))
    p.add_argument("--id", type=int, default=0, help="생성할 마커 ID")
    p.add_argument("--size", type=int, default=600, help="이미지 한 변 픽셀 크기")
    p.add_argument("--border", type=int, default=1, help="테두리 비트 두께")
    p.add_argument("--all", type=int, default=None,
                   help="0부터 N-1까지 여러 장 한꺼번에 생성")
    p.add_argument("--out", default="markers", help="저장 폴더")
    return p.parse_args()


def main():
    import os
    args = parse_args()
    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICTS[args.dict])
    os.makedirs(args.out, exist_ok=True)

    ids = range(args.all) if args.all else [args.id]
    for marker_id in ids:
        img = cv2.aruco.generateImageMarker(
            aruco_dict, marker_id, args.size, borderBits=args.border)
        path = os.path.join(args.out, f"{args.dict}_id{marker_id}.png")
        cv2.imwrite(path, img)
        print(f"[저장] {path}")

    print("완료. 이 이미지를 화면에 띄우거나 인쇄해서 카메라에 보여주세요.")


if __name__ == "__main__":
    main()
