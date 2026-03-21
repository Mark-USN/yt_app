""" Holds all Tk variables that widgets bind to, and knows how to 
    apply metadata to them. 
"""

from __future__ import annotations

# from functools import cache
import time
# import json
# from dataclasses import dataclass
# from pathlib import Path
from urllib.parse import urlparse
# from functools import partial
from tkinter import Tk, StringVar, IntVar, DoubleVar, Text # , Toplevel, filedialog, messagebox
# from tkinter import ttk
from yt_lib.yt_ids import extract_video_id
from yt_lib.yt_transcript import youtube_json # , youtube_text, youtube_sentences
from yt_lib.ytdlp_info import YtdlpInfo
from yt_lib.utils.log_utils import get_logger
from lib.app_context import RunContextStore
from lib.info_cache import InfoManager
from lib.format_transcript import json_to_sentences, json_to_text, convert_json



logger = get_logger(__name__)

def format_hms(duration: int) -> str:
    """ Turn seconds into hours:minutes:seconds. """
    return time.strftime("%H:%M:%S", time.gmtime(duration))


def is_valid_youtube_url(text: str) -> bool:
    """ Basic check for whether a URL is a valid YouTube video URL. """
    text = text.strip()
    if not text:
        return False

    parsed = urlparse(text)
    if not parsed.scheme or not parsed.netloc:
        return False

    return extract_video_id(text) is not None




# @dataclass(slots=True)
class UiVars:
    """ Holds all Tk variables that widgets bind to, and knows how to apply metadata to them."""
    root: Tk
    ctx: RunContextStore
    cache: InfoManager
    combo_url: StringVar
    video_id: StringVar
    title: StringVar
    url: StringVar
    transcript_type: StringVar
    out_format: StringVar
    video_type: StringVar
    video_format: StringVar
    resolution: StringVar
    fps: DoubleVar
    duration: StringVar
    file_size: IntVar
    transcript_json: str
    desc_txt: str
    transcript_txt: str
    desc_widget: Text | None
    transcript_widget: Text | None
    previous_url: str



    def __init__(
            self,
            root: Tk,
            ctx: RunContextStore,
            cache: InfoManager,
        ) -> None:
        self.win = root
        self.ctx = ctx
        self.cache = cache

        self.combo_url = StringVar(self.win, "")
        self.video_id = StringVar(self.win, "")
        self.title = StringVar(self.win, "")
        self.url = StringVar(self.win, "")
        self.transcript_type = StringVar(self.win, "json")
        self.out_format = StringVar(self.win, "markdown")
        self.video_type = StringVar(self.win, "")
        self.video_format = StringVar(self.win, "")
        self.resolution = StringVar(self.win, "")
        self.fps = DoubleVar(self.win, 0.0)
        self.duration = StringVar(self.win, "0")
        self.file_size = IntVar(self.win, 0)
        self.transcript_json = ""
        self.desc_txt = """- Description -"""
        self.transcript_txt = """- Transcript -"""
        self.desc_widget = None
        self.transcript_widget = None
        self.previous_url = ""



    def set_desc_widget(self, widget: Text) -> None:
        """ Store a reference to the description Text widget, so we can update it when metadata changes. """
        self.desc_widget = widget
        self.set_text(self.desc_widget, self.desc_txt)



    def set_transcript_widget(self, widget: Text) -> None:
        """ Store a reference to the transcript Text widget, so we can update it when metadata changes """
        self.transcript_widget = widget
        self.set_text(self.transcript_widget, self.transcript_txt)





    def clear(self) -> None:
        """ Set default values for the widgets. """
        self.combo_url.set("")
        self.video_id.set("")
        self.title.set("")
        self.url.set("")
        self.transcript_type.set("json")
        self.out_format.set("markdown")
        self.video_type.set("")
        self.resolution.set("")
        self.video_format.set("")
        self.fps.set(0.0)
        self.duration.set("")
        self.file_size.set(0)
        self.transcript_json = ""
        self.desc_txt = """- Description -"""
        if self.desc_widget is not None:
            self.set_text(self.desc_widget, self.desc_txt)
        self.transcript_txt = """- Transcript -"""
        if self.transcript_widget is not None:
            self.set_text(self.transcript_widget, self.transcript_txt)
        self.previous_url = ""

    # -----------------------------------------------------------------------------
    # Controller/update function
    # -----------------------------------------------------------------------------


    def ui_change(self) -> None:
        """
        Convert/cache metadata -> widget variables.
        Keep ALL mapping/formatting rules here.
        """
        combo_url = self.combo_url.get().strip()
        if not combo_url:
            return
        if not is_valid_youtube_url(combo_url):
            return
        info: YtdlpInfo = self.cache.get_YtdlpInfo(combo_url)

        # Required

        self.video_id.set(str(info.id).strip())
        self.title.set(str(info.title).strip())
        self.url.set(str(info.webpage_url).strip())

        # Optional / may be absent depending on your cache object
        self.video_type.set(str(info.selection_summary.overall_format).strip())
        self.video_format.set(str(info.format_name or "").strip())
        self.resolution.set(str(getattr(info, "resolution", "") or ""))

        fps = info.best_format.fps
        try:
            self.fps.set(float(fps) if fps is not None else 0.0)
        except (TypeError, ValueError):
            self.fps.set(0.0)

        # duration: store as string for display
        self.duration.set(format_hms(info.selection_summary.duration_s))

        self.file_size.set(info.best_format.best_filesize)
        self.desc_txt = info.description.strip() if info.description else "- Description -"
        if self.desc_widget is not None:
            self.set_text(self.desc_widget, self.desc_txt)
        if combo_url != self.previous_url:
            self.previous_url = combo_url
            self.transcript_json = youtube_json(combo_url)
        # ---- transcript output ----
        match self.transcript_type.get().strip():
            case "json":
                self.transcript_txt = convert_json(self.transcript_json)
            case "transcript":
                self.transcript_txt = json_to_text(self.transcript_json)
            case "sentences":
                self.transcript_txt = json_to_sentences(self.transcript_json)
            case _:
                self.transcript_txt = f"Unknown format: {self.transcript_type.get()}"

        if self.transcript_widget != None:
            if not self.transcript_txt.strip():
                self.transcript_txt = "- Transcript -"
            self.set_text(self.transcript_widget, self.transcript_txt)




    # -----------------------------------------------------------------------------
    # Small UI helpers
    # -----------------------------------------------------------------------------


    def set_text(self,widget: Text, value: str) -> None:
        """ Update disabled Text widgets. """
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.see("1.0")
        widget.configure(state="disabled")






