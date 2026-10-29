import json
from types import SimpleNamespace

import pytest

from video_processor.pipeline import run


def test_scenario_accepts_explicit_adapters_and_reports_actual_model(tmp_path):
    from video_processor.ports import Segment, Transcription, VideoInfo

    calls = []

    class Downloader:
        def probe(self, url):
            calls.append("probe")
            return VideoInfo(id="OdpcOLrxBnA", title="Лекция")

        def download(self, url, info, directory):
            calls.append("download")
            video = directory / "video.mkv"
            video.write_bytes(b"video")
            return video

    class Audio:
        def check_available(self):
            calls.append("check")

        def extract(self, video, wav):
            calls.append("extract")
            wav.write_bytes(b"audio")

    def recognize(wav):
        calls.append("transcribe")
        assert wav.read_bytes() == b"audio"
        return Transcription([Segment(65.1, 70.8, " Привет! ")], "ru", "actual-model")

    directory = run(
        "https://youtu.be/OdpcOLrxBnA",
        downloader=Downloader(),
        audio_extractor=Audio(),
        recognizer=SimpleNamespace(transcribe=recognize),
        artifacts_root=tmp_path,
        report=lambda _: None,
    )
    assert calls == ["check", "probe", "download", "extract", "transcribe"]
    assert (directory / "transcript.txt").read_text() == "[00:01:05 → 00:01:10] Привет!\n"
    assert json.loads((directory / "source.json").read_text())["model"] == "actual-model"
    assert not list(directory.glob("*.wav"))


def test_cli_uses_one_explicit_root_for_outputs_cache_and_models(monkeypatch, tmp_path):
    from video_processor import cli
    from video_processor.adapters.ffmpeg import FfmpegAudioExtractor
    from video_processor.adapters.whisper import WhisperSpeechRecognizer
    from video_processor.adapters.ytdlp import YtDlpDownloader

    def scenario(url, *, downloader, audio_extractor, recognizer, artifacts_root):
        assert artifacts_root == tmp_path
        assert isinstance(downloader, YtDlpDownloader)
        assert downloader.cache_root == tmp_path / ".yt-dlp-cache"
        assert isinstance(audio_extractor, FfmpegAudioExtractor)
        assert isinstance(recognizer, WhisperSpeechRecognizer)
        assert recognizer.models_root == tmp_path / ".models"
        return tmp_path

    monkeypatch.setattr(cli, "ARTIFACTS_ROOT", tmp_path)
    monkeypatch.setattr(cli, "run", scenario)
    assert cli.main(["https://youtu.be/OdpcOLrxBnA"]) == 0


@pytest.mark.parametrize("failed_stage", ["check", "probe", "download", "extract", "transcribe"])
def test_failure_stops_before_later_adapters(tmp_path, failed_stage):
    from video_processor.pipeline import ProcessingError
    from video_processor.ports import VideoInfo

    calls = []
    order = ["check", "probe", "download", "extract", "transcribe"]

    def stage(name, result=None):
        def call(*args):
            calls.append(name)
            if name == failed_stage:
                raise RuntimeError("failure")
            return result

        return call

    downloader = SimpleNamespace(
        probe=stage("probe", VideoInfo("OdpcOLrxBnA", "Лекция")),
        download=stage("download", tmp_path / "video.mkv"),
    )
    audio = SimpleNamespace(check_available=stage("check"), extract=stage("extract"))
    with pytest.raises(ProcessingError, match="failure"):
        run(
            "https://youtu.be/OdpcOLrxBnA",
            downloader=downloader,
            audio_extractor=audio,
            recognizer=SimpleNamespace(transcribe=stage("transcribe")),
            artifacts_root=tmp_path,
            report=lambda _: None,
        )
    assert calls == order[: order.index(failed_stage) + 1]
    assert not list(tmp_path.rglob("*.wav"))
    assert not list(tmp_path.rglob("transcript.txt"))


def test_error_before_directory_preserves_previous_results(tmp_path):
    from video_processor.pipeline import ProcessingError

    old = tmp_path / "previous" / "transcript.txt"
    old.parent.mkdir()
    old.write_text("previous result")

    def fail(url):
        raise RuntimeError("metadata unavailable")

    with pytest.raises(ProcessingError, match="метаданные"):
        run(
            "https://youtu.be/OdpcOLrxBnA",
            downloader=SimpleNamespace(probe=fail),
            audio_extractor=SimpleNamespace(check_available=lambda: None),
            recognizer=SimpleNamespace(),
            artifacts_root=tmp_path,
            report=lambda _: None,
        )
    assert old.read_text() == "previous result"
