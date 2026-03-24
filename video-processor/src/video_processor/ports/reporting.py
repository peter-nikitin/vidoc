from typing import Protocol

from video_processor.domain.entities import (
    FilePath,
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

class ReportWriterPort(Protocol):
    def write_report(self, report: ProcessingReport) -> FilePath: ...