""" Menu commands for the youtube transcript app.
    Also includes the Save functionality.
"""


from __future__ import annotations

# from dataclasses import dataclass
from pathlib import Path
# from functools import partial
from tkinter import Tk, Menu, filedialog, messagebox    # , Toplevel, StringVar, IntVar, Text
# from tkinter import ttk
from yt_lib.utils.log_utils import get_logger
from lib.app_context import RunContextStore
from lib.ui_vars import UiVars

logger = get_logger(__name__)

# -----------------------------------------------------------------------------
# Menu commands
# -----------------------------------------------------------------------------


class MenuCommands:
    def __init__(
        self,
        root: Tk,
        ctx: RunContextStore,
        ui: UiVars,
        # txt_out: Text,
    ) -> None:
        self.win = root
        self.ctx = ctx
        self.ui = ui
        # self.txt_out = txt_out

        self.win.option_add("*tearOff", False)

        self.menubar = Menu(self.win)
        self.win["menu"] = self.menubar

        self.menu_file = Menu(self.menubar)
        self.menu_edit = Menu(self.menubar)

        self.menubar.add_cascade(menu=self.menu_file, label="File")
        self.menubar.add_cascade(menu=self.menu_edit, label="Edit")

        self.menu_file.add_command(label="Save...", command=self.save_as)
        self.menu_file.add_separator()
        self.menu_file.add_command(label="Exit", command=self.win.destroy)

        self.menu_edit.add_command(label="Clear", command=self.clear)

    def clear(self) -> None:
        if messagebox.askyesno(
            "Clear Transcript",
            "Are you sure you want to clear the transcript?",
        ):
            self.ui.clear()

    def save_as(self) -> None:
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
            initialdir=str(self.ctx.documents_dir),  # or whatever your real path is
        )

        if not filename:
            return

        path = Path(filename)

        try:
            self.save_md(path)
        except OSError as exc:
            messagebox.showerror("Save failed", f"Could not save file {path}:\n{exc}")


    def create_front_matter(self) -> list[str]:
        front_matter: list[str] = [
                "---",
                f"video_id: {self.ui.video_id.get().strip()}",
                f"title: {self.ui.title.get().strip()}",
         ]
        if self.ui.url:
            front_matter.append(f"url: {self.ui.url}")
        # if self.ui.output_type:
        #     front_matter.append(f"output_type: {self.ui.output_type}")

        front_matter.append("---\n")
        return front_matter


    def save_md(self, filepath:Path) -> None:

        front_matter = self.create_front_matter()

        body = (
            "\n".join(front_matter)
            + "## Description\n\n"
            + (self.ui.desc_txt.strip() + "\n\n" if
               self.ui.desc_txt.strip() else "\n")
            + "## Transcript / Output\n\n"
            + self.ui.transcript_txt.rstrip()
            + "\n"
        )
        filepath.write_text(body, encoding="utf-8")
