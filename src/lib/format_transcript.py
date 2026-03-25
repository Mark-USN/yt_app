""" Utilities for formatting YouTube transcript data.
    Rather than calling youtube transcript functions repeatedly to deliver
    different formats, we can call once getting the json formatted transcript 
    and then format the data as needed.
    """
from __future__ import annotations

import re
# from dataclasses import dataclass
# from pathlib import Path
from typing import Sequence
from yt_lib.yt_transcript import TranscriptSnippet
from yt_lib.utils.log_utils import get_logger
# from lib.app_context import RunContextStore

logger = get_logger(__name__)


_SENTENCE_PATTERN: re.Pattern[str] = re.compile(
    r'(.+?(?<!\b[A-Z]\.)(?<!\b[A-Z][a-z]\.)[.!?…]+["\')\]]*)(?=\s|$)'
)

def split_sentences(text: str) -> tuple[list[str], str]:
    out: list[str] = []
    last_end = 0

    for m in _SENTENCE_PATTERN.finditer(text):
        out.append(m.group(1).strip())
        last_end = m.end()

    remainder = text[last_end:].strip()
    return out, remainder



def json_to_sentences(transcript_list: Sequence["TranscriptSnippet"]) -> str:

    sentences: list[str] = []

    prev_end = ""

    for snip in transcript_list:
        part = str(snip.get("text", "")).strip()
        if not part:
            continue

        chunk = f"{prev_end} {part}" if prev_end else part

        sentence_list, prev_end = split_sentences(chunk)
        sentences.extend(sentence_list)

    if prev_end:
        sentences.append(prev_end)

    return "\n".join(sentences)

def json_to_text(transcript_list: Sequence["TranscriptSnippet"]) -> str:

    sentences: list[str] = []

    for snip in transcript_list:
        txt = str(snip.get("text", "")).strip()
        if not txt:
            continue

        sentences.append(txt)

    return "\n".join(sentences)

def convert_json(transcript_list: Sequence["TranscriptSnippet"])->str:
    snippets: list[str] = []

    for entry in transcript_list:
        snippets.append(f"{{text: {entry['text']}, start={entry['start']}"
                        f", duration={entry['duration']}}},")
    return "\n".join(snippets)
