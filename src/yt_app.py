"""
Simple Tkinter app to fetch and view YouTube transcripts from local cache,
and display metadata + transcript in a GUI.

- Uses an InfoManager cache for URL history + metadata.
- Uses yt_lib transcript helpers for output formats.
- Keeps main() streamlined by using a small "view-model" dataclass (UiVars)
  that owns Tk variables and knows how to apply metadata to them.
"""

from __future__ import annotations


# from dataclasses import dataclass
# from pathlib import Path
from tkinter import Tk, Text # , StringVar, IntVar, DoubleVar, Menu, filedialog, messagebox
from tkinter import ttk
# from yt_lib.ytdlp_info import YtdlpInfo
from yt_lib.utils.log_utils import configure_logging, LogConfig, FileLogConfig, get_logger
from lib.app_context import create_runtime_context, RunContextStore
from lib.info_cache import InfoManager
from lib.ui_vars import UiVars, is_valid_youtube_url


APP_NAME = "yt_app"
APP_AUTHOR = "HenCode"

###############################################################################
#
# Context configuration to pass APP data/objects around without globals or tight
# coupling.
#
################################################################################


ctx = create_runtime_context(app_name = APP_NAME, app_author = APP_AUTHOR)
ctx_store = RunContextStore(ctx=ctx)

###############################################################################
#
# Logging setup: configure a logger for the app, with file output to an
# OS-appropriate user log directory.
#
################################################################################

log_cfg = LogConfig(root=APP_NAME)
file_log_conf = FileLogConfig(path = ctx_store.log_dir / "yt_app.log")

configure_logging(cfg=log_cfg,
                  file=file_log_conf,
                  force=True,
                  tee_console=False
                )
logger = get_logger(__name__)

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> None:
    """ Set up the GUI, load initial data, and bind events. """

    cache = InfoManager(ctx_store)

    root = Tk()
    root.title("yt_app")
    root.geometry("1100x700")  # prevents giant off-screen windows
    root.minsize(900, 500)

    # Single place for widget-bound vars
    ui_vars = UiVars(root=root, ctx=ctx_store, cache=cache)



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

    cmbo_url = ttk.Combobox(frm_url, textvariable=ui_vars.combo_url)
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
    ttk.Label(frm_title, textvariable=ui_vars.video_id).grid(column=1, row=0, columnspan=7, sticky="w")

    ttk.Label(frm_title, text="Title:").grid(column=0, row=1, sticky="w")
    ttk.Label(frm_title, textvariable=ui_vars.title).grid(column=1, row=1, columnspan=7, sticky="w")

    ttk.Label(frm_title, text="URL:").grid(column=0, row=2, sticky="w")
    ttk.Label(frm_title, textvariable=ui_vars.url).grid(column=1, row=2, columnspan=7, sticky="w")

    ttk.Label(frm_title, text="Transcript Type:").grid(column=0, row=3, sticky="w")
    ttk.Label(frm_title, textvariable=ui_vars.transcript_type).grid(column=1, row=3, sticky="w")

    ttk.Label(frm_title, text="Video Type:").grid(column=1, row=3, sticky="w")
    ttk.Label(frm_title, textvariable=ui_vars.video_type).grid(column=3, row=3, sticky="w")

    ttk.Label(frm_title, text="Video format:").grid(column=2, row=3, sticky="w")
    ttk.Label(frm_title, textvariable=ui_vars.video_format).grid(column=3, row=3, sticky="w")

    ttk.Label(frm_title, text="Video Resolution:").grid(column=0, row=4, sticky="w")
    ttk.Label(frm_title, textvariable=ui_vars.resolution).grid(column=1, row=4, sticky="w")

    ttk.Label(frm_title, text="fps:").grid(column=2, row=4, sticky="w")
    ttk.Label(frm_title, textvariable=ui_vars.fps).grid(column=3, row=4, sticky="w")

    ttk.Label(frm_title, text="Duration:").grid(column=4, row=4, sticky="w")
    ttk.Label(frm_title, textvariable=ui_vars.duration).grid(column=5, row=4, sticky="w")

    ttk.Label(frm_title, text="File Size:").grid(column=6, row=4, sticky="w")
    ttk.Label(frm_title, textvariable=ui_vars.file_size).grid(column=7, row=4, sticky="w")

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
    ui_vars.set_desc_widget(txt_dscr)

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

    ui_vars.set_transcript_widget(txt_out)

    # --- Right side controls ---
    frm_right.columnconfigure(0, weight=1)

    ttk.Button(frm_right, text="History").grid(column=0, row=0,
                                             sticky=("e", "w"), padx=6, pady=(6, 2))
    ttk.Label(frm_right, text="Transcript type:").grid(column=0,
                                                       row=1, sticky="w", padx=6, pady=(6, 2))
    ttk.Radiobutton(frm_right, text="Json", variable=ui_vars.transcript_type,
                    value="json").grid(column=0, row=2, sticky="w", padx=6)
    ttk.Radiobutton(frm_right, text="Text", variable=ui_vars.transcript_type,
                    value="transcript").grid(column=0, row=3, sticky="w", padx=6)
    ttk.Radiobutton(frm_right, text="Sentences", variable=ui_vars.transcript_type,
                    value="sentences").grid(column=0, row=4, sticky="w", padx=6)
    ttk.Label(frm_right, text="Output Format:").grid(column=0, row=6, sticky="w",
                                                     padx=6, pady=(6, 2))
    ttk.Radiobutton(frm_right, text="Markdown", variable=ui_vars.out_format,
                    value="markdown").grid(column=0, row=7, sticky="w", padx=6)
    ttk.Radiobutton(frm_right, text="text", variable=ui_vars.out_format,
                    value="text").grid(column=0, row=8, sticky="w", padx=6)

    ttk.Button(frm_exit, text="Exit", command=root.destroy).grid(column=0,
                                        row=0, sticky=("s", "e", "w"), padx=6, pady=(10, 6))

    ui_vars.clear()

    # -------------------------------------------------------------------------
    # Bindings (update on selection, Enter, or focus-out)
    # -------------------------------------------------------------------------

    def do_populate() -> None:
        ui_vars.ui_change()
        # Load choices into the combobox
        choices = cache.get_cached_urls()
        cmbo_url["values"] = choices


    cmbo_url.bind("<<ComboboxSelected>>", lambda _e: do_populate())
    cmbo_url.bind("<Return>", lambda _e: do_populate())
    cmbo_url.bind("<FocusOut>", lambda _e: do_populate())

    # Also repopulate if the user switches output format radios (handy UX)
    def on_format_change(*_args: object) -> None:
        # if there's a valid URL in the box, refresh the transcript area
        if is_valid_youtube_url(cmbo_url.get()):
            do_populate()

    ui_vars.transcript_type.trace_add("write", on_format_change)
    ui_vars.out_format.trace_add("write", on_format_change)

    root.mainloop()


if __name__ == "__main__":
    main()