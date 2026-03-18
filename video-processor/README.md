# video-processor

Python project scaffold for video processing work.

## Dependency model

Python does not usually use a direct `node_modules` equivalent in the project root.

- `pyproject.toml` is the project manifest and is the closest analogue to `package.json`
- `.venv/` is the local virtual environment and is the practical analogue to a project-local dependency installation
- dependencies are installed into `.venv/lib/...` instead of a flat `node_modules/`

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Run tests

```bash
pytest
```

## Dependency groups

- base: core runtime dependencies from `[project.dependencies]`
- `speech`: local speech-to-text stack
- `slides`: frame analysis and slide change detection
- `dev`: everything needed for active development

Examples:

```bash
python -m pip install -e .
python -m pip install -e ".[speech]"
python -m pip install -e ".[slides]"
python -m pip install -e ".[dev]"
```

## System dependency

`ffmpeg` is required for audio extraction and frame sampling, but it is not installed through `pip`.
