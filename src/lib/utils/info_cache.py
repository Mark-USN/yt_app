from __future__ import annotations
 
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
import json
import textwrap
# import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable
from yt_dlp import YoutubeDL
from yt_lib.yt_ids import YtdlpMetadata, YoutubeIdKind, extract_video_id
from yt_lib.utils.paths import resolve_cache_paths
from yt_lib.utils.log_utils import get_logger, log_tree

logger = get_logger(__name__)


def filetime_to_datetime(file: Path) -> datetime:
    """Convert a file's modification time to a timezone-aware datetime (UTC)."""
    timestamp = file.stat().st_mtime
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


@dataclass(slots=True, frozen=True)
class YouTubeSource:
    kind: YoutubeIdKind
    id: str
    url: str
    title: str
 
    @classmethod
    def from_VideoMetadata(cls, *, meta: dict[str, object]) -> YouTubeSource:
        return cls(
            kind=YoutubeIdKind.VIDEO,
            url=meta["url"],
            id=meta["video_id"],
            title=meta["title"],
        )

@dataclass(slots=True)
class PromptChoice:
    title: str
    url: str

def _atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Write text atomically by replace()'ing a temp file in the same directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w",
        delete=False,
        dir=path.parent,
        encoding=encoding,
        newline="\n",
    ) as tf:
        tmp = Path(tf.name)
        tf.write(text)
        tf.flush()
    tmp.replace(path)


def _video_metadata_to_json(meta: YtdlpMetadata) -> str:
    # Keep it human-readable and stable for diffs.
    return json.dumps(asdict(meta), ensure_ascii=False, indent=2)


def _video_metadata_from_json(text: str) -> YtdlpMetadata:
    """
    Load VideoMetadata from JSON while tolerating future added fields
    (e.g., 'web_url') or other extras.
    """
    raw = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError("Expected JSON object for VideoMetadata.")

    allowed = {f.name for f in fields(YtdlpMetadata)}
    filtered = {k: v for k, v in raw.items() if k in allowed}

    # This will still raise if required fields are missing; that’s good—corrupt cache should fail loudly.
    return YtdlpMetadata(**filtered)  # pyright: ignore[reportArgumentType]


class InfoManager:
    """
    Cache layout:
      <cache_dir>/<video_id>.info   (JSON serialized VideoMetadata)

    In-memory index:
      self.yt_source_list: list[tuple[mtime, YouTubeSource]] sorted newest->oldest,
      with Paths pointing to .info files.
    """

    def __init__(self, *, app_name: str = "transcripts", start: Path | None = None) -> None:
        start = start or Path(__file__)
        self.cache_dir: Path = resolve_cache_paths(app_name=app_name, start=start).app_cache_dir
        self.yt_source_list: list[tuple[float, YouTubeSource]] = []
        self.refresh_index()

    # ----------------------------
    # Indexing / sorting
    # ----------------------------

    def refresh_index(self) -> None:
        """Rebuild the in-memory file index from disk (newest -> oldest)."""
        entries: list[tuple[float, YouTubeSource]] = []
        for p in self.cache_dir.glob("*.info"):
            if not p.is_file():
                continue
            try:
                meta = _video_metadata_from_json(p.read_text(encoding="utf-8"))
                yt_source: YouTubeSource = YouTubeSource.from_VideoMetadata(meta=asdict(meta))
                entries.append((p.stat().st_mtime, yt_source))
            except OSError:
                continue

        entries.sort(key=lambda t: t[0], reverse=True)
        self.yt_source_list = entries

    def get_latest_file(self) -> Path | None:
        """Return the newest .info file, or None if the cache is empty."""
        yt_source: YouTubeSource  = self.yt_source_list[0][1] if self.yt_source_list else None
        if yt_source:
            return self.info_path_for(yt_source.id)
        return None

    def get_latest_metadata(self) -> YtdlpMetadata | None:
        """Return VideoMetadata from the newest cache entry, or None if none readable."""
        latest_file = self.get_latest_file()
        if not latest_file or not latest_file.is_file():
            return None
        try:
            return _video_metadata_from_json(latest_file.read_text(encoding="utf-8"))
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning("Error reading metadata from %s: %s", latest_file, e)
            return None

    # ----------------------------
    # File naming + stale cleanup
    # ----------------------------

    def info_path_for(self, video_id: str) -> Path:
        return self.cache_dir / f"{video_id}.info"

    def remove_stale_files_for_video_id(self, video_id: str, *, keep: Path | None = None) -> None:
        """
        Remove stale cache artifacts for the same base video_id.

        Deletes any files in cache_dir whose name starts with '<video_id>.'
        (e.g. old '<video_id>.url', '<video_id>.json', '<video_id>.json.lock', etc.).
        """
        prefix = f"{video_id}."
        for p in self.cache_dir.iterdir():
            if not p.is_file():
                continue
            if not p.name.startswith(prefix):
                continue
            if keep is not None and p.resolve() == keep.resolve():
                continue
            try:
                p.unlink(missing_ok=True)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning("Failed to delete stale cache file %s: %s", p, e)

        # Remove from index too
        self.yt_source_list = [(mt, yt_src) for (mt,yt_src) in 
                               self.yt_source_list if yt_src.id != video_id]

    def _prepend_to_index(self, yt_source: YouTubeSource) -> None:
        """Prepend info_file to the top of the index and keep it sorted newest->oldest."""
        try:
            info_file = self.info_path_for(yt_source.id)
            mtime = info_file.stat().st_mtime
        except OSError:
            self.refresh_index()
            return

        # Drop any existing entry for this video ID, then prepend.
        self.yt_source_list = [(mt, yt_src) for (mt, yt_src) in 
                               self.yt_source_list if yt_src.id != yt_source.id]
        self.yt_source_list.insert(0, (mtime, yt_source))

        # Optional: keep strict ordering if mtimes collide or clocks are weird
        self.yt_source_list.sort(key=lambda t: t[0], reverse=True)

    # ----------------------------
    # Write/update cache entries
    # ----------------------------

    def cache_VideoMetadata(self, meta: YtdlpMetadata) -> None:
        """
        Cache VideoMetadata for a YouTube source.

        Behavior:
          - determines a video_id (prefers yt_source.id; falls back to extracting from URL if needed)
          - removes stale entries for the same base video_id
          - writes <video_id>.info (JSON VideoMetadata)
          - prepends the new entry to the in-memory index
        """
        vid = meta.video_id
        # ensure it's a real video id if caller passed a URL or something odd
        if video_id := extract_video_id(vid) != vid:
            if video_id := extract_video_id(meta.url):
                meta.video_id = video_id
                vid = video_id
            else:
                raise ValueError(f"Could not extract video_id from {vid} or {meta.url}")

        # 20260206 MMH Don't want to clobber jason file if it already exists.
        # If the video_id is the same but the URL is different, that’s a bit
        # weird but we can just update the metadata and keep the same .info file.

 
        # If your VideoMetadata.video_id should drive the filename, you can enforce it here:
        info_file = self.info_path_for(vid)

       # Remove stale artifacts (including old .url caches) before writing.
        self.remove_stale_files_for_video_id(video_id, keep=info_file)

        _atomic_write_text(info_file, _video_metadata_to_json(meta), encoding="utf-8")
        logger.info("Cached YouTube VideoMetadata to %s.", info_file)

        yt_source = YouTubeSource.from_VideoMetadata(meta=asdict(meta))
        self._prepend_to_index(yt_source)
        # return info_file

    # ----------------------------
    # Cropping cache
    # ----------------------------

    def crop_cache(self, num_entries: int = 10) -> None:
        """Keep only the most recent `num_entries` entries; delete older artifacts."""
        if num_entries < 0:
            raise ValueError("num_entries must be >= 0")

        # Ensure we’re operating on a correctly sorted view
        self.yt_source_list.sort(key=lambda t: t[0], reverse=True)

        stale = self.yt_source_list[num_entries:]
        keep = self.yt_source_list[:num_entries]

        for _, yt_src in stale:
            vid = yt_src.id
            try:
                # Delete everything for that video_id (including .info itself)
                self.remove_stale_files_for_video_id(vid, keep=None)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning("Error deleting cache artifacts for %s: %s", vid, e)

        self.yt_source_list = keep

    # ----------------------------
    # yt-dlp metadata
    # ----------------------------

    
    def _fetch_yt_dlp_metadata(self, url: str) -> YtdlpMetadata:
        """Use yt-dlp to extract video metadata from a YouTube URL."""
