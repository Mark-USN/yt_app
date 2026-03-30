""" Utilities for formatting YouTube transcript data.
    Rather than calling youtube transcript functions repeatedly to deliver
    different formats, we can call once getting the json formatted transcript 
    and then format the data as needed.
    """
from __future__ import annotations

import re
from typing import Sequence
from yt_lib.yt_transcript import TranscriptSnippet
from yt_lib.utils.log_utils import get_logger

logger = get_logger(__name__)


_SENTENCE_PATTERN: re.Pattern[str] = re.compile(
    r'(.+?(?<!\b[A-Z]\.)(?<!\b[A-Z][a-z]\.)[.!?…]+["\')\]]*)(?=\s|$)'
)

def split_sentences(text: str) -> tuple[list[str], str]:
    """ Splits the input text into sentences based on punctuation marks. 
        Args:
            text: The input text to split into sentences.
        Returns:
            A tuple containing a list of sentences and any remaining text that
            did not match the sentence pattern.
    """
    out: list[str] = []
    last_end = 0

    for m in _SENTENCE_PATTERN.finditer(text):
        out.append(m.group(1).strip())
        last_end = m.end()

    remainder = text[last_end:].strip()
    return out, remainder



def json_to_sentences(transcript_list: Sequence["TranscriptSnippet"]) -> str:
    """ Converts a list of transcript snippets into a formatted string of sentences. 
        Args:
            transcript_list: A list of transcript snippets, where each snippet is a dictionary
                                containing a "text" field.
        Returns:
            A formatted string of sentences.
        Note:
            This function processes each transcript snippet, concatenating the text and splitting
            it into sentences based on punctuation marks. It handles cases where sentences may 
            span across multiple snippets, ensuring that the output is a coherent sequence of
            sentences.  It is only as good as the transcript's punctuation, and can take a long
            time if the punctuation is sparce. So it may not always produce perfect results.
    """

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
    """ Converts a list of transcript snippets into a single string of text.
        Args:
            transcript_list: A list of transcript snippets, where each snippet is a dictionary
                                containing a "text" field.
        Returns:
            A single string of text concatenated from all the transcript snippets.  With each
            line containing the text from one snippet.  This is a simpler format than
            json_to_sentences, and is faster to produce.
    """

    sentences: list[str] = []

    for snip in transcript_list:
        txt = str(snip.get("text", "")).strip()
        if not txt:
            continue

        sentences.append(txt)

    return "\n".join(sentences)

def convert_json(transcript_list: Sequence["TranscriptSnippet"])->str:
    """ Converts a list of transcript snippets into a formatted string representation
        of the original JSON structure with text, start time and duration.
        Args:
            transcript_list: A list of transcript snippets, where each snippet is a dictionary
                                containing "text", "start", and "duration" fields.
        Returns:
            A formatted string representation of the transcript snippets, preserving
            the original JSON structure with text, start time, and duration.
    """
    snippets: list[str] = []

    for entry in transcript_list:
        snippets.append(f"{{text: {entry['text']}, start={entry['start']}"
                        f", duration={entry['duration']}}},")
    return "\n".join(snippets)
