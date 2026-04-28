""" Dialog for selecting PDF font, size, and output filename before saving."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk, StringVar, DoubleVar, Toplevel, filedialog, messagebox

from reportlab.lib.pagesizes import letter

from lib.ui_vars import UiVars, UiDoc
from yt_lib.utils.app_context import RunContextStore
from lib.print.constants import COMMON_FONT_SIZES
from lib.print.pdf_backend import write_pdf, PDF_FONT_NAMES

@dataclass(slots=True, frozen=True)
class PdfSettings:
    """ Selected settings for PDF export."""

    font_name: str
    font_size_pt: float
    pdf_path: Path


class PdfDialog(Toplevel):
    """ Modal dialog for choosing PDF font, size, and output filename."""

    def __init__(
        self,
        parent,
        ui_vars: UiVars,
        ctx: RunContextStore,
        *,
        default_font_name: str = "Helvetica",
        default_font_size_pt: float = 10.0,
    ) -> None:
        """ Initialize the dialog.
            Args:
                parent: The parent Tkinter widget.
                ui_vars: The UI variables containing the transcript data.
                ctx: The application context for accessing directories.
                default_font_name: The default font name to select.
                default_font_size_pt: The default font size in points to select.
        """
        super().__init__(parent)
        self.ctx = ctx
        self.title("Save PDF")
        self.transient(parent)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

        self.ui_doc = UiDoc(ui_vars)
        self.result: PdfSettings | None = None

        self._default_font_name = default_font_name
        self._default_font_size_pt = default_font_size_pt

        self.font_var = StringVar(self, default_font_name)
        self.size_var = DoubleVar(self, default_font_size_pt)
        self.filename_var = StringVar(self, self._build_default_filename())

        self.columnconfigure(0, weight=1)

        outer = ttk.Frame(self, padding=12)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(1, weight=1)

        ttk.Label(outer, text="Font:").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=4
        )
        self.font_combo = ttk.Combobox(
            outer,
            textvariable=self.font_var,
            state="readonly",
            values=PDF_FONT_NAMES,
        )
        self.font_combo.grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(outer, text="Size:").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=4
        )
        self.size_combo = ttk.Combobox(
            outer,
            textvariable=self.size_var,
            state="readonly",
            values=[str(size) for size in COMMON_FONT_SIZES],
        )
        self.size_combo.grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(outer, text="File:").grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=4
        )
        filename_row = ttk.Frame(outer)
        filename_row.grid(row=2, column=1, sticky="ew", pady=4)
        filename_row.columnconfigure(0, weight=1)

        self.filename_entry = ttk.Entry(
            filename_row,
            textvariable=self.filename_var,
            width=40,
        )
        self.filename_entry.grid(row=0, column=0, sticky="ew")

        ttk.Button(
            filename_row,
            text="Browse...",
            command=self.on_browse,
        ).grid(row=0, column=1, padx=(8, 0))

        button_row = ttk.Frame(outer)
        button_row.grid(row=3, column=0, columnspan=2, sticky="e", pady=(12, 0))

        ttk.Button(button_row, text="Save", command=self.on_save).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(button_row, text="Cancel", command=self.on_cancel).grid(
            row=0, column=1
        )

        if default_font_name not in PDF_FONT_NAMES:
            self.font_var.set(PDF_FONT_NAMES[0])

        self.grab_set()
        self.wait_visibility()
        self.focus_set()

    def _build_default_filename(self) -> str:
        """ Return a reasonable default PDF filename.
            Returns:
                A default filename based on the video ID, or "report.pdf" if no ID is
        """
        video_id = self.ui_doc.ui.video_id.get().strip()
        if video_id:
            return f"{video_id}.pdf"
        return "report.pdf"

    def on_browse(self) -> None:
        """ Open the save-as dialog and store the selected filename."""
        current_name = self.filename_var.get().strip() or self._build_default_filename()

        pdf_path = filedialog.asksaveasfilename(
            parent=self,
            title="Save PDF As",
            defaultextension=".pdf",
            initialfile=current_name,
            initialdir=str(self.ctx.documents_dir),
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],

        )
        if pdf_path:
            self.filename_var.set(pdf_path)
            font_name = self.font_var.get().strip()
            font_size = float(self.size_var.get())

            write_pdf(
                pdf_path=pdf_path,
                items=self.ui_doc.get(),
                pagesize=letter,
                font_name=font_name,
                font_size=font_size,
                title=f"Transcript of Youtube video {self.ui_doc.ui.video_id.get()}",
            )
            self.result = PdfSettings(
                font_name=font_name,
                font_size_pt=font_size,
                pdf_path=pdf_path,
            )
            self.destroy()


    def on_save(self) -> None:
        """ Save the PDF if the dialog has a valid filename to the user's documents directory."""
        font_name = self.font_var.get().strip()
        font_size = float(self.size_var.get())
        filename = self.filename_var.get().strip()

        if not font_name or not filename:
            return

        pdf_path = self.ctx.documents_path(filename)
        if not pdf_path.exists():
            write_pdf(
                pdf_path=pdf_path,
                items=self.ui_doc.get(),
                pagesize=letter,
                font_name=font_name,
                font_size=font_size,
                title=f"Transcript of Youtube video {self.ui_doc.ui.video_id.get()}",
            )

            self.result = PdfSettings(
                font_name=font_name,
                font_size_pt=font_size,
                pdf_path=pdf_path,
            )
            self.destroy()
        messagebox.showerror("Save failed",
                        "File exists!\nUse the Browse button to move, rename, "
                        "or overwrite the file."
                    )


    def on_cancel(self) -> None:
        """ Cancel the dialog."""
        self.result = None
        self.destroy()
