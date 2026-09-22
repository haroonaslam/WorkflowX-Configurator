"""Parse line-based cloning scripts without loading the inference stack."""

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path


CATALOG = json.loads((Path(__file__).resolve().parents[2] / "web" / "js" / "auk" / "tags.json").read_text(encoding="utf-8"))
STYLES = {item["tag"].casefold(): item["instruction"] for item in CATALOG["styles"]}
CONVERSIONS = {item["tag"]: item for item in CATALOG["conversions"]}
NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")
TAG = re.compile(r"\[([^\[\]\r\n]+)\]")
DURATION = re.compile(r"\(\s*((?:\d+(?:\.\d*)?|\.\d+))\s*s\s*\)\s*$", re.IGNORECASE)
WORDS = re.compile(r"[^\W_]+(?:['’\-‐‑][^\W_]+)*", re.UNICODE)
SPEAKER = re.compile(r"@voice([12])(?=\s|\[|$)", re.IGNORECASE)


@dataclass(frozen=True)
class Conversion:
    tag: str
    value: str | float | None
    instruction: str
    duration: str
    preprocess: str | None
    unchanged: bool


def parse_conversion(tag, line):
    name, separator, value = tag.partition(":")
    name = name.strip().casefold()
    item = CONVERSIONS.get(name)
    if item is None:
        raise ValueError(f"Line {line}: unknown conversion [{tag}]. Choose a change from Add conversion.")
    value = value.strip()
    parameter = item.get("parameter")
    if parameter:
        if not separator or not value:
            raise ValueError(f"Line {line}: [{name}] needs a value after ':'.")
        if parameter == "number":
            if name == "c-volume" and value.casefold().endswith("db"):
                value = value[:-2].strip()
            if not NUMBER.fullmatch(value):
                raise ValueError(f"Line {line}: [{tag}] needs a finite decimal number.")
            value = float(value)
            if not math.isfinite(value) or (name == "c-speed" and value <= 0):
                raise ValueError(f"Line {line}: [{tag}] needs a finite number" + (" greater than zero." if name == "c-speed" else "."))
    elif separator:
        raise ValueError(f"Line {line}: [{name}] does not take a value.")
    else:
        value = None
    numeric = isinstance(value, float)
    direction = ("Raise" if value > 0 else "Lower") if numeric and name == "c-pitch" else ("Increase" if numeric and value > 0 else "Decrease")
    instruction = item["instruction"].format(
        value=format(value, ".15g") if numeric else value,
        quoted=json.dumps(value, ensure_ascii=False), direction=direction,
        magnitude=format(abs(value), ".15g") if numeric else "",
    )
    return Conversion(name, value, instruction, item["duration"], item.get("preprocess"), numeric and value == item.get("neutral"))


@dataclass(frozen=True)
class Segment:
    line: int
    text: str
    tags: tuple[str, ...]
    seconds: float
    explicit: bool
    instruction: str
    conversions: tuple[Conversion, ...]
    voice: int = 1
    voice_explicit: bool = False
    pieces: tuple = ()


def parse_script(script, words_per_second, multi_speaker=False, inline_edits=False):
    if not math.isfinite(words_per_second) or words_per_second <= 0:
        raise ValueError("Words per second must be a finite number greater than zero.")
    segments = []
    previous_voice = 1
    for line_number, raw in enumerate(script.splitlines(), 1):
        text = raw.strip()
        if not text:
            continue
        speaker = SPEAKER.match(text)
        if text.startswith("@") and speaker is None:
            raise ValueError(f"Line {line_number}: use @voice1 or @voice2 before the tags.")
        if speaker:
            previous_voice = int(speaker[1])
            text = text[speaker.end():].lstrip()
        tags = []
        while text.startswith("["):
            match = TAG.match(text)
            if match is None or not match[1].strip():
                raise ValueError(f"Line {line_number}: malformed or empty leading tag.")
            if match[1].strip().startswith("@"):
                raise ValueError(f"Line {line_number}: put one speaker selector before the tags, without brackets.")
            tags.append(match[1].strip())
            text = text[match.end():].lstrip()
        if text.startswith("@"):
            raise ValueError(f"Line {line_number}: put only one speaker selector at the start, before the tags.")
        if text.startswith("]"):
            raise ValueError(f"Line {line_number}: unmatched closing tag bracket.")
        raw_inline = text
        text = INLINE_MARKER.sub("", text)
        duration = DURATION.search(text)
        if duration:
            seconds = float(duration[1])
            text = text[:duration.start()].rstrip()
        else:
            # Ordinary trailing parenthetical dialogue remains spoken text. A
            # numeric or seconds-marked suffix is reserved for timing notation.
            suffix = re.search(r"\(([^()]*)\)?\s*$", text)
            if suffix:
                value = suffix[1].rstrip(")").strip()
                if re.match(r"^[+\-\d.]", value) or re.search(r"(?:\d\s*(?:s|sec|seconds?)|\bs|\bseconds?)$", value, re.I) or value.casefold() in {"nans", "infs", "infinitys"}:
                    raise ValueError(f"Line {line_number}: invalid duration; use a positive value such as (2.5s).")
            seconds = len(WORDS.findall(text)) / words_per_second
        if not text or not WORDS.search(text):
            raise ValueError(f"Line {line_number}: spoken text is required.")
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError(f"Line {line_number}: duration must be finite and greater than zero.")
        styles = []
        conversions = []
        for tag in tags:
            if tag.casefold().startswith("c-"):
                conversions.append(parse_conversion(tag, line_number))
            else:
                styles.append(tag)
                if len(styles) > 1:
                    raise ValueError(f"Line {line_number}: use only one voice style. Keep one ordinary tag and use c- conversions for additional changes (for example [Shy][c-whisper]).")
                if conversions:
                    raise ValueError(f"Line {line_number}: put the voice style before the c- conversions.")
        if styles:
            style = STYLES.get(styles[0].casefold(), f"in a {styles[0]} tone")
            instruction = f"Say the following {style} using the same voice: {json.dumps(text, ensure_ascii=False)}."
        else:
            instruction = f"Say the following with the same voice: {json.dumps(text, ensure_ascii=False)}."
        pieces = parse_inline(raw_inline, line_number, seconds, words_per_second, duration is not None) if inline_edits else ()
        segments.append(Segment(line_number, text, tuple(tags), seconds, duration is not None, instruction, tuple(conversions), previous_voice if multi_speaker else 1, speaker is not None, pieces))
    if not segments:
        raise ValueError("Enter at least one line of spoken text.")
    return segments


# Tag-shaped markers only: comparisons such as < 3 and > remain dialogue.
INLINE_MARKER = re.compile(r"</?[A-Za-z][A-Za-z0-9_-]*(?:[ ]+[A-Za-z][A-Za-z0-9_-]*)*(?::[^<>\r\n]*)?>")


@dataclass(frozen=True)
class Piece:
    text: str
    seconds: float
    change: Conversion | None


def inline_conversion(tag, line):
    name, separator, value = tag.partition(":")
    name = name.casefold()
    canonical = CATALOG["inline_aliases"].get(name, name)
    if canonical in CONVERSIONS:
        return parse_conversion(canonical + (":" + value if separator else ""), line)
    item = next((item for item in CATALOG["styles"] if item["tag"].casefold() == name), None)
    if item and not separator:
        if name == "whispers":
            return parse_conversion("c-whisper", line)
        return Conversion(name, None, item["edit_instruction"], "same", None, False)
    raise ValueError(f"Line {line}: unknown inline edit <{tag}>. Choose an Inline edit.")


def parse_inline(raw, line, seconds, rate, explicit):
    raw = DURATION.sub("", raw).rstrip()
    stripped = INLINE_MARKER.sub("", raw)
    known = sorted(set(CATALOG["inline_aliases"]) | set(CONVERSIONS) | set(STYLES), key=len, reverse=True)
    if re.search(r"</?(?:" + "|".join(re.escape(name) for name in known) + r")(?=[:\s/>]|$)", stripped, re.I):
        raise ValueError(f"Line {line}: incomplete inline marker; use matching <tag>words</tag> markers.")
    matches = list(INLINE_MARKER.finditer(raw))
    if not matches:
        return ()
    chunks = []
    opening = None
    last = 0
    for match in matches:
        closing = match[0].startswith("</")
        tag = match[0][2 if closing else 1:-1]
        if closing:
            if opening is None or tag.casefold() != opening[0].partition(":")[0].casefold():
                raise ValueError(f"Line {line}: mismatched inline closing tag {match[0]}.")
            body = raw[last:match.start()]
            if not WORDS.search(body):
                raise ValueError(f"Line {line}: inline edit <{opening[0]}> needs spoken words.")
            chunks.append([body, opening[1]])
            opening = None
        else:
            if opening is not None:
                raise ValueError(f"Line {line}: inline edits cannot be nested.")
            if match.start() > last:
                chunks.append([raw[last:match.start()], None])
            opening = (tag, inline_conversion(tag, line))
        last = match.end()
    if opening is not None:
        raise ValueError(f"Line {line}: close <{opening[0]}> before the line ends.")
    if last < len(raw):
        chunks.append([raw[last:], None])
    # Keep punctuation with neighbouring speech, never generate punctuation alone.
    speech = []
    pending = ""
    for text, change in chunks:
        if not WORDS.search(text):
            if speech:
                speech[-1][0] += text
            else:
                pending += text
        else:
            speech.append([pending + text, change]); pending = ""
    total = sum(len(WORDS.findall(text)) for text, _ in speech)
    return tuple(Piece(text, seconds * len(WORDS.findall(text)) / total if explicit else len(WORDS.findall(text)) / rate, change) for text, change in speech)
