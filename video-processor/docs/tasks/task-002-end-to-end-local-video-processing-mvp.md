# Task 002: End-To-End Local Video Processing MVP

## Context

Task 001 established the initial domain and use-case skeleton for video processing.
The next step should produce a small but real product result.

The developer should be able to take a local video file and run one command that produces:

- a real transcription
- real slide change detection
- one combined JSON report
- saved representative frame images for detected slide changes

This task is the first thin vertical slice through the whole system.
It must use real infrastructure adapters, but still preserve the clean architecture defined in [`docs/architecture.md`](/Users/petrnikitin/Documents/Sites/vidoc/video-processor/docs/architecture.md).

## Why This Task Matters

The first task proved the orchestration shape.
That is necessary, but not sufficient.

After this task, the project should stop being only an architectural exercise and start behaving like a product.

This task establishes:

- the first real end-to-end processing flow
- the first executable local interface
- the first concrete artifact contract
- the first integration point between domain, application, and infrastructure

It is also the first point where architectural discipline becomes real.
If the adapters leak tool-specific concerns into the use case or domain, the design will start degrading immediately.

## Goal

Implement a real local MVP for processing one conference video into one JSON report.

After this task, we should be able to:

1. pass in a local video file
2. extract audio with `ffmpeg`
3. transcribe speech with `faster-whisper`
4. detect slide changes with OpenCV
5. save representative frame images for each detected change
6. write one `report.json`
7. run the whole flow from a CLI command

## Product Result

The visible product result of this task is:

- input: one local video file such as `input.mp4`
- output directory containing:
  - `report.json`
  - saved frame images for slide changes

The JSON report should include:

- video metadata available at this stage
- transcript language when available
- transcript segments
- slide change events
- paths to saved representative frame images

This task does **not** need to produce separate transcription and slide files.
The product shape for this milestone is one combined report, because that matches the target architecture better.

## Scope

This task should introduce the smallest real vertical slice.

In scope:

- refactor the current skeleton where needed to align with the intended architecture
- real `ffmpeg` audio extraction adapter
- real `faster-whisper` transcription adapter
- real OpenCV slide change detection adapter
- file system adapter for writing report artifacts
- one CLI entrypoint for local execution
- one integration test for the full pipeline on a short fixture video
- unit tests for application and domain behavior affected by the refactor

Out of scope:

- OCR
- subtitle file formats such as `.srt` or `.vtt`
- speaker diarization
- remote APIs
- background jobs
- database persistence
- batching multiple videos
- UI
- e2e/browser automation

## Architectural Expectations

This task must follow the architecture in [`docs/architecture.md`](/Users/petrnikitin/Documents/Sites/vidoc/video-processor/docs/architecture.md).

That means:

- business rules stay in domain and application layers
- `ffmpeg`, `faster-whisper`, OpenCV, filesystem, and CLI concerns stay in infrastructure or interface layers
- the use case depends only on ports
- dependencies point inward
- domain code stays framework-agnostic and IO-free

Important:

- do not let `faster-whisper` result objects leak outside the speech adapter
- do not let OpenCV arrays or image-processing details leak into the domain
- do not put JSON serialization logic inside domain entities
- do not let CLI argument parsing shape the application API

## Refactoring Requirement

Before adding new infrastructure, review the current Task 001 implementation and normalize it where needed.

The current code already shows some drift from the architectural source of truth:

- inconsistent module layout
- naming drift in ports and use case names
- domain value objects introduced early without clear need
- test structure that verifies too little

This task should include a small correction pass so the real adapters are added to stable boundaries.

Keep this refactor focused.
Do not expand it into a broad architecture rewrite.

## Recommended Project Structure

The implementation should move toward this structure:

```text
src/video_processor/
  domain/
    entities.py
  application/
    use_cases/
      process_conference_video.py
  ports/
    audio.py
    speech.py
    slides.py
    reporting.py
  infrastructure/
    ffmpeg/
      audio_extractor.py
    whisper/
      faster_whisper_transcriber.py
    vision/
      opencv_slide_detector.py
    storage/
      file_system.py
      json_report_writer.py
  interfaces/
    cli/
      main.py
tests/
  application/
  integration/
```

You do not need to force the exact final folder layout everywhere in one pass, but the new code should move in this direction instead of deepening the current inconsistencies.

## Domain Requirements

Define or normalize the minimal domain entities needed for this slice.

Start with:

- `VideoAsset`
- `TranscriptSegment`
- `SlideChangeEvent`
- `ProcessingReport`

Recommended shape:

`VideoAsset`
- `source_path: Path`
- `duration_sec: float | None = None`

`TranscriptSegment`
- `start_sec: float`
- `end_sec: float`
- `text: str`
- `confidence: float | None = None`

`SlideChangeEvent`
- `timestamp_sec: float`
- `frame_path: Path`
- `score: float`

`ProcessingReport`
- `video: VideoAsset`
- `transcript_language: str | None`
- `transcript_segments: list[TranscriptSegment]`
- `slide_changes: list[SlideChangeEvent]`

Keep the domain explicit and boring.
Do not add extra abstractions unless they improve clarity immediately.

## Port Requirements

Define ports as `Protocol`s.
Ports define contracts only.

### `ports/audio.py`

`AudioExtractorPort`

Method:

- `extract_audio(video: VideoAsset, output_dir: Path) -> Path`

The adapter is responsible for producing a local extracted audio file and returning its path.
This port is conceptually about processing a video asset, so it should accept the domain entity rather than a raw file path.

### `ports/speech.py`

`SpeechToTextPort`

Method:

- `transcribe(audio_path: Path) -> tuple[str | None, list[TranscriptSegment]]`

The adapter maps raw model output into domain objects.

### `ports/slides.py`

