from typing import Protocol
from video_processor.domain.video import FilePath

class AudioExtractorPort(Protocol):
  def extract_audio(self, video_path: FilePath) -> FilePath:
    ...
  
