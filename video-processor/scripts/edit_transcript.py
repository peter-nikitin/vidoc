#!/usr/bin/env python3
"""Локальная редактура расшифровки через Ollama; только stdlib."""

import argparse
import hashlib
import json
import re
import time
import urllib.request
from pathlib import Path

MODEL = "qwen3.5:9b-q4_K_M"
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["blocks"],
    "properties": {
        "blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "text", "unclear"],
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "unclear": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["quote", "reason"],
                            "properties": {
                                "quote": {"type": "string"},
                                "reason": {"type": "string"},
                            },
                        },
                    },
                },
            },
        }
    },
}
RULES = """Ты литературный редактор русской устной речи. Верни строго JSON по схеме.
Редактируй каждый blocks отдельно, в исходном порядке, один результат на каждый id.
Не переноси сведения между блоками. Внутри блока сохраняй порядок каждой мысли.
Сохрани все содержательные утверждения, примеры, оговорки, числа, отрицания,
причины и следствия, степень уверенности и авторские оценки. Не пересказывай и не
сокращай. Удали лишь запинки и случайные повторы. Исправь грамматику, согласование,
пунктуацию и разбей текст на смысловые абзацы. Сохрани рекламу, самопродвижение,
обращения к зрителю, авторское первое лицо и ссылки автора на собственное будущее
рассуждение. Не добавляй собственных сведений, объяснений, глаголов или действий.
canonical_names и facts — справка редактора: разрешают каноническое написание
имён/названий и языковую форму, согласуя падежи. Не расширяй имена до полных.
Не добавляй из справки имена, даты или подробности, которых автор не произносит в исходном блоке.
Проверка одного человека не относится автоматически к другому.
Факты справки не превращай в речь автора. Конфликтующие с ними
даты, числа и утверждения автора сохраняй, не исправляй молча, не добавляй
«автор предполагает». Не вставляй в text ссылки, сноски, фактчек или редакторские
примечания. Даты исправляй только как языковую форму, не меняя значения.
Если нельзя уверенно понять слово, участника или действие, сохрани точную исходную
цитату в text и добавь её в unclear с причиной. Не угадывай по справке или контексту.
unclear.quote должна быть дословной непрерывной цитатой из text исходного блока.
Не объявляй неясную фразу достоверными словами автора. Таймкоды добавит контроллер.
"""


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def seconds(value):
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"(?<!\d)(\d{1,2}:\d{2}(?::\d{2})?)(?!\d)", str(value))
    if not match:
        raise ValueError(f"Не распознан timestamp: {value!r}")
    parts = [int(x) for x in match.group(1).split(":")]
    return sum(n * 60**i for i, n in enumerate(reversed(parts)))


def fact_interval(timestamp):
    if isinstance(timestamp, (int, float)):
        return float(timestamp), float(timestamp)
    matches = re.findall(r"(?<!\d)\d{1,2}:\d{2}(?::\d{2})?(?!\d)", str(timestamp))
    if not matches:
        raise ValueError(f"Не распознан timestamp: {timestamp!r}")
    points = [seconds(value) for value in matches]
    return min(points), max(points)


def fact_overlaps(timestamp, start, end):
    first, last = fact_interval(timestamp)
    if first == last:
        return start <= first < end
    return first < end and last > start


def read_segments(path):
    segments = []
    for line in path.read_text().splitlines():
        match = re.fullmatch(r"\[(\d\d:\d\d:\d\d) → (\d\d:\d\d:\d\d)\] (.+)", line)
        if not match:
            raise ValueError(f"Не распознана строка {len(segments) + 1}: {line!r}")
        start, end, text = match.groups()
        if seconds(end) < seconds(start) or (
            segments and seconds(start) < seconds(segments[-1]["end"])
        ):
            raise ValueError("Обратный или перекрывающийся интервал ASR")
        segments.append({"segment": len(segments) + 1, "start": start, "end": end, "text": text})
    if not segments:
        raise ValueError("Расшифровка пуста")
    return segments


def make_blocks(segments):
    blocks, pos = [], 0
    while pos < len(segments):
        start = seconds(segments[pos]["start"])
        candidates = []
        for j in range(pos, len(segments)):
            duration = seconds(segments[j]["end"]) - start
            if duration > 45:
                break
            if duration >= 25:
                # Законченная фраза важнее точного попадания в 35 секунд.
                penalty = 0 if re.search(r'[.!?…][»"\x27]?$', segments[j]["text"]) else 18
                candidates.append((abs(duration - 35) + penalty, j))
        end = min(candidates)[1] if candidates else len(segments) - 1
        # Последний короткий остаток допустим: не раздуваем предыдущий блок.
        chunk = segments[pos : end + 1]
        blocks.append(
            {
                "id": f"B{len(blocks) + 1:03}",
                "start": chunk[0]["start"],
                "end": chunk[-1]["end"],
                "segment_ids": [s["segment"] for s in chunk],
                "text": " ".join(s["text"] for s in chunk),
            }
        )
        pos = end + 1
    assert [i for b in blocks for i in b["segment_ids"]] == list(range(1, len(segments) + 1))
    return blocks


def load_facts(path):
    if path is None:
        return [], []
    document = json.loads(path.read_text())
    claims = document["claims"]
    if not isinstance(claims, list):
        raise ValueError("facts.claims должен быть массивом")
    curated_names = document.get("canonical_names")
    if curated_names is not None and not isinstance(curated_names, list):
        raise ValueError("facts.canonical_names должен быть массивом")
    names = [] if curated_names is None else curated_names
    for claim in claims:
        fact_interval(claim["timestamp"])
        normalization = claim.get("allowed_normalization")
        if curated_names is None and normalization and normalization not in names:
            names.append(normalization)
    return claims, names


def request_for(blocks, claims, names):
    start, end = seconds(blocks[0]["start"]), seconds(blocks[-1]["end"])
    fields = (
        "id",
        "timestamp",
        "claim_ru",
        "status",
        "finding_ru",
        "editor_action_ru",
        "allowed_normalization",
    )
    facts = [
        {key: c[key] for key in fields if key in c}
        for c in claims
        if fact_overlaps(c["timestamp"], start, end)
    ]
    content = RULES + "\ncanonical_names:\n" + json.dumps(names, ensure_ascii=False)
    content += "\nfacts:\n" + json.dumps(facts, ensure_ascii=False)
    content += "\nblocks:\n" + json.dumps(
        [{k: b[k] for k in ("id", "start", "end", "text")} for b in blocks], ensure_ascii=False
    )
    return {
        "model": MODEL,
        "stream": False,
        "think": False,
        "format": SCHEMA,
        "options": {
            "temperature": 0.2,
            "presence_penalty": 0,
            "repeat_penalty": 1,
            "seed": 42,
            "num_ctx": 16384,
            "num_predict": 6144,
        },
        "messages": [{"role": "user", "content": content}],
    }


def validate(output, inputs):
    if (
        not isinstance(output, dict)
        or set(output) != {"blocks"}
        or not isinstance(output["blocks"], list)
    ):
        raise ValueError("Ожидается объект только с массивом blocks")
    if [b.get("id") if isinstance(b, dict) else None for b in output["blocks"]] != [
        b["id"] for b in inputs
    ]:
        raise ValueError("ID блоков отсутствуют, дублируются или нарушен порядок")
    for block in output["blocks"]:
        if (
            set(block) != {"id", "text", "unclear"}
            or not isinstance(block["text"], str)
            or not block["text"].strip()
        ):
            raise ValueError("Неверные поля или пустой text")
        if not isinstance(block["unclear"], list):
            raise ValueError("unclear должен быть массивом")
        if re.search(r"https?://|\[\^", block["text"]):
            raise ValueError("В text обнаружена ссылка или сноска")
        for item in block["unclear"]:
            if (
                not isinstance(item, dict)
                or set(item) != {"quote", "reason"}
                or any(
                    not isinstance(item[k], str) or not item[k].strip() for k in ("quote", "reason")
                )
            ):
                raise ValueError("Неверная запись unclear")
    return output


def validate_api(raw, inputs):
    if not isinstance(raw, dict) or raw.get("done") is not True or raw.get("done_reason") != "stop":
        raise ValueError("API не подтвердил полное завершение: нужны done=true и done_reason=stop")
    return validate(json.loads(raw["message"]["content"]), inputs)


def annotate(output, inputs):
    result = []
    for edited, source in zip(output["blocks"], inputs, strict=False):
        notes = []
        for item in edited["unclear"]:
            notes.append(
                {
                    **item,
                    "quote_exact_in_source": item["quote"] in source["text"],
                    "quote_present_in_output": item["quote"] in edited["text"],
                    "timestamp_scope": "block_start_not_exact_word",
                }
            )
        result.append(
            {**source, "source_text": source["text"], "text": edited["text"], "unclear": notes}
        )
    return result


def render(blocks, total, output_dir, title):
    lines = [f"# {title}", "", f"Диапазон: {total[0]['start']}–{total[-1]['end']}.", ""]
    for b in blocks:
        lines += [f"## {b['start']}", "", b["text"].strip(), ""]
        for note in b["unclear"]:
            if note["quote_exact_in_source"]:
                lines += [
                    f"> Неясно (блок {b['start']}–{b['end']}): «{note['quote']}». {note['reason']}",
                    "",
                ]
            else:
                lines += [
                    f"> Неясно (блок {b['start']}–{b['end']}): модель сообщила о неясности; "
                    "её цитата не подтверждена исходным блоком. См. metadata.",
                    "",
                ]
    (output_dir / "article.md").write_text("\n".join(lines))


