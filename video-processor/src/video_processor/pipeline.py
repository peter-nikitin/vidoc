"""Локальная расшифровка одного YouTube-видео."""

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ARTIFACTS_ROOT = Path(__file__).resolve().parents[3] / "artifacts"
MODEL = "small"


class ProcessingError(Exception):
    def __init__(self, stage: str, message: str):
        super().__init__(f"{stage}: {message}")


def validate_url(url: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    video_id = ""
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith(("/shorts/", "/embed/", "/live/")):
            video_id = parsed.path.split("/")[2]
    elif host == "youtu.be":
        video_id = parsed.path.removeprefix("/")
    if parsed.scheme not in {"http", "https"} or not re.fullmatch(r"[\w-]{11}", video_id):
        raise ValueError("Нужна ссылка на одно YouTube-видео, например https://youtu.be/VIDEO_ID")


def ytdlp_options() -> dict:
    return {
        "noplaylist": True,
        "quiet": True,
        "js_runtimes": {"deno": {}, "node": {}},
        "cachedir": str(ARTIFACTS_ROOT / ".yt-dlp-cache"),
    }


def probe_video(url: str) -> dict:
    from yt_dlp import YoutubeDL

    with YoutubeDL(ytdlp_options()) as downloader:
        return downloader.extract_info(url, download=False)


def output_directory(root: Path, info: dict) -> Path:
    title = re.sub(r'[\x00-\x1f/\\:*?"<>|]', "_", info["title"]).strip(" .")
    title = title.encode("utf-8")[:180].decode("utf-8", errors="ignore") or "video"
    video_id = info["id"]
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise ValueError("Некорректный YouTube ID")
    return root / f"{title}-{video_id}"


def download_video(url: str, info: dict, directory: Path) -> Path:
    from yt_dlp import YoutubeDL

    # Повторно используем только завершённый файл, .part остаётся загрузчику.
    for path in sorted(directory.glob("video.*")):
        if (
            path.stem == "video"
            and path.suffix in {".mp4", ".mkv", ".webm", ".mov"}
            and path.stat().st_size
        ):
            return path
    staging = directory / ".download"
    staging.mkdir(exist_ok=True)
    options = {
        **ytdlp_options(),
        "format": "bestvideo+bestaudio/best",
        "outtmpl": str(staging).replace("%", "%%") + "/video.%(ext)s",
        "merge_output_format": "mkv",
    }
    with YoutubeDL(options) as downloader:
        result = downloader.extract_info(url, download=True)
        path = Path(downloader.prepare_filename(result))
        # При объединении yt-dlp меняет контейнер и расширение.
        merged = path.with_suffix(".mkv")
        if merged.is_file():
            path = merged
    if not path.is_file() or not path.stat().st_size:
        raise RuntimeError("yt-dlp не создал полный видеофайл")
    completed = directory / f"video{path.suffix}"
    path.replace(completed)
    shutil.rmtree(staging)
    return completed


def extract_audio(video: Path, wav: Path) -> None:
    result = subprocess.run(
        [
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
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "ffmpeg завершился с ошибкой")


def transcribe(wav: Path):
    from faster_whisper import WhisperModel

    model = WhisperModel(
        MODEL, device="cpu", compute_type="int8", download_root=str(ARTIFACTS_ROOT / ".models")
    )
    segments, info = model.transcribe(str(wav))
    return segments, info.language


def timestamp(seconds: float) -> str:
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def run(url: str, *, artifacts_root: Path = ARTIFACTS_ROOT, report=print) -> Path:
    stage = "проверка ссылки и ffmpeg"
    directory = None
    wav = None
    try:
        report("Проверка ссылки и ffmpeg…")
        validate_url(url)
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg не найден. Установите: brew install ffmpeg")
        stage = "метаданные"
        report("Получение названия видео…")
        info = probe_video(url)
        if not info or info.get("_type") in {"playlist", "multi_video"}:
            raise ValueError("Плейлисты не поддерживаются")
        if info.get("is_live") or info.get("live_status") in {
            "is_live",
            "is_upcoming",
            "post_live",
        }:
            raise ValueError("Прямые эфиры и запланированные трансляции не поддерживаются")
        directory = output_directory(artifacts_root, info)
        directory.mkdir(parents=True, exist_ok=True)
        # Старые результаты не должны выглядеть как результат неудачной попытки.
        for name in ("transcript.txt", "source.json"):
            (directory / name).unlink(missing_ok=True)
        stage = "скачивание"
        report("Скачивание полного видео…")
        video = download_video(url, info, directory)
        stage = "аудио"
        report("Извлечение аудио…")
        with tempfile.NamedTemporaryFile(
            suffix=".wav", prefix=".audio-", dir=directory, delete=False
        ) as temporary:
            wav = Path(temporary.name)
        extract_audio(video, wav)
        stage = "распознавание"
        report("Распознавание речи: small, CPU INT8 (первый запуск загружает модель)…")
        segments, language = transcribe(wav)
        transcript = "".join(
            f"[{timestamp(segment.start)} → {timestamp(segment.end)}] {segment.text.strip()}\n"
            for segment in segments
        )
        stage = "запись результата"
        source = {
            "url": url,
            "youtube_id": info["id"],
            "title": info["title"],
            "language": language,
            "model": MODEL,
        }
        for name, content in [
            ("transcript.txt", transcript),
            ("source.json", json.dumps(source, ensure_ascii=False, indent=2) + "\n"),
        ]:
            temporary = directory / f".{name}.tmp"
            temporary.write_text(content, encoding="utf-8")
            temporary.replace(directory / name)
        return directory
    except (Exception, KeyboardInterrupt) as error:
        if directory:
            for name in (
                "transcript.txt",
                "source.json",
                ".transcript.txt.tmp",
                ".source.json.tmp",
            ):
                (directory / name).unlink(missing_ok=True)
        if isinstance(error, KeyboardInterrupt):
            raise
        raise ProcessingError(stage, str(error)) from error
    finally:
        if wav:
            wav.unlink(missing_ok=True)
