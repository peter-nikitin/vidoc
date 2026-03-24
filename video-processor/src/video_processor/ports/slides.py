from typing import Protocol

from video_processor.domain.entities import SlideChangedEvent, VideoAsset


class SlideChangePort(Protocol):
    def recognize_slide_change(self, video: VideoAsset) -> list[SlideChangedEvent]: ...
