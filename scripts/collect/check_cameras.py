#!/usr/bin/env python
"""List OpenCV camera indices available to the laptop."""

from __future__ import annotations

import cv2


def main() -> None:
    found = []
    for index in range(10):
        cap = cv2.VideoCapture(index)
        try:
            if cap.isOpened():
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                found.append(index)
                print(f"Camera {index}: available ({width}x{height}, reported_fps={fps:.1f})")
        finally:
            cap.release()

    if not found:
        print("No OpenCV cameras found in indices 0..9.")


if __name__ == "__main__":
    main()
