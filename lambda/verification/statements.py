from __future__ import annotations

import re

_ABBREVIATIONS = frozenset(
    {
        "dr", "drs", "mr", "mrs", "ms", "prof", "st", "jr", "sr",
        "approx", "est", "vs", "etc", "eg", "ie", "dept", "min", "hr",
        "wk", "mo", "yr", "mg", "ml", "kg", "lb", "oz", "am", "pm", "a.m",
        "p.m", "bid", "tid", "prn", "hx", "dx", "rx", "fig", "ref", "pt",
        "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept",
        "oct", "nov", "dec",
    }
)

_CANDIDATE = re.compile(r'[.!?]+["\'’”)\]]*(?=\s)')

_WORD_BEFORE = re.compile(r"([A-Za-z]+)\.$")


def _is_sentence_end(text, match):
    """Decide whether a candidate boundary actually ends a sentence."""
    following = text[match.end() :].lstrip()
    if not following:
        return True

    if not (following[0].isupper() or following[0].isdigit() or following[0] in "\"'“"):
        return False

    fragment = match.group(0)
    if fragment != ".":
        return True

    word = _WORD_BEFORE.search(text[: match.end()])
    if word is None:
        return True

    token = word.group(1)
    if len(token) == 1 and token.isupper():
        return False
    return token.lower() not in _ABBREVIATIONS


def _split_block(block) -> list[str]:
    """Split one line of text into sentences."""
    sentences = []
    start = 0
    for match in _CANDIDATE.finditer(block):
        if not _is_sentence_end(block, match):
            continue
        sentence = block[start : match.end()].strip()
        if sentence:
            sentences.append(sentence)
        start = match.end()

    tail = block[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def split_statements(summary) -> list[dict]:
    """The summary split at sentence ends and line breaks, as ordered index and text dicts."""
    if not summary or not summary.strip():
        return []

    sentences = []
    for line in summary.splitlines():
        sentences.extend(_split_block(line))

    numbered = []
    for index, text in enumerate(sentences):
        numbered.append({"index": index, "text": text})
    return numbered
