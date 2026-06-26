#!/usr/bin/env python3
"""인쇄용 ArUco 마커 PDF 생성 (정확한 물리 크기 보장).

각 마커의 검은 사각형 외곽 한 변(= pose 추정용 markerLength)이
지정한 cm 크기로 정확히 인쇄됩니다. PDF에 DPI 정보를 심어 물리 크기를
보장하므로, 인쇄 대화상자에서 '실제 크기 / 100% / 배율 맞춤 해제'로 출력하세요.

사용 예:
    python3 generate_print_markers.py --size-cm 7              # ID 0~9, 7cm
    python3 generate_print_markers.py --size-cm 8 --count 20   # ID 0~19, 8cm
    python3 generate_print_markers.py --size-cm 7 --ids 0 3 5  # 특정 ID만
"""
import argparse
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

CM_PER_INCH = 2.54
PX_PER_CM = 120                  # 1cm = 120px → 7cm=840px, 8cm=960px (셀 정수 분할)
DPI = PX_PER_CM * CM_PER_INCH    # = 304.8 DPI
PAPER_CM = {                     # 용지 크기 (가로 x 세로, cm)
    "A4": (21.0, 29.7),
    "Letter": (21.59, 27.94),
}

ARUCO_DICTS = {
    "DICT_4X4_50": (cv2.aruco.DICT_4X4_50, 4),
    "DICT_5X5_100": (cv2.aruco.DICT_5X5_100, 5),
    "DICT_6X6_250": (cv2.aruco.DICT_6X6_250, 6),
}


def _load_font(px):
    for name in ("DejaVuSans.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default()


def make_page(aruco_dict, chunk_ids, size_cm, paper="A4", per_page=2):
    """용지 한 페이지에 정확한 cm 크기의 마커 여러 개를 세로로 배치한다.

    페이지 크기 자체가 용지 크기와 같으므로, '실제 크기/100%'든
    '용지에 맞춤'이든 마커는 항상 size_cm 로 인쇄된다.
    """
    paper_w_cm, paper_h_cm = PAPER_CM[paper]
    page_w = round(paper_w_cm * PX_PER_CM)
    page_h = round(paper_h_cm * PX_PER_CM)
    marker_px = round(size_cm * PX_PER_CM)   # 검은 사각형 외곽 = size_cm

    label_h = round(1.0 * PX_PER_CM)         # 라벨 영역 높이
    block_h = marker_px + label_h            # 마커 + 라벨 한 덩어리
    slot_h = page_h // per_page              # 페이지를 per_page 칸으로 나눔

    page = np.full((page_h, page_w), 255, np.uint8)
    placed = []                              # (id, x0, y0)
    for slot, marker_id in enumerate(chunk_ids):
        marker = cv2.aruco.drawMarker(
            aruco_dict, marker_id, marker_px, borderBits=1)
        x0 = (page_w - marker_px) // 2                       # 가로 중앙
        y0 = slot * slot_h + (slot_h - block_h) // 2         # 칸 안에서 세로 중앙
        page[y0:y0 + marker_px, x0:x0 + marker_px] = marker
        placed.append((marker_id, x0, y0))

    img = Image.fromarray(page).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = _load_font(round(0.6 * PX_PER_CM))
    for marker_id, x0, y0 in placed:
        text = f"ArUco 4x4  ID={marker_id}  {size_cm:g}cm"
        tw = draw.textlength(text, font=font)
        draw.text(((page_w - tw) / 2, y0 + marker_px + 0.25 * PX_PER_CM),
                  text, fill=0, font=font)

    note = "* 인쇄: 실제 크기/100% (자로 한 변을 재서 확인하세요)"
    nf = _load_font(round(0.35 * PX_PER_CM))
    nw = draw.textlength(note, font=nf)
    draw.text(((page_w - nw) / 2, page_h - 0.7 * PX_PER_CM),
              note, fill=(130, 130, 130), font=nf)
    return img, DPI


def main():
    p = argparse.ArgumentParser(description="인쇄용 ArUco 마커 PDF 생성")
    p.add_argument("--dict", default="DICT_4X4_50", choices=list(ARUCO_DICTS))
    p.add_argument("--size-cm", type=float, required=True,
                   help="마커 한 변 실제 크기 (cm)")
    p.add_argument("--count", type=int, default=10,
                   help="ID 0부터 N-1까지 생성 (기본 10)")
    p.add_argument("--ids", type=int, nargs="+", default=None,
                   help="특정 ID만 생성 (지정 시 --count 무시)")
    p.add_argument("--paper", default="A4", choices=list(PAPER_CM),
                   help="용지 크기 (기본 A4)")
    p.add_argument("--per-page", type=int, default=2,
                   help="한 페이지에 넣을 마커 수 (기본 2)")
    p.add_argument("--out", default="markers", help="저장 폴더")
    args = p.parse_args()

    dict_id, marker_bits = ARUCO_DICTS[args.dict]
    aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
    os.makedirs(args.out, exist_ok=True)

    ids = args.ids if args.ids is not None else list(range(args.count))

    pages, dpi = [], None
    for i in range(0, len(ids), args.per_page):
        chunk = ids[i:i + args.per_page]
        img, dpi = make_page(aruco_dict, chunk, args.size_cm,
                             args.paper, args.per_page)
        pages.append(img)

    pdf = os.path.join(
        args.out, f"{args.dict}_{args.size_cm:g}cm_{args.paper}.pdf")
    pages[0].save(pdf, "PDF", resolution=dpi, save_all=True,
                  append_images=pages[1:])
    print(f"[PDF] {pdf}  ({len(pages)}페이지 x {args.per_page}개, "
          f"{args.paper}, ID {ids[0]}~{ids[-1]}, 마커 {args.size_cm:g}cm, "
          f"{dpi:.1f} DPI)")
    print("인쇄 시 '실제 크기/100%' 권장 (A4라 '용지에 맞춤'도 동일하게 정확).")


if __name__ == "__main__":
    main()
