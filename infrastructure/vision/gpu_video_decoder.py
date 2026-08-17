import subprocess
import threading
import queue
import numpy as np
import torch
from infrastructure.vision.annexb_pipe import pull_aus
from infrastructure.vision.gpu_frame import decoded_frame_to_rgb
from utils.setup_log import setup_logger

logger = setup_logger("gpu_video_decoder", "logs/gpu_decoder/log")


def _submit_au(decoder, nvc, au):
    # PacketData.bsl_data = pointer (int), bsl = size. Buffer must live until Decode returns.
    buf = np.frombuffer(au, dtype=np.uint8).copy()
    pkt = nvc.PacketData()
    pkt.bsl_data = int(buf.ctypes.data)
    pkt.bsl = int(buf.nbytes)
    out = decoder.Decode(pkt)
    _ = buf
    if out is None:
        return []
    return out


class GPUVideoDecoder:
    """FFmpeg demux (-c:v copy) → Annex-B → NVDEC in-process → tensor CUDA."""

    def __init__(self, rtsp_url, width=640, height=480):
        self.rtsp_url = rtsp_url
        self.width = width
        self.height = height
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
            "-nostdin",
            "-hide_banner",
            "-loglevel", "warning",
            "-rtsp_transport", "tcp",
            "-i", self.rtsp_url,
            "-map", "0:v:0",
            "-c:v", "copy",
            "-an",
            "-bsf:v", "h264_mp4toannexb,dump_extra=freq=keyframe",
            "-f", "h264",
            "pipe:1",
        ]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=64 * 1024,
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

    def _decode_loop(self):
        decoder = None
        first_frame = True
        buf = bytearray()
        try:
            import PyNvVideoCodec as nvc

            torch.cuda.init()
            decoder = nvc.CreateDecoder(
                gpuid=0,
                codec=nvc.cudaVideoCodec.H264,
                usedevicememory=True,
                maxwidth=1920,
                maxheight=1080,
                latency=nvc.DisplayDecodeLatencyType.LOW,
            )
            logger.info(f"NVDEC session open {self.rtsp_url}")
            stdout = self.process.stdout if self.process else None

            while self.running and stdout is not None:
                chunk = stdout.read(4096)
                if not chunk:
                    break
                buf.extend(chunk)
                aus, buf = pull_aus(buf)
                for au in aus:
                    for decoded in _submit_au(decoder, nvc, au):
                        frame = decoded_frame_to_rgb(
                            decoded, self.height, self.width, self.height, self.width
                        )
                        if self.queue.full():
                            try:
                                self.queue.get_nowait()
                            except queue.Empty:
                                pass
                        self.queue.put(frame)
                        if first_frame:
                            self._ready.set()
                            first_frame = False
                            logger.info(f"Decoder ready for {self.rtsp_url}")
        except Exception as e:
            msg = str(e)
            if "Invoked with" in msg:
                msg = msg.split("Invoked with")[0].strip()
            logger.error(f"Decode error: {msg}")
        finally:
            self.running = False
            self._opened = False
            if self.process is not None and self.process.poll() is None:
                try:
                    self.process.kill()
                except Exception:
                    pass
            del decoder

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
        if not is_ready:
            logger.warning(f"Decoder timeout waiting for first frame from {self.rtsp_url}")
        return is_ready
