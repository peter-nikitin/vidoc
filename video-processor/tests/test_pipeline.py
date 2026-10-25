import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from video_processor import pipeline as p
from video_processor.cli import main

URL = "https://www.youtube.com/watch?v=OdpcOLrxBnA&list=example"
INFO = {"id": "OdpcOLrxBnA", "title": "Лекция / опасное: название", "live_status": "not_live"}


def test_safe_directories_and_distinct_ids(tmp_path):
    one = p.output_directory(tmp_path, INFO)
    two = p.output_directory(tmp_path, {**INFO, "id": "abcdefghijk"})
    assert one.parent == tmp_path
    assert "Лекция" in one.name
    assert "/" not in one.name and ":" not in one.name
    assert one != two
    assert len(p.output_directory(tmp_path, {**INFO, "title": "я" * 500}).name.encode()) < 256


@pytest.mark.parametrize(
    "seconds,expected", [(0, "00:00:00"), (65.8, "00:01:05"), (3661, "01:01:01")]
)
def test_timestamps(seconds, expected):
    assert p.timestamp(seconds) == expected


@pytest.fixture
def offline(monkeypatch, tmp_path):
    monkeypatch.setattr(p.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(p, "probe_video", lambda url: INFO.copy())

    def download(url, info, directory):
        video = directory / "video.mp4"
        video.write_bytes(b"video")
        return video

    def extract(video, wav):
        wav.write_bytes(b"audio")

    monkeypatch.setattr(p, "download_video", download)
    monkeypatch.setattr(p, "extract_audio", extract)
    monkeypatch.setattr(
        p,
        "transcribe",
        lambda wav: (iter([SimpleNamespace(start=65.1, end=70.8, text=" Привет! ")]), "ru"),
    )
    return tmp_path


def test_pipeline_outputs_and_cleanup(offline):
    directory = p.run(URL, artifacts_root=offline, report=lambda _: None)
    assert (directory / "transcript.txt").read_text() == "[00:01:05 → 00:01:10] Привет!\n"
    metadata = json.loads((directory / "source.json").read_text())
    assert metadata == {
        "url": URL,
        "youtube_id": INFO["id"],
        "title": INFO["title"],
        "language": "ru",
        "model": "small",
    }
    assert (directory / "video.mp4").exists()
    assert not list(directory.glob("*.wav"))


@pytest.mark.parametrize(
    "stage,function",
    [("скачивание", "download_video"), ("аудио", "extract_audio"), ("распознавание", "transcribe")],
)
def test_stage_errors_remove_stale_outputs_and_wav(offline, monkeypatch, stage, function):
    directory = p.run(URL, artifacts_root=offline, report=lambda _: None)

    def fail(*args):
        raise RuntimeError("external failure")

    monkeypatch.setattr(p, function, fail)
    with pytest.raises(p.ProcessingError, match=stage):
        p.run(URL, artifacts_root=offline, report=lambda _: None)
    assert not (directory / "transcript.txt").exists()
    assert not (directory / "source.json").exists()
    assert (directory / "video.mp4").exists()
    assert not list(directory.glob("*.wav"))


def test_lazy_segments_failure_removes_wav(offline, monkeypatch):
    def segments():
        yield SimpleNamespace(start=0, end=1, text="first")
        raise RuntimeError("decode failure")

    monkeypatch.setattr(p, "transcribe", lambda wav: (segments(), "en"))
    with pytest.raises(p.ProcessingError, match="распознавание"):
        p.run(URL, artifacts_root=offline, report=lambda _: None)
    assert not list(offline.rglob("*.wav"))
    assert not list(offline.rglob("transcript.txt"))


def test_missing_ffmpeg_fails_before_download(offline, monkeypatch):
    monkeypatch.setattr(p.shutil, "which", lambda _: None)
    monkeypatch.setattr(p, "probe_video", lambda _: pytest.fail("network called"))
    with pytest.raises(p.ProcessingError, match="brew install ffmpeg"):
        p.run(URL, artifacts_root=offline)


@pytest.mark.parametrize(
    "url", ["https://example.org/video", "https://youtube.com/playlist?list=x", "garbage"]
)
def test_invalid_url_rejected_before_network(offline, monkeypatch, url):
    monkeypatch.setattr(p, "probe_video", lambda _: pytest.fail("network called"))
    with pytest.raises(p.ProcessingError, match="ссылк"):
        p.run(url, artifacts_root=offline)


@pytest.mark.parametrize(
    "extra", [{"live_status": "is_live"}, {"live_status": "is_upcoming"}, {"_type": "playlist"}]
)
def test_live_and_playlist_rejected(offline, monkeypatch, extra):
    monkeypatch.setattr(p, "probe_video", lambda _: {**INFO, **extra})
    with pytest.raises(p.ProcessingError):
        p.run(URL, artifacts_root=offline)


def test_cli_exit_codes(monkeypatch, capsys, tmp_path):
    from video_processor import cli

    monkeypatch.setattr(cli, "run", lambda url: tmp_path)
    assert main([URL]) == 0
    assert str(tmp_path) in capsys.readouterr().out

    def fail(url):
        raise p.ProcessingError("скачивание", "offline")

    monkeypatch.setattr(cli, "run", fail)
    assert main([URL]) == 1
    assert "скачивание" in capsys.readouterr().err

    def interrupt(url):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run", interrupt)
    assert main([URL]) == 130
    assert "Прервано" in capsys.readouterr().err


@pytest.mark.parametrize("title", ["Лекция", "Рост 100%"])
def test_download_does_not_reuse_partial_stream(tmp_path, monkeypatch, title):
    tmp_path = tmp_path / title
    tmp_path.mkdir()
    import sys

    partial = tmp_path / "video.f137.mp4"
    partial.write_bytes(b"video without audio")
    options_seen = []

    class Downloader:
        def __init__(self, options):
            self.options = options
            options_seen.append(options)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def extract_info(self, url, download):
            assert url == URL and download is True
            path = Path(self.options["outtmpl"] % {"ext": "mkv"})
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"complete video and audio")
            return {**INFO, "ext": "mkv"}

        def prepare_filename(self, result):
            return self.options["outtmpl"] % {"ext": result["ext"]}

    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=Downloader))
    video = p.download_video(URL, INFO, tmp_path)
    assert video.read_bytes() == b"complete video and audio"
    assert video.parent == tmp_path
    assert options_seen[0]["noplaylist"] is True
    assert p.download_video(URL, INFO, tmp_path) == video
    assert len(options_seen) == 1


