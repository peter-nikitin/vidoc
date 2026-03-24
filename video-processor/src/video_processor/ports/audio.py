from typing import Protocol

from video_processor.domain.entities import AudioAsset, VideoAsset


class AudioExtractorPort(Protocol):
    def extract_audio(self, video: VideoAsset) -> AudioAsset: ...
  
