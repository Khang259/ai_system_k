"""
Encode userinfo trong RTSP URL trước khi đưa FFmpeg / MediaMTX.

DB có thể giữ password thô (vd. có `#`). Parser URI coi `#` là fragment →
cần percent-encode user/password khi mở stream.
"""
from __future__ import annotations

from urllib.parse import quote, unquote


def encode_rtsp_userinfo(url: str) -> str:
    """
    Percent-encode user và password trong rtsp(s)://user:pass@host/...

    - Giữ nguyên URL không có userinfo hoặc không phải rtsp/rtsps.
    - Không dùng urlsplit trên URL thô (`#` trong pass làm hỏng parse).
    - Tách userinfo tại `@` cuối cùng (host đứng sau `@` đó).
    - unquote rồi quote → đã `%23` thì không double-encode.
    """
    raw = (url or "").strip()
    if not raw:
        return raw

    lower = raw.lower()
    if lower.startswith("rtsps://"):
        scheme, scheme_len = raw[:8], 8
    elif lower.startswith("rtsp://"):
        scheme, scheme_len = raw[:7], 7
    else:
        return raw

    rest = raw[scheme_len:]
    at = rest.rfind("@")
    if at <= 0:
        return raw

    userinfo = rest[:at]
    host_and_path = rest[at + 1 :]
    if not host_and_path:
        return raw

    if ":" in userinfo:
        user, _, password = userinfo.partition(":")
        enc_userinfo = (
            f"{quote(unquote(user), safe='')}:"
            f"{quote(unquote(password), safe='')}"
        )
    else:
        enc_userinfo = quote(unquote(userinfo), safe="")

    return f"{scheme}{enc_userinfo}@{host_and_path}"
