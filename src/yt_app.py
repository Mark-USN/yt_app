"""
Simple Tkinter app to fetch and view YouTube transcripts from local cache,
and display metadata + transcript in a GUI.

- Uses an InfoManager cache for URL history + metadata.
- Uses yt_lib transcript helpers for output formats.
- Keeps main() streamlined by using a small "view-model" dataclass (UiVars)
  that owns Tk variables and knows how to apply metadata to them.
"""

from __future__ import annotations


import time
from dataclasses import dataclass
from venv import logger
from tkinter import StringVar, IntVar, Text, Tk

from tkinter import ttk

from urllib.parse import urlparse

from yt_lib.yt_ids import extract_video_id, YtdlpMetadata
from yt_lib.yt_transcript import youtube_json, youtube_sentences, youtube_text
from yt_lib.utils.log_utils import configure_logging, LogConfig, FileLogConfig, get_logger
from yt_lib.utils.paths import resolve_runtime_dirs, RuntimeDirs
from lib.utils.globals import APP_NAME, APP_PATHS
from lib.utils.info_cache import InfoManager

file_log_conf = FileLogConfig(
        log_dir=APP_PATHS.user_log_dir,
        log_file_prefix=APP_NAME,
    )
log_cfg = LogConfig(root=APP_NAME)
configure_logging(cfg=log_cfg,
                  file=file_log_conf,
                  force=True,
                  tee_console=False
                )
logger = get_logger(__name__)



def format_hms(duration: int) -> str:
    """ Turn seconds into hours:minutes:seconds. """
    return time.strftime("%H:%M:%S", time.gmtime(duration))
# -----------------------------------------------------------------------------
# Demo fallback (remove once your cache always returns real metadata)
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Init default entries
# -----------------------------------------------------------------------------

@dataclass(slots=True)
class InitInfo:
    """
        A blank/default metadata object to use on app startup, or when the cache doesn't 
        have metadata for a url. The UI will just show blanks or defaults for all fields.
    """
    video_id: str = " - "
    title: str = " - "
    url: str = " - "
    # transcript_type: str = "json"
    # out_format:str = "markdown"
    video_type: str = " - "
    video_res: str = " - "
    fps: int = 0
    duration: int =  0
    video_size: int = 0
    description: str = """- Description -"""
    transcript: str = """- Transcript -"""


# -----------------------------------------------------------------------------
# Tk "view-model": all widget-bound variables live here
# -----------------------------------------------------------------------------


@dataclass(slots=True)
class UiVars:
    """ Holds all Tk variables that widgets bind to, and knows how to apply metadata to them."""
    video_id: StringVar
    title: StringVar
    url: StringVar
    transcript_type: StringVar
    out_format: StringVar
    video_type: StringVar
    video_format: StringVar
    resolution: StringVar
    fps: IntVar
    duration: StringVar
    file_size: IntVar

    def clear(self) -> None:
        """ Set default values for the widgets. """
        self.video_id.set(" - ")
        self.title.set(" - ")
        self.url.set("")
        self.transcript_type.set("json")
        self.out_format.set("markdown")
        self.video_type.set(" - ")
        self.resolution.set(" - ")
        self.video_format.set(" - ")
        self.fps.set(0)
        self.duration.set(" - ")
        self.file_size.set(0)

    def apply_metadata(
                        self,
                        info: YtdlpMetadata,
                        *,
                        transcript_type: str,
                        out_format: str,
                        url: str
                    ) -> None:
        """
        Convert/cache metadata -> widget variables.
        Keep ALL mapping/formatting rules here.
        """
        # Required
        self.video_id.set(str(getattr(info, "video_id", "") or "").strip())
        self.title.set(str(getattr(info, "title", "") or "").strip())
        self.url.set(str(getattr(info, "url", "") or url).strip())
        self.transcript_type.set(transcript_type)
        self.out_format.set(out_format)
        # Optional / may be absent depending on your cache object
        self.video_type.set(str(getattr(info, "ext", "") or "").strip())
        self.video_format.set(str(getattr(info, "video_format", "") or "").strip())
        self.resolution.set(str(getattr(info, "resolution", " - ") or " - "))
        fps = getattr(info, "fps", None)
        try:
            self.fps.set(int(fps) if fps is not None else 0)
        except (TypeError, ValueError):
            self.fps.set(0)

        # duration: store as string for display
        self.duration.set(format_hms(getattr(info, "duration", 0) or 0))

        self.file_size.set(int(getattr(info, "filesize", 0) or 0))


