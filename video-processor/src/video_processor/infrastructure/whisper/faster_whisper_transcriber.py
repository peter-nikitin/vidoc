from faster_whisper import WhisperModel

from video_processor.domain.entities import AudioAsset, Timestamp, TranscriptionSegment
from video_processor.ports.speech import SpeechToTextPort


class FasterWhisperTranscriber(SpeechToTextPort):
    def __init__(self) -> None:
        self.model = WhisperModel(model_size_or_path="large-v3", device="cpu", compute_type="int8")


    def transcribe(self, audio: AudioAsset) -> list[TranscriptionSegment]: 
        file_path = audio.path
        segments, _ = self.model.transcribe(str(file_path))
        
        transcription_segments = []
        for segment in segments:
            transcription_segments.append(
                TranscriptionSegment(
                    start_sec=Timestamp(segment.start),
                    end_sec=Timestamp(segment.end),
                    text=segment.text
                )
            )

        return transcription_segments
