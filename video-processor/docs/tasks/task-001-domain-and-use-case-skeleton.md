# Task 001: Domain Model And Use Case Skeleton

## Context

We are building a video processing pipeline for conference talks.
At the first stage, the system should eventually produce a JSON report with:

- basic video metadata
- transcript segments
- slide change events

Before integrating `ffmpeg`, speech-to-text, and frame analysis, we need to define the internal architecture correctly.

Your goal is to create the first clean slice of the system:

- domain entities
- port interfaces
- application use case skeleton

No real side effects yet.

## Why This Task Matters

If you start with infrastructure, the shape of the system will be dictated by external tools.
That is exactly what we do not want in a DDD/Clean Architecture design.

This task establishes:

- the language of the domain
- the boundaries between pure logic and side effects
- the orchestration flow of the first use case

## Goal

Implement a minimal but coherent architecture skeleton for the use case `ProcessConferenceVideo`.

After this task, we should be able to:

1. construct a use case with fake adapters
2. pass in a video path
3. get back a structured in-memory report object
4. verify the orchestration with unit tests

## Scope

You should create only pure-core and boundary definitions.

In scope:

- domain entities as Python `dataclass`es
- ports as Python `Protocol`s
- a use case that orchestrates calls through ports
- unit tests using fake implementations

Out of scope:

- `ffmpeg`
- OpenCV
- whisper / speech models
- filesystem writes
- real JSON output
- CLI

## Files To Create

Create these files:

```text
src/video_processor/domain/entities.py
src/video_processor/ports/audio.py
src/video_processor/ports/speech.py
src/video_processor/ports/slides.py
src/video_processor/ports/reporting.py
src/video_processor/application/use_cases/process_conference_video.py
tests/application/test_process_conference_video.py
```

If you need small `__init__.py` files for packages, add them too.

## Design Requirements

### 1. Domain Entities

Define minimal domain models in `domain/entities.py`.

Start with these entities:

- `VideoAsset`
- `TranscriptSegment`
- `SlideChangeEvent`
- `ProcessingReport`

Recommended shape:

- use `@dataclass(frozen=True)` unless mutability is clearly needed
- use `pathlib.Path` for file paths
- use plain `float` for timestamps for now

Suggested fields:

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

Do not over-engineer value objects yet.
The task is to get the structure right first.

### 2. Ports

Define ports as `Protocol`s.

`ports/audio.py`
- `AudioExtractorPort`
- method:
  - `extract_audio(video_path: Path) -> Path`

`ports/speech.py`
- `SpeechToTextPort`
- method:
  - `transcribe(audio_path: Path) -> tuple[str | None, list[TranscriptSegment]]`

`ports/slides.py`
- `KeyframeDetectorPort`
- method:
  - `detect_slide_changes(video_path: Path) -> list[SlideChangeEvent]`

`ports/reporting.py`
- for this task, define one port:
  - `ReportBuilderPort`
- method:
  - `build_report(video: VideoAsset, transcript_language: str | None, transcript_segments: list[TranscriptSegment], slide_changes: list[SlideChangeEvent]) -> ProcessingReport`

Important:
- ports define contracts only
- no implementation logic in port modules

### 3. Use Case

Implement `ProcessConferenceVideo` in `application/use_cases/process_conference_video.py`.

It should accept dependencies via constructor injection:

- `audio_extractor: AudioExtractorPort`
- `speech_to_text: SpeechToTextPort`
- `keyframe_detector: KeyframeDetectorPort`
- `report_builder: ReportBuilderPort`

It should expose one method:

- `execute(video_path: Path) -> ProcessingReport`

Expected orchestration:

1. create `VideoAsset` from `video_path`
2. call `audio_extractor.extract_audio(video_path)`
3. call `speech_to_text.transcribe(audio_path)`
4. call `keyframe_detector.detect_slide_changes(video_path)`
5. call `report_builder.build_report(...)`
6. return the resulting `ProcessingReport`

Keep it explicit and readable.
No hidden magic, no premature abstractions.

## Testing Requirements

Create `tests/application/test_process_conference_video.py`.

Write unit tests with fake adapters.

Minimum required tests:

1. Happy path:
   verifies that `execute()` returns a `ProcessingReport`
   with the expected transcript and slide changes.

2. Orchestration test:
   verifies dependencies are called in the expected order.

Use simple in-memory fakes.
Do not use `mock.patch` unless there is a clear reason.
For this task, explicit fakes are better than clever mocking.

## Quality Bar

Your implementation should be:

- small
- explicit
- typed
- easy to read

Avoid:

- introducing base classes you do not need
- adding Pydantic here
- mixing domain and infrastructure concerns
- adding serialization logic into domain entities

## Definition Of Done

The task is done when:

1. all listed files exist
2. entities are defined as clean domain models
3. ports are defined as `Protocol`s
4. `ProcessConferenceVideo.execute()` orchestrates the flow
5. tests pass with `pytest`
6. no real side effects are used

## What I Will Review

When you finish, I will review for:

- whether boundaries are clean
- whether the use case depends only on ports
- whether entity design is simple and sufficient
- whether tests verify behavior instead of implementation noise

## Hints

- prefer a boring solution over a clever one
- if you are unsure whether something belongs in `domain` or `infrastructure`, it probably does not belong in `domain`
- keep methods short
- name things in domain language, not tool language

If you finish early and it still feels too easy, do not add more architecture.
That usually means the task was sized correctly.
