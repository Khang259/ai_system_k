from application.cameras.webrtc_sessions import WebrtcSessionRegistry
from application.cameras.webrtc_signaling import (
    DeleteWebrtcSession,
    GetWebrtcGrid,
    OfferWebrtc,
)
from tests.application.fakes import FakeCameraRuntime


class FakeGateway:
    def __init__(self, ready=True, fail=False):
        self.ready = ready
        self.fail = fail
        self.hangups = []

    def is_ready(self):
        return self.ready

    def whep_offer(self, camera_id, rtsp, sdp_offer):
        if self.fail:
            raise RuntimeError("MediaMTX WHEP failed")
        return "v=0\r\no=answer", "http://127.0.0.1:8889/cam1/whep/x"

    def hangup(self, remote):
        self.hangups.append(remote)


def test_fifth_session_conflict():
    reg = WebrtcSessionRegistry(max_sessions=4)
    uc = OfferWebrtc(reg)
    ids = []
    for i in range(4):
        r = uc.execute(1, "preview", "v=0")
        assert r.data["http_status"] == 503
        ids.append(r.data["session_id"])
    fifth = uc.execute(1, "detect", "v=0")
    assert not fifth.success
    assert fifth.data["http_status"] == 409
    assert reg.count() == 4

    gone = DeleteWebrtcSession(reg).execute(1, ids[0])
    assert gone.success
    again = uc.execute(2, "preview", "v=0")
    assert again.data["http_status"] == 503
    assert reg.count() == 4


def test_delete_wrong_camera():
    reg = WebrtcSessionRegistry(max_sessions=4)
    offer = OfferWebrtc(reg).execute(1, "preview", "v=0")
    sid = offer.data["session_id"]
    bad = DeleteWebrtcSession(reg).execute(99, sid)
    assert bad.data["http_status"] == 404
    ok = DeleteWebrtcSession(reg).execute(1, sid)
    assert ok.success


def test_preview_whep_returns_sdp():
    reg = WebrtcSessionRegistry(max_sessions=4)
    gw = FakeGateway()
    cams = FakeCameraRuntime()
    r = OfferWebrtc(reg, cameras=cams, gateway=gw).execute(1, "preview", "v=0")
    assert r.success
    assert r.data["sdp"].startswith("v=0")
    sid = r.data["session_id"]
    gone = DeleteWebrtcSession(reg, gateway=gw).execute(1, sid)
    assert gone.success
    assert gw.hangups == ["http://127.0.0.1:8889/cam1/whep/x"]


def test_detect_whep_returns_sdp():
    reg = WebrtcSessionRegistry(max_sessions=4)
    gw = FakeGateway()
    r = OfferWebrtc(reg, cameras=FakeCameraRuntime(), gateway=gw).execute(
        1, "detect", "v=0"
    )
    assert r.success
    assert r.data["sdp"].startswith("v=0")
    assert r.data["mode"] == "detect"


def test_preview_missing_rtsp_404():
    cams = FakeCameraRuntime()
    cams.rtsp_missing = True
    r = OfferWebrtc(
        WebrtcSessionRegistry(), cameras=cams, gateway=FakeGateway()
    ).execute(1, "preview", "v=0")
    assert r.data["http_status"] == 404
    assert "session_id" not in r.data


def test_mix_preview_detect_four_then_fifth():
    reg = WebrtcSessionRegistry(max_sessions=4)
    uc = OfferWebrtc(reg, cameras=FakeCameraRuntime(), gateway=FakeGateway())
    assert uc.execute(1, "preview", "v=0").success
    assert uc.execute(2, "preview", "v=0").success
    assert uc.execute(3, "detect", "v=0").success
    assert uc.execute(4, "detect", "v=0").success
    fifth = uc.execute(5, "preview", "v=0")
    assert fifth.data["http_status"] == 409
    assert GetWebrtcGrid(reg).execute().data == {"count": 4, "max": 4}


def test_hangup_one_keeps_others():
    reg = WebrtcSessionRegistry(max_sessions=4)
    uc = OfferWebrtc(reg, cameras=FakeCameraRuntime(), gateway=FakeGateway())
    a = uc.execute(1, "preview", "v=0")
    b = uc.execute(2, "detect", "v=0")
    sid_b = b.data["session_id"]
    DeleteWebrtcSession(reg).execute(1, a.data["session_id"])
    assert reg.count() == 1
    c = uc.execute(3, "preview", "v=0")
    assert c.success
    assert reg.count() == 2
    assert DeleteWebrtcSession(reg).execute(2, sid_b).success
    assert reg.count() == 1


def test_preview_whep_fail_releases_slot():
    reg = WebrtcSessionRegistry(max_sessions=4)
    r = OfferWebrtc(
        reg, cameras=FakeCameraRuntime(), gateway=FakeGateway(fail=True)
    ).execute(1, "preview", "v=0")
    assert r.data["http_status"] == 503
    assert reg.count() == 0
