"""Локальное распознавание с ленивым преобразованием сегментов."""

from pathlib import Path

from video_processor.ports import Segment, Transcription

MODEL = "small"


class WhisperSpeechRecognizer:
    def __init__(self, models_root: Path):
        self.models_root = models_root

    def transcribe(self, wav: Path) -> Transcription:
        from faster_whisper import WhisperModel

        model = WhisperModel(
            MODEL, device="cpu", compute_type="int8", download_root=str(self.models_root)
        )
        segments, info = model.transcribe(str(wav))
        return Transcription(
            (Segment(segment.start, segment.end, segment.text) for segment in segments),
            info.language,
            MODEL,
        )
