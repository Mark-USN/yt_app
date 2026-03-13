""" ui_info.py
    Module to handle mapping raw yt-dlp info dicts into compact, UI-friendly metadata objects.
"""


from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import logging
from typing import Any
from yt_lib.ytdlp_info import (
                YtdlpInfo,
                fetch_ytdlp_info_object,
                YtdlpFormat,
                # StreamEstimate,
                # SelectionSummary,
                # estimate_stream,
                summarize_selection,
                pick_selected_formats,
                pick_best_format,
                split_selected_streams,
            )
from yt_lib.utils.log_utils import get_logger


logger = get_logger(__name__)

# -----------------------------------------------------------------------------
# Small typed coercion helpers
# -----------------------------------------------------------------------------

def _as_str(value: Any, default: str | None = None) -> str | None:
    """Return a non-empty string, else default."""
    return value if isinstance(value, str) and value else default


def _as_int(value: Any, default: int | None = None) -> int | None:
    """Return an int, excluding bool, else default."""
    if isinstance(value, bool):
        return default
    return value if isinstance(value, int) else default


def _as_float(value: Any, default: float | None = None) -> float | None:
    """Return a float from int/float, else default."""
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        return float(value)
    return default





# -----------------------------------------------------------------------------
# Compact metadata model for UI / cache / CSV use
# -----------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class UiMetadata:
    """
    Compact, UI-friendly metadata snapshot.

    This preserves the most useful normalized values for display, CSV export,
    caching, or quick summaries without forcing all callers to inspect raw info.
    """

    # Identity / display
    url: str = " - "
    video_id: str = " - "
    title: str = " - "
    description: str = " - "
    channel: str = " - "
    upload_date: str = " - "
    webpage_url: str = " - "

    # Media selection summary
    duration: int = 0
    ext: str = " - "
    format_id: str = " - "
    format_note: str = " - "
    video_format: str = " - "
    resolution: str = " - "
    fps: int = 0
    filesize: int = 0

    # Codec / bitrate
    vcodec: str = " - "
    acodec: str = " - "
    tbr_kbps: float = 0.0

    # Optional raw info for debugging / later extraction
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def blank(cls) -> UiMetadata:
        """Return a placeholder object suitable for initial UI state."""
        return cls()

    @classmethod
    def from_info(
        cls,
        info: dict[str, Any],
        *,
        url_fallback: str = "",
        include_raw: bool = False,
        copy_raw: bool = False,
        prefer_selected: bool = True,
    ) -> UiMetadata:
        """
        Build compact metadata from raw yt-dlp info.

        Args:
            url_fallback:
                Used if yt-dlp did not provide a stable URL field.
            include_raw:
                Whether to include the raw info dict on the result.
            copy_raw:
                Deep-copy raw info if storing it.
            prefer_selected:
                If True, use the explicitly selected formats first.
                If False, fall back immediately to heuristic best format.
        """
        if not isinstance(info, dict):
            raise TypeError(f"info must be dict[str, Any], got {type(info).__name__}")

        raw: dict[str, Any] = {}
        if include_raw:
            raw = deepcopy(info) if copy_raw else info

        duration = _as_int(info.get("duration"), 0) or 0

        selected = pick_selected_formats(info) if prefer_selected else []
        video_sel, audio_sel, muxed_sel = split_selected_streams(selected)
        best = pick_best_format(info)

        # Choose the most useful display format source.
        # Priority:
        # 1) selected muxed
        # 2) selected video-only
        # 3) heuristic best format
        primary = muxed_sel or video_sel or best

        url = (
            _as_str(info.get("webpage_url"))
            or _as_str(info.get("original_url"))
            or url_fallback
            or " - "
        )

        video_format = (
            _as_str(info.get("format"))
            or _as_str(info.get("format_id"))
            or " - "
        )

        format_id = (
            primary.format_id
            or _as_str(info.get("format_id"))
            or " - "
        )

        format_note = (
            primary.format_note
            or primary.format_name
            or _as_str(info.get("format"))
            or " - "
        )

        ext = primary.ext or _as_str(info.get("ext")) or " - "
        resolution = primary.computed_resolution if primary else None
        fps = int(primary.fps) if primary and primary.fps is not None else 0

        # Filesize:
        # - muxed selected size if present
        # - video+audio selected sizes summed
        # - primary best size
        # - top-level info size
        filesize: int = 0
        if muxed_sel and muxed_sel.best_filesize is not None:
            filesize = muxed_sel.best_filesize
        else:
            v_size = video_sel.best_filesize if video_sel else None
            a_size = audio_sel.best_filesize if audio_sel else None
            if v_size is not None and a_size is not None:
                filesize = v_size + a_size
            else:
                filesize = (
                    v_size
                    or a_size
                    or (primary.best_filesize if primary else None)
                    or _as_int(info.get("filesize"), 0)
                    or _as_int(info.get("filesize_approx"), 0)
                    or 0
                )

        # Codec selection:
        # - for separate selection, prefer video codec from video stream and
        #   audio codec from audio stream
        # - otherwise use primary stream fields
        vcodec = (
            (video_sel.vcodec if video_sel else None)
            or (primary.vcodec if primary else None)
            or " - "
        )
        acodec = (
            (audio_sel.acodec if audio_sel else None)
            or (primary.acodec if primary else None)
            or " - "
        )

        # Total bitrate:
        # - for separate selected streams sum both tbr values
        # - otherwise use the primary stream tbr
        tbr_kbps = 0.0
        if video_sel or audio_sel:
            tbr_kbps = (
                (video_sel.tbr_kbps if video_sel and video_sel.tbr_kbps is not None else 0.0)
                + (audio_sel.tbr_kbps if audio_sel and audio_sel.tbr_kbps is not None else 0.0)
            )
        elif primary and primary.tbr_kbps is not None:
            tbr_kbps = primary.tbr_kbps

        return cls(
            url=url,
            video_id=_as_str(info.get("id")) or " - ",
            title=_as_str(info.get("title")) or " - ",
            description=_as_str(info.get("description")) or " - ",
            channel=(
                _as_str(info.get("channel"))
                or _as_str(info.get("uploader"))
                or " - "
            ),
            upload_date=_as_str(info.get("upload_date")) or " - ",
            webpage_url=_as_str(info.get("webpage_url")) or " - ",
            duration=duration,
            ext=ext,
            format_id=format_id,
            format_note=format_note,
            video_format=video_format,
            resolution=resolution or " - ",
            fps=fps,
            filesize=filesize,
            vcodec=vcodec,
            acodec=acodec,
            tbr_kbps=tbr_kbps,
            raw=raw,
        )

    @property
    def filesize_mib(self) -> float:
        """File size in MiB."""
        return self.filesize / (1024.0 * 1024.0)

    @property
    def mbps_estimated(self) -> float:
        """Bitrate estimate in Mbps based on total tbr."""
        return self.tbr_kbps / 1024.0


# -----------------------------------------------------------------------------
# High-level convenience APIs
# -----------------------------------------------------------------------------


def fetch_ui_metadata(
    url: str,
    *,
    format_selector: str = "bestvideo+bestaudio/best",
    include_raw: bool = False,
    copy_raw: bool = False,
    prefer_selected: bool = True,
    extra_options: dict[str, Any] | None = None,
) -> UiMetadata:
    """
    Fetch yt-dlp info and return a compact metadata snapshot.

    This is the most convenient function for UI code.
    """
    info = fetch_ytdlp_info_object(
        url,
        format_selector=format_selector,
        extra_options=extra_options,
    )
    return UiMetadata.from_info(
        info,
        url_fallback=url,
        include_raw=include_raw,
        copy_raw=copy_raw,
        prefer_selected=prefer_selected,
    )
