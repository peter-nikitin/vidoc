import subprocess
from pathlib import Path

from video_processor.domain.entities import AudioAsset, FilePath, VideoAsset
from video_processor.ports.audio import AudioExtractorPort


class FfmpegAudioExtractor(AudioExtractorPort):
    def extract_audio(self, video: VideoAsset) -> AudioAsset:
        output_path = 'audio.wav'
        
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(video.path.path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-ac",
                "2",
                output_path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        
        return AudioAsset(path=FilePath(path=Path(output_path)))  