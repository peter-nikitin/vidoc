from typing import Protocol

from video_processor.domain.video import FilePath, SlideChangedEvent


class SlideChangePort(Protocol):
    def recognize_slide_change(self, file: FilePath) -> list[SlideChangedEvent]: ...
