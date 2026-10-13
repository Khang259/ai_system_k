"""encode_rtsp_userinfo — password có # và ký tự đặc biệt."""
from utils.rtsp_url import encode_rtsp_userinfo


def test_encode_hash_in_password():
    raw = "rtsp://admin:Kortek2026#@192.168.50.111:554/Streaming/Channels/102"
    out = encode_rtsp_userinfo(raw)
    assert out == (
        "rtsp://admin:Kortek2026%23@192.168.50.111:554/Streaming/Channels/102"
    )


def test_already_encoded_not_double():
    raw = "rtsp://admin:Kortek2026%23@192.168.50.111:554/Streaming/Channels/102"
    assert encode_rtsp_userinfo(raw) == raw


def test_special_chars_in_password():
    raw = "rtsp://u:p@ss:w?x@10.0.0.1:554/stream"
    out = encode_rtsp_userinfo(raw)
    assert out == "rtsp://u:p%40ss%3Aw%3Fx@10.0.0.1:554/stream"


def test_no_userinfo_unchanged():
    raw = "rtsp://192.168.1.1:554/stream"
    assert encode_rtsp_userinfo(raw) == raw


def test_empty_and_non_rtsp():
    assert encode_rtsp_userinfo("") == ""
    assert encode_rtsp_userinfo("http://a:b@h/") == "http://a:b@h/"


def test_user_only_no_password():
    raw = "rtsp://admin@192.168.1.1/live"
    assert encode_rtsp_userinfo(raw) == "rtsp://admin@192.168.1.1/live"


def test_rtsps_scheme():
    raw = "rtsps://admin:pass#@cam.local:322/stream"
    assert encode_rtsp_userinfo(raw) == "rtsps://admin:pass%23@cam.local:322/stream"