def protect_inputs(output_dir, inputs, group_count):
    """Откажись до записи, если результат затрёт расшифровку или справку."""
    targets = [
        output_dir / name
        for name in ("manifest.json", "article.md", "output-blocks.json", "progress.json")
    ]
    for number in range(1, group_count + 1):
        targets += [
            output_dir / "requests" / f"{number:02}.json",
            output_dir / "responses" / f"{number:02}.json",
        ]
        for attempt in (1, 2):
            targets += [
                output_dir / "requests" / f"{number:02}-attempt-{attempt}.json",
                output_dir / "raw" / f"{number:02}-attempt-{attempt}.json",
            ]
    targets += [path.with_suffix(path.suffix + ".tmp") for path in targets]
    for source in inputs:
        if source is None:
            continue
        for target in targets:
            if source.resolve() == target.resolve() or (
                target.exists() and source.samefile(target)
            ):
                raise ValueError(f"Выходной файл перезапишет вход: {source}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--facts", type=Path)
    parser.add_argument("--title", default="Отредактированная расшифровка")
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    segments = read_segments(args.transcript)
    blocks = make_blocks(segments)
    claims, names = load_facts(args.facts)
    groups = [blocks[i : i + 3] for i in range(0, len(blocks), 3)]
    requests = [request_for(group, claims, names) for group in groups]
    protect_inputs(output_dir, [args.transcript, args.facts], len(groups))
    manifest = {
        "transcript_sha256": digest(segments),
        "facts_sha256": digest(claims),
        "facts_available": args.facts is not None,
        "model": MODEL,
        "segments": len(segments),
        "blocks": blocks,
        "groups": [
            {"number": i, "block_ids": [b["id"] for b in group], "request_sha256": digest(req)}
            for i, (group, req) in enumerate(zip(groups, requests, strict=False), 1)
        ],
    }
    dump(output_dir / "manifest.json", manifest)
    for i, request in enumerate(requests, 1):
        dump(output_dir / "requests" / f"{i:02}.json", request)
    if args.prepare_only:
        print(
            f"Подготовлено: {len(segments)} сегментов, {len(blocks)} блоков, "
            f"{len(groups)} запросов; {blocks[0]['start']}–{blocks[-1]['end']}. "
            "Модель не вызывалась."
        )
        return
    completed, all_output = [], []
    for i, (group, request) in enumerate(zip(groups, requests, strict=False), 1):
        response_path = output_dir / "responses" / f"{i:02}.json"
        saved = json.loads(response_path.read_text()) if response_path.exists() else None
        if (
            saved
            and saved.get("request_sha256") == digest(request)
            and saved.get("raw_done") is True
            and saved.get("raw_done_reason") == "stop"
        ):
            output = validate(saved["output"], group)
        else:
            error = ""
            for attempt in range(2):
                actual_request = json.loads(json.dumps(request))
                if attempt:
                    actual_request["messages"][0]["content"] += (
                        f"\nПредыдущий ответ не прошёл проверку: {error}. "
                        "Верни все блоки строго по JSON-схеме и исходному порядку."
                    )
                dump(output_dir / "requests" / f"{i:02}-attempt-{attempt + 1}.json", actual_request)
                started = time.monotonic()
                req = urllib.request.Request(
                    "http://127.0.0.1:11434/api/chat",
                    data=json.dumps(actual_request).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=1800) as response:
                    raw_bytes = response.read()
                raw_path = output_dir / "raw" / f"{i:02}-attempt-{attempt + 1}.json"
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                raw_path.write_bytes(raw_bytes)
                try:
                    raw = json.loads(raw_bytes)
                    output = validate_api(raw, group)
                    break
                except (ValueError, KeyError, TypeError) as exc:
                    error = str(exc)
                    if attempt:
                        raise RuntimeError(
                            f"Группа {i}: два ответа с ошибкой формата: {error}"
                        ) from exc
            dump(
                response_path,
                {
                    "request_sha256": digest(request),
                    "output": output,
                    "raw_done": raw["done"],
                    "raw_done_reason": raw["done_reason"],
                    "elapsed_seconds": round(time.monotonic() - started, 2),
                    "attempts": attempt + 1,
                },
            )
        all_output.extend(annotate(output, group))
        completed.append(i)
        dump(output_dir / "output-blocks.json", {"blocks": all_output})
        dump(
            output_dir / "progress.json",
            {
                "completed_groups": completed,
                "total_groups": len(groups),
                "request_hashes": [digest(r) for r in requests[:i]],
                "complete": i == len(groups),
                "quality_review": "not_performed",
            },
        )
        render(all_output, blocks, output_dir, args.title)
        print(f"Группа {i}/{len(groups)} сохранена", flush=True)


if __name__ == "__main__":
    main()