#     def fetch_info(url: str) -> dict[str, object]:
        ydl_opts: dict[str, object] = {
            "quiet": True,
            "no_warnings": True,     # <- key
            "skip_download": True,
            "noprogress": True,
            "format": "bestvideo+bestaudio/best",
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not isinstance(info, dict):
            raise ValueError("yt-dlp returned non-dict info. %s", info)

        # youtube_ids.VideoMetadata.from_yt_dlp expects dict[str, object]
        meta = YtdlpMetadata.from_yt_dlp(url=url, info=info)  # pyright: ignore[reportArgumentType]
        self.cache_VideoMetadata(meta)

        return meta  # pyright: ignore[reportArgumentType]

    # ----------------------------
    # cached URL list retrieval
    # ----------------------------

    def get_cached_urls(self) -> list[str]:
        """Return a list of URLs from the current cache entries, newest first."""
        urls = []
        for _, yt_source in self.yt_source_list:
            try:
                urls.append(yt_source.url)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning("Error reading URL from %s: %s", yt_source, e)
                continue
        return urls

    def get_cached_prompts(self) -> list[PromptChoice]:
        """Return a list of title and URL tuples from the current cache entries, newest first."""
        choices: list[PromptChoice] = []

        for _, yt_source in self.yt_source_list:
            try:
                choices.append(PromptChoice(title=yt_source.title, url=yt_source.url))
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning("Error reading URL or Title from %s: %s", yt_source, e)
                continue
        return choices


    def get_video_metadata(self, url: str) -> YtdlpMetadata:
        """ Get VideoMetadata for a URL, checking the cache for the url 
            and if found update the cache list.  If it is not in the cache 
            get it from yt-dlp and put it in the top of the list.
        """
        try:
            vid = extract_video_id(url)
            if not vid:
                raise ValueError("URL does not contain a Video Id. %s", url)
            for _, yt_src in self.yt_source_list:
                if yt_src.id == vid:
                    info_file = self.info_path_for(yt_src.id)
                    if info_file.is_file():
                        try:
                            info_file.touch()  # update mtime to reflect recent access
                            self.refresh_index()  # re-sort index after mtime update
                            return _video_metadata_from_json(info_file.read_text(encoding="utf-8"))
                        except Exception as e:  # pylint: disable=broad-exception-caught
                            logger.warning("Error reading metadata from %s: %s", info_file, e)
                            break  # fallback to fetching fresh metadata
            # If we didn’t find a valid cache entry, fetch fresh metadata.
            return self._fetch_yt_dlp_metadata(url)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error fetching metadata for %s: %s", url, e)
            raise
