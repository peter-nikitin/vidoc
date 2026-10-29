"""Извлечение PCM-аудио через системный ffmpeg."""

import shutil
import subprocess
from pathlib import Path


class FfmpegAudioExtractor:
    def check_available(self) -> None:
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg не найден. Установите: brew install ffmpeg")

    def extract(self, video: Path, wav: Path) -> None:
        result = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(video),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(wav),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "ffmpeg завершился с ошибкой")
