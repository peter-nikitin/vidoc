# Video Processor Architecture

## Goal

The project processes conference presentation videos where a speaker talks over slides.
The system works in two modalities:

1. Audio:
   extract the audio track and convert speech to text.
2. Slides:
   extract key frames to detect when presentation slides change.

The first delivery milestone is a single JSON document with structured video data.

## Architectural Style

The project follows a DDD-oriented modular monolith with clean architecture boundaries:

- Pure domain core with no infrastructure dependencies.
- Side effects isolated behind explicit ports.
- Application layer orchestrates use cases.
- Infrastructure layer integrates local tools and models.

The domain must not depend on:

- `ffmpeg`
- OpenCV
- local ML runtime
- filesystem
- JSON serialization details

## Bounded Context

At the current stage, one bounded context is enough: `video_processing`.

Inside it, there are three main areas:

- `speech`: audio extraction result, transcript segments, language, confidence.
- `slides`: representative frames and slide change events.
- `reporting`: assembly of the final processing result.

This should remain a modular monolith for now. Splitting into services is premature.

## Layers

### Domain

Pure business model and rules.

Candidate entities and value objects:

- `VideoAsset`
- `AudioTrack`
- `TranscriptSegment`
- `SlideChangeEvent`
- `ProcessingReport`
- `Timestamp`
- `Duration`
- `Confidence`
- `FrameRef`

Responsibilities:

- represent processing results in domain terms
- validate domain invariants
- stay free of side effects

### Application

Use case orchestration through ports.

Core use cases:

- `ProcessConferenceVideo`
- `ExtractAudio`
- `TranscribeAudio`
- `DetectSlideChanges`
- `AssembleVideoReport`

Responsibilities:

- coordinate workflow
- invoke ports in the right order
- map infrastructure outputs into domain objects

### Ports

Interfaces that isolate side effects.

Initial ports:

- `VideoReaderPort`
- `AudioExtractorPort`
- `SpeechToTextPort`
- `KeyframeDetectorPort`
- `StoragePort`
- `ReportWriterPort`

Responsibilities:

- define contracts used by the application layer
- keep infrastructure replaceable

### Infrastructure

Concrete implementations of ports.

Planned adapters:

- `ffmpeg` for audio extraction and frame sampling
- `faster-whisper` or `whisper.cpp` for local speech-to-text
- OpenCV for frame comparison and slide change detection
- filesystem adapters for artifacts and JSON output

## Processing Flow

Main use case: `ProcessConferenceVideo`

1. Validate input video.
2. Extract audio track.
3. Run speech-to-text.
4. Sample frames from the video.
5. Detect significant slide changes.
6. Build a domain `ProcessingReport`.
7. Serialize the report to JSON.

## Modality Design

### Speech Pipeline

Recommended MVP approach:

- use `ffmpeg` to extract mono 16 kHz WAV
- run local transcription with `faster-whisper`
- return transcript segments with:
  - `start_sec`
  - `end_sec`
  - `text`
  - `confidence` where available
  - detected language where available

### Slides Pipeline

Recommended MVP approach:

- sample frames with `ffmpeg` or OpenCV at low frequency, for example `1 fps` or `0.5 fps`
- compare neighboring frames using histogram difference or SSIM
- create a `SlideChangeEvent` when the difference score exceeds a threshold
- store:
  - timestamp
  - score
  - representative frame path

OCR is intentionally out of scope for the first stage.

## Output Contract

The first stage output is a single JSON document.

Example target structure:

```json
{
  "video": {
    "source_path": "input.mp4",
    "duration_sec": 1234.5
  },
  "transcript": {
    "language": "ru",
    "segments": [
      {
        "start_sec": 0.5,
        "end_sec": 4.2,
        "text": "Добрый день...",
        "confidence": 0.93
      }
    ]
  },
  "slides": {
    "changes": [
      {
        "timestamp_sec": 12.0,
        "frame_path": "artifacts/frames/slide_0001.jpg",
        "score": 0.81
      }
    ]
  },
  "processing": {
    "created_at": "2026-03-18T12:00:00Z",
    "tool_versions": {
      "ffmpeg": "..."
    }
  }
}
```

## Proposed Project Structure

```text
src/video_processor/
  domain/
    entities.py
    value_objects.py
    services.py
  application/
    use_cases/
      process_conference_video.py
    dto.py
  ports/
    audio.py
    speech.py
    slides.py
    storage.py
    reporting.py
  infrastructure/
    ffmpeg/
      audio_extractor.py
      frame_sampler.py
    whisper/
      faster_whisper_transcriber.py
    vision/
      opencv_slide_detector.py
    storage/
      file_system.py
      json_writer.py
  interfaces/
    cli/
      main.py
```

## Implementation Sequence

1. Define the domain model and JSON schema.
2. Define ports and application DTOs.
3. Implement `ProcessConferenceVideo` with fake adapters and unit tests.
4. Add the `ffmpeg` audio extraction adapter.
5. Add speech-to-text via `faster-whisper`.
6. Add frame sampling.
7. Implement slide change detection with OpenCV.
8. Add JSON report writer.
9. Add CLI entrypoint such as `process-video input.mp4 --out report.json`.
10. Add integration tests against a short sample video.

## Testing Strategy

### Unit Tests

Scope:

- `domain`
- `application`

Rules:

- no real filesystem
- no real `ffmpeg`
- no real ML runtime
- use mocks or fakes for ports

### Integration Tests

Scope:

- `ffmpeg` adapters
- speech-to-text adapter
- slide detection adapter

### Golden Tests

Use one short sample video and validate:

- output JSON structure
- transcript presence
- expected slide change timestamps with tolerance

## Technology Choices For MVP

Recommended initial stack:

- `ffmpeg` for media extraction
- `faster-whisper` for local transcription
- `opencv-python` for frame comparison
- `pydantic` only for boundary DTOs and output validation

The domain model should remain framework-independent.
