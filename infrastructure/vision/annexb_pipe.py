"""Tách Access Unit H.264 Annex-B từ pipe FFmpeg (không CreateDemuxer)."""


def _nal_type(buf, start_code_pos):
    nal_i = start_code_pos + 3
    if nal_i >= len(buf):
        return None
    return buf[nal_i] & 0x1F


def pull_aus(buf):
    """
    Tách AU hoàn chỉnh: SPS/PPS + 1 VCL (slice/IDR).
    Trả (list[bytes], remainder).
    """
    starts = []
    i = 0
    while True:
        j = buf.find(b"\x00\x00\x01", i)
        if j < 0:
            break
        starts.append(j)
        i = j + 3

    if len(starts) < 2:
        return [], buf

    aus = []
    au_idx = 0
    for n, pos in enumerate(starts):
        nal_type = _nal_type(buf, pos)
        if nal_type in (1, 5) and n + 1 < len(starts):
            end = starts[n + 1]
            aus.append(bytes(buf[starts[au_idx] : end]))
            au_idx = n + 1

    return aus, bytearray(buf[starts[au_idx] :])
