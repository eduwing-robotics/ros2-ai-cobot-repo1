#!/usr/bin/env python3
"""Generate an exact-size A4 landscape ChArUco calibration board PDF."""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "boards"
PDF_PATH = OUTPUT_DIR / "charuco_5x7_A4_square35mm_marker17.5mm.pdf"
PNG_PATH = OUTPUT_DIR / "charuco_5x7_square35mm_marker17.5mm_600dpi.png"

A4_WIDTH_MM = 297.0
A4_HEIGHT_MM = 210.0
SQUARES_X = 5
SQUARES_Y = 7
SQUARE_MM = 35.0
MARKER_MM = 17.5
DPI = 600


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_50)
    board = cv2.aruco.CharucoBoard_create(
        SQUARES_X, SQUARES_Y, SQUARE_MM, MARKER_MM, dictionary
    )

    portrait_width_px = round(SQUARES_X * SQUARE_MM / 25.4 * DPI)
    portrait_height_px = round(SQUARES_Y * SQUARE_MM / 25.4 * DPI)
    portrait = board.draw(
        (portrait_width_px, portrait_height_px), marginSize=0, borderBits=1
    )
    landscape = cv2.rotate(portrait, cv2.ROTATE_90_COUNTERCLOCKWISE)
    Image.fromarray(landscape).save(PNG_PATH, dpi=(DPI, DPI), optimize=True)

    board_width_mm = SQUARES_Y * SQUARE_MM
    board_height_mm = SQUARES_X * SQUARE_MM
    left = (A4_WIDTH_MM - board_width_mm) / 2.0
    bottom = (A4_HEIGHT_MM - board_height_mm) / 2.0

    page_width_px = round(A4_WIDTH_MM / 25.4 * DPI)
    page_height_px = round(A4_HEIGHT_MM / 25.4 * DPI)
    page = Image.new("L", (page_width_px, page_height_px), 255)
    board_image = Image.fromarray(landscape)
    left_px = round(left / 25.4 * DPI)
    top_px = round((A4_HEIGHT_MM - bottom - board_height_mm) / 25.4 * DPI)
    page.paste(board_image, (left_px, top_px))

    draw = ImageDraw.Draw(page)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 46)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)
    except OSError:
        font = ImageFont.load_default()
        small_font = font
    title = "ChArUco 5x7 | DICT_5X5_50 | square 35 mm | marker 17.5 mm"
    title_box = draw.textbbox((0, 0), title, font=font)
    draw.text(((page_width_px - (title_box[2] - title_box[0])) // 2, 95), title, fill=0, font=font)

    mm100 = round(100 / 25.4 * DPI)
    x1 = round(20 / 25.4 * DPI)
    x2 = x1 + mm100
    y = page_height_px - round(7 / 25.4 * DPI)
    tick = round(2 / 25.4 * DPI)
    draw.line((x1, y, x2, y), fill=0, width=4)
    draw.line((x1, y - tick, x1, y + tick), fill=0, width=4)
    draw.line((x2, y - tick, x2, y + tick), fill=0, width=4)
    draw.text((x1 + mm100 // 2 - 170, y - 80), "100 mm print check", fill=0, font=small_font)
    note = "Print: A4 landscape, Actual size / 100%, no Fit"
    note_box = draw.textbbox((0, 0), note, font=small_font)
    draw.text((page_width_px - (note_box[2] - note_box[0]) - 130, y - 25), note, fill=0, font=small_font)

    page.convert("RGB").save(PDF_PATH, "PDF", resolution=DPI, quality=100, subsampling=0)

    print(PDF_PATH)
    print(PNG_PATH)
    print(f"Board grid: {board_width_mm:.1f} x {board_height_mm:.1f} mm (landscape)")


if __name__ == "__main__":
    main()
