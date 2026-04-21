""" Modal dialog to display history titles in the cache and return the selected URL.
    The history is prepended with the video id. The dialog is resizable and will size 
    itself to fit the longest title, up to a maximum width.
    The user can select a title and click OK or double-click a title to select it. 
    The selected URL is returned to the caller, or None if the dialog is cancelled.
"""
from __future__ import annotations

from typing import TypedDict
import tkinter as tk
from tkinter import ttk, Toplevel, Listbox, Event, Misc, font, END
from yt_lib.utils.log_utils import get_logger

logger = get_logger(__name__)

class HistoryItem(TypedDict):
    """ Represents a history item with a title and URL. The title combines the Video Id and the
        Video's title.
    """
    title: str
    url: str



class HistoryDialog(Toplevel):
    """Modal dialog that displays history titles and returns the selected URL."""

    url: str | None
    def __init__(
        self,
        parent: tk.Misc,
        items: list[dict[str, str]],
        *,
        title: str = "History",
    ) -> None:
        """ Initialize the history dialog.
            Args:
                parent: The parent window.
                items: A list of history items, each containing a 'title' and 'url'.
                title: The title of the dialog window.
        """
        super().__init__(parent)

        self.items = items
        self.result: str | None = None

        self.title(title)
        self.transient(parent)
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        outer = ttk.Frame(self, padding=12)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        ttk.Label(outer, text="Select a cached video:").grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 8),
        )

        list_frame = ttk.Frame(outer)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        titles:list[str] = [item['title'] for item in self.items]

        max_len = max((len(t) for t in titles), default=20)

        self.listbox = Listbox(
            list_frame,
            activestyle="dotbox",
            width=min(max_len + 2, 120),
        )
        # Pixel-perfect sizing
        f = font.nametofont(self.listbox.cget("font"))

        if titles:
            pixel_width = max((f.measure(t) for t in titles), default=200)
            self.geometry(f"{pixel_width + 60}x400")

        self.listbox.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.listbox.yview,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=scrollbar.set)

        for ttl in titles:
            self.listbox.insert(END, ttl)

        if self.items:
            self.listbox.selection_set(0)
            self.listbox.activate(0)

        self.listbox.bind("<Double-1>", self.on_ok)
        self.listbox.bind("<Return>", self.on_ok)
        self.bind("<Escape>", self.on_cancel)

        button_frame = ttk.Frame(outer)
        button_frame.grid(row=2, column=0, sticky="e", pady=(10, 0))

        ttk.Button(button_frame, text="OK", command=self.on_ok).grid(
            row=0,
            column=0,
            padx=(0, 6),
        )
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel).grid(
            row=0,
            column=1,
        )

        self.update_idletasks()
        self.center_over_parent(parent)

        self.grab_set()
        self.listbox.focus_set()

    def center_over_parent(self, parent: Misc) -> None:
        """ Center dialog over parent window.
            Args:
                parent: The parent window to center over.
        """
        self.update_idletasks()

        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()

        dialog_w = self.winfo_width()
        dialog_h = self.winfo_height()

        x = parent_x + (parent_w - dialog_w) // 2
        y = parent_y + (parent_h - dialog_h) // 2

        self.geometry(f"+{x}+{y}")

    def on_ok(self, _event: Event[Misc] | None = None) -> None:
        """ Handle the OK button press or double-click event.
            Args:
                event: The event that triggered the callback, if any.
        """
        selection = self.listbox.curselection()
        if not selection:
            return

        index = selection[0]

        self.result = self.items[index]['url']
        self.destroy()

    def on_cancel(self, _event: Event[Misc] | None = None) -> None:
        """ Handle the Cancel button press or Escape key event.
            Args:
                event: The event that triggered the callback, if any.
        """
        self.result = None
        self.destroy()


def ask_history_url(
    parent: Misc,
    items: list[dict[str,str]],
) -> str | None:
    """ Open the modal history dialog and return the selected URL or None.
        Args:
            parent: The parent window.
            items: A list of history items, each containing a 'title' and 'url'.
        Returns:
            The URL of the selected history item, or None if cancelled.
    """
    dialog = HistoryDialog(parent, items)
    parent.wait_window(dialog)
    return dialog.result
