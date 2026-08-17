"""Đọc bitstream từ pipe FFmpeg; chỉ CreateDemuxer khi đã có header."""


def prime_fmp4(stdout, max_bytes=512 * 1024):
    """Chờ ftyp+moov (empty_moov) rồi mới probe — tránh demuxer đọc 5s H264 raw."""
    buf = bytearray()
    while stdout is not None and len(buf) < max_bytes:
        piece = stdout.read(4096)
        if not piece:
            break
        buf.extend(piece)
        if b"ftyp" in buf and b"moov" in buf:
            break
    return bytes(buf)


class PipeFeeder:
    def __init__(self, stdout, primed=b""):
        self.stdout = stdout
        self._pending = bytearray(primed)

    def feed_chunk(self, demuxer_buffer):
        capacity = len(demuxer_buffer)
        chunk = bytearray()
        if self._pending:
            n = min(capacity, len(self._pending))
            chunk.extend(self._pending[:n])
            del self._pending[:n]
        need = capacity - len(chunk)
        if need > 0 and self.stdout is not None:
            more = self.stdout.read(need)
            if more:
                chunk.extend(more)
        if not chunk:
            return 0
        n = len(chunk)
        try:
            demuxer_buffer[:n] = chunk
        except (TypeError, ValueError):
            demuxer_buffer[:n] = memoryview(chunk)
        return n
