"""
Simple Tkinter app to fetch and view YouTube transcripts from local cache,
and display metadata + transcript in a GUI.

- Uses an InfoManager cache for URL history + metadata.
- Uses yt_lib transcript helpers for output formats.
- Keeps main() streamlined by using a small "view-model" dataclass (UiVars)
  that owns Tk variables and knows how to apply metadata to them.
"""

from __future__ import annotations

from dataclasses import dataclass
from tkinter import DoubleVar, StringVar, Text, Tk
from tkinter import ttk
from typing import Any
from urllib.parse import urlparse

from yt_lib.yt_ids import extract_video_id
from yt_lib.yt_transcript import youtube_json, youtube_sentences, youtube_text

from lib.utils.info_cache import InfoManager


# -----------------------------------------------------------------------------
# Demo fallback (remove once your cache always returns real metadata)
# -----------------------------------------------------------------------------


@dataclass(slots=True)
class TestInfo:
    video_id: str = "6bHDQtVfsCM"
    title: str = "Python List Comprehension (Visually Explained) | The Cleanest Way to Code | #Python Course 33"
    url: str = "https://www.youtube.com/watch?v=6bHDQtVfsCM"
    trans_type: str = "transcript"
    video_type: str = "mp4"
    video_res: str = "1080p"
    fps: float = 30.0
    duration: str = "15:00"
    video_size: str = "100 MB"
    description: str = """
Visually explained how Python List Comprehensions simplify loops and make your code cleaner and faster.
List Comprehension is one of the most powerful ways to write elegant, efficient, and readable Python code.
"""
    transcript: str = """
All right, my friends. Now we have reached the final advanced technique, the last advanced tool that we have in the
toolbox in order to work with the data structure in Python. And to be honest, this one is the coolest feature in Python.
We have the list comprehensions...
"""


# -----------------------------------------------------------------------------
# Tk "view-model": all widget-bound variables live here
# -----------------------------------------------------------------------------


@dataclass(slots=True)
class UiVars:
    video_id: StringVar
    title: StringVar
    url: StringVar
    transcript_type: StringVar
    video_type: StringVar
    resolution: StringVar
    fps: DoubleVar
    duration: StringVar
    file_size: StringVar

    def clear(self) -> None:
        self.video_id.set("")
        self.title.set("")
        self.url.set("")
        self.transcript_type.set("")
        self.video_type.set("")
        self.resolution.set("")
        self.fps.set(0.0)
        self.duration.set("")
        self.file_size.set("")

    def apply_metadata(self, info: Any, *, fmt: str, url: str) -> None:
        """
        Convert/cache metadata -> widget variables.
        Keep ALL mapping/formatting rules here.
        """
        # Required
        self.video_id.set(str(getattr(info, "video_id", "") or ""))
        self.title.set(str(getattr(info, "title", "") or ""))
        self.url.set(str(getattr(info, "url", "") or url))
        self.transcript_type.set(fmt)

        # Optional / may be absent depending on your cache object
        self.video_type.set(str(getattr(info, "video_type", "") or ""))
        self.resolution.set(str(getattr(info, "video_res", "") or ""))

        fps = getattr(info, "fps", None)
        try:
            self.fps.set(float(fps) if fps is not None else 0.0)
        except (TypeError, ValueError):
            self.fps.set(0.0)

        # duration: store as string for display
        self.duration.set(str(getattr(info, "duration", "") or ""))

        self.file_size.set(str(getattr(info, "video_size", "") or ""))


def make_ui_vars(root: Tk) -> UiVars:
    return UiVars(
        video_id=StringVar(root, ""),
        title=StringVar(root, ""),
        url=StringVar(root, ""),
        transcript_type=StringVar(root, ""),
        video_type=StringVar(root, ""),
        resolution=StringVar(root, ""),
        fps=DoubleVar(root, 0.0),
        duration=StringVar(root, ""),
        file_size=StringVar(root, ""),
    )


# -----------------------------------------------------------------------------
# Small UI helpers
# -----------------------------------------------------------------------------


def set_text(widget: Text, value: str) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", value)
    widget.see("1.0")
    widget.configure(state="disabled")


def is_valid_youtube_url(text: str) -> bool:
    text = text.strip()
    if not text:
        return False

    parsed = urlparse(text)
    if not parsed.scheme or not parsed.netloc:
        return False

    return extract_video_id(text) is not None


# -----------------------------------------------------------------------------
# Controller/update function
# -----------------------------------------------------------------------------


