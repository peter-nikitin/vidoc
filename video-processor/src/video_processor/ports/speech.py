from typing import Protocol

from video_processor.domain.entities import AudioAsset, TranscriptionSegment


class SpeechToTextPort(Protocol):
    def transcribe(self, audio: AudioAsset) -> list[TranscriptionSegment]: ...
