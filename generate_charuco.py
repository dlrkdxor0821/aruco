#!/usr/bin/env python3
"""카메라 캘리브레이션용 ChArUco 보드(아루코 체커보드) PDF 생성.

ChArUco = 체스보드 + ArUco 마커. 일반 체스보드보다 가림/부분 노출에 강해
캘리브레이션 정확도가 좋다. 보드의 한 칸(squareLength)이 지정한 cm로
정확히 인쇄되므로, 캘리브레이션 시 그 값을 그대로 넣으면 된다.

기본값(A4 세로): 5 x 7 칸, 칸 3.5cm, 마커 2.6cm, DICT_4X4_50.

사용 예:
    python3 generate_charuco.py                       # 기본 5x7, 3.5cm
    python3 generate_charuco.py --square-cm 3 --marker-cm 2.2
    python3 generate_charuco.py --squares-x 5 --squares-y 7
"""
import argparse
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

CM_PER_INCH = 2.54
PX_PER_CM = 120
DPI = PX_PER_CM * CM_PER_INCH     # 304.8
PAPER_CM = {"A4": (21.0, 29.7), "Letter": (21.59, 27.94)}

ARUCO_DICTS = {
    "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
    "DICT_5X5_100": cv2.aruco.DICT_5X5_100,
    "DICT_6X6_250": cv2.aruco.DICT_6X6_250,
}


def _load_font(px):
    for name in ("DejaVuSans.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default()


def main():
    p = argparse.ArgumentParser(description="ChArUco 보드 PDF 생성")
    p.add_argument("--dict", default="DICT_4X4_50", choices=list(ARUCO_DICTS))
    p.add_argument("--squares-x", type=int, default=5, help="가로 칸 수")
    p.add_argument("--squares-y", type=int, default=7, help="세로 칸 수")
    p.add_argument("--square-cm", type=float, default=3.5, help="한 칸 길이(cm)")
    p.add_argument("--marker-cm", type=float, default=2.6,
                   help="칸 안 마커 길이(cm), 칸보다 작아야 함")
    p.add_argument("--paper", default="A4", choices=list(PAPER_CM))
    p.add_argument("--out", default="markers", help="저장 폴더")
    args = p.parse_args()

    if args.marker_cm >= args.square_cm:
        raise SystemExit("marker-cm 은 square-cm 보다 작아야 합니다.")

    dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICTS[args.dict])
    # OpenCV 4.6 API: 길이는 미터 단위로 넣지만 비율만 의미가 있다(픽셀에서 환산)
    board = cv2.aruco.CharucoBoard_create(
        args.squares_x, args.squares_y,
        args.square_cm / 100.0, args.marker_cm / 100.0, dictionary)

    board_w = round(args.squares_x * args.square_cm * PX_PER_CM)
    board_h = round(args.squares_y * args.square_cm * PX_PER_CM)
    board_img = board.draw((board_w, board_h))   # 정확히 칸=square_cm 가 되도록

    paper_w_cm, paper_h_cm = PAPER_CM[args.paper]
    page_w = round(paper_w_cm * PX_PER_CM)
    page_h = round(paper_h_cm * PX_PER_CM)
    board_cm_w = args.squares_x * args.square_cm
    board_cm_h = args.squares_y * args.square_cm
    if board_w > page_w or board_h > page_h:
        raise SystemExit(
            f"보드({board_cm_w:.1f}x{board_cm_h:.1f}cm)가 "
            f"{args.paper} 용지보다 큽니다. 칸 크기나 칸 수를 줄이세요.")

    page = np.full((page_h, page_w), 255, np.uint8)
    x0 = (page_w - board_w) // 2
    y0 = round(1.5 * PX_PER_CM)            # 위에서 1.5cm
    page[y0:y0 + board_h, x0:x0 + board_w] = board_img
    img = Image.fromarray(page).convert("RGB")

    draw = ImageDraw.Draw(img)
    font = _load_font(round(0.55 * PX_PER_CM))
    line1 = (f"ChArUco {args.squares_x}x{args.squares_y}  "
             f"square={args.square_cm:g}cm  marker={args.marker_cm:g}cm")
    line2 = f"{args.dict}  (inner corners {args.squares_x-1}x{args.squares_y-1})"
    yt = y0 + board_h + 0.4 * PX_PER_CM
    for ln in (line1, line2):
        tw = draw.textlength(ln, font=font)
        draw.text(((page_w - tw) / 2, yt), ln, fill=0, font=font)
        yt += 0.75 * PX_PER_CM

    note = "* 인쇄: 실제 크기/100% (칸 한 변을 자로 재서 확인하세요)"
    nf = _load_font(round(0.35 * PX_PER_CM))
    nw = draw.textlength(note, font=nf)
    draw.text(((page_w - nw) / 2, page_h - 0.7 * PX_PER_CM),
              note, fill=(130, 130, 130), font=nf)

    os.makedirs(args.out, exist_ok=True)
    base = (f"charuco_{args.squares_x}x{args.squares_y}_"
            f"{args.square_cm:g}cm_{args.paper}")
    pdf = os.path.join(args.out, base + ".pdf")
    img.save(pdf, "PDF", resolution=DPI)
    img.save(os.path.join(args.out, base + ".png"), dpi=(DPI, DPI))
    print(f"[PDF] {pdf}")
    print(f"  보드 {board_cm_w:.1f} x {board_cm_h:.1f} cm, "
          f"칸 {args.square_cm:g}cm, 마커 {args.marker_cm:g}cm, {DPI:.1f} DPI")
    print("  인쇄는 '실제 크기/100%'. 캘리브레이션 때 이 칸/마커 cm 값을 그대로 입력.")


if __name__ == "__main__":
    main()
