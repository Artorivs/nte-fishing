"""
NTE auto-fishing bot (macOS).

Full loop:
  1. IDLE / WAITING: taps F periodically (this both casts the line and, once
     a fish bites, triggers the "start reeling" prompt).
  2. REELING: once the reel bar (green zone + yellow marker) is detected on
     screen, holds A/D to keep the marker centered in the green zone until
     the bar disappears again (fish caught, escaped, or line broke) -> back
     to step 1.

config.json already contains coordinates/colors sampled from your own
screenshot. If the bot stops detecting the bar correctly (e.g. you change
resolution or window size), rerun calibrate.py to regenerate it.

REQUIRED macOS PERMISSIONS (System Settings -> Privacy & Security):
  - Screen Recording: enable for Terminal / iTerm / whatever runs this script.
  - Accessibility: enable for the same app, so it's allowed to send key events
    and register the global F8/F9 hotkeys.
You'll likely need to restart the terminal app after granting these.

Hotkeys:
  F8  - start/stop the bot
  F9  - quit the program entirely

NOTE: This automates real input on your Mac. Automating gameplay like this
typically violates the game's Terms of Service, and anti-cheat systems can
flag synthetic input even for something as small as a fishing minigame -
use at your own risk.
"""

import json
import threading
import time

import cv2
import mss
import numpy as np
import pyautogui
from pynput import keyboard as pynput_keyboard

pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True  # move mouse to a screen corner to abort pyautogui

CONFIG_PATH = "config.json"

# --- Tunable behavior ---------------------------------------------------
LEFT_KEY = "a"
RIGHT_KEY = "d"
CAST_KEY = "f"
REEL_LOOP_HZ = 25          # sampling rate while actively reeling
IDLE_LOOP_HZ = 8           # sampling rate while waiting for a bite
KEY_TAP_SECONDS = 0.04     # how long each corrective A/D tap is held
CAST_TAP_SECONDS = 0.08    # how long the F tap is held
CAST_RETRY_SECONDS = 1.5   # how often to re-tap F while idle
DEAD_ZONE_PX = 4           # if marker is within this many px of zone center, do nothing
MIN_MATCH_PIXELS = 5       # ignore tiny color-noise blobs (raw pixel count, not contour area)
# -------------------------------------------------------------------------


class BotState:
    def __init__(self):
        self.running = False
        self.quit = False
        self.lock = threading.Lock()


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def find_centroid_x(hsv_frame, lower, upper, min_pixels=5):
    """Mean x-position of all matching pixels. Works for thin lines too,
    unlike a contour-area based approach (contourArea badly underestimates
    thin/line-like shapes)."""
    mask = cv2.inRange(hsv_frame, np.array(lower), np.array(upper))
    ys, xs = np.nonzero(mask)
    if len(xs) < min_pixels:
        return None
    return float(xs.mean())


def find_zone_bounds(hsv_frame, lower, upper, min_pixels=5):
    """Leftmost/rightmost x of all matching pixels."""
    mask = cv2.inRange(hsv_frame, np.array(lower), np.array(upper))
    ys, xs = np.nonzero(mask)
    if len(xs) < min_pixels:
        return None
    return int(xs.min()), int(xs.max())


def tap_key(key, hold_seconds):
    pyautogui.keyDown(key)
    time.sleep(hold_seconds)
    pyautogui.keyUp(key)


def start_hotkey_listener(state: BotState):
    def on_press(key):
        try:
            if key == pynput_keyboard.Key.f8:
                with state.lock:
                    state.running = not state.running
                print("Bot", "STARTED" if state.running else "PAUSED")
            elif key == pynput_keyboard.Key.f9:
                with state.lock:
                    state.quit = True
                print("Quitting.")
                return False  # stop listener
        except Exception:
            pass

    listener = pynput_keyboard.Listener(on_press=on_press)
    listener.start()
    return listener


def run_bot(config, state: BotState):
    region = config["region"]
    monitor = {
        "left": region["x"],
        "top": region["y"],
        "width": region["w"],
        "height": region["h"],
    }
    green_lower = config["green_hsv_range"]["lower"]
    green_upper = config["green_hsv_range"]["upper"]
    yellow_lower = config["yellow_hsv_range"]["lower"]
    yellow_upper = config["yellow_hsv_range"]["upper"]

    print("Loaded config. Press F8 to start/stop, F9 to quit.")
    last_cast_tap = 0.0

    with mss.mss() as sct:
        while True:
            with state.lock:
                if state.quit:
                    break
                running = state.running

            if not running:
                time.sleep(0.1)
                continue

            frame = np.array(sct.grab(monitor))
            bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

            marker_x = find_centroid_x(hsv, yellow_lower, yellow_upper)
            zone_bounds = find_zone_bounds(hsv, green_lower, green_upper)

            if marker_x is None or zone_bounds is None:
                # Not currently in the reeling minigame -> idle/casting mode.
                now = time.time()
                if now - last_cast_tap > CAST_RETRY_SECONDS:
                    tap_key(CAST_KEY, CAST_TAP_SECONDS)
                    last_cast_tap = now
                time.sleep(1.0 / IDLE_LOOP_HZ)
                continue

            # Reeling minigame is active -> correct marker toward zone center.
            zone_left, zone_right = zone_bounds
            zone_center = (zone_left + zone_right) / 2.0
            error = marker_x - zone_center

            if error > DEAD_ZONE_PX:
                tap_key(LEFT_KEY, KEY_TAP_SECONDS)
            elif error < -DEAD_ZONE_PX:
                tap_key(RIGHT_KEY, KEY_TAP_SECONDS)

            time.sleep(1.0 / REEL_LOOP_HZ)


def main():
    config = load_config()
    state = BotState()
    listener = start_hotkey_listener(state)
    try:
        run_bot(config, state)
    finally:
        listener.stop()


if __name__ == "__main__":
    main()