"""NV12 / RGB GPU frame → RGB CHW uint8 trên VRAM."""
import torch
import torch.nn.functional as F


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
    return torch.stack((r, g, b), dim=0)
