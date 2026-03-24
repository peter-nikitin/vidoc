from pathlib import Path

from video_processor.domain.entities import (
    AudioAsset,
    FilePath,
    ProcessingReport,
    SlideChangedEvent,
    Timestamp,
    TranscriptionSegment,
    VideoAsset,
)
from video_processor.ports.audio import AudioExtractorPort
from video_processor.ports.reporting import ReportBuilderPort
from video_processor.ports.slides import SlideChangePort
from video_processor.ports.speech import SpeechToTextPort


class FakeAudioExtractor(AudioExtractorPort):
  def extract_audio(self, video: VideoAsset) -> AudioAsset:
    return AudioAsset(path=FilePath(path=Path("fake audio path")))


class FakeAudioTranscriber(SpeechToTextPort):
  def transcribe(self, audio: AudioAsset) -> list[TranscriptionSegment]:
        return [
            TranscriptionSegment(text="fake text", start_sec=Timestamp(0), end_sec=Timestamp(10))
        ]


class FakeSlidesChange(SlideChangePort):
    def recognize_slide_change(self, video: VideoAsset) -> list[SlideChangedEvent]:
        return [
            SlideChangedEvent(
                slide=FilePath(Path("fake slide path")),
                timestamp=Timestamp(3),
            )
        ]


class FakeReportBuilder(ReportBuilderPort):
    def build_report(
        self,
        video: VideoAsset,
        transcriptions: list[TranscriptionSegment],
        slides: list[SlideChangedEvent],
    ) -> ProcessingReport:
        return ProcessingReport(slides=slides, transcription=transcriptions, video=video)
