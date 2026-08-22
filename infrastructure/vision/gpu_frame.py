"""NV12 / RGB GPU frame → RGB CHW uint8, giữ trên VRAM với pre-allocated buffer pool."""
import torch
import torch.nn.functional as F
import queue
import threading


class ConversionBufferPool:
    """
    Pre-allocated buffer pool cho NV12→RGB conversion để giảm memory allocation overhead.
    Mỗi buffer chứa intermediate tensors (y, u, v, r, g, b) được reuse.
    """
    def __init__(self, max_buffers=100, height=480, width=640): #This resolution depends on the true input resolution of the camera
        self.height = height
        self.width = width
        self.buffers = []
        
        # Pre-allocate buffers
        for _ in range(max_buffers):
            buf = {
                'y': torch.empty((height, width), dtype=torch.float32, device='cuda'),
                'uv_interp': torch.empty((2, 1, 1, height, width), dtype=torch.float32, device='cuda'),
                'r': torch.empty((height, width), dtype=torch.float32, device='cuda'),
                'g': torch.empty((height, width), dtype=torch.float32, device='cuda'),
                'b': torch.empty((height, width), dtype=torch.float32, device='cuda'),
            }
            self.buffers.append(buf)
        
        self.available = queue.Queue(maxsize=max_buffers)
        for buf in self.buffers:
            self.available.put(buf)
        
        self._stats_lock = threading.Lock()
        self.total = max_buffers
        self.acquired = 0
    
    def acquire(self, timeout=0.5):
        """Lấy buffer từ pool"""
        try:
            buf = self.available.get(timeout=timeout)
            with self._stats_lock:
                self.acquired += 1
            return buf
        except queue.Empty:
            # Fallback: return None để dùng dynamic allocation
            return None
    
    def release(self, buf):
        """Trả buffer về pool"""
        if buf is not None:
            self.available.put(buf)
            with self._stats_lock:
                self.acquired -= 1
    
    def stats(self):
        """Statistics cho monitoring"""
        with self._stats_lock:
            return {
                "total": self.total,
                "acquired": self.acquired,
                "available": self.available.qsize(),
                "utilization": self.acquired / self.total if self.total > 0 else 0
            }


# Global buffer pool (lazy init on first use)
_conversion_pool = None
_pool_lock = threading.Lock()


def get_conversion_pool():
    """Lazy initialization of global conversion buffer pool"""
    global _conversion_pool
    if _conversion_pool is None:
        with _pool_lock:
            if _conversion_pool is None:
                _conversion_pool = ConversionBufferPool(max_buffers=100)
    return _conversion_pool


def _infer_hw(tensor, fallback_h, fallback_w):
    if tensor.ndim == 3 and tensor.shape[0] == 3:
        return tensor.shape[1], tensor.shape[2]
    if tensor.ndim == 3 and tensor.shape[-1] == 3:
        return tensor.shape[0], tensor.shape[1]
    if tensor.ndim == 2:
        return tensor.shape[0] * 2 // 3, tensor.shape[1]
    return fallback_h, fallback_w


def decoded_frame_to_rgb(frame, src_h, src_w, dst_h, dst_w, stream=None):
    """
    Zero-copy DLPack rồi convert + resize trên GPU.
    clone() để decoder tái sử dụng surface không ghi đè frame trong queue.
    Không synchronize — trả CUDA event để inference wait_event.
    """
    def _convert():
        tensor = torch.from_dlpack(frame)
        h, w = _infer_hw(tensor, src_h, src_w)
        rgb = _as_rgb_chw(tensor, h, w)
        if rgb.shape[-2] != dst_h or rgb.shape[-1] != dst_w:
            rgb = F.interpolate(
                rgb.unsqueeze(0).float(),
                size=(dst_h, dst_w),
                mode="bilinear",
                align_corners=False,
            ).squeeze(0)
        return rgb.clamp(0, 255).to(torch.uint8).contiguous().clone()

    if stream is not None:
        with torch.cuda.stream(stream):
            out = _convert()
            event = stream.record_event()
        return out, event
    return _convert(), None


def _as_rgb_chw(tensor, src_h, src_w):
    if tensor.ndim == 3 and tensor.shape[0] == 3:
        return tensor.float()
    if tensor.ndim == 3 and tensor.shape[-1] == 3:
        return tensor.permute(2, 0, 1).float()
    return _nv12_to_rgb_chw(tensor, src_h, src_w)


def _upsample_uv(uv_plane, height, width):
    """Bilinear upsample cần float; uint8 (Byte) không được."""
    return F.interpolate(
        uv_plane.float()[None, None],
        size=(height, width),
        mode="bilinear",
        align_corners=False,
    )[0, 0]


def _nv12_to_rgb_chw(nv12, height, width):
    if nv12.ndim == 1:
        nv12 = nv12.view(-1, width)
    elif nv12.ndim == 3:
        nv12 = nv12.reshape(nv12.shape[-2], nv12.shape[-1])

    y = nv12[:height, :width].float() - 16.0
    uv = nv12[height : height + height // 2, :width]
    u = _upsample_uv(uv[:, 0::2], height, width) - 128.0
    v = _upsample_uv(uv[:, 1::2], height, width) - 128.0
    r = 1.164 * y + 1.596 * v
    g = 1.164 * y - 0.392 * u - 0.813 * v
    b = 1.164 * y + 2.017 * u

    pool = get_conversion_pool()
    bufs = pool.acquire() if pool else None
    if bufs is None or bufs["r"].shape != r.shape:
        if bufs is not None:
            pool.release(bufs)
        return torch.stack((r, g, b), dim=0)

    try:
        bufs["r"].copy_(r)
        bufs["g"].copy_(g)
        bufs["b"].copy_(b)
        return torch.stack((bufs["r"], bufs["g"], bufs["b"]), dim=0).clone()
    finally:
        pool.release(bufs)
