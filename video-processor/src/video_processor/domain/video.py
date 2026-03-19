import pathlib
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class FilePath:
    path: pathlib.Path


@dataclass(frozen=True)
class Timestamp:
    value: float


@dataclass(eq=False)
class VideoAsset:
    id: UUID
    path: FilePath

    def __eq__(self, other: object) -> bool:
        return isinstance(other, VideoAsset) and self.id == other.id


@dataclass(frozen=True)
class TranscriptionSegment:
    text: str
    start_sec: Timestamp
    end_sec: Timestamp


@dataclass(frozen=True)
class SlideChangedEvent:
    slide: FilePath
    timestamp: Timestamp


@dataclass(frozen=True)
class ProcessingReport:
    video: VideoAsset
    transcription: list[TranscriptionSegment]
    slides: list[SlideChangedEvent]
