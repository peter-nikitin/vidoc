from video_processor import get_version


def test_get_version() -> None:
    assert get_version() == "0.1.0"
