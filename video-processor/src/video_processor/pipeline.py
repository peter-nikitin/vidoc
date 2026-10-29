"""Локальная расшифровка одного YouTube-видео."""

import json
import re
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from video_processor.ports import AudioExtractor, SpeechRecognizer, VideoDownloader, VideoInfo

ARTIFACTS_ROOT = Path(__file__).resolve().parents[3] / "artifacts"


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


def output_directory(root: Path, info: VideoInfo) -> Path:
    title = re.sub(r'[\x00-\x1f/\\:*?"<>|]', "_", info.title).strip(" .")
    title = title.encode("utf-8")[:180].decode("utf-8", errors="ignore") or "video"
    video_id = info.id
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise ValueError("Некорректный YouTube ID")
    return root / f"{title}-{video_id}"


def timestamp(seconds: float) -> str:
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def run(
    url: str,
    *,
    downloader: VideoDownloader,
    audio_extractor: AudioExtractor,
    recognizer: SpeechRecognizer,
    artifacts_root: Path = ARTIFACTS_ROOT,
    report=print,
) -> Path:
    stage = "проверка ссылки и ffmpeg"
    directory = None
    wav = None
    try:
        report("Проверка ссылки и ffmpeg…")
        validate_url(url)
        audio_extractor.check_available()
        stage = "метаданные"
        report("Получение названия видео…")
        info = downloader.probe(url)
        if info.kind in {"playlist", "multi_video"}:
            raise ValueError("Плейлисты не поддерживаются")
        if info.is_live or info.live_status in {
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
        video = downloader.download(url, info, directory)
        stage = "аудио"
        report("Извлечение аудио…")
        with tempfile.NamedTemporaryFile(
            suffix=".wav", prefix=".audio-", dir=directory, delete=False
        ) as temporary:
            wav = Path(temporary.name)
        audio_extractor.extract(video, wav)
        stage = "распознавание"
        report("Распознавание речи: small, CPU INT8 (первый запуск загружает модель)…")
        transcription = recognizer.transcribe(wav)
        transcript = "".join(
            f"[{timestamp(segment.start)} → {timestamp(segment.end)}] {segment.text.strip()}\n"
            for segment in transcription.segments
        )
        stage = "запись результата"
        source = {
            "url": url,
            "youtube_id": info.id,
            "title": info.title,
            "language": transcription.language,
            "model": transcription.model,
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
