"""Получение метаданных и полного видео через yt-dlp."""

import shutil
from pathlib import Path

from video_processor.ports import VideoInfo


class YtDlpDownloader:
    def __init__(self, cache_root: Path):
        self.cache_root = cache_root

    def _options(self) -> dict:
        return {
            "noplaylist": True,
            "quiet": True,
            "js_runtimes": {"deno": {}, "node": {}},
            "cachedir": str(self.cache_root),
        }

    def probe(self, url: str) -> VideoInfo:
        from yt_dlp import YoutubeDL

        with YoutubeDL(self._options()) as downloader:
            info = downloader.extract_info(url, download=False)
        if not info:
            return VideoInfo("", "", kind="playlist")
        return VideoInfo(
            id=info.get("id", ""),
            title=info.get("title", ""),
            kind=info.get("_type"),
            is_live=bool(info.get("is_live")),
            live_status=info.get("live_status"),
        )

    def download(self, url: str, info: VideoInfo, directory: Path) -> Path:
        from yt_dlp import YoutubeDL

        # Повторно используем только завершённый файл, .part остаётся загрузчику.
        for path in sorted(directory.glob("video.*")):
            if (
                path.stem == "video"
                and path.suffix in {".mp4", ".mkv", ".webm", ".mov"}
                and path.stat().st_size
            ):
                return path
        staging = directory / ".download"
        staging.mkdir(exist_ok=True)
        options = {
            **self._options(),
            "format": "bestvideo+bestaudio/best",
            "outtmpl": str(staging).replace("%", "%%") + "/video.%(ext)s",
            "merge_output_format": "mkv",
        }
        with YoutubeDL(options) as downloader:
            result = downloader.extract_info(url, download=True)
            path = Path(downloader.prepare_filename(result))
            # При объединении yt-dlp меняет контейнер и расширение.
            merged = path.with_suffix(".mkv")
            if merged.is_file():
                path = merged
        if not path.is_file() or not path.stat().st_size:
            raise RuntimeError("yt-dlp не создал полный видеофайл")
        completed = directory / f"video{path.suffix}"
        path.replace(completed)
        shutil.rmtree(staging)
        return completed
