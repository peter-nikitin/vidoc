from pathlib import Path

from tests.application.fakes import (
    FakeAudioExtractor,
    FakeAudioTranscriber,
    FakeReportBuilder,
    FakeSlidesChange,
)
from video_processor.application.use_cases.process_conference_video import ProcessVideo
from video_processor.domain.entities import FilePath, ProcessingReport


def test_process_conference_video_returns_report() -> None:
    testFile = FilePath(Path("test video"))

    use_case = ProcessVideo(
        audio_extractor=FakeAudioExtractor(),
        keyframe_detector=FakeSlidesChange(),
        report_builder=FakeReportBuilder(),
        speech_to_text=FakeAudioTranscriber(),
    )

    report = use_case.execute(testFile)

    assert isinstance(report, ProcessingReport)
