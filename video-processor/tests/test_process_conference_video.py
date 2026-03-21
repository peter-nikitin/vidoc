from pathlib import Path

from application.use_cases.process_conference_video import ProcessVideo
from video_processor.domain.video import (
    FilePath,
    ProcessingReport,
    SlideChangedEvent,
    Timestamp,
    TranscriptionSegment,
    VideoAsset,
)
from video_processor.ports.audio_extractor_port import AudioExtractorPort
from video_processor.ports.report_builder_port import ReportBuilderPort
from video_processor.ports.slides_change_port import SlideChangePort
from video_processor.ports.speech_port import SpeechToTextPort


class FakeAudioExtractor(AudioExtractorPort):
    def extract_audio(self, video_path: FilePath) -> FilePath:
        return FilePath(path=Path(video_path.path.absolute.__str__() + "fake audio path"))


class FakeAudioTranscriber(SpeechToTextPort):
    def transcribe(self, file: FilePath) -> list[TranscriptionSegment]:
        return [
            TranscriptionSegment(text="fake text", start_sec=Timestamp(0), end_sec=Timestamp(10))
        ]


class FakeSlidesChange(SlideChangePort):
    def recognize_slide_change(self, file: FilePath) -> list[SlideChangedEvent]:
        return [
            SlideChangedEvent(
                slide=FilePath(Path(file.path.absolute.__str__() + "fake slide path")),
                timestamp=Timestamp(3),
            )
        ]


class FakeReportBuilder(ReportBuilderPort):
    def build_report(
        self,
        video: VideoAsset,
        transcriptions: list[TranscriptionSegment],
        slides: list[SlideChangedEvent],
        language: str,
    ) -> ProcessingReport:
        return ProcessingReport(
            language=language, slides=slides, transcription=transcriptions, video=video
        )


def test_process_conference_video_returns_report():
    testFile = FilePath(Path("test video"))
    
    use_case = ProcessVideo(
        audio_extractor=FakeAudioExtractor(),
        keyframe_detector=FakeSlidesChange(),
        report_builder=FakeReportBuilder(),
        speech_to_text=FakeAudioTranscriber(),
    )
    
    report = use_case.execute(testFile)
    
    assert isinstance(report, ProcessingReport)
