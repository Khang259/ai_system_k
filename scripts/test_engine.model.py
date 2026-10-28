import os
import sys

# CRITICAL: These must be set BEFORE importing cv2
# Enforces TCP transport and sets a 5-second socket timeout (5,000,000 microseconds)
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;5000000"

import time
import math
import ctypes
import threading
from urllib.parse import quote
import cv2
import numpy as np
from ultralytics import YOLO

# ---------------------------------------------------------
# 1. SCREEN RESOLUTION & QUADRANT SIZING
# ---------------------------------------------------------
def get_screen_dimensions():
    """Detects primary monitor resolution with Windows DPI awareness."""
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
    screen_w = ctypes.windll.user32.GetSystemMetrics(0)
    screen_h = ctypes.windll.user32.GetSystemMetrics(1)
    return screen_w, screen_h

SCREEN_W, SCREEN_H = get_screen_dimensions()

# Leave margin for Windows taskbar and window title bars (~40px)
TITLE_BAR_OFFSET = 35
TASKBAR_OFFSET = 50

# Each window occupies half the screen width and half the screen height
WIN_WIDTH = SCREEN_W // 2
WIN_HEIGHT = (SCREEN_H - TASKBAR_OFFSET) // 2

# Inside each window (2x2 grid), each camera tile gets half the window size
TILE_WIDTH = WIN_WIDTH // 2
TILE_HEIGHT = (WIN_HEIGHT - TITLE_BAR_OFFSET) // 2

# Desktop quadrant positions (X, Y) for 4 windows
QUADRANT_POSITIONS = [
    (0, 0),                                # Window 1: Top-Left
    (WIN_WIDTH, 0),                         # Window 2: Top-Right
    (0, WIN_HEIGHT),                        # Window 3: Bottom-Left
    (WIN_WIDTH, WIN_HEIGHT)                 # Window 4: Bottom-Right
]

# ---------------------------------------------------------
# 2. CONFIGURATION
# ---------------------------------------------------------
# Khớp engine export: batch=16, imgsz=[736, 1280] (xem scripts/export_engine.py)
ENGINE_PATH = r"models\KortekFL01102601.engine"

user = "admin"
password = quote("Kortek2026#", safe="")  # Encodes '#' as '%23'

RTSP_STREAMS = {
    # "Cam 1":  f"rtsp://{user}:{password}@192.168.50.111:554/Streaming/Channels/102",
    # "Cam 2":  f"rtsp://{user}:{password}@192.168.50.112:554/Streaming/Channels/102",
    # "Cam 3":  f"rtsp://{user}:{password}@192.168.50.113:554/Streaming/Channels/102",
    # "Cam 4":  f"rtsp://{user}:{password}@192.168.50.114:554/Streaming/Channels/102",
    # "Cam 5":  f"rtsp://{user}:{password}@192.168.50.115:554/Streaming/Channels/102",
    # "Cam 6":  f"rtsp://{user}:{password}@192.168.50.116:554/Streaming/Channels/102",
    # "Cam 7":  f"rtsp://{user}:{password}@192.168.50.117:554/Streaming/Channels/102",
    # "Cam 8":  f"rtsp://{user}:{password}@192.168.50.118:554/Streaming/Channels/102",
    # "Cam 9":  f"rtsp://{user}:{password}@192.168.50.119:554/Streaming/Channels/102",
    # "Cam 10": f"rtsp://{user}:{password}@192.168.50.120:554/Streaming/Channels/102",
    # "Cam 11": f"rtsp://{user}:{password}@192.168.50.121:554/Streaming/Channels/102",
    # "Cam 12": f"rtsp://{user}:{password}@192.168.50.122:554/Streaming/Channels/102",
    # "Cam 13": f"rtsp://{user}:{password}@192.168.50.123:554/Streaming/Channels/102",
     "Cam 14": f"rtsp://{user}:{password}@192.168.50.124:554/Streaming/Channels/102",
    #"Cam 15": f"rtsp://{user}:{password}@192.168.50.125:554/Streaming/Channels/102",
    # "Cam 16": f"rtsp://{user}:{password}@192.168.50.126:554/Streaming/Channels/102",
}

INFERENCE_IMGSZ = [736, 1280]  # Khớp engine input (16, 3, 736, 1280)
MAX_TRT_BATCH = 16            # Engine static batch — predict phải đúng 16
FEEDS_PER_WINDOW = 4          # 2x2 layout per window

