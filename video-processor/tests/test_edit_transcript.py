"""Проверки локального инструмента без Ollama и сети."""

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "edit_transcript.py"
TEXT = "[00:00:00 → 00:00:30] Первый рассказ.\n[00:00:30 → 00:01:00] Продолжение.\n"


@pytest.fixture
def runner():
    assert SCRIPT.exists(), "Инструмент должен находиться в отслеживаемом каталоге scripts"
    spec = importlib.util.spec_from_file_location("edit_transcript", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def invoke(runner, monkeypatch, transcript, output, *extra):
    monkeypatch.setattr(
        sys,
        "argv",
        [str(SCRIPT), "--transcript", str(transcript), "--output-dir", str(output), *extra],
    )
    runner.main()


def read_json(path):
    return json.loads(path.read_text())


def test_prepare_two_inputs_from_other_cwd(tmp_path):
    for name, text in (("one", TEXT), ("two", TEXT.replace("Первый", "Другой"))):
        source = tmp_path / f"{name}.txt"
        source.write_text(text)
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--transcript",
                source.name,
                "--output-dir",
                name,
                "--prepare-only",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        manifest = read_json(tmp_path / name / "manifest.json")
        assert manifest["facts_available"] is False
        assert manifest["segments"] == 2
        request = read_json(tmp_path / name / "requests" / "01.json")
        assert "canonical_names:\n[]\nfacts:\n[]" in request["messages"][0]["content"]
        assert text.split("] ")[1].split("\n")[0] in request["messages"][0]["content"]
        assert source.read_text() == text
        assert not (tmp_path / name / "article.md").exists()
    assert (
        read_json(tmp_path / "one" / "manifest.json")["transcript_sha256"]
        != read_json(tmp_path / "two" / "manifest.json")["transcript_sha256"]
    )


@pytest.mark.parametrize("with_facts", [True, False])
def test_full_run_resume_changed_request_and_title(runner, monkeypatch, tmp_path, with_facts):
    source, facts, output = tmp_path / "input.txt", tmp_path / "facts.json", tmp_path / "out"
    source.write_text(TEXT)
    facts.write_text(
        json.dumps(
            {
                "claims": [{"timestamp": "00:00:10", "claim_ru": "Справка"}],
                "canonical_names": ["Имя"],
            }
        )
    )

    facts_args = ("--facts", str(facts)) if with_facts else ()

    def fake_api(request, timeout):
        payload = json.loads(request.data)
        content = payload["messages"][0]["content"]
        if with_facts:
            assert "Справка" in content and "Имя" in content
        else:
            assert "canonical_names:\n[]\nfacts:\n[]" in content
        blocks = json.loads(content.split("\nblocks:\n")[1])
        response = {
            "done": True,
            "done_reason": "stop",
            "message": {
                "content": json.dumps(
                    {"blocks": [{"id": b["id"], "text": b["text"], "unclear": []} for b in blocks]}
                )
            },
        }
        return io.BytesIO(json.dumps(response).encode())

    monkeypatch.setattr(runner.urllib.request, "urlopen", fake_api)
    invoke(runner, monkeypatch, source, output, *facts_args, "--title", "Другой фильм")
    assert (output / "article.md").read_text().startswith("# Другой фильм\n")
    assert read_json(output / "progress.json")["complete"] is True
    assert read_json(output / "output-blocks.json")["blocks"][0]["source_text"] == "Первый рассказ."
    original_response = (output / "responses" / "01.json").read_bytes()

    def forbidden(*args, **kwargs):
        pytest.fail("Сохранённый ответ должен использоваться без API")

    monkeypatch.setattr(runner.urllib.request, "urlopen", forbidden)
    invoke(runner, monkeypatch, source, output, *facts_args)
    assert (output / "article.md").read_text().startswith("# Отредактированная расшифровка\n")
    assert (output / "responses" / "01.json").read_bytes() == original_response
    source.write_text(TEXT.replace("Первый", "Изменённый"))
    monkeypatch.setattr(runner.urllib.request, "urlopen", fake_api)
    invoke(runner, monkeypatch, source, output, *facts_args)
    assert "Изменённый рассказ." in (output / "article.md").read_text()
    assert (output / "responses" / "01.json").read_bytes() != original_response


@pytest.mark.parametrize(
    "relative",
    [
        "manifest.json",
        "manifest.json.tmp",
        "article.md",
        "requests/01.json",
        "responses/01.json",
        "progress.json",
    ],
)
@pytest.mark.parametrize("kind", ["transcript", "facts", "symlink"])
def test_rejects_input_overwrite_before_writes(runner, monkeypatch, tmp_path, relative, kind):
    output = tmp_path / "out"
    target = output / relative
    target.parent.mkdir(parents=True)
    source = tmp_path / "input.txt"
    source.write_text(TEXT)
    facts = tmp_path / "facts.json"
    facts.write_text('{"claims": []}')
    if kind == "transcript":
        target.write_text(TEXT)
        source = target
    elif kind == "facts":
        target.write_bytes(facts.read_bytes())
        facts = target
    else:
        target.symlink_to(source)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="вход"):
        invoke(runner, monkeypatch, source, output, "--facts", str(facts), "--prepare-only")
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before
