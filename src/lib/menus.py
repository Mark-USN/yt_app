""" Main Menu commands for the youtube transcript app.
    Also includes the Save functionality.
"""


from __future__ import annotations

from pathlib import Path
from tkinter import Tk, Menu, filedialog, messagebox    # , Toplevel, StringVar, IntVar, Text
from yt_lib.utils.log_utils import get_logger
from lib.app_context import RunContextStore
from lib.ui_vars import UiVars
from lib.save import FileSaver
from lib.print.print_dialog import PrintDialog
from lib.print.pdf_dialog import PdfDialog

logger = get_logger(__name__)

# -----------------------------------------------------------------------------
# Menu commands
# -----------------------------------------------------------------------------


class MenuCommands:
    """ Menu commands for the youtube transcript app. 
        Holds references to the objects needed to create the menu system
        and perform the menu actions.
    """
    def __init__(
        self,
        root: Tk,
        ctx: RunContextStore,
        ui: UiVars,
    ) -> None:
        """ Initialize the MenuCommands object.
            Args:
                root: The root Tkinter window.
                ctx: The RunContextStore object that holds the application's paths.
                ui: The UiVars object that holds the application's UI variables.
        """
        self.win = root
        self.ctx = ctx
        self.ui = ui
        self.saver = FileSaver(self.ctx,self.ui)
        # self.txt_out = txt_out

        self.win.option_add("*tearOff", False)

        self.menubar = Menu(self.win)
        self.win["menu"] = self.menubar

        self.menu_file = Menu(self.menubar)
        self.menu_edit = Menu(self.menubar)

        self.menubar.add_cascade(menu=self.menu_file, label="File")
        self.menubar.add_cascade(menu=self.menu_edit, label="Edit")

        self.menu_file.add_command(label="Save...", command=self.save_as)
        self.menu_file.add_command(label="Save PDF...", command=self.save_as_pdf)
        self.menu_file.add_command(label="Print...", command=self.print)
        self.menu_file.add_separator()
        self.menu_file.add_command(label="Exit", command=self.win.destroy)

        self.menu_edit.add_command(label="Clear", command=self.clear)

    def clear(self) -> None:
        """ Clear the transcript fields if the user confirms. """
        if messagebox.askyesno(
            "Clear Transcript",
            "Are you sure you want to clear the transcript?",
        ):
            self.ui.clear()

    def save_as(self) -> None:
        """ Save the transcript to a file. """
        ext = "md" # if self.ui.out_format.get().strip() == "markdown" else "txt"

        video_id = self.ui.video_id.get().strip()
        default_filename = f"{video_id}.{ext}" # if video_id else f"transcript.{ext}"

        filename = filedialog.asksaveasfilename(
            title="Save As",
            defaultextension=f".{ext}",
            filetypes=[
                ("Markdown files", "*.md"),
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ],
            initialfile=default_filename,
            initialdir=str(self.ctx.documents_dir),
        )

        if not filename:
            return

        path = Path(filename)

        try:
            if path.suffix == ".md":
                self.saver.save_md(path)
            else:
                self.saver.save_txt(path)
        except OSError as exc:
            messagebox.showerror("Save failed", f"Could not save file {path}:\n{exc}")

    def save_as_pdf(self) -> None:
        """ Save the transcript to as a pdf to a file. """
        PdfDialog(self.win, self.ui, self.ctx)

    def print(self):
        """ Open the print dialog. """
        # prn_dlg = PrintDialog(self.win, self.ui)
        PrintDialog(self.win, self.ui)
