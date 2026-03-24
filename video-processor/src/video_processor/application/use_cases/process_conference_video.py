from uuid import uuid4

from video_processor.domain.entities import FilePath, ProcessingReport, VideoAsset
from video_processor.ports.audio import AudioExtractorPort
from video_processor.ports.reporting import ReportBuilderPort
from video_processor.ports.slides import SlideChangePort
from video_processor.ports.speech import SpeechToTextPort


class ProcessVideo:
    def __init__(
        self,
        audio_extractor: AudioExtractorPort,
        speech_to_text: SpeechToTextPort,
        keyframe_detector: SlideChangePort,
        report_builder: ReportBuilderPort,
    ) -> None:
        self._audio_extractor = audio_extractor
        self._speech_to_text = speech_to_text
        self._keyframe_detector = keyframe_detector
        self._report_builder = report_builder

    def execute(self, video_path: FilePath) -> ProcessingReport:
        video = VideoAsset(id=uuid4(), path=video_path)
        audio = self._audio_extractor.extract_audio(video)
        transcription = self._speech_to_text.transcribe(audio)
        slides = self._keyframe_detector.recognize_slide_change(video)

        report = self._report_builder.build_report(
            slides=slides, 
            transcriptions=transcription, 
            video=video
        )

        return report
