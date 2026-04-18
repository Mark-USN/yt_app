"""
Simple Tkinter app to fetch and view YouTube transcripts from local cache,
and display metadata + transcript in a GUI.

- Uses an InfoManager cache for URL history + metadata.
- Uses yt_lib transcript to retrieve YouTube transcripts in the event of cache misses.
- Keeps main() streamlined by using a small "view-model" dataclass (UiVars)
  that owns Tk variables and knows how to apply metadata to them and modules to implement
  different parts of the UI.
"""

from __future__ import annotations

from tkinter import Tk, Text
from tkinter import ttk
from yt_lib.utils.log_utils import configure_logging, LogConfig, FileLogConfig, get_logger
from lib.app_context import create_runtime_context, RunContextStore
from lib.info_cache import InfoManager
from lib.ui_vars import UiVars, is_valid_youtube_url
from lib.history_dialog import HistoryDialog
from lib.menus import MenuCommands


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
    """Set up the GUI, load initial data, and bind events."""

    cache = InfoManager(ctx_store)
    root = Tk()
    root.title("yt_app")
    root.geometry("1100x700")
    root.minsize(900, 500)

    ui_vars = UiVars(root=root, ctx=ctx_store, cache=cache)

    MenuCommands(root=root, ctx=ctx_store, ui=ui_vars)

    # frame['padding'] = (left, top, right, bottom)
    main_frame = ttk.Frame(root, padding=(6, 6, 12, 12))
    main_frame.grid(column=0, row=0, sticky="nsew")

    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    main_frame.columnconfigure(0, weight=1)
    main_frame.rowconfigure(1, weight=1)  # description area expands
    main_frame.rowconfigure(2, weight=1)  # transcript area expands

    # -------------------------------------------------------------------------
    # Top section: left = URL + info, right = controls
    # -------------------------------------------------------------------------
    top_frame = ttk.Frame(main_frame, padding=(6, 6, 12, 12), borderwidth=1, relief="ridge")
    top_frame.grid(column=0, row=0, sticky="ew")

    top_frame.columnconfigure(0, weight=1)  # left side expands
    top_frame.columnconfigure(1, weight=0)  # right side stays natural size

    # --- URL row ---
    url_frame = ttk.Frame(top_frame, padding=(6, 6, 12, 12), borderwidth=1)
    url_frame.grid(column=0, row=0, sticky="ew", padx=6, pady=6)
    url_frame.columnconfigure(1, weight=1)

    ttk.Label(url_frame, text="URL=>").grid(column=0, row=0, sticky="w")

    cmbo_url = ttk.Combobox(url_frame, textvariable=ui_vars.combo_url)
    cmbo_url.grid(column=1, row=0, sticky="ew", padx=(6, 0))

    # Populate the URL dropdown with cached URLs. This is done here at setup, and also
    # after any URL selection or change, to ensure it stays up to date with the cache.
    choices = cache.get_cached_urls()
    cmbo_url["values"] = choices

    # --- Info frame ---
    # Holds information about the currently selected video/transcript, and updates
    # when the URL changes.
    info_frame = ttk.Frame(top_frame, padding=(6, 6, 12, 12), borderwidth=1, relief="ridge")
    info_frame.grid(column=0, row=1, sticky="nsew", padx=6, pady=(0, 6))

    for c in range(4):
        info_frame.columnconfigure(c, weight=1)
    # Uses the DisplayField class which combines the field's label, value, and formatting logic
    # into a single object that can be easily displayed in the UI. Each field is bound to a 
    # StringVar that updates automatically when the field's value changes.
    # The info frame is organized into rows and columns to display the video metadata in a clear
    # and structured way.
    ttk.Label(info_frame, textvariable=ui_vars.title.var).grid(column=0,
                    row=0, columnspan=4, sticky="w")
    ttk.Label(info_frame, textvariable=ui_vars.url.var).grid(column=0,
                    row=1, columnspan=4, sticky="w")
    ttk.Label(info_frame, textvariable=ui_vars.video_format.var).grid(column=0,
                    row=2, columnspan=4, sticky="w")
    ttk.Label(info_frame, textvariable=ui_vars.video_id.var).grid(column=0, row=3, sticky="w")
    ttk.Label(info_frame, textvariable=ui_vars.transcript_type.var).grid(column=1, row=3,
                sticky="w")
    ttk.Label(info_frame, textvariable=ui_vars.ext.var).grid(column=2, row=3, sticky="w")
    ttk.Label(info_frame, textvariable=ui_vars.resolution.var).grid(column=3, row=3, sticky="w")
    ttk.Label(info_frame, textvariable=ui_vars.file_size.var).grid(column=0, row=4, sticky="w")
    ttk.Label(info_frame, textvariable=ui_vars.duration.var).grid(column=1, row=4, sticky="w")
    ttk.Label(info_frame, textvariable=ui_vars.fps.var).grid(column=2, row=4, sticky="w")
    ttk.Label(info_frame, textvariable=ui_vars.bit_rate.var).grid(column=3, row=4, sticky="w")

    # --- Options frame on the right of URL + info ---
    # This frame holds controls for interacting with the app, like opening the history dialog and
    # selecting the transcript format.
    option_frame = ttk.Frame(top_frame, padding=(6, 6, 12, 12), borderwidth=1, relief="ridge")
    # pady(0, 6) aligns the bottom of this frame with the bottom of the info frame, and the top
    # with the top of the URL frame
    option_frame.grid(column=1, row=0, rowspan=2, sticky="ns", padx=6, pady=(0, 6))

    def open_history() -> None:
        prompts: list[dict[str,str]] = cache.get_cached_prompts()
        if not prompts:
            return
        dialog = HistoryDialog(root, prompts)
        root.wait_window(dialog)
        if dialog.result is not None:
            selected_url = dialog.result
            if selected_url:
                ui_vars.combo_url.set(selected_url)
                ui_vars.ui_change()


    ttk.Button(option_frame, text="History", command=open_history).grid(column=0,
                    row=0, sticky="ew", padx=6, pady=(6, 2))

    ttk.Label(option_frame, text="Transcript type:").grid(column=0,
                    row=1, sticky="w", padx=6, pady=(6, 2))
    ttk.Radiobutton(
        option_frame,
        text="Json",
        variable=ui_vars.transcript_rb,
        value="Json",
    ).grid(column=0, row=2, sticky="w", padx=6)
    ttk.Radiobutton(
        option_frame,
        text="Text",
        variable=ui_vars.transcript_rb,
        value="Text",
    ).grid(column=0, row=3, sticky="w", padx=6)
    ttk.Radiobutton(
        option_frame,
        text="Sentences",
        variable=ui_vars.transcript_rb,
        value="Sentences",
    ).grid(column=0, row=4, sticky="w", padx=6)


    # -------------------------------------------------------------------------
    # Description: shows the video description metadata, which is often useful 
    #   context for understanding the transcript. It is freeform and can
    #   contain nothing, or a lot of text, so it is in a scrollable Text widget.
    # -------------------------------------------------------------------------
    desc_frame = ttk.LabelFrame(main_frame, padding=(6, 6, 12, 12), text="Description")
    desc_frame.grid(column=0, row=1, sticky="nsew", padx=6, pady=(0, 6))
    desc_frame.columnconfigure(0, weight=1)
    desc_frame.rowconfigure(0, weight=1)

    txt_dscr = Text(desc_frame, wrap="word")
    scrl_dscr = ttk.Scrollbar(desc_frame, orient="vertical", command=txt_dscr.yview)
    txt_dscr.configure(yscrollcommand=scrl_dscr.set)

    txt_dscr.grid(column=0, row=0, sticky="nsew")
    scrl_dscr.grid(column=1, row=0, sticky="ns")
    ui_vars.set_desc_widget(txt_dscr)

    # -------------------------------------------------------------------------
    # Transcript: shows the transcript text in a scrollable Text widget. 
    #   The content and formatting of the transcript are selectable via the 
    #   "Transcript type" radio buttons, which update the transcript_type field
    #   in the info section and trigger a reload of the transcript content.
    # -------------------------------------------------------------------------
    out_frame = ttk.LabelFrame(main_frame, padding=(6, 6, 12, 12), text="Transcript")
    out_frame.grid(column=0, row=2, sticky="nsew", padx=6, pady=(0, 6))
    out_frame.columnconfigure(0, weight=1)
    out_frame.rowconfigure(0, weight=1)

    txt_out = Text(out_frame, wrap="word")
    scrl_out = ttk.Scrollbar(out_frame, orient="vertical", command=txt_out.yview)
    txt_out.configure(yscrollcommand=scrl_out.set)

    txt_out.grid(column=0, row=0, sticky="nsew")
    scrl_out.grid(column=1, row=0, sticky="ns")
    ui_vars.set_transcript_widget(txt_out)

    ui_vars.clear()

    def do_populate() -> None:
        """ Small helper to repopulate the UI upon a change in the URL or transcript type. """
        ui_vars.ui_change()
        cmbo_url["values"] = cache.get_cached_urls()

    cmbo_url.bind("<<ComboboxSelected>>", lambda _e: do_populate())
    cmbo_url.bind("<Return>", lambda _e: do_populate())
    cmbo_url.bind("<FocusOut>", lambda _e: do_populate())

    def on_format_change(*_args: object) -> None:
        """ Update the transcript type in the info section and reload the transcript when
            the transcript format radio buttons change. 
            Args:
                *_args: Required by the trace_add callback signature, but not used.
        """
        if is_valid_youtube_url(cmbo_url.get()):
            do_populate()
        else:
            # If the URL is not valid, just update the transcript type variable so it shows in the
            # info section.
            ui_vars.transcript_type.set(ui_vars.transcript_rb.get())

    ui_vars.transcript_rb.trace_add("write", on_format_change)

    root.mainloop()

if __name__ == "__main__":
    main()
