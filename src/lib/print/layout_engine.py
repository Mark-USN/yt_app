"""
Shared line-layout logic for plain-text reports.

This module contains the output-target-independent formatting rules used
by both the printer and PDF backends.

Supported source item types:

- LineItem:
  A single source line that may wrap by words.
- ParagraphItem:
  A list of source lines, each wrapped independently.
- BlocksItem:
  A list of intact block strings packed together onto lines without
  splitting any individual block.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from lib.print.layout_types import (
    BlocksItem,
    LineItem,
    CenteredLineItem,
    PageLayout,
    ParagraphItem,
    RenderItem,
    RenderLine,
    TextMeasurer,
)


def is_long_word(word: str, max_width: float, measurer: TextMeasurer) -> bool:
    """ Determine if a single word exceeds the available width.
        Args:
            word: The word to check.
            max_width: The maximum allowable width.
            measurer: The text measurer to use. 
        Returns:
            True if the word exceeds the max width, False otherwise.
    
    """
    return measurer.measure(word) > max_width


###############################################################################
#
# Although initially created to support splitting long words into lines, if it
# is desired to append the first part of the long word onto the current line,
# just concatenating the the long word to the current line will do this!
#
###############################################################################

def split_long_word(
    text: str,
    max_width: float,
    measurer: TextMeasurer,
) -> list[str]:
    """Split a long string into width-constrained chunks using binary search.
        Args:
            text: The long string to split.
            max_width: The maximum allowable width.
            measurer: The text measurer to use.
        Returns:
            A list of width-constrained chunks.
    """

    result: list[str] = []
    i = 0
    n = len(text)

    while i < n:
        lo = i + 1
        hi = n
        best = lo

        # Binary search for the longest substring that fits
        while lo <= hi:
            mid = (lo + hi) // 2
            chunk = text[i:mid]
            width = measurer.measure(chunk)

            if width <= max_width:
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1

        # Prevent infinite loop (very narrow width case)
        if best == i:
            best = i + 1

        result.append(text[i:best])
        i = best

    return result




def wrap_text_words(
    text: str,
    *,
    measurer: TextMeasurer,
    max_width: float,
    continuation_indent: float,
) -> list[RenderLine]:
    """
    Wrap a logical source line into one or more rendered lines.

    Wrapping is performed at word boundaries. The first rendered line starts
    at the normal left margin. Continuation lines are indented by
    ``continuation_indent``.

    Parameters
    ----------
    text:
        The logical source line to wrap.
    measurer:
        Width measurer for the active backend.
    max_width:
        Maximum usable width from the left margin to the right margin.
    continuation_indent:
        Horizontal offset applied to continuation lines.

    Returns
    -------
    list[RenderLine]
        The wrapped rendered lines.

    Notes
    -----
    If a single word is wider than the available width, it is emitted as-is
    on its own line rather than being split mid-word.
    """
    stripped = text.strip()
    if not stripped:
        return [RenderLine(0.0, "")]

    words = stripped.split()
    lines: list[RenderLine] = []
    current_words: list[str] = []
    current_indent = 0.0

    for word in words:

        word_slices: list[str] = []
        candidate_words = [*current_words, word]
        candidate_text = " ".join(candidate_words)
        candidate_width = current_indent + measurer.measure(candidate_text)

        if is_long_word(word, max_width, measurer):
            word_slices:list[str] = split_long_word(candidate_text, max_width, measurer)
            lines.append(RenderLine(max_width, chunk) for chunk in word_slices[:-2])
            current_words = []
            word = word_slices[-1]
            candidate_words = [word]
            candidate_text = " ".join(candidate_words)
            candidate_width = current_indent + measurer.measure(candidate_text)

        if current_words and candidate_width > max_width:
            lines.append(RenderLine(current_indent, " ".join(current_words)))
            current_words = [word]
            current_indent = continuation_indent
            continue

        current_words = candidate_words

    if current_words:
        lines.append(RenderLine(current_indent, " ".join(current_words)))

    return lines


def wrap_centered_text(
    text: str,
    *,
    measurer: TextMeasurer,
    max_width: float,
    # continuation_indent: float,
) -> list[RenderLine]:
    """
    Wrap a logical source line into one or more rendered lines.

    Wrapping is performed at word boundaries. The first rendered line starts
    at the normal left margin. Continuation lines are indented by
    ``continuation_indent``.

    Parameters
    ----------
    text:
        The logical source line to wrap and center.
    measurer:
        Width measurer for the active backend.
    max_width:
        Maximum usable width from the left margin to the right margin.
    # continuation_indent:
    #     Horizontal offset applied to continuation lines.

    Returns
    -------
    list[RenderLine]
        The wrapped rendered lines.

    Notes
    -----
    If a single word is wider than the available width, it is emitted as-is
    on its own line rather than being split mid-word.
    """
    stripped = text.strip()
    if not stripped:
        return [RenderLine(0.0, "")]

    words = stripped.split()
    lines: list[RenderLine] = []
    current_words: list[str] = []
    total_width = measurer.measure(text)
    total_lines = math.ceil(total_width / max_width)
    avg_line_width = total_width / total_lines
    max_line_width = min(max_width, avg_line_width * 1.25)  # Allow some variance in line widths

    for word in words:
        word_slices: list[str] = []
        candidate_words = [*current_words, word]
        candidate_text = " ".join(candidate_words)
        if is_long_word(word, max_line_width, measurer):
            word_slices = split_long_word(candidate_text, max_line_width, measurer)
            lines.extend(RenderLine(
                (max_width - measurer.measure(slice)) / 2, slice) for slice in word_slices[:-2])
            current_words = []
            word = word_slices[-1]
            candidate_words = [word]
            candidate_text = " ".join(candidate_words)

        # candidate_width = current_indent + measurer.measure(candidate_text)
        candidate_width = measurer.measure(candidate_text)

        if current_words and candidate_width > max_line_width:
            indent = (max_width - measurer.measure(" ".join(current_words))) / 2
            lines.append(RenderLine(indent, " ".join(current_words)))
            current_words = [word]
            # current_indent = continuation_indent
            continue

        current_words = candidate_words

    if current_words:
        current_text = " ".join(current_words)
        indent = (max_width - measurer.measure(current_text)) / 2
        lines.append(RenderLine(indent, current_text))

    return lines


def blocks_to_lines(
    blocks: list[str],
    *,
    measurer: TextMeasurer,
    max_width: float,
    separator: str,
) -> list[RenderLine]:
    """
    Pack intact block strings onto rendered lines.

    Each block remains whole. Blocks are combined with ``separator`` until
    adding the next block would exceed ``max_width``. A new rendered line is
    then started.

    Parameters
    ----------
    blocks:
        The intact block strings to pack.
    measurer:
        Width measurer for the active backend.
    max_width:
        Maximum usable width from the left margin to the right margin.
    separator:
        String inserted between adjacent blocks on the same output line.

    Returns
    -------
    list[RenderLine]
        The packed output lines.

    Notes
    -----
    If a single block exceeds the available width by itself, it is emitted
    on a line of its own rather than being split.
    """
    if not blocks:
        return []

    lines: list[RenderLine] = []
    current = blocks[0]

    for block in blocks[1:]:
        candidate = f"{current}{separator}{block}"
        if measurer.measure(candidate) <= max_width:
            current = candidate
        else:
            lines.append(RenderLine(0.0, current))
            current = block

    lines.append(RenderLine(0.0, current))
    return lines


def expand_items_to_lines(
    items: Iterable[RenderItem],
    *,
    measurer: TextMeasurer,
    layout: PageLayout,
) -> list[RenderLine]:
    """
    Convert mixed input items into fully laid-out rendered lines.

    Parameters
    ----------
    items:
        The mixed content items to format.
    measurer:
        Width measurer for the active backend.
    layout:
        Page layout containing usable width, indent, and separator settings.

    Returns
    -------
    list[RenderLine]
        Fully laid-out rendered lines in output order.
    """
    output: list[RenderLine] = []
    max_width = layout.usable_width

    for item in items:
        if isinstance(item, LineItem):
            output.extend(
                wrap_text_words(
                    item.text,
                    measurer=measurer,
                    max_width=max_width,
                    continuation_indent=layout.wrap_indent,
                )
            )
        elif isinstance(item, CenteredLineItem):
            output.extend(
                wrap_centered_text(
                    item.text,
                    measurer=measurer,
                    max_width=max_width,
                )
            )
        elif isinstance(item, ParagraphItem):
            for line in item.lines:
                output.extend(
                    wrap_text_words(
                        line,
                        measurer=measurer,
                        max_width=max_width,
                        continuation_indent=layout.wrap_indent,
                    )
                )
        elif isinstance(item, BlocksItem):
            output.extend(
                blocks_to_lines(
                    item.blocks,
                    measurer=measurer,
                    max_width=max_width,
                    separator=layout.block_separator,
                )
            )
        else:
            msg = f"Unsupported render item type: {type(item).__name__}"
            raise TypeError(msg)

    return output