def make_ui_vars(root: Tk) -> UiVars:
    """ Factory for the UiVars dataclass, so we can keep all Tk variable creation in one place. """
    return UiVars(
        video_id=StringVar(root, " - "),
        title=StringVar(root, " - "),
        url=StringVar(root, ""),
        transcript_type=StringVar(root, "json"),
        out_format=StringVar(root, "markdown"),
        video_type=StringVar(root, " - "),
        video_format=StringVar(root, " - "),
        resolution=StringVar(root, " - "),
        fps=IntVar(root, 0),
        duration=StringVar(root, "0"),
        file_size=IntVar(root, 0),
    )


# -----------------------------------------------------------------------------
# Small UI helpers
# -----------------------------------------------------------------------------


def set_text(widget: Text, value: str) -> None:
    """ Update disabled Text widgets. """
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", value)
    widget.see("1.0")
    widget.configure(state="disabled")


def is_valid_youtube_url(text: str) -> bool:
    """ Basic check for whether a URL is a valid YouTube video URL. """
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
                cache: InfoManager,
                ui: UiVars,
                txt_dscr: Text,
                txt_out: Text,
            ) -> None:
    """ When the user selects a URL or changes the transcript type or output format,
        update the metadata and transcript areas.
    """
    url = cmbo_url.get().strip()

    if not url:
        return
    if not is_valid_youtube_url(url):
        return

    # ---- metadata from cache ----
    # If the url is valid, we should have metadata for it in the cache.
    # If not, the cache can return a blank/default metadata object (never None)
    # and the UI will just show blanks/defaults.
    info = cache.get_video_metadata(url)
    ui.apply_metadata(
                        info,
                        transcript_type=ui.transcript_type.get(),
                        out_format=ui.out_format.get(),
                        url=url
                      )

    # After querying the cache, the history will have changed, so refresh the combobox choices.
    choices = cache.get_cached_urls()
    cmbo_url["values"] = choices


    # description (prefer cache description; fall back to blank)
    desc = str(getattr(info, "description", "") or "")
    set_text(txt_dscr, desc)

    # ---- transcript output ----
    match ui.transcript_type.get().strip():
        case "json":
            transcript = youtube_json(url)
        case "transcript":
            transcript = youtube_text(url)
        case "sentences":
            transcript = youtube_sentences(url)
        case _:
            transcript = f"Unknown format: {ui.transcript_type.get()}"

    set_text(txt_out, transcript)




# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> None:
    """ Set up the GUI, load initial data, and bind events. """

    cache = InfoManager()

    root = Tk()
    root.title("yt_app")
    root.geometry("1100x700")  # prevents giant off-screen windows
    root.minsize(900, 500)

    # Single place for widget-bound vars
    ui = make_ui_vars(root)


    # Demo: initial content if you want something visible before selection
    init = InitInfo()
    ui.apply_metadata(
                        init,
                        transcript_type=ui.transcript_type.get(),
                        out_format=ui.out_format.get(),
                        url=init.url
                    )

    content = ttk.Frame(root, padding=(6, 6, 12, 12))
    content.grid(column=0, row=0, sticky=("n", "s", "e", "w"))

    # Make the root/content expandable
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    content.columnconfigure(0, weight=1)
    content.rowconfigure(0, weight=1)

    # Two main columns: left for metadata + transcript, right for controls/history
    frm_left = ttk.Frame(content, borderwidth=5, relief="ridge")
    frm_right = ttk.Frame(content, borderwidth=5, relief="ridge")
    # frm_exit = ttk.Frame(content, borderwidth=5, relief="ridge")
    frm_exit = ttk.Frame(content, borderwidth=5)
    frm_left.grid(column=0, row=0, rowspan=2, sticky=("n", "s", "e", "w"))
    frm_right.grid(column=1, row=0, sticky=("n", "s"), padx=(8, 0))
    frm_exit.grid(column=1, row=1, sticky=("n", "s"), padx=(8, 0))

    content.columnconfigure(0, weight=1)  # left expands
    content.columnconfigure(1, weight=0)  # right stays tight

    # Left layout: rows that expand are the text areas
    frm_left.columnconfigure(0, weight=1)
    frm_left.rowconfigure(2, weight=1)  # description expands
    frm_left.rowconfigure(3, weight=1)  # transcript expands

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
    for c in range(11):
        frm_title.columnconfigure(c, weight=1)

    ttk.Label(frm_title, text="Video Id:").grid(column=0, row=0, sticky="w")
    ttk.Label(frm_title, textvariable=ui.video_id).grid(column=1, row=0, columnspan=7, sticky="w")

    ttk.Label(frm_title, text="Title:").grid(column=0, row=1, sticky="w")
    ttk.Label(frm_title, textvariable=ui.title).grid(column=1, row=1, columnspan=7, sticky="w")

    ttk.Label(frm_title, text="URL:").grid(column=0, row=2, sticky="w")
    ttk.Label(frm_title, textvariable=ui.url).grid(column=1, row=2, columnspan=7, sticky="w")

    ttk.Label(frm_title, text="Transcript Type:").grid(column=0, row=3, sticky="w")
    ttk.Label(frm_title, textvariable=ui.transcript_type).grid(column=1, row=3, sticky="w")

    ttk.Label(frm_title, text="Video Type:").grid(column=1, row=3, sticky="w")
    ttk.Label(frm_title, textvariable=ui.video_type).grid(column=3, row=3, sticky="w")

    ttk.Label(frm_title, text="Video format:").grid(column=2, row=3, sticky="w")
    ttk.Label(frm_title, textvariable=ui.video_format).grid(column=3, row=3, sticky="w")

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

    set_text(txt_dscr, init.description)

    # --- Transcript text + scrollbar ---
    out_frame = ttk.Frame(frm_left)
    out_frame.grid(column=0, row=3, sticky=("n", "s", "e", "w"), padx=6, pady=(0, 6))
    out_frame.columnconfigure(0, weight=1)
    out_frame.rowconfigure(0, weight=1)

    txt_out = Text(out_frame, wrap="word")
    scrl_out = ttk.Scrollbar(out_frame, orient="vertical", command=txt_out.yview)
    txt_out.configure(yscrollcommand=scrl_out.set)

    txt_out.grid(column=0, row=0, sticky=("n", "s", "e", "w"))
    scrl_out.grid(column=1, row=0, sticky=("n", "s"))

    set_text(txt_out, init.transcript)

    # --- Right side controls ---
    frm_right.columnconfigure(0, weight=1)

    ttk.Button(frm_right, text="History").grid(column=0, row=0,
                                             sticky=("e", "w"), padx=6, pady=(6, 2))
    ttk.Label(frm_right, text="Transcript type:").grid(column=0,
                                                       row=1, sticky="w", padx=6, pady=(6, 2))
    ttk.Radiobutton(frm_right, text="Json", variable=ui.transcript_type,
                    value="json").grid(column=0, row=2, sticky="w", padx=6)
    ttk.Radiobutton(frm_right, text="Text", variable=ui.transcript_type,
                    value="transcript").grid(column=0, row=3, sticky="w", padx=6)
    ttk.Radiobutton(frm_right, text="Sentences", variable=ui.transcript_type,
                    value="sentences").grid(column=0, row=4, sticky="w", padx=6)
    ttk.Label(frm_right, text="Output Format:").grid(column=0, row=6, sticky="w",
                                                     padx=6, pady=(6, 2))
    ttk.Radiobutton(frm_right, text="Markdown", variable=ui.out_format,
                    value="markdown").grid(column=0, row=7, sticky="w", padx=6)
    ttk.Radiobutton(frm_right, text="text", variable=ui.out_format,
                    value="text").grid(column=0, row=8, sticky="w", padx=6)

    ttk.Button(frm_exit, text="Exit", command=root.destroy).grid(column=0,
                                        row=0, sticky=("s", "e", "w"), padx=6, pady=(10, 6))

    # -------------------------------------------------------------------------
    # Bindings (update on selection, Enter, or focus-out)
    # -------------------------------------------------------------------------

    def do_populate() -> None:
        populate(
            cmbo_url=cmbo_url,
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

    ui.transcript_type.trace_add("write", on_format_change)
    ui.out_format.trace_add("write", on_format_change)

    root.mainloop()


if __name__ == "__main__":
    main()
