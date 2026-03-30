"""
Windows printer backend for plain-text report rendering.

This module renders shared layout-engine output to a Windows printer using
pywin32 device contexts.

Library notes
-------------
The CDC methods used here follow the documented pywin32 API surface for
printer device contexts, including CreatePrinterDC, GetTextExtent,
TextOut, GetDeviceCaps, StartDoc, StartPage, EndPage, EndDoc, and
DeleteDC. Device capabilities are queried using Win32 constants such as
HORZRES, VERTRES, and LOGPIXELSY. :contentReference[oaicite:1]{index=1}
"""

from __future__ import annotations

from typing import Protocol, TYPE_CHECKING
import win32gui     # pylint: disable=import-error
import win32con     # pylint: disable=import-error
import win32ui      # pylint: disable=import-error

from lib.print.layout_engine import expand_items_to_lines
from lib.print.layout_types import PageLayout, RenderItem, RenderLine, TextDrawer
if TYPE_CHECKING:
    from lib.print.layout_types import TextMeasurer

# pylint: disable=too-few-public-methods, invalid-name
class PrinterDC(Protocol):
    """Structural type describing the subset of pywin32 CDC methods used here."""

    def GetTextExtent(self, text: str) -> tuple[int, int]:
        """Return text extent as ``(width, height)`` in device units."""

    def TextOut(self, x: int, y: int, text: str) -> None:
        """Draw text at ``(x, y)``."""

    def GetDeviceCaps(self, index: int) -> int:
        """Return a device capability value."""

    def StartDoc(self, doc_name: str) -> None:
        """Start a document."""

    def StartPage(self) -> None:
        """Start a page."""

    def EndPage(self) -> None:
        """Finish the current page."""

    def EndDoc(self) -> None:
        """Finish the current document."""

    def DeleteDC(self) -> None:
        """Release the device context."""

    def CreatePrinterDC(self, printer_name: str) -> None:
        """Bind the DC to the named printer."""

    def SelectObject(self, obj: object) -> object | None:
        """Select a GDI object into the DC and return the previous object."""

# pylint: disable=too-few-public-methods
class PrinterMeasurer:
    """Measure text widths in printer device units."""

    def __init__(self, dc: PrinterDC) -> None:
        """
        Initialize the measurer.

        Parameters
        ----------
        dc:
            A printer device context.
        """
        self._dc = dc

    def measure(self, text: str) -> float:
        """
        Return the rendered width of *text* in printer device units.

        Parameters
        ----------
        text:
            The text to measure.

        Returns
        -------
        float
            The width in device units, typically pixels.
        """
        width, _height = self._dc.GetTextExtent(text)
        return float(width)

# pylint: disable=too-few-public-methods
class PrinterDrawer:
    """Draw text to a printer device context."""

    def __init__(self, dc: PrinterDC) -> None:
        """
        Initialize the drawer.

        Parameters
        ----------
        dc:
            A printer device context.
        """
        self._dc = dc

    def draw_text(self, x: float, y: float, text: str) -> None:
        """
        Draw *text* at ``(x, y)``.

        Parameters
        ----------
        x:
            Horizontal position in device units.
        y:
            Vertical position in device units.
        text:
            The text to draw.
        """
        self._dc.TextOut(int(round(x)), int(round(y)), text)


def create_printer_font(
    dc: PrinterDC,
    *,
    face_name: str,
    point_size: float,
    weight: int = win32con.FW_NORMAL,       # pylint: disable=c-extension-no-member
) -> object:
    """
    Create a printer font sized for the target device context.

    Parameters
    ----------
    dc:
        The printer device context.
    face_name:
        The font face name, such as ``"Arial"``.
    point_size:
        The requested font size in typographic points.
    weight:
        The Win32 font weight, defaulting to ``FW_NORMAL``.

    Returns
    -------
    object
        A pywin32 font object suitable for ``dc.SelectObject(...)``.

    Notes
    -----
    Win32 font heights are commonly specified in logical units. A negative
    height requests a character height corresponding to the given point size.
    """
    dpi_y = dc.GetDeviceCaps(win32con.LOGPIXELSY)   # pylint: disable=c-extension-no-member
    height = -round(point_size * dpi_y / 72.0)

    # pylint: disable=c-extension-no-member
    return win32ui.CreateFont(
        {
            "name": face_name,
            "height": height,
            "weight": weight,
        }
    )


