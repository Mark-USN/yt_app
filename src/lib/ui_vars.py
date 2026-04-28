""" Holds all Tk variables that widgets bind to, and knows how to 
    apply metadata to them. 
"""

from __future__ import annotations

from urllib.parse import urlparse
import tkinter as tk
from tkinter import StringVar, Text 
from yt_lib.yt_ids import extract_video_id
from yt_lib.yt_transcript import youtube_json # , youtube_text, youtube_sentences
from yt_lib.ytdlp_info import YtdlpInfo
from yt_lib.utils.log_utils import get_logger
from yt_lib.utils.app_context import RunContextStore
from lib.info_cache import InfoManager
from lib.format_transcript import json_to_sentences, json_to_text, convert_json
from lib.display_field import DisplayField, DurationField, FileSizeField
from lib.print.layout_types import (
        RenderItem,
        LineItem,
        CenteredLineItem,
        ParagraphItem,
        BlocksItem
    )

logger = get_logger(__name__)

def is_valid_youtube_url(text: str) -> bool:
    """ Basic check for whether a URL is a valid YouTube video URL.
        Args:
            text: The URL to check.
        Returns:
            True if the URL is a valid YouTube video URL, False otherwise.
    """
    text = text.strip()
    if not text:
        return False

    parsed = urlparse(text)
    if not parsed.scheme or not parsed.netloc:
        return False

    return extract_video_id(text) is not None