# ---------------------------------------------------------
# 3. THREADED RTSP CAPTURE WORKER
# ---------------------------------------------------------
class RTSPCapture:
    """Dedicated thread per camera with isolated reconnection logic."""
    def __init__(self, name, url):
        self.name = name
        self.url = url
        self.frame = None
        self.running = True
        self.lock = threading.Lock()
        self.cap = None

        self._connect()
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def _connect(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
        self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def _capture_loop(self):
        while self.running:
            try:
                if self.cap is None or not self.cap.isOpened():
                    time.sleep(1.0)
                    self._connect()
                    continue

                ret, frame = self.cap.read()
                if ret and frame is not None and frame.size > 0:
                    with self.lock:
                        self.frame = frame
                else:
                    time.sleep(0.02)
            except cv2.error:
                time.sleep(0.5)
                self._connect()
            except Exception:
                time.sleep(0.5)
                self._connect()

    def get_latest_frame(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def release(self):
        self.running = False
        time.sleep(0.1)
        if self.cap is not None:
            try:
                if self.cap.isOpened():
                    self.cap.release()
            except Exception:
                pass

# ---------------------------------------------------------
# 4. GRID BUILDER (2x2 PER WINDOW)
# ---------------------------------------------------------
def create_2x2_window_grid(tiles):
    """Combines 4 pre-scaled tiles into a 2x2 grid."""
    while len(tiles) < 4:
        blank = np.zeros((TILE_HEIGHT, TILE_WIDTH, 3), dtype=np.uint8)
        cv2.putText(blank, "EMPTY SLOT", (20, TILE_HEIGHT // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 80, 80), 2)
        tiles.append(blank)

    top_row = np.hstack([tiles[0], tiles[1]])
    bottom_row = np.hstack([tiles[2], tiles[3]])
    return np.vstack([top_row, bottom_row])

def make_offline_tile(camera_name):
    """Placeholder tile rendered when an RTSP feed is disconnected."""
    blank = np.zeros((TILE_HEIGHT, TILE_WIDTH, 3), dtype=np.uint8)
    cv2.putText(blank, camera_name, (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    cv2.putText(blank, "CONNECTING / NO SIGNAL", (20, TILE_HEIGHT // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120, 120, 120), 1)
    return blank

# ---------------------------------------------------------
# 5. INITIALIZATION & WINDOW POSITIONING
# ---------------------------------------------------------
print(f"Detected screen resolution: {SCREEN_W}x{SCREEN_H}")
print(f"Loading TensorRT engine: {ENGINE_PATH}...")
model = YOLO(ENGINE_PATH, task="detect")

# Static TRT batch=16: warmup đúng shape trước vòng RTSP
_h, _w = INFERENCE_IMGSZ
_warmup = [np.zeros((_h, _w, 3), dtype=np.uint8) for _ in range(MAX_TRT_BATCH)]
print(f"Warmup TRT batch={MAX_TRT_BATCH} imgsz={INFERENCE_IMGSZ}...")
model.predict(
    source=_warmup,
    device=0,
    conf=0.4,
    imgsz=INFERENCE_IMGSZ,
    batch=MAX_TRT_BATCH,
    verbose=False,
)

print("Initializing RTSP stream workers...")
workers = [RTSPCapture(name, url) for name, url in RTSP_STREAMS.items()]
num_workers = len(workers)
num_windows = math.ceil(num_workers / FEEDS_PER_WINDOW)

# Create and position OpenCV windows in quadrants
window_names = []
for win_idx in range(num_windows):
    win_name = f"KortexFL Monitor - Group {win_idx + 1}"
    window_names.append(win_name)
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, WIN_WIDTH, WIN_HEIGHT)

    # Position each window into its desktop quadrant
    if win_idx < len(QUADRANT_POSITIONS):
        pos_x, pos_y = QUADRANT_POSITIONS[win_idx]
        cv2.moveWindow(win_name, pos_x, pos_y)

print(f"Streams connected. Running batched inference across {num_windows} windows...")
prev_time = time.time()

# ---------------------------------------------------------
# 6. INFERENCE & DISPLAY LOOP
# ---------------------------------------------------------
try:
    while True:
        active_frames = []
        active_indices = []

        # Pull latest frame while maintaining absolute camera index
        for idx, worker in enumerate(workers):
            frame = worker.get_latest_frame()
            if frame is not None:
                active_frames.append(frame)
                active_indices.append(idx)

        # Container for all 16 rendered tiles
        rendered_tiles = [None] * num_workers

        # Run batched TensorRT inference on online cameras.
        # Engine static batch=16 → mỗi lần predict PHẢI đúng 16 frame (pad blank nếu thiếu).
        if active_frames:
            blank = np.zeros_like(active_frames[0])
            trt_results = []
            for i in range(0, len(active_frames), MAX_TRT_BATCH):
                chunk = active_frames[i : i + MAX_TRT_BATCH]
                real_n = len(chunk)
                if real_n < MAX_TRT_BATCH:
                    chunk = chunk + [blank] * (MAX_TRT_BATCH - real_n)
                chunk_results = model.predict(
                    source=chunk,
                    device=0,
                    conf=0.4,
                    imgsz=INFERENCE_IMGSZ,
                    batch=MAX_TRT_BATCH,
                    verbose=False,
                )
                trt_results.extend(chunk_results[:real_n])

            for slot_idx, res in zip(active_indices, trt_results):
                annotated = res.plot()
                annotated_tile = cv2.resize(annotated, (TILE_WIDTH, TILE_HEIGHT))
                cv2.putText(
                    annotated_tile,
                    workers[slot_idx].name,
                    (15, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 255),
                    2
                )
                rendered_tiles[slot_idx] = annotated_tile

        # Fill any offline cameras with placeholder tiles so layout never shifts
        for idx in range(num_workers):
            if rendered_tiles[idx] is None:
                rendered_tiles[idx] = make_offline_tile(workers[idx].name)

        # Calculate pipeline FPS
        curr_time = time.time()
        fps = 1.0 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0.0
        prev_time = curr_time

        # Render feeds into their respective quadrant windows (4 feeds per window)
        for win_idx in range(num_windows):
            start_i = win_idx * FEEDS_PER_WINDOW
            end_i = start_i + FEEDS_PER_WINDOW
            group_tiles = rendered_tiles[start_i:end_i]

            grid_img = create_2x2_window_grid(group_tiles)

            # Global FPS indicator on Group 1 window
            if win_idx == 0:
                cv2.putText(
                    grid_img,
                    f"Pipeline FPS: {fps:.1f} | Active Feeds: {len(active_frames)}/{num_workers}",
                    (15, grid_img.shape[0] - 15),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )

            cv2.imshow(window_names[win_idx], grid_img)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:
    for worker in workers:
        worker.release()
    cv2.destroyAllWindows()