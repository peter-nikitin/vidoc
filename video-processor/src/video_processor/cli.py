"""Команда vidoc URL."""

import argparse
import sys

from video_processor.adapters.ffmpeg import FfmpegAudioExtractor
from video_processor.adapters.whisper import WhisperSpeechRecognizer
from video_processor.adapters.ytdlp import YtDlpDownloader
from video_processor.pipeline import ARTIFACTS_ROOT, ProcessingError, run


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="vidoc", description="Локальная расшифровка одного YouTube-видео.", add_help=False
    )
    parser.add_argument("-h", "--help", action="help", help="показать справку и выйти")
    parser.add_argument("url", metavar="URL", help="ссылка на YouTube-видео")
    args = parser.parse_args(argv)
    try:
        directory = run(
            args.url,
            downloader=YtDlpDownloader(ARTIFACTS_ROOT / ".yt-dlp-cache"),
            audio_extractor=FfmpegAudioExtractor(),
            recognizer=WhisperSpeechRecognizer(ARTIFACTS_ROOT / ".models"),
            artifacts_root=ARTIFACTS_ROOT,
        )
    except ProcessingError as error:
        print(f"Ошибка — {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Прервано пользователем.", file=sys.stderr)
        return 130
    print(f"Готово. Результат: {directory}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
