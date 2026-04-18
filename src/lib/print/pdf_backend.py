""" ReportLab PDF backend for plain-text report rendering.

    This module renders shared layout-engine output to a PDF file using
    ReportLab.

    Library notes
    -------------
    ReportLab's canvas supports drawing text with ``drawString``, and text
    width can be measured with ``pdfmetrics.stringWidth``. Those are the APIs
    used here. :contentReference[oaicite:2]{index=2}
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from lib.print.layout_engine import expand_items_to_lines
from lib.print.layout_types import PageLayout, RenderItem, RenderLine, TextDrawer


PDF_FONT_NAMES: list[str] = [
    "Courier",
    "Courier-Bold",
    "Courier-BoldOblique",
    "Courier-Oblique",
    "Helvetica",
    "Helvetica-Bold",
    "Helvetica-BoldOblique",
    "Helvetica-Oblique",
    "Symbol",
    "Times-Bold",
    "Times-BoldItalic",
    "Times-Italic",
    "Times-Roman",
    "ZapfDingbats",
]

# pylint: disable=too-few-public-methods
class PdfMeasurer:
    """ Measure text widths in PDF points."""

    def __init__(self, font_name: str, font_size: float) -> None:
        """ Initialize the measurer.
            Args:
                font_name: ReportLab font name.
                font_size: Font size in points.
        """
        self._font_name = font_name
        self._font_size = font_size

    def measure(self, text: str) -> float:
        """ Return the rendered width of *text* in points.
            Args:
                text: The text to measure.
            Returns:
                The width in PDF points.
        """
        return float(stringWidth(text, self._font_name, self._font_size))


# pylint: disable=too-few-public-methods
class PdfDrawer:
    """ Draw text to a ReportLab canvas."""

    def __init__(self, canvas: Canvas) -> None:
        """ Initialize the drawer.
            Args:
                canvas: The ReportLab canvas used for drawing.
        """
        self._canvas = canvas

    def draw_text(self, x: float, y: float, text: str) -> None:
        """ Draw *text* at ``(x, y)``.
            Args:
                x: Horizontal position in points.
                y: Vertical position in points.
                text: The text to draw.
        """
        self._canvas.drawString(x, y, text)

def get_pdf_layout(
    *,
    page_width: float,
    page_height: float,
    font_size: float,
    margin_points: float = 36.0,
    line_spacing: float = 1.25,
    wrap_indent_points: float = 18.0,
) -> PageLayout:
    """ Build a page layout for PDF output.
        Args:
            page_width: Page width in points.
            page_height: Page height in points.
            font_size: The active font size in points.
            margin_points: Margin size in points on all sides.
            line_spacing: Multiplier applied to the font size for line spacing.
            wrap_indent_points: Indentation used for continuation lines, in points.
        Returns:
            PageLayout: The computed PDF page layout.

        Notes
        -----
        ReportLab uses a bottom-left origin. To move downward on the page,
        subsequent lines use decreasing ``y`` values.
    """
    return PageLayout(
        page_width=page_width,
        page_height=page_height,
        left_margin=margin_points,
        right_margin=margin_points,
        top_y=page_height - margin_points,
        bottom_limit=margin_points,
        line_height=font_size * line_spacing,
        wrap_indent=wrap_indent_points,
    )


def _paginate_pdf_lines(
    lines: list[RenderLine],
    *,
    layout: PageLayout,
) -> list[list[RenderLine]]:
    """ Split rendered lines into PDF pages.
        Args:
            lines: The rendered lines to paginate.
            layout: The page layout used for pagination.
        Returns:
            A list of pages, where each page is a list of RenderLine objects.
    """
    pages: list[list[RenderLine]] = []
    current_page: list[RenderLine] = []
    y = layout.top_y

    for line in lines:
        if current_page and y < layout.bottom_limit:
            pages.append(current_page)
            current_page = []
            y = layout.top_y

        current_page.append(line)
        y -= layout.line_height

    if current_page or not pages:
        pages.append(current_page)

    return pages


def _render_pdf_page(
    lines: list[RenderLine],
    *,
    drawer: TextDrawer,
    layout: PageLayout,
) -> None:
    """ Render one page of lines to a PDF canvas.
        Args:
            lines: The lines to render on the page.
            drawer: The TextDrawer used for drawing text.
            layout: The PageLayout used for positioning text.
    """
    y = layout.top_y
    for line in lines:
        x = layout.left_margin + line.x_offset
        drawer.draw_text(x, y, line.text)
        y -= layout.line_height


def write_pdf(
    pdf_path: str | Path,
    items: list[RenderItem],
    *,
    pagesize: tuple[float, float] = letter,
    font_name: str = "Helvetica",
    font_size: float = 10.0,
    title: str = "Report",
) -> None:
    """ Render mixed content items to a PDF file.

        Args:
            pdf_path: Destination path for the generated PDF.
            items: Mixed layout items to render.
            pagesize: ReportLab page size tuple in points.
            font_name: ReportLab font name.
            font_size: Font size in points.
            title: Document title metadata.
    """
    output_path = Path(pdf_path)
    page_width, page_height = pagesize

    canvas = Canvas(str(output_path), pagesize=pagesize)
    canvas.setTitle(title)
    canvas.setFont(font_name, font_size)

    measurer = PdfMeasurer(font_name, font_size)
    drawer = PdfDrawer(canvas)
    layout = get_pdf_layout(
        page_width=page_width,
        page_height=page_height,
        font_size=font_size,
    )

    lines = expand_items_to_lines(items, measurer=measurer, layout=layout)
    pages = _paginate_pdf_lines(lines, layout=layout)

    for index, page in enumerate(pages):
        if index > 0:
            canvas.showPage()
            canvas.setFont(font_name, font_size)
        _render_pdf_page(page, drawer=drawer, layout=layout)

    canvas.save()