# @dataclass(slots=True)
class UiVars:
    """ Holds all Tk variables that widgets bind to, and knows how to apply metadata to them.
        Also holds references to the RunContextStore, to determine file paths, and the InfoManager
        (cache), to get metadata for URLs.

        NOTE: The Discription and Transcript Text widgets are not stored as Tk variables, because
        unlike the basic TkVars, the widgets must be created and manuipulated directly to update
        their content. So instead, we store references to the Text widgets themselves, and update
        them manually when the metadata changes.
        Also, the Text windows are set to disabled by default, so any updates must temporarily
        enable them, update the text, then disable them again to prevent user editing.

        DisplayFields are used for all other metadata, which combine the raw value with formatting
        and units for display, and can be easily updated by setting their value and calling their
        render method.
    """
    root: tk
    ctx: RunContextStore
    cache: InfoManager
    combo_url: StringVar
    transcript_rb: StringVar
    video_id: DisplayField
    title: DisplayField
    url: DisplayField
    transcript_type: DisplayField
    ext: DisplayField
    video_format: DisplayField
    resolution: DisplayField
    fps: DisplayField
    duration: DurationField
    file_size: FileSizeField
    bit_rate: DisplayField
    transcript_json: str
    desc_txt: str
    transcript_txt: str
    desc_widget: Text | None
    transcript_widget: Text | None
    previous_url: str


    def __init__(
            self,
            root: tk.Misc,
            ctx: RunContextStore,
            cache: InfoManager,
        ) -> None:
        """ Initialize all variables and references.
            Args:
                root: The Tk root window, needed to create Tk variables.
                ctx: The RunContextStore, to determine file paths.
                cache: The InfoManager, to get metadata for URLs.        
        """
        self.win = root
        self.ctx = ctx
        self.cache = cache

        self.combo_url = StringVar(self.win, "")
        self.transcript_rb = StringVar(self.win, "Json")
        self.video_id = DisplayField.from_dict(
                data={
                    'ctx': self.ctx,
                    'label':"Video ID",
                    'var':StringVar(self.win, ""),
                }
            )
        self.title = DisplayField.from_dict(
                data={
                   'ctx': self.ctx,
                   'label':"Title",
                    'var':StringVar(self.win, ""),
                }
            )
        self.url = DisplayField.from_dict(
                data={
                    'ctx': self.ctx,
                    'label':"URL",
                    'var':StringVar(self.win, ""),
                }
            )
        self.transcript_type = DisplayField.from_dict(
                data={
                    'ctx': self.ctx,
                    'label':"Transcript Type",
                    # 'var':StringVar(self.win, "Json"),
                    'var':StringVar(self.win, self.transcript_rb.get()),
                }
            )
        # self.transcript_type.set("Json")
        self.ext = DisplayField.from_dict(
                data={
                    'ctx': self.ctx,
                    'label':"Extension",
                    'var':StringVar(self.win, ""),
                }
            )
        self.video_format = DisplayField.from_dict(
                data={
                    'ctx': self.ctx,
                    'label':"Video Format",
                    'var':StringVar(self.win, ""),
                }
            )
        self.resolution = DisplayField.from_dict(
                data={
                    'ctx': self.ctx,
                    'label':"Resolution",
                    'var':StringVar(self.win, ""),
                }
            )
        self.fps = DisplayField.from_dict(
                            data={
                                'ctx': self.ctx,
                                'label':"FPS",
                                'var':StringVar(self.win, ""),
                                'decimals':0,
                                'is_int':True,
                            }
            )
        self.duration = DurationField.from_dict(
                            data={
                                'ctx': self.ctx,
                                'label':"Duration",
                                'var':StringVar(self.win, ""),
                            }
            )
        self.file_size = FileSizeField.from_dict(
                            data={
                                'ctx': self.ctx,
                                'label':"File Size",
                                'var':StringVar(self.win, ""),
                            }
            )
        self.bit_rate = DisplayField.from_dict(
                            data={
                                'ctx':self.ctx,
                                'label':"Bit Rate",
                                'decimals':4,
                                'var':StringVar(self.win, ""),
                                'units':"Mbps",
                            }
            )
        self.transcript_json = ""
        self.desc_txt = """- Description -"""
        self.transcript_txt = """- Transcript -"""
        self.desc_widget = None
        self.transcript_widget = None
        self.previous_url = ""

    def set_desc_widget(self, widget: Text) -> None:
        """ Store a reference to the description Text widget, so we can 
            update it when metadata changes.
            Args:
                widget: The Text widget that displays the video description.
        """
        self.desc_widget = widget
        self.set_text(self.desc_widget, self.desc_txt)



    def set_transcript_widget(self, widget: Text) -> None:
        """ Store a reference to the transcript Text widget, so we can 
            update it when metadata changes
            Args:
                widget: The Text widget that displays the video transcript.
        """
        self.transcript_widget = widget
        self.set_text(self.transcript_widget, self.transcript_txt)


    def clear(self) -> None:
        """ Set default values for the widgets. """
        self.combo_url.set("")
        self.transcript_rb.set("Json")
        self.video_id.set("")
        self.title.set("")
        self.url.set("")
        self.transcript_type.set(self.transcript_rb.get())
        # self.out_format.set("markdown")
        self.ext.set("")
        self.resolution.set("")
        self.video_format.set("")
        self.fps.set(0)
        self.duration.set("00")
        self.file_size.set(0)
        self.bit_rate.set(0.0)
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

            Called whenever the URL changes, or the transcript type changes, to update all
            metadata fields and the transcript.
        """
        combo_url = self.combo_url.get().strip()
        if not combo_url:
            return
        if not is_valid_youtube_url(combo_url):
            return
        info: YtdlpInfo = self.cache.get_ytdlpinfo(combo_url)

        # Required
        self.transcript_type.set(self.transcript_rb.get())
        self.video_id.set(str(info.id).strip())
        self.title.set(str(info.title).strip())
        self.url.set(str(info.webpage_url).strip())

        # Optional / may be absent depending on your cache object
        self.ext.set(str(info.ext).strip())
        self.video_format.set(str(info.format_name or "").strip())
        self.resolution.set(str(info.best_format.computed_resolution) or "")

        self.fps.set(info.best_format.fps)

        # duration: store as string for display
        self.duration.set(info.selection_summary.duration_s)

        self.file_size.set(info.selection_summary.total_filesize_bytes)
        self.bit_rate.set(info.selection_summary.total_mbps_from_filesize)

        self.desc_txt = info.description.strip() if info.description else ""
        if self.desc_widget is not None:
            self.set_text(self.desc_widget, self.desc_txt)
        if combo_url != self.previous_url:
            self.previous_url = combo_url
            self.transcript_json = youtube_json(combo_url)
        # ---- transcript output ----
        match str(self.transcript_rb.get()).lower().strip():
            case "json":
                self.transcript_txt = convert_json(self.transcript_json)
            case "text":
                self.transcript_txt = json_to_text(self.transcript_json)
            case "sentences":
                self.transcript_txt = json_to_sentences(self.transcript_json)
            case _:
                self.transcript_txt = f"Unknown format: {self.transcript_type.get()}"

        if self.transcript_widget is not None:
            self.set_text(self.transcript_widget, self.transcript_txt)

    # -----------------------------------------------------------------------------
    # Small UI helpers
    # -----------------------------------------------------------------------------

    def set_text(self,widget: Text, value: str) -> None:
        """ Update disabled Text widgets. 
            Args:
                widget: The Text widget to update. Must be disabled, since it's only for display.
                value: The text to insert into the widget.
        """
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.see("1.0")
        widget.configure(state="disabled")

# pylint: disable=too-few-public-methods
class UiDoc:
    """ A simple class to hold the content to be printed, and convert it into a list of
        RenderItems for the print dialog.
    """

    def __init__(self, ui_vars:UiVars):
        """ Initialize the document content from the UiVars. """
        self.ui: UiVars = ui_vars
        self.lines: list[RenderItem] = []
        self.lines.append(CenteredLineItem(f"Transcript of Youtube video {self.ui.video_id.get()}"))
        self.lines.append(LineItem(self.ui.title.var.get()))
        self.lines.append(LineItem(self.ui.url.var.get()))
        self.lines.append(LineItem(self.ui.video_format.var.get()))
        self.lines.append(BlocksItem(
            [
                self.ui.video_id.var.get(),
                self.ui.transcript_type.var.get(),
                self.ui.ext.var.get(),
                self.ui.resolution.var.get(),
                self.ui.fps.var.get(),
                self.ui.duration.var.get(),
                self.ui.file_size.var.get(),
                self.ui.bit_rate.var.get()
            ]
        ))

        self.lines.append(LineItem("Description:"))
        self.lines.append(ParagraphItem(self.ui.desc_txt.splitlines()))
        self.lines.append(LineItem("Transcript:"))
        self.lines.append(ParagraphItem(self.ui.transcript_txt.splitlines()))

    def get(self) -> list[RenderItem]:
        """ Get the content of the document as a list of RenderItems, which can be passed to the
            print dialog.
        """
        return self.lines
