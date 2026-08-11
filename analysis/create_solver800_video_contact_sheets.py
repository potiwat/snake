"""Create decoded-frame contact sheets for solver-800 representative videos.

These images are visual verification only; population inference remains in the
paired benchmark statistics.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw


VIDEO_ROOT = Path("results/capability_visuals/videos_solver800")
OUTPUT_ROOT = Path("results/capability_visuals")
TIMES_S = (0.5, 4.0, 9.5)
CONDITIONS = ("healthy", "locked", "free", "partial_torque")
LABELS = {
    "healthy": "HEALTHY",
    "locked": "LOCKED",
    "free": "FREE",
    "partial_torque": "PARTIAL TORQUE",
}
ENVIRONMENTS = ("flat", "low_friction", "variable_friction", "incline10")


def _frame(video: Path, time_s: float) -> Image.Image:
    capture = cv2.VideoCapture(str(video))
    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            raise RuntimeError(f"Cannot read FPS from {video}")
        capture.set(cv2.CAP_PROP_POS_FRAMES, round(time_s * fps))
        ok, bgr = capture.read()
        if not ok:
            raise RuntimeError(f"Cannot decode {time_s}s frame from {video}")
        return Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    finally:
        capture.release()


def make_contact_sheet(environment: str) -> Path:
    frames = []
    for condition in CONDITIONS:
        video = VIDEO_ROOT / environment / f"c5_{environment}_{condition}_joint3_seed7.mp4"
        frames.append([_frame(video, time_s) for time_s in TIMES_S])
    frame_width, frame_height = frames[0][0].size
    label_height = 30
    header_height = 30
    sheet = Image.new(
        "RGB",
        (frame_width * len(TIMES_S), header_height + (frame_height + label_height) * len(CONDITIONS)),
        "white",
    )
    draw = ImageDraw.Draw(sheet)
    for column, time_s in enumerate(TIMES_S):
        draw.text((column * frame_width + 8, 8), f"t = {time_s:.1f} s", fill="black")
    for row, (condition, condition_frames) in enumerate(zip(CONDITIONS, frames)):
        y = header_height + row * (frame_height + label_height)
        for column, frame in enumerate(condition_frames):
            sheet.paste(frame, (column * frame_width, y))
        draw.text((8, y + frame_height + 7), LABELS[condition], fill="black")
    output = OUTPUT_ROOT / f"{environment}_solver800_video_contact_sheet.png"
    sheet.save(output)
    print(f"saved {output}")
    return output


def main() -> None:
    for environment in ENVIRONMENTS:
        make_contact_sheet(environment)


if __name__ == "__main__":
    main()
