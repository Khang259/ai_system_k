import subprocess
import threading
import queue
import numpy as np
from config.settings import settings
from utils.setup_log import setup_logger

logger = setup_logger("gpu_video_decoder", "logs/gpu_decoder/log")


class GPUVideoDecoder:
    """
    Giải mã RTSP bằng FFmpeg NVDEC (GPU), đọc frame BGR numpy ra queue.
    PyNvVideoCodec CreateDemuxer không ổn định trên live pipe — giữ NVDEC, frame về RAM.
    """

    def __init__(self, rtsp_url, width=640, height=480):
        self.rtsp_url = rtsp_url
        self.width = width
        self.height = height
        self.frame_size = width * height * 3
        self.queue = queue.Queue(maxsize=3)
        self.process = None
        self.thread = None
        self.running = False
        self._opened = False
        self._ready = threading.Event()
        self._start_decode()

    def _start_decode(self):
        if self.running:
            return

        cmd = [
            "ffmpeg",
            "-hwaccel", "cuda",
            "-hwaccel_output_format", "cuda",
            "-c:v", "h264_cuvid",
            "-rtsp_transport", "tcp",
            "-i", self.rtsp_url,
            "-vf", f"scale_cuda={self.width}:{self.height},hwdownload,format=nv12,format=bgr24",
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-",
        ]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=getattr(settings, "GPU_DECODE_BUFFER_SIZE", 0),
            )
            self.running = True
            self._opened = True
            threading.Thread(target=self._log_stderr, daemon=True).start()
            self.thread = threading.Thread(target=self._decode_loop, daemon=True)
            self.thread.start()
        except Exception as e:
            logger.error(f"Failed to start FFmpeg: {e}")
            self._opened = False

    def _log_stderr(self):
        if self.process is None or self.process.stderr is None:
            return
        for line in iter(self.process.stderr.readline, b""):
            text = line.decode("utf-8", errors="replace").rstrip()
            if not text or text.startswith("frame="):
                continue
            logger.warning(f"ffmpeg: {text}")

    def _read_exact(self, n):
        buf = bytearray()
        while len(buf) < n:
            if self.process is None or self.process.stdout is None:
                break
            chunk = self.process.stdout.read(n - len(buf))
            if not chunk:
                break
            buf.extend(chunk)
        return bytes(buf)

    def _decode_loop(self):
        first_frame = True
        while self.running:
            try:
                raw = self._read_exact(self.frame_size)
                if len(raw) != self.frame_size:
                    logger.error(
                        f"FFmpeg stdout closed before full frame "
                        f"({len(raw)}/{self.frame_size}) from {self.rtsp_url}"
                    )
                    break

                frame = np.frombuffer(raw, np.uint8).reshape((self.height, self.width, 3))
                if first_frame:
                    self._ready.set()
                    first_frame = False

                if self.queue.full():
                    try:
                        self.queue.get_nowait()
                    except queue.Empty:
                        pass
                self.queue.put(frame)
            except Exception as e:
                logger.error(f"Decode error: {e}")
                break

    def isOpened(self):
        return self._opened and self.process is not None and self.process.poll() is None

    def read(self):
        if not self.isOpened():
            return False, None
        if not self.queue.empty():
            return True, self.queue.get()
        return False, None

    def release(self):
        self.running = False
        self._opened = False
        if self.process:
            try:
                self.process.kill()
                self.process.wait(timeout=2)
            except Exception:
                pass
            self.process = None

    def get_width_height(self):
        return self.width, self.height

    def wait_ready(self, timeout=10.0):
        is_ready = self._ready.wait(timeout)
        if is_ready:
            logger.info(f"Decoder ready for {self.rtsp_url}")
        else:
            logger.warning(f"Decoder timeout waiting for first frame from {self.rtsp_url}")
        return is_ready
