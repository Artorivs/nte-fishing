"""
Calibration tool for the NTE fishing bot.

macOS note: grant Screen Recording permission to whatever terminal app runs
this (System Settings -> Privacy & Security -> Screen Recording), or the
captured frame will be black. You likely need to restart the terminal app
after granting it.

LIGHTING NOTE: the bar is a semi-transparent HUD overlay, so its rendered
color shifts a bit between bright daytime skies and dark night skies. Run
this script once during the day and once at night (or under any other
noticeably different lighting) - it will MERGE new samples into your
existing config.json, widening the accepted color range instead of
overwriting it, so the bot works under all the conditions you calibrate.

Run this WHILE a fish is actively biting (the green bar + yellow marker
are visible on screen). It will:
  1. Let you draw a box around the fishing bar region.
  2. Let you click on the GREEN zone, then the YELLOW marker, to sample
     their colors in HSV.
  3. Save/merge everything into config.json for fish_bot.py to use.

Controls while selecting the region:
  - Drag a rectangle with the mouse, press ENTER/SPACE to confirm, or
    press "c" to cancel and redraw.

Controls while sampling colors:
  - Click once on the green zone.
  - Click once on the yellow marker.
  - Press "q" if you need to quit early.
"""

import json
import os
import sys

import cv2
import mss
import numpy as np

CONFIG_PATH = "config.json"


def grab_full_screen():
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # primary monitor
        img = np.array(sct.grab(monitor))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR), monitor


def select_region(frame):
    print("\nDrag a box around the fishing bar (the strip with the green "
          "zone and yellow marker), then press ENTER or SPACE.")
    r = cv2.selectROI("Select fishing bar region", frame, showCrosshair=True)
    cv2.destroyWindow("Select fishing bar region")
    x, y, w, h = r
    if w == 0 or h == 0:
        print("No region selected, aborting.")
        sys.exit(1)
    return int(x), int(y), int(w), int(h)


def sample_colors(region_frame):
    clicked = {}

    def on_click(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            bgr = region_frame[y, x].tolist()
            hsv = cv2.cvtColor(np.uint8([[bgr]]), cv2.COLOR_BGR2HSV)[0][0].tolist()
            if "green" not in clicked:
                clicked["green"] = hsv
                print(f"Sampled GREEN zone HSV: {hsv}")
            elif "yellow" not in clicked:
                clicked["yellow"] = hsv
                print(f"Sampled YELLOW marker HSV: {hsv}")

    cv2.namedWindow("Click GREEN zone, then YELLOW marker (press q when done)")
    cv2.setMouseCallback(
        "Click GREEN zone, then YELLOW marker (press q when done)", on_click
    )

    print("\nClick on the GREEN zone first, then the YELLOW marker.")
    while True:
        cv2.imshow("Click GREEN zone, then YELLOW marker (press q when done)", region_frame)
        key = cv2.waitKey(30) & 0xFF
        if key == ord("q") or len(clicked) >= 2:
            break
    cv2.destroyAllWindows()

    if "green" not in clicked or "yellow" not in clicked:
        print("Did not sample both colors, aborting.")
        sys.exit(1)
    return clicked


def hsv_range(hsv, h_tol=10, s_tol=80, v_tol=80):
    h, s, v = hsv
    lower = [max(0, h - h_tol), max(0, s - s_tol), max(0, v - v_tol)]
    upper = [min(179, h + h_tol), min(255, s + s_tol), min(255, v + v_tol)]
    return lower, upper


def merge_range(existing, new):
    """Union of two [lower, upper] HSV ranges, so the mask accepts colors
    seen under either lighting condition."""
    lower = [min(a, b) for a, b in zip(existing["lower"], new[0])]
    upper = [max(a, b) for a, b in zip(existing["upper"], new[1])]
    return {"lower": lower, "upper": upper}


def load_existing_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return None


def main():
    print("Make sure a fish is currently biting so the bar is visible on screen.")
    input("Press ENTER once the fishing minigame bar is visible...")

    frame, monitor = grab_full_screen()
    x, y, w, h = select_region(frame)
    region_frame = frame[y : y + h, x : x + w]

    colors = sample_colors(region_frame)
    green_lower, green_upper = hsv_range(colors["green"])
    yellow_lower, yellow_upper = hsv_range(colors["yellow"])

    existing = load_existing_config()
    merge = False
    if existing is not None:
        answer = input(
            "\nExisting config.json found. Merge these new samples into it "
            "(recommended for day/night robustness)? [Y/n]: "
        ).strip().lower()
        merge = answer in ("", "y", "yes")

    if merge:
        green_range = merge_range(existing["green_hsv_range"], (green_lower, green_upper))
        yellow_range = merge_range(existing["yellow_hsv_range"], (yellow_lower, yellow_upper))
        print("Merged with existing color ranges.")
    else:
        green_range = {"lower": green_lower, "upper": green_upper}
        yellow_range = {"lower": yellow_lower, "upper": yellow_upper}

    # Store region in absolute screen coordinates (monitor offset baked in)
    # so fish_bot.py can use it directly as an mss capture region.
    config = {
        "region": {
            "x": monitor["left"] + x,
            "y": monitor["top"] + y,
            "w": w,
            "h": h,
        },
        "green_hsv_range": green_range,
        "yellow_hsv_range": yellow_range,
    }

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\nSaved config to {CONFIG_PATH}:")
    print(json.dumps(config, indent=2))
    print("\nIf lighting still varies a lot (e.g. you haven't calibrated at "
          "night yet), run this script again under that lighting to widen "
          "the range further. Then run fish_bot.py while fishing.")


if __name__ == "__main__":
    main()