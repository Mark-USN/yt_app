""" Common layout types and protocols for plain-text report rendering.

    This module is intentionally independent of any specific output target.
    The shared layout engine works with these abstractions and can then be
    reused for printer output, PDF output, or other text-capable backends.

    Coordinate units are target-specific:

    - Printer backends typically use device pixels.
    - PDF backends typically use points.

    The important rule is that a measurer and drawer used together must
    agree on the same units.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


# pylint: disable=too-few-public-methods
class TextMeasurer(Protocol):
    """ Measure the rendered width of text in backend-specific units."""

    def measure(self, text: str) -> float:
        """ Return the width of *text* in the units used by the active backend.
            Args:
                text: The text to measure.
            Returns:
                The rendered width of the text. 
        """

# pylint: disable=too-few-public-methods
class TextDrawer(Protocol):
    """ Draw text at a given position using backend-specific coordinates."""

    def draw_text(self, x: float, y: float, text: str) -> None:
        """ Draw *text* at the position ``(x, y)``.
            Args:
                x: Horizontal position in backend-specific units.
                y: Vertical position in backend-specific units.
                text: The text to render.
        """


@dataclass(slots=True, frozen=True)
class PageLayout:
    """ Describes page geometry and line spacing for a rendering target.

        Notes
        -----
        ``top_y`` is the first baseline at which text should be drawn.
        ``bottom_limit`` is the cutoff beyond which no further lines should be
        drawn on the current page.

        For a printer backend, lines usually move downward by increasing ``y``.
        For a PDF backend, lines usually move downward by decreasing ``y``.
    """

    page_width: float
    page_height: float
    left_margin: float
    right_margin: float
    top_y: float
    bottom_limit: float
    line_height: float
    wrap_indent: float
    block_separator: str = "   "

    @property
    def usable_width(self) -> float:
        """ Return the horizontal width available for text content.
            Returns:
                The horizontal width available for text content, in the units used
        """
        return self.page_width - self.left_margin - self.right_margin


@dataclass(slots=True, frozen=True)
class RenderLine:
    """ A single fully-laid-out line ready to render."""

    x_offset: float
    text: str


@dataclass(slots=True, frozen=True)
class LineItem:
    """ A single logical source line.

        This item may wrap onto multiple rendered lines if it exceeds the
        available width.
    """

    text: str

@dataclass(slots=True, frozen=True)
class CenteredLineItem:
    """ A single logical source line to be centered in the output.

        This item may wrap onto multiple rendered lines if it exceeds the
        available width.
    """

    text: str



@dataclass(slots=True, frozen=True)
class ParagraphItem:
    """ A list of logical source lines.

        Each source line is wrapped independently.
    """

    lines: list[str]


@dataclass(slots=True, frozen=True)
class BlocksItem:
    """ A sequence of already-formed block strings.

        Each block remains intact and is never split across lines. Blocks are
        packed onto output lines until the next block would overflow the
        available width.
    """

    blocks: list[str]


type RenderItem = LineItem | CenteredLineItem | ParagraphItem | BlocksItem