`SlideChangeDetectorPort`

Method:

- `detect_slide_changes(video: VideoAsset, output_dir: Path) -> list[SlideChangeEvent]`

The adapter is responsible for saving representative frame artifacts and returning domain events that reference them.
This port is also conceptually about processing a video asset, so it should accept `VideoAsset`.

### `ports/reporting.py`

Define two ports:

`ReportBuilderPort`
- builds a `ProcessingReport` from domain pieces

`ReportWriterPort`
- writes a `ProcessingReport` to a target output path

Suggested methods:

- `build_report(video: VideoAsset, transcript_language: str | None, transcript_segments: list[TranscriptSegment], slide_changes: list[SlideChangeEvent]) -> ProcessingReport`
- `write(report: ProcessingReport, output_path: Path) -> Path`

If the report builder adds no meaningful behavior, it is acceptable to replace it with direct construction in the application layer.
If you do that, the reasoning should be explicit.

## Use Case Requirements

Implement or refactor the application entrypoint to keep one main use case:

- `ProcessConferenceVideo`

Suggested method:

- `execute(video_path: Path, output_dir: Path) -> ProcessingReport`

Expected orchestration:

1. validate the input path at the application boundary
2. create `VideoAsset`
3. extract audio from the `VideoAsset` to a working artifact path
4. transcribe audio
5. detect slide changes from the `VideoAsset` and save representative frame images
6. assemble a `ProcessingReport`
7. write `report.json`
8. return the in-memory `ProcessingReport`

Keep the use case explicit.
Do not hide steps inside convenience abstractions.

## Infrastructure Requirements

### `ffmpeg` Audio Extraction

Implement an adapter that:

- invokes `ffmpeg`
- extracts mono 16 kHz WAV audio
- writes the result into the chosen output or working directory

The adapter should fail clearly when `ffmpeg` is unavailable or returns an error.

### `faster-whisper` Transcription

Implement an adapter that:

- loads a configured `faster-whisper` model
- transcribes the extracted audio
- maps segments into `TranscriptSegment`
- returns detected language where available

Keep all `faster-whisper` specific objects inside the adapter.

For this MVP:

- use a small model that is practical for local development
- prefer explicit configuration over hidden defaults

### OpenCV Slide Change Detection

Implement an adapter that:

- samples frames from the video at a low fixed rate
- compares neighboring frames
- detects slide changes using a simple threshold-based strategy
- saves representative frame images for detected changes
- returns `SlideChangeEvent` domain objects

Acceptable first-pass approaches:

- histogram difference
- structural similarity
- another simple deterministic image-difference technique

Do not over-engineer this stage.
The goal is a useful baseline, not perfect slide semantics.

### JSON Report Writing

Implement an adapter that:

- serializes a `ProcessingReport`
- writes it as `report.json`
- keeps serialization concerns outside the domain model

Use the standard library unless there is a strong reason not to.

## CLI Requirements

Add a CLI entrypoint for local execution.

Example shape:

```bash
process-video input.mp4 --output-dir ./artifacts
```

Responsibilities:

- parse arguments
- call the use case
- present a minimal success or failure message

The CLI must remain thin.
It is not the place for business logic.

## Configuration Guidance

This task will need some configuration choices, especially for transcription.

Keep configuration simple and local.
At minimum, make the following explicit somewhere appropriate:

- `faster-whisper` model size
- slide-change detection threshold
- frame sampling rate
- output directory layout

Avoid a heavy configuration system.
Simple constructor parameters or a small configuration object is enough for this stage.

## Output Contract

The target `report.json` should follow this shape closely:

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
        "text": "Hello world",
        "confidence": 0.93
      }
    ]
  },
  "slides": {
    "changes": [
      {
        "timestamp_sec": 12.0,
        "frame_path": "frames/slide_0001.jpg",
        "score": 0.81
      }
    ]
  }
}
```

Additional metadata may be included if it is clearly useful and does not pollute the contract.

## Testing Requirements

Testing priority remains:

1. unit tests
2. integration tests
3. e2e last

### Unit Tests

Cover:

- application orchestration
- any domain validation or transformation logic introduced during the refactor
- serialization mapping if it contains meaningful logic

Use fakes for ports where appropriate.

### Integration Tests

Add at least one integration test that:

- runs the real processing pipeline on a short fixture video
- verifies `report.json` is written
- verifies transcript segments exist
- verifies at least one slide change frame artifact is produced when the fixture makes that reasonable

The integration test should validate the real end-to-end path across ports and adapters.

Do not replace missing unit tests with broader integration coverage.

## Definition Of Done

The task is done when:

1. the application has one real end-to-end local processing path
2. `ffmpeg` audio extraction works
3. `faster-whisper` transcription works
4. OpenCV slide change detection works at a basic but usable level
5. representative frame images are saved
6. `report.json` is written
7. the flow is runnable from a CLI command
8. unit tests pass
9. at least one integration test passes
10. architecture boundaries remain clean

## What I Will Review

When this task is finished, I will review:

- whether the use case still depends only on ports
- whether infrastructure details stay out of domain and application layers
- whether the output contract is coherent and practical
- whether the slide detection approach is simple and defensible
- whether `faster-whisper` integration is contained cleanly
- whether tests respect the unit-first, integration-second strategy
- whether the CLI is thin and not doing orchestration work

## Hints

- prefer a small real product over a wide but incomplete feature set
- keep the first slide-change algorithm simple and measurable
- map external tool outputs into domain language immediately
- prefer domain entities at ports when the operation is conceptually about the video, and use `Path` when the operation is explicitly about a concrete derived artifact
- resist adding abstraction layers that only wrap one implementation
- if a choice is between “clean and slightly boring” and “clever but implicit”, choose the boring one