def get_printer_layout(
    dc: PrinterDC,
    *,
    point_size: float,
    margin_inches: float = 0.5,
    line_spacing: float = 1.25,
    wrap_indent_inches: float = 0.25,
) -> PageLayout:
    """
    Build a page layout for the active printer.

    Parameters
    ----------
    dc:
        The printer device context.
    point_size:
        The font size in points used for line-height estimation.
    margin_inches:
        Margin size in inches on all sides.
    line_spacing:
        Multiplier applied to the nominal font height.
    wrap_indent_inches:
        Indentation used for continuation lines, in inches.

    Returns
    -------
    PageLayout
        The computed printer page layout.
    """
    page_width = float(dc.GetDeviceCaps(win32con.HORZRES))  # pylint: disable=c-extension-no-member
    page_height = float(dc.GetDeviceCaps(win32con.VERTRES)) # pylint: disable=c-extension-no-member
    dpi_y = float(dc.GetDeviceCaps(win32con.LOGPIXELSY))    # pylint: disable=c-extension-no-member
    dpi_x = float(dc.GetDeviceCaps(win32con.LOGPIXELSX))    # pylint: disable=c-extension-no-member

    left_right_margin = margin_inches * dpi_x
    top_bottom_margin = margin_inches * dpi_y
    line_height = (point_size * dpi_y / 72.0) * line_spacing
    wrap_indent = wrap_indent_inches * dpi_x

    return PageLayout(
        page_width=page_width,
        page_height=page_height,
        left_margin=left_right_margin,
        right_margin=left_right_margin,
        top_y=top_bottom_margin,
        bottom_limit=page_height - top_bottom_margin,
        line_height=line_height,
        wrap_indent=wrap_indent,
    )


def _paginate_printer_lines(
    lines: list[RenderLine],
    *,
    layout: PageLayout,
) -> list[list[RenderLine]]:
    """
    Split rendered lines into printer pages.

    Parameters
    ----------
    lines:
        The fully laid-out lines to paginate.
    layout:
        The page layout.

    Returns
    -------
    list[list[RenderLine]]
        A list of pages, where each page is a list of rendered lines.
    """
    pages: list[list[RenderLine]] = []
    current_page: list[RenderLine] = []
    y = layout.top_y

    for line in lines:
        if current_page and y > layout.bottom_limit:
            pages.append(current_page)
            current_page = []
            y = layout.top_y

        current_page.append(line)
        y += layout.line_height

    if current_page or not pages:
        pages.append(current_page)

    return pages


def _render_printer_page(
    lines: list[RenderLine],
    *,
    drawer: TextDrawer,
    layout: PageLayout,
) -> None:
    """
    Render one page of lines to the printer.

    Parameters
    ----------
    lines:
        The page's rendered lines.
    drawer:
        The text drawer.
    layout:
        The page layout.
    """
    y = layout.top_y
    for line in lines:
        x = layout.left_margin + line.x_offset
        drawer.draw_text(x, y, line.text)
        y += layout.line_height


def print_items(
    printer_name: str,
    items: list[RenderItem],
    *,
    document_name: str = "Report",
    face_name: str = "Arial",
    point_size: float = 10.0,
) -> None:
    """
    Render mixed content items to a Windows printer.

    Parameters
    ----------
    printer_name:
        Name of the target printer.
    items:
        Mixed layout items to render.
    document_name:
        Document title shown to the print subsystem.
    face_name:
        Requested font face name.
    point_size:
        Requested font size in points.
    """
    dc = win32ui.CreateDC()             # pylint: disable=c-extension-no-member
    dc.CreatePrinterDC(printer_name)

    font = create_printer_font(dc, face_name=face_name, point_size=point_size)
    old_font = dc.SelectObject(font)

    try:
        measurer = PrinterMeasurer(dc)
        drawer = PrinterDrawer(dc)
        layout = get_printer_layout(dc, point_size=point_size)

        lines = expand_items_to_lines(items, measurer=measurer, layout=layout)
        pages = _paginate_printer_lines(lines, layout=layout)

        dc.StartDoc(document_name)
        for page in pages:
            dc.StartPage()
            _render_printer_page(page, drawer=drawer, layout=layout)
            dc.EndPage()
        dc.EndDoc()
    finally:
        if old_font is not None:
            dc.SelectObject(old_font)
        dc.DeleteDC()


def list_fonts(dc: win32ui.CDC) -> set[str]:  # pylint: disable=c-extension-no-member
    """Return a set of available font names for the given device context."""

    fonts: set[str] = set()

    def callback(logfont, _textmetric, _fonttype, _param):
        fonts.add(logfont.lfFaceName)
        return True

    lf = win32gui.LOGFONT()  # pylint: disable=c-extension-no-member
    lf.lfCharSet = win32con.DEFAULT_CHARSET  # pylint: disable=c-extension-no-member

    win32gui.EnumFontFamiliesEx(dc.GetHandleOutput(), lf, callback, None)  # pylint: disable=c-extension-no-member
    return fonts
