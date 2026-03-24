import pathlib

import cv2
from cv2.typing import MatLike

from video_processor.domain.entities import FilePath, SlideChangedEvent, Timestamp, VideoAsset
from video_processor.ports.slides import SlideChangePort


class OpenCvSlideDetector(SlideChangePort):
    def __init__(self) -> None:
        self.path = "./frames"
        self.interval_sec = 1.0
        self.diff_threshold = 0.15

    def recognize_slide_change(self, video: VideoAsset) -> list[SlideChangedEvent]:
        cap = self._open_video(video)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = int(fps * self.interval_sec)

        frames = self._sample_every_n_frames(cap, frame_interval)
        processed_frames = [self.process_frame(frame) for frame in frames]

        events = []
        for i in range(1, len(processed_frames)):
            score = self._difference_score(processed_frames[i - 1], processed_frames[i])
            if score > self.diff_threshold:
                timestamp = Timestamp(i * self.interval_sec)
                event = self._save_frame(frames[i], timestamp)
                events.append(event)

        cap.release()
        return events

    def _open_video(self, video: VideoAsset) -> cv2.VideoCapture:
        return cv2.VideoCapture(str(video.path.path))

    def _sample_every_n_frames(
        self,
        cap: cv2.VideoCapture,
        n: int,
    ) -> list[MatLike]:
        frames = []
        frame_count = 0
        while True:
            success, frame = cap.read()
            if not success:
                break
            if frame_count % n == 0:
                frames.append(frame)
            frame_count += 1
        return frames

    def process_frame(self, frame: MatLike) -> MatLike:
        width = 320
        height = 320
        processed = cv2.cvtColor(cv2.resize(frame, (width, height)), cv2.COLOR_BGR2GRAY)
        processed = cv2.GaussianBlur(processed, (5, 5), 0)
        return processed

    def _difference_score(self, previous: MatLike, current: MatLike) -> float:
        diff = cv2.absdiff(previous, current)
        _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)

        non_zero_pixels = int(cv2.countNonZero(thresh))
        total_pixels = int(thresh.shape[0] * thresh.shape[1])

        return float(non_zero_pixels / total_pixels)

    def _save_frame(self, frame: MatLike, timestamp: Timestamp) -> SlideChangedEvent:
        filename = f"{self.path}/frame_{timestamp:.2f}.jpg"
        cv2.imwrite(filename, frame)

        return SlideChangedEvent(
            slide=FilePath(pathlib.Path(filename)),
            timestamp=timestamp,
        )
