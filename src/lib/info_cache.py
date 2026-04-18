""" 
    Tracks the history of YouTube sources (video URLs) and their metadata, 
    with a simple file-based cache.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from yt_lib.yt_ids import YoutubeIdKind, extract_video_id
from yt_lib.ytdlp_info import (
                                YtdlpInfo,
                                fetch_YtdlpInfo_object,
                                write_info,
                                read_YtdlpInfo
                            )
from yt_lib.utils.log_utils import get_logger
from .app_context import RunContextStore


logger = get_logger(__name__)


def filetime_to_datetime(file: Path) -> datetime:
    """ Convert a file's modification time to a timezone-aware datetime (UTC).
        Args:
            file: A Path object representing the file to check.
        Returns:
            A datetime object representing the file's modification time in UTC.
    """
    timestamp = file.stat().st_mtime
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


@dataclass(slots=True, frozen=True)
class YouTubeSource:
    """ Represents a YouTube source with its ID, URL, and title."""
    kind: YoutubeIdKind
    id: str
    url: str
    title: str

    @classmethod
    def from_ytdlpinfo(cls, *, info: YtdlpInfo) -> YouTubeSource:
        """ Grabs the data from data returned from the cache.
            Args:
                info: A YtdlpInfo object containing the metadata for a YouTube source.
            Returns:
                A YouTubeSource object populated with the data from the YtdlpInfo object.
        """
        return cls(
            kind=YoutubeIdKind.VIDEO,
            url=info.get("webpage_url") if info.get("webpage_url") else info.get("original_url"),
            id=info.get("id"),
            title=info.get("title"),
        )

def _atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """ Write text atomically by replacing a temp file in the same directory.
        Args:
            path: The path to write the text to.
            text: The text to write.
            encoding: The encoding to use when writing the text.
    """
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




class InfoManager:
    """
        Controls the caching and retrieval of YouTube video metadata (YtdlpInfo) Manages:
            - Fetching YouTube info for cache misses.
            - The size of the cache.
            - The cache history based on cache file mod time.
            - Returning the info for a cached entry
            - Providing a list of cached URLs and titles for UI prompts.
        Cache layout:
          <cache_dir>/<video_id>.info   (JSON serialized VideoMetadata)

        In-memory index:
          self.yt_source_list: list[tuple[mtime, YouTubeSource]] sorted newest->oldest,
          with Paths pointing to .info files.
    """

    # def __init__(self, *, app_name: str = "transcripts", start: Path | None = None) -> None:
    def __init__(self,rt_ctx_store: RunContextStore) -> None:
        """ Initialize the InfoManager with a reference to the RunContextStore for path management.
            Args:
                rt_ctx_store: The RunContextStore object that holds the application's paths.
        """
        self.ctx_store = rt_ctx_store
        self.cache_dir: Path = self.ctx_store.cache_dir
        self.yt_source_list: list[tuple[float, YouTubeSource]] = []
        self.refresh_index()

    # ----------------------------
    # Indexing / sorting
    # ----------------------------

    def refresh_index(self) -> None:
        """ Rebuild the in-memory file index from disk (newest -> oldest)."""
        entries: list[tuple[float, YouTubeSource]] = []
        for p in self.cache_dir.glob("*.json"):
            if not p.is_file():
                continue
            try:
                info = read_YtdlpInfo(p)
                yt_source: YouTubeSource = YouTubeSource.from_ytdlpinfo(info=asdict(info))
                entries.append((p.stat().st_mtime, yt_source))
            except OSError:
                continue

        entries.sort(key=lambda t: t[0], reverse=True)
        self.yt_source_list = entries

    def get_latest_file(self) -> Path | None:
        """ Return the newest .info file, or None if the cache is empty.
            Returns:
                The Path to the newest .info file, or None if no valid files are found.
        """
        yt_source: YouTubeSource  = self.yt_source_list[0][1] if self.yt_source_list else None
        if yt_source:
            return self.info_path_for(yt_source.id)
        return None

    def get_latest_ytdlpinfo(self) -> YtdlpInfo | None:
        """ Return YtdlpInfo from the newest cache entry, or None if none readable.
            Returns:
                A YtdlpInfo object from the newest cache entry, or None if no valid entries
                are found.
        """
        latest_file = self.get_latest_file()
        if not latest_file or not latest_file.is_file():
            return None
        return read_YtdlpInfo(latest_file)

    # ----------------------------
    # File naming + stale cleanup
    # ----------------------------

    def info_path_for(self, video_id: str) -> Path:
        """ Get the expected .info file path for a given video_id.
            Args:
                video_id: The YouTube video ID to get the .info path for.
            Returns:
                The Path to the expected .info file for the given video ID.
        """
        return self.cache_dir / f"{video_id}.json"

    def remove_stale_files_for_video_id(self, video_id: str, *, keep: Path | None = None) -> None:
        """ Remove stale cache artifacts for the same base video_id.
            Deletes any files in cache_dir whose name starts with '<video_id>.'
            (e.g. old '<video_id>.url', '<video_id>.json', '<video_id>.json.lock', etc.).
            Args:
                video_id: The YouTube video ID to remove stale files for.
                keep: An optional Path to a file to keep (e.g. the new .info file being written).
                      If provided, this file will not be deleted even if it matches the prefix.
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
        """ Prepend info_file to the top of the index and keep it sorted newest->oldest.
            Args:
                yt_source: The YouTubeSource object to add to the index.
        """
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

    def cache_ytdlpinfo(self, info: YtdlpInfo) -> None:
        """ Cache YtdlpInfo for a YouTube source.
            Args:
                info: The YtdlpInfo object to cache.

            Behavior:
              - determines a video_id (prefers yt_source.id; 
                falls back to extracting from URL if needed)
              - removes stale entries for the same base video_id
              - writes <video_id>.info (JSON VideoMetadata)
              - prepends the new entry to the in-memory index
        """
        # 20260206 MMH Don't want to clobber json file if it already exists.
        # If the video_id is the same but the URL is different, that’s a bit
        # weird but we can just update the metadata and keep the same .info file.

        # If your VideoMetadata.video_id should drive the filename, you can enforce it here:
        info_file = self.info_path_for(info.id)

       # Remove stale artifacts (including old .url caches) before writing.
        self.remove_stale_files_for_video_id(info.id, keep=info_file)
        # write_YtdlpInfo(info_file, info)
        write_info(info_file, info.raw)
        logger.info("Cached Ytdlp_info to %s.", info_file)

        yt_source = YouTubeSource.from_ytdlpinfo(info=asdict(info))
        self._prepend_to_index(yt_source)
        # return info_file

    # ----------------------------
    # Cropping cache
    # ----------------------------

    def crop_cache(self, num_entries: int = 10) -> None:
        """ Keep only the most recent `num_entries` entries; delete older artifacts.
            Args:
                num_entries: The number of most recent entries to keep in the cache. Must be >=
                    0. If 0, all entries will be removed.
        """
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
    # cached URL list retrieval
    # ----------------------------


    def get_ytdlpinfo(self, url: str) -> YtdlpInfo:
        """ Get YtdlpInfo for a URL, checking the cache for the url 
            and if found update the cache list.  If it is not in the cache 
            get it from yt-dlp and put it in the top of the list.
            Args:
                url: The YouTube video URL to get the YtdlpInfo for.
            Returns:
                A YtdlpInfo object containing the metadata for the given URL, either from cache
                or freshly fetched.
        """
        vid = extract_video_id(url)
        if not vid:
            raise ValueError(f"URL does not contain a Video Id. URL:  {url}")
        try:
            for _, yt_src in self.yt_source_list:
                if yt_src.id == vid:
                    info_file = self.info_path_for(yt_src.id)
                    if info_file.is_file():
                        try:
                            info_file.touch()  # update mtime to reflect recent access
                            self.refresh_index()  # re-sort index after mtime update
                            return read_YtdlpInfo(info_file)
                        except Exception as e:  # pylint: disable=broad-exception-caught
                            logger.warning("Error reading metadata from %s: %s", info_file, e)
                            break  # fallback to fetching fresh metadata
            # If we didn’t find a valid cache entry, fetch fresh metadata.
            new_info: YtdlpInfo = fetch_YtdlpInfo_object(url)
            self.cache_ytdlpinfo(new_info)
            return new_info

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error fetching YtdlpInfo for %s: %s", url, e)
            raise


    def get_cached_urls(self) -> list[str]:
        """ Return a list of URLs from the current cache entries, newest first.
            Returns:
                A list of URLs from the current cache entries, ordered from newest to oldest.
        """
        urls = []
        for _, yt_source in self.yt_source_list:
            try:
                urls.append(yt_source.url)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning("Error reading URL from %s: %s", yt_source, e)
                continue
        return urls

    def get_cached_prompts(self) -> list[dict[str,str]]:
        """ Return a list of title and URL tuples from the current cache entries, newest first.
            Returns:
                A list of dictionaries containing the title and URL for each cached entry,
                ordered from newest to oldest.
        """
        choices: list[dict[str,str]] = []

        for _, yt_source in self.yt_source_list:
            try:
                # List entries as Video ID: Title
                key = yt_source.id + ": " + yt_source.title
                choices.append({'title':key, 'url':yt_source.url})
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning("Error reading URL or Title from %s: %s", yt_source, e)
                continue
        return choices
