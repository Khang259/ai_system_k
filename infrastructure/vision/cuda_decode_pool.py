"""Pool CUDA stream cho decode — round-robin theo camera, không 1 stream/camera."""
import threading

import torch

from config.settings import settings

_lock = threading.Lock()
_streams = None


def get_decode_stream(camera_index: int):
    """Lấy stream từ pool (kích thước DECODE_STREAM_POOL_SIZE)."""
    global _streams
    if _streams is None:
        with _lock:
            if _streams is None:
                if not torch.cuda.is_initialized():
                    torch.cuda.init()
                n = max(1, settings.DECODE_STREAM_POOL_SIZE)
                _streams = [torch.cuda.Stream() for _ in range(n)]
    return _streams[camera_index % len(_streams)]
