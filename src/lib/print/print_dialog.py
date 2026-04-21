""" Dialog for selecting printer, font, and size before printing a transcript. """

from __future__ import annotations

from dataclasses import dataclass
from tkinter import ttk, StringVar, DoubleVar, Toplevel, messagebox
from yt_lib.utils.log_utils import get_logger
from lib.ui_vars import UiVars, UiDoc
from lib.print.constants import COMMON_FONT_SIZES
from lib.print.print_backend import (
    get_default_printer,
    get_printer_fonts,
    list_printers,
    print_items,
)

logger = get_logger(__name__)

@dataclass(slots=True, frozen=True)
class PrintSettings:
    """ Selected settings for printing a transcript."""
    printer_name: str
    font_name: str
    font_size_pt: int

class PrintDialog(Toplevel):
    """Modal dialog for choosing printer, font, and size before printing."""

    def __init__(
        self,
        parent,
        ui_vars: UiVars,
        *,
        default_font_name: str = "Courier New",
        default_font_size_pt: float = 10.0,
    ) -> None:
        """ Initialize the dialog.
            Args:
                parent: The parent Tkinter widget.
                ui_vars: The UI variables containing the transcript data.
                default_font_name: The default font to select if available.
                default_font_size_pt: The default font size in points.
                doc_title: The title to use for the printed document.
        """
        super().__init__(parent)

        self.title("Print")
        self.transient(parent)
        self.ui_doc = UiDoc(ui_vars)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

        self.result: PrintSettings | None = None

        self._default_font_name = default_font_name
        self._default_font_size_pt = default_font_size_pt

        self.printer_var = StringVar(self, "")
        self.font_var = StringVar(self, "")
        self.size_var = DoubleVar(self, default_font_size_pt)

        self.columnconfigure(0, weight=1)

        outer = ttk.Frame(self, padding=12)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(1, weight=1)

        ttk.Label(outer, text="Printer:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.printer_combo = ttk.Combobox(outer, textvariable=self.printer_var, state="readonly")
        self.printer_combo.grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(outer, text="Font:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        self.font_combo = ttk.Combobox(outer, textvariable=self.font_var, state="readonly")
        self.font_combo.grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(outer, text="Size:").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        self.size_combo = ttk.Combobox(
            outer,
            textvariable=self.size_var,
            state="readonly",
            values=[str(size) for size in COMMON_FONT_SIZES],
        )
        self.size_combo.grid(row=2, column=1, sticky="ew", pady=4)

        button_row = ttk.Frame(outer)
        button_row.grid(row=3, column=0, columnspan=2, sticky="e", pady=(12, 0))

        ttk.Button(button_row, text="Print", command=self.on_print).grid(row=0,
                    column=0, padx=(0, 8))
        ttk.Button(button_row, text="Cancel", command=self.on_cancel).grid(row=0, column=1)

        self.printer_combo.bind("<<ComboboxSelected>>", self.on_printer_changed)

        self._populate_printers()
        self.grab_set()
        self.wait_visibility()
        self.focus_set()

    def _populate_printers(self) -> None:
        """ Load installed printers and select a default."""
        printers = list_printers()
        self.printer_combo["values"] = printers

        if not printers:
            return

        default_printer = get_default_printer()
        selected = default_printer if default_printer in printers else printers[0]
        self.printer_var.set(selected)
        self._populate_fonts(selected)

    def _populate_fonts(self, printer_name: str) -> None:
        """ Load fonts for the selected printer.
            Args:
                printer_name: The name of the selected printer.
        """

        fonts = get_printer_fonts(printer_name.strip())

        self.font_combo["values"] = fonts

        if not fonts:
            self.font_var.set("")
            return

        if self._default_font_name in fonts:
            self.font_var.set(self._default_font_name)
        else:
            self.font_var.set(fonts[0])

        self.size_var.set(self._default_font_size_pt)

    def on_printer_changed(self, _event=None) -> None:
        """Refresh fonts when the selected printer changes."""
        printer_name = self.printer_var.get()
        if printer_name:
            self._populate_fonts(printer_name)

    def on_print(self) -> None:
        """ Print the document using the selected settings and close the dialog."""
        printer_name = self.printer_var.get().strip()
        font_name = self.font_var.get().strip()
        font_size = self.size_var.get()

        if not font_name or not font_size:
            return
        try:
            print_items(
                printer_name = printer_name,
                items = self.ui_doc.get(),
                document_name = f"Transcript of Youtube video {self.ui_doc.ui.video_id.get()}",
                face_name = font_name,
                point_size = font_size,
            )
        except Exception as exc:
            logger.error("Failed to print: %s", exc)
            messagebox.showerror("Failed to Print",
                                 f"Transcript of YouTube video {self.ui_doc.ui.video_id.get()} "
                                 f"failed to print to {printer_name}.")
        self.destroy()

    def on_cancel(self) -> None:
        """ Cancel the dialog."""
        self.result = None
        self.destroy()
