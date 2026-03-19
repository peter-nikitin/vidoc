from typing import Protocol

from video_processor.domain.video import FilePath, TranscriptionSegment


class SpeechToTextPort(Protocol):
    def transcribe(self, file: FilePath) -> list[TranscriptionSegment]: ...
