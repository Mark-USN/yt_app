"""
app_context.py

Module to hold global constants and shared objects.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platformdirs import PlatformDirs


@dataclass(slots=True, frozen=True)
class RuntimeContext:
    """Application runtime context, including platform-specific directories."""

    app_name: str
    app_author: str
    cache_dir: Path
    config_dir: Path
    data_dir: Path
    state_dir: Path
    log_dir: Path
    documents_dir: Path


def create_runtime_context(app_name: str, app_author: str) -> RuntimeContext:
    """Create a RuntimeContext with platform-specific directories."""
    pd = PlatformDirs(appname=app_name, appauthor=app_author)

    return RuntimeContext(
        app_name=app_name,
        app_author=app_author,
        cache_dir=Path(pd.user_cache_dir),
        config_dir=Path(pd.user_config_dir),
        data_dir=Path(pd.user_data_dir),
        state_dir=Path(pd.user_state_dir),
        log_dir=Path(pd.user_log_dir),
        documents_dir=Path(pd.user_documents_dir),
    )


@dataclass(slots=True)
class RunContextStore:
    """
    Store for RuntimeContext, allowing convenient shared access
    to application context information.
    """

    ctx: RuntimeContext

    @property
    def app_name(self) -> str:
        """Return the application name."""
        return self.ctx.app_name

    @property
    def app_author(self) -> str:
        """Return the application author."""
        return self.ctx.app_author

    @property
    def cache_dir(self) -> Path:
        """Return the cache directory."""
        path = self.ctx.cache_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def config_dir(self) -> Path:
        """Return the config directory."""
        path = self.ctx.config_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def data_dir(self) -> Path:
        """Return the data directory."""
        path = self.ctx.data_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def state_dir(self) -> Path:
        """Return the state directory."""
        path = self.ctx.state_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def log_dir(self) -> Path:
        """Return the log directory."""
        path = self.ctx.log_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def documents_dir(self) -> Path:
        """Return the documents directory."""
        path = self.ctx.documents_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    def documents_path(self, file_path: str) -> Path:
        """Return the transcript file path for a given video ID."""
        return self.documents_dir / file_path

    def transcript_dir(self) -> Path:
        """Return the transcript directory, creating it if necessary."""
        path = self.data_dir / "transcripts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def transcript_path(self, video_id: str) -> Path:
        """Return the transcript file path for a given video ID."""
        return self.transcript_dir() / f"{video_id}.json"

    def vid_info_dir(self) -> Path:
        """Return the video info directory, creating it if necessary."""
        path = self.cache_dir / "vid_info"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def vid_info_path(self, video_id: str) -> Path:
        """Return the video info file path for a given video ID."""
        return self.vid_info_dir() / f"{video_id}.json"