def test_probe_processes_only_watch_video(monkeypatch):
    import sys

    class Downloader:
        def __init__(self, options):
            assert options["noplaylist"] is True

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def extract_info(self, url, download):
            assert url == URL and download is False
            return INFO

    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=Downloader))
    assert p.probe_video(URL) == INFO


def test_audio_contract_and_error(monkeypatch, tmp_path):
    video, wav = tmp_path / "video.mkv", tmp_path / "audio.wav"

    def execute(command, **kwargs):
        assert command == [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(wav),
        ]
        return SimpleNamespace(returncode=1, stderr="no audio stream")

    monkeypatch.setattr(p.subprocess, "run", execute)
    with pytest.raises(RuntimeError, match="no audio stream"):
        p.extract_audio(video, wav)


def test_speech_uses_local_multilingual_cpu_model(monkeypatch, tmp_path):
    import sys

    class Model:
        def __init__(self, name, **kwargs):
            assert name == "small"
            assert kwargs["device"] == "cpu" and kwargs["compute_type"] == "int8"
            assert Path(kwargs["download_root"]).name == ".models"

        def transcribe(self, filename):
            assert filename == str(tmp_path / "audio.wav")
            return iter([]), SimpleNamespace(language="ru")

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=Model))
    segments, language = p.transcribe(tmp_path / "audio.wav")
    assert list(segments) == [] and language == "ru"


def test_write_error_removes_partial_results(offline, monkeypatch):
    replace = Path.replace

    def fail_source(self, target):
        if self.name == ".source.json.tmp":
            raise OSError("disk full")
        return replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_source)
    with pytest.raises(p.ProcessingError, match="запись результата"):
        p.run(URL, artifacts_root=offline, report=lambda _: None)
    assert not list(offline.rglob("transcript.txt"))
    assert not list(offline.rglob("source.json"))
    assert not list(offline.rglob("*.tmp"))
    assert not list(offline.rglob("*.wav"))


def test_interrupt_cleans_working_audio(offline, monkeypatch):
    def interrupt(wav):
        raise KeyboardInterrupt

    monkeypatch.setattr(p, "transcribe", interrupt)
    with pytest.raises(KeyboardInterrupt):
        p.run(URL, artifacts_root=offline, report=lambda _: None)
    assert not list(offline.rglob("*.wav"))
    assert not list(offline.rglob("transcript.txt"))


def test_help_is_russian_and_does_not_load_model(monkeypatch, capsys):
    import builtins

    original_import = builtins.__import__

    def guard(name, *args, **kwargs):
        if name in {"faster_whisper", "yt_dlp"}:
            pytest.fail("help imported a heavyweight dependency")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guard)
    with pytest.raises(SystemExit) as error:
        main(["--help"])
    assert error.value.code == 0
    help_text = capsys.readouterr().out
    assert "показать справку" in help_text