def populate(
    *,
    cmbo_url: ttk.Combobox,
    out_format: StringVar,
    cache: InfoManager,
    ui: UiVars,
    txt_dscr: Text,
    txt_out: Text,
) -> None:
    url = cmbo_url.get().strip()
    fmt = out_format.get().strip() or "json"

    if not url:
        return
    if not is_valid_youtube_url(url):
        return

    # ---- metadata from cache ----
    info = cache.get_video_metadata(url)
    ui.apply_metadata(info, fmt=fmt, url=url)

    # After querying the cache, the history will have changed, so refresh the combobox choices.
    choices = cache.get_cached_urls()
    cmbo_url["values"] = choices


    # description (prefer cache description; fall back to blank)
    desc = str(getattr(info, "description", "") or "")
    set_text(txt_dscr, desc)

    # ---- transcript output ----
    match fmt:
        case "json":
            transcript = youtube_json(url)
        case "transcript":
            transcript = youtube_text(url)
        case "sentences":
            transcript = youtube_sentences(url)
        case _:
            transcript = f"Unknown format: {fmt}"

    set_text(txt_out, transcript)




# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> None:
    cache = InfoManager()

    root = Tk()
    root.title("yt_app")
    root.geometry("1100x700")  # prevents giant off-screen windows
    root.minsize(900, 500)

    # Single place for widget-bound vars
    ui = make_ui_vars(root)

    # Default output format (create early so other widgets can refer to it safely)
    out_format = StringVar(root, "json")

    # Demo: initial content if you want something visible before selection
    demo = TestInfo()
    ui.apply_metadata(demo, fmt=out_format.get(), url=demo.url)

    content = ttk.Frame(root, padding=(6, 6, 12, 12))
    content.grid(column=0, row=0, sticky=("n", "s", "e", "w"))

    # Make the root/content expandable
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    content.columnconfigure(0, weight=1)
    content.rowconfigure(0, weight=1)

    frm_left = ttk.Frame(content, borderwidth=5, relief="ridge")
    frm_right = ttk.Frame(content, borderwidth=5, relief="ridge")
    frm_left.grid(column=0, row=0, sticky=("n", "s", "e", "w"))
    frm_right.grid(column=1, row=0, sticky=("n", "s"), padx=(8, 0))

    content.columnconfigure(0, weight=1)  # left expands
    content.columnconfigure(1, weight=0)  # right stays tight

    # Left layout: rows that expand are the text areas
    frm_left.columnconfigure(0, weight=1)
    frm_left.rowconfigure(2, weight=1)  # description expands
    frm_left.rowconfigure(3, weight=1)  # output expands

    # --- URL row ---
    frm_url = ttk.Frame(frm_left)
    frm_url.grid(column=0, row=0, sticky=("e", "w"), padx=6, pady=6)
    frm_url.columnconfigure(1, weight=1)  # combobox expands

    ttk.Label(frm_url, text="URL=>").grid(column=0, row=0, sticky="w")

    cmbo_url = ttk.Combobox(frm_url)
    cmbo_url.grid(column=1, row=0, sticky=("e", "w"), padx=(6, 0))

    # Load choices into the combobox
    choices = cache.get_cached_urls()
    cmbo_url["values"] = choices

    # --- Title/info frame ---
    frm_title = ttk.Frame(frm_left, borderwidth=5, relief="ridge")
    frm_title.grid(column=0, row=1, sticky=("e", "w"), padx=6, pady=(0, 6))

    # Configure enough columns (you use up to column 7)
    for c in range(8):
        frm_title.columnconfigure(c, weight=1)

    ttk.Label(frm_title, text="Video Id:").grid(column=0, row=0, sticky="w")
    ttk.Label(frm_title, textvariable=ui.video_id).grid(column=1, row=0, columnspan=7, sticky="w")

    ttk.Label(frm_title, text="Title:").grid(column=0, row=1, sticky="w")
    ttk.Label(frm_title, textvariable=ui.title).grid(column=1, row=1, columnspan=7, sticky="w")

    ttk.Label(frm_title, text="URL:").grid(column=0, row=2, sticky="w")
    ttk.Label(frm_title, textvariable=ui.url).grid(column=1, row=2, columnspan=7, sticky="w")

    ttk.Label(frm_title, text="Transcript Type:").grid(column=0, row=3, sticky="w")
    ttk.Label(frm_title, textvariable=ui.transcript_type).grid(column=1, row=3, sticky="w")

    ttk.Label(frm_title, text="Video Type:").grid(column=2, row=3, sticky="w")
    ttk.Label(frm_title, textvariable=ui.video_type).grid(column=3, row=3, sticky="w")

    ttk.Label(frm_title, text="Video Resolution:").grid(column=0, row=4, sticky="w")
    ttk.Label(frm_title, textvariable=ui.resolution).grid(column=1, row=4, sticky="w")

    ttk.Label(frm_title, text="fps:").grid(column=2, row=4, sticky="w")
    ttk.Label(frm_title, textvariable=ui.fps).grid(column=3, row=4, sticky="w")

    ttk.Label(frm_title, text="Duration:").grid(column=4, row=4, sticky="w")
    ttk.Label(frm_title, textvariable=ui.duration).grid(column=5, row=4, sticky="w")

    ttk.Label(frm_title, text="File Size:").grid(column=6, row=4, sticky="w")
    ttk.Label(frm_title, textvariable=ui.file_size).grid(column=7, row=4, sticky="w")

    # --- Description text + scrollbar ---
    desc_frame = ttk.Frame(frm_left)
    desc_frame.grid(column=0, row=2, sticky=("n", "s", "e", "w"), padx=6, pady=(0, 6))
    desc_frame.columnconfigure(0, weight=1)
    desc_frame.rowconfigure(0, weight=1)

    txt_dscr = Text(desc_frame, wrap="word")
    scrl_dscr = ttk.Scrollbar(desc_frame, orient="vertical", command=txt_dscr.yview)
    txt_dscr.configure(yscrollcommand=scrl_dscr.set)

    txt_dscr.grid(column=0, row=0, sticky=("n", "s", "e", "w"))
    scrl_dscr.grid(column=1, row=0, sticky=("n", "s"))

    set_text(txt_dscr, demo.description)

    # --- Output text + scrollbar ---
    out_frame = ttk.Frame(frm_left)
    out_frame.grid(column=0, row=3, sticky=("n", "s", "e", "w"), padx=6, pady=(0, 6))
    out_frame.columnconfigure(0, weight=1)
    out_frame.rowconfigure(0, weight=1)

    txt_out = Text(out_frame, wrap="word")
    scrl_out = ttk.Scrollbar(out_frame, orient="vertical", command=txt_out.yview)
    txt_out.configure(yscrollcommand=scrl_out.set)

    txt_out.grid(column=0, row=0, sticky=("n", "s", "e", "w"))
    scrl_out.grid(column=1, row=0, sticky=("n", "s"))

    set_text(txt_out, demo.transcript)

    # --- Right side controls ---
    frm_right.columnconfigure(0, weight=1)

    ttk.Button(frm_right, text="History").grid(column=0, row=0, sticky=("e", "w"), padx=6, pady=(6, 2))
    ttk.Label(frm_right, text="Output Format:").grid(column=0, row=1, sticky="w", padx=6, pady=(6, 2))
    ttk.Radiobutton(frm_right, text="Json", variable=out_format, value="json").grid(column=0, row=2, sticky="w", padx=6)
    ttk.Radiobutton(frm_right, text="Text", variable=out_format, value="transcript").grid(column=0, row=3, sticky="w", padx=6)
    ttk.Radiobutton(frm_right, text="Sentences", variable=out_format, value="sentences").grid(column=0, row=4, sticky="w", padx=6)
    ttk.Button(frm_right, text="Save").grid(column=0, row=6, sticky=("e", "w"), padx=6, pady=(10, 2))
    ttk.Button(frm_right, text="Exit", command=root.destroy).grid(column=0, row=8, sticky=("s", "e", "w"), padx=6, pady=(10, 6))

    # -------------------------------------------------------------------------
    # Bindings (update on selection, Enter, or focus-out)
    # -------------------------------------------------------------------------

    def do_populate() -> None:
        populate(
            cmbo_url=cmbo_url,
            out_format=out_format,
            cache=cache,
            ui=ui,
            txt_dscr=txt_dscr,
            txt_out=txt_out,
        )

    cmbo_url.bind("<<ComboboxSelected>>", lambda _e: do_populate())
    cmbo_url.bind("<Return>", lambda _e: do_populate())
    cmbo_url.bind("<FocusOut>", lambda _e: do_populate())

    # Also repopulate if the user switches output format radios (handy UX)
    def on_format_change(*_args: object) -> None:
        # if there's a valid URL in the box, refresh the transcript area
        if is_valid_youtube_url(cmbo_url.get()):
            do_populate()

    out_format.trace_add("write", on_format_change)

    root.mainloop()


if __name__ == "__main__":
    main()