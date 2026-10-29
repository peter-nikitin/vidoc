"""Контракты процессора: типы внешних инструментов остаются в адаптерах."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class VideoInfo:
    id: str
    title: str
    kind: str | None = None
    is_live: bool = False
    live_status: str | None = None


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Transcription:
    segments: Iterable[Segment]
    language: str
    model: str


class VideoDownloader(Protocol):
    def probe(self, url: str) -> VideoInfo: ...

    def download(self, url: str, info: VideoInfo, directory: Path) -> Path: ...


class AudioExtractor(Protocol):
    def check_available(self) -> None: ...

    def extract(self, video: Path, wav: Path) -> None: ...


class SpeechRecognizer(Protocol):
    def transcribe(self, wav: Path) -> Transcription: ...
