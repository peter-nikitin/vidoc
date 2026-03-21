from typing import Protocol

from video_processor.domain.video import (
    ProcessingReport,
    SlideChangedEvent,
    TranscriptionSegment,
    VideoAsset,
)


class ReportBuilderPort(Protocol):
    def build_report(
        self,
        video: VideoAsset,
        transcriptions: list[TranscriptionSegment],
        slides: list[SlideChangedEvent],
    ) -> ProcessingReport: ...
