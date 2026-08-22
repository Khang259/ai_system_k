from application.cameras.webrtc_ice import ice_servers_for_browser, ice_servers_for_mediamtx


def test_ice_lan_empty_by_default():
    assert ice_servers_for_browser() == []
    assert ice_servers_for_mediamtx() == []
