"""
Diagnostic tool for the NTE fishing bot.

Run this WHILE the reeling bar (green zone + yellow marker) is visible on
screen. It captures exactly the region config.json points at, saves it as
an image, and reports whether the green zone / yellow marker were found.

Usage:
    python3 debug_capture.py

Outputs (in the current folder):
    debug_full_region.png   - the raw captured region, as fish_bot.py sees it
    debug_green_mask.png    - white = pixels matching the green HSV range
    debug_yellow_mask.png   - white = pixels matching the yellow HSV range

Send debug_full_region.png (and the printed console output) back if
detection still fails - that's enough to diagnose it.
"""

import json

import cv2
import mss
import numpy as np

CONFIG_PATH = "config.json"


def main():
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    region = config["region"]
    monitor = {
        "left": region["x"],
        "top": region["y"],
        "width": region["w"],
        "height": region["h"],
    }
    green_lower = np.array(config["green_hsv_range"]["lower"])
    green_upper = np.array(config["green_hsv_range"]["upper"])
    yellow_lower = np.array(config["yellow_hsv_range"]["lower"])
    yellow_upper = np.array(config["yellow_hsv_range"]["upper"])

    print("Config region:", region)
    input("Press ENTER once the reeling bar is visible on screen...")

    with mss.mss() as sct:
        frame = np.array(sct.grab(monitor))

    bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    cv2.imwrite("debug_full_region.png", bgr)

    # Basic sanity check: is the captured frame suspiciously blank/uniform?
    std_dev = bgr.std()
    print(f"\nCaptured region size: {bgr.shape[1]}x{bgr.shape[0]}")
    print(f"Pixel value std-dev: {std_dev:.2f} "
          f"({'looks BLANK/uniform - likely a permissions or region problem!' if std_dev < 3 else 'looks like real image data'})")

    green_mask = cv2.inRange(hsv, green_lower, green_upper)
    yellow_mask = cv2.inRange(hsv, yellow_lower, yellow_upper)
    cv2.imwrite("debug_green_mask.png", green_mask)
    cv2.imwrite("debug_yellow_mask.png", yellow_mask)

    green_px = int((green_mask > 0).sum())
    yellow_px = int((yellow_mask > 0).sum())
    print(f"\nGreen-matching pixels: {green_px}")
    print(f"Yellow-matching pixels: {yellow_px}")

    if green_px == 0:
        print("-> No pixels matched the green HSV range. The zone color or "
              "region is likely off.")
    if yellow_px == 0:
        print("-> No pixels matched the yellow HSV range. The marker color "
              "or region is likely off.")
    if green_px > 0 and yellow_px > 0:
        print("-> Both colors detected! If fish_bot.py still isn't nudging "
              "A/D, the issue is likely elsewhere (e.g. key presses not "
              "reaching the game, not a detection problem).")

    print("\nSaved debug_full_region.png, debug_green_mask.png, "
          "debug_yellow_mask.png in the current folder. Please share "
          "debug_full_region.png back.")


if __name__ == "__main__":
    main()