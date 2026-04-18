"""
app_context.py

Module to hold global constants and shared objects.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from babel.numbers import format_decimal
from platformdirs import PlatformDirs


_LOCALE_NAME_MAX_LENGTH = 85


def _round_half_up(value: float | Decimal) -> int:
    """ Round a number to the nearest integer using the "round half up" strategy.
        Args:
            value: The number to round, as a float or Decimal.
        Returns:
            The rounded integer value.
    """
    return int(
        Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


@dataclass(slots=True, frozen=True)
class RuntimeContext:
    """ Application runtime context, including platform-specific directories."""

    app_name: str
    app_author: str
    locale: str
    cache_dir: Path
    config_dir: Path
    data_dir: Path
    state_dir: Path
    log_dir: Path
    documents_dir: Path


def get_user_posix_locale() -> str:
    """ Return locale like 'en-US' using Windows API.
        Returns:
            The user's default locale in POSIX format (e.g., 'en-US').
    """
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    func = kernel32.GetUserDefaultLocaleName
    func.argtypes = [wintypes.LPWSTR, ctypes.c_int]
    func.restype = ctypes.c_int

    buf = ctypes.create_unicode_buffer(_LOCALE_NAME_MAX_LENGTH)

    if func(buf, len(buf)) == 0:
        raise OSError(ctypes.get_last_error(), "GetUserDefaultLocaleName failed")

    return buf.value



def detect_locale(default: str = "en_US") -> str:
    """ Detect system locale in a safe, Babel-compatible way.
        Args:
            default: The default locale to return if detection fails.
        Returns:
            The detected locale in a Babel-compatible format, or the default if detection fails.
    """
    try:
        loc = get_user_posix_locale()
        if not loc:
            return default
        # Convert from e.g. 'en-US'
        return loc.replace("-", "_")
    except Exception:                   # pylint: disable=broad-exception-caught
        return default


def create_runtime_context(app_name: str, app_author: str) -> RuntimeContext:
    """ Create a RuntimeContext with platform-specific directories.
        Args:
            app_name: The name of the application.
            app_author: The author of the application.
        Returns:
            A RuntimeContext object with platform-specific directories.
    """
    pd = PlatformDirs(appname=app_name, appauthor=app_author)

    return RuntimeContext(
        app_name=app_name,
        app_author=app_author,
        locale=detect_locale(),
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
        """ Return the application name."""
        return self.ctx.app_name

    @property
    def app_author(self) -> str:
        """ Return the application author."""
        return self.ctx.app_author

    @property
    def locale(self) -> str:
        """ Return the application locale."""
        return self.ctx.locale

    @property
    def cache_dir(self) -> Path:
        """ Return the cache directory."""
        path = self.ctx.cache_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def config_dir(self) -> Path:
        """ Return the config directory."""
        path = self.ctx.config_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def data_dir(self) -> Path:
        """ Return the data directory."""
        path = self.ctx.data_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def state_dir(self) -> Path:
        """ Return the state directory."""
        path = self.ctx.state_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def log_dir(self) -> Path:
        """ Return the log directory."""
        path = self.ctx.log_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def documents_dir(self) -> Path:
        """ Return the documents directory."""
        path = self.ctx.documents_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    def documents_path(self, file_path: str) -> Path:
        """ Return the document file path for a given file name.
            Args:
                file_path: The relative file path within the documents directory.
            Returns:
                The full path to the document file.
        """
        return self.documents_dir / file_path

    def transcript_dir(self) -> Path:
        """ Return the transcript directory, creating it if necessary."""
        path = self.data_dir / "transcripts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def transcript_path(self, video_id: str) -> Path:
        """ Return the transcript file path for a given video ID.
            Args:
                video_id: The ID of the video.
            Returns:
                The full path to the transcript file.
        """
        return self.transcript_dir() / f"{video_id}.json"

    def vid_info_dir(self) -> Path:
        """ Return the video info directory, creating it if necessary."""
        path = self.cache_dir / "vid_info"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def vid_info_path(self, video_id: str) -> Path:
        """ Return the video info file path for a given video ID.
            Args:
                video_id: The ID of the video.
            Returns:
                The full path to the video info file.
        """
        return self.vid_info_dir() / f"{video_id}.json"


    def format_number(
        self,
        value: int | float | Decimal | None,
        *,
        decimals: int = 2,
        as_int: bool = False,
    ) -> str:
        """ Format a number using Babel with locale awareness.
            Args:
                value: The number to format, which can be an int, float, Decimal, or None.
                decimals: The number of decimal places to display (default is 2).
                as_int: If True, round the number to the nearest integer and display without decimals.
            Returns:
                The formatted number as a string.

            - None → ""
            - decimals → fixed number of decimal places
            - as_int=True → round (half-up) and display as integer
        """

        if value is None:
            return ""

        # --- integer mode ---
        if as_int:
            if isinstance(value, float | Decimal):
                value = _round_half_up(value)

            return format_decimal(value, format="#,##0", locale=self.locale)

        # --- decimal mode ---
        pattern = "#,##0"
        if decimals > 0:
            pattern = f"#,##0.{'0' * decimals}"

        return format_decimal(value, format=pattern, locale=self.locale)
