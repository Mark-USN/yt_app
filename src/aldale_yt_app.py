"""Simple TUI app to fetch and view YouTube transcripts from local cache, and save them as markdown."""

from __future__ import annotations

# import sys
import json
import textwrap
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from prompt_toolkit.application import Application
from prompt_toolkit.input import create_input
from prompt_toolkit.output import create_output
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout
from prompt_toolkit.layout.containers import Float, FloatContainer, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.shortcuts import message_dialog
from prompt_toolkit.styles import Style
from prompt_toolkit.validation import ValidationError, Validator
from prompt_toolkit.widgets import Button, Dialog, Label, RadioList, TextArea
from yt_lib.yt_ids import extract_video_id, YtdlpMetadata
from yt_lib.yt_transcript import youtube_json, youtube_sentences, youtube_text
from yt_lib.utils.log_utils import LogConfig, configure_logging, get_logger, log_tree
from yt_lib.utils.paths import CachePaths, resolve_cache_paths, resolve_project_path
from lib.ui.file_save_dialog import FileSaveDialog, FileSaveDialogConfig
from lib.utils.info_cache import InfoManager, PromptChoice

configure_logging(LogConfig(level="INFO"))
logger = get_logger(__name__)


def format_as_json(segments: list[dict[str, Any]]) -> str:
    return json.dumps(segments, indent=2, ensure_ascii=False)


def wrap_very_long_lines(text: str, *, width: int = 120) -> str:
    """
    Old prompt_toolkit versions sometimes behave poorly when the buffer is effectively a single,
    gigantic “visual line” (e.g., transcript returned as one blob). This forces sane line breaks.

    Strategy: preserve existing newlines, but wrap any *individual* line that’s extremely long.
    """
    if not text:
        return text

    lines = text.splitlines(keepends=False)
    if not lines:
        return text

    # If the content is already reasonably line-broken, don’t touch it.
    max_len = max((len(ln) for ln in lines), default=0)
    if max_len <= 500:
        return text

    wrapped: list[str] = []
    for ln in lines:
        if len(ln) <= 500:
            wrapped.append(ln)
            continue

        # Wrap long lines without collapsing internal whitespace too aggressively.
        # (textwrap.fill will reflow whitespace; we keep it acceptable for transcripts.)
        wrapped.extend(
            textwrap.wrap(
                ln,
                width=width,
                break_long_words=False,
                break_on_hyphens=False,
                replace_whitespace=False,
                drop_whitespace=False,
            )
        )

    return "\n".join(wrapped)


class YouTubeUrlValidator(Validator):
    def validate(self, document: Document) -> None:
        text = document.text.strip()
        if not text:
            raise ValidationError(message="URL cannot be empty")

        parsed = urlparse(text)
        if not parsed.scheme or not parsed.netloc:
            raise ValidationError(message="Not a valid URL")

        if extract_video_id(text) is None:
            raise ValidationError(message="Not a valid YouTube URL", cursor_position=len(text))


class CacheChoiceCompleter(Completer):
    """Shows cached titles, inserts URL."""

    def __init__(self, choices: list[PromptChoice]) -> None:
        self._choices = choices

    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:  # noqa: ANN001
        typed = document.text.strip()
        typed_l = typed.lower()

        for c in self._choices:
            if typed and (typed_l not in c.title.lower()) and (typed_l not in c.url.lower()):
                continue

            yield Completion(
                text=c.url,
                start_position=-len(document.text),
                display=c.title,
                display_meta=c.url,
            )


@dataclass(slots=True)
class SavePayload:
    video_id: str
    title: str
    description: str
    displayed_text: str
    url: str | None = None
    output_type: str | None = None


def save_payload_to_markdown(path: Path, payload: SavePayload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    front_matter: list[str] = [
        "---",
        f"video_id: {payload.video_id}",
        f"title: {payload.title}",
    ]
    if payload.url:
        front_matter.append(f"url: {payload.url}")
    if payload.output_type:
        front_matter.append(f"output_type: {payload.output_type}")
    front_matter.append("---\n")

    body = (
        "\n".join(front_matter)
        + "## Description\n\n"
        + (payload.description.strip() + "\n\n" if payload.description.strip() else "\n")
        + "## Transcript / Output\n\n"
        + payload.displayed_text.rstrip()
        + "\n"
    )
    path.write_text(body, encoding="utf-8")


class ModalRadioDialog:
    """Simple in-app modal dialog returning a selected value via callback."""

    def __init__(
        self,
        *,
        app: Application,
        root_container: FloatContainer,
        title: str,
        text: str,
        values: list[tuple[str, str]],
        on_accept: Callable[[str | None], None],
        initial: str | None = None,
    ) -> None:
        self.app = app
        self.root_container = root_container
        self.on_accept = on_accept

        self._radio = RadioList(values=values)
        if initial is not None:
            try:
                self._radio.current_value = initial
            except Exception:
                pass

        self._kb = KeyBindings()

        @self._kb.add("escape")
        def _esc(event) -> None:  # noqa: ANN001
            self._cancel()

        @self._kb.add("enter")
        def _enter(event) -> None:  # noqa: ANN001
            self._ok()

        self._dialog = Dialog(
            title=title,
            body=HSplit([Label(text=text), self._radio], padding=1),
            buttons=[Button(text="OK", handler=self._ok), Button(text="Cancel", handler=self._cancel)],
            with_background=True,
        )

        self._float: Float | None = None
        self._old_kb = None
        self._old_focus = None

    def open(self) -> None:
        if self._float is not None:
            return

        self._float = Float(content=self._dialog)
        self.root_container.floats.append(self._float)

        self._old_focus = self.app.layout.current_window
        self._old_kb = self.app.key_bindings
        self.app.key_bindings = self._kb

        self.app.layout.focus(self._radio)
        self.app.invalidate()

    def close(self) -> None:
        if self._float is not None and self._float in self.root_container.floats:
            self.root_container.floats.remove(self._float)
        self._float = None

        if self._old_kb is not None:
            self.app.key_bindings = self._old_kb
        self._old_kb = None

        if self._old_focus is not None:
            try:
                self.app.layout.focus(self._old_focus)
            except Exception:
                pass
        self._old_focus = None

        self.app.invalidate()

    def _ok(self) -> None:
        value = self._radio.current_value
        self.close()
        self.on_accept(value)

    def _cancel(self) -> None:
        self.close()
        self.on_accept(None)


@dataclass(slots=True)
class AppState:
    url: str | None = None
    output_type: str = "json"  # "json" | "transcript" | "sentences"
    video_meta: YtdlpMetadata | None = None
    displayed_text: str = ""


def build_app() -> Application:
    cache = InfoManager()
    choices = cache.get_cached_prompts()

    history = InMemoryHistory()
    for c in choices:
        if c.url:
            history.append_string(c.url)

    state = AppState()

    style = Style.from_dict(
        {
            "muted": "fg:#888888",
            "title": "bold",
            "desc": "fg:#aaaaaa",
        }
    )

    url_input = TextArea(
        height=1,
        multiline=False,
        prompt="YouTube URL> ",
        completer=CacheChoiceCompleter(choices),
        history=history,
    )
    url_input.buffer.validator = YouTubeUrlValidator()
    url_input.validate_while_typing = False

    meta_title = TextArea(text="", height=1, focusable=False, style="class:title")
    meta_desc = TextArea(text="", height=4, focusable=False, style="class:desc", wrap_lines=True)

    # ✅ Output takes remaining space and scrolls
    output = TextArea(
        text="",
        wrap_lines=True,
        focus_on_click=True,
        read_only=True,
        scrollbar=True,
        height=Dimension(weight=1),
    )

    # ✅ Footer is a fixed-height Window (won't be overwritten)
    footer = Window(
        content=FormattedTextControl(
            "Keys: Enter=Fetch • Ctrl+O=Pick from cache • Ctrl+T=Output type • Ctrl+S=Save As • Ctrl+Q=Quit"
        ),
        height=Dimension.exact(1),
        style="class:muted",
    )

    root = FloatContainer(
        content=HSplit(
            [
                url_input,
                HSplit([meta_title, meta_desc]),
                output,
                footer,
            ]
        ),
        floats=[],
    )

    kb = KeyBindings()

    # IMPORTANT (Windows):
    # Explicit input/output required or prompt_toolkit may exit immediately.

    app = Application(
        layout=Layout(root),
        key_bindings=kb,
        full_screen=True,
        mouse_support=True,
        style=style,
        input=create_input(),
        output=create_output(),
    )

    def show_message(title: str, text: str) -> None:
        async def _run() -> None:
            await message_dialog(title=title, text=text).run_async()

        app.create_background_task(_run())

    def set_meta(vm: YtdlpMetadata | None) -> None:
        meta_title.text = (vm.title or "").strip() if vm else ""
        meta_desc.text = (vm.description or "").strip() if vm else ""

    def set_output(text: str, *, kind: str) -> None:
        # If transcript comes back as a “blob”, force line breaks so scrolling behaves.
        if kind == "transcript":
            text = wrap_very_long_lines(text, width=120)

        output.text = text
        state.displayed_text = text

        # Reset view to top after refresh
        try:
            output.buffer.cursor_position = 0
        except Exception:
            pass

        app.invalidate()

    def fetch_and_render(url: str) -> None:
        url = url.strip()
        if not url:
            return

        vm = cache.get_video_metadata(url)
        state.url = url
        state.video_meta = vm

        if vm is None:
            set_meta(None)
            set_output(
                "❌ No cached video metadata found for:\n"
                f"{url}\n\n"
                "Try a URL that has a cached .info/.json entry.",
                kind="error",
            )
            return

        set_meta(vm)

        try:
            match state.output_type:
                case "json":
                    segments = youtube_json(vm.video_id)
                    text = format_as_json(segments)
                    kind = "json"
                case "sentences":
                    text = youtube_sentences(vm.video_id)
                    kind = "sentences"
                case _:
                    text = youtube_text(vm.video_id)
                    kind = "transcript"
        except Exception as e:  # noqa: BLE001
            logger.exception("Transcript error")
            show_message("Transcript Error", str(e))
            return

        set_output(text, kind=kind)

    def current_payload() -> SavePayload:
        vm = state.video_meta
        vid = vm.video_id if vm is not None else (extract_video_id(state.url or "") or "")
        title = (vm.title if vm is not None else "") or ""
        desc = (vm.description if vm is not None else "") or ""
        return SavePayload(
            video_id=vid,
            title=title.strip(),
            description=desc.strip(),
            displayed_text=state.displayed_text,
            url=state.url,
            output_type=state.output_type,
        )

    def default_filename() -> str:
        vm = state.video_meta
        vid = vm.video_id if vm is not None else (extract_video_id(state.url or "") or "transcript")
        return f"{vid}.md"

    def do_save(path: Path) -> None:
        payload = current_payload()
        if not payload.displayed_text.strip():
            raise RuntimeError("Nothing to save yet. Fetch a transcript first.")
        save_payload_to_markdown(path, payload)

    save_dialog = FileSaveDialog(
        app=app,
        root_container=root,
        on_accept=do_save,
        config=FileSaveDialogConfig(
            title="Save Transcript",
            start_dir=(Path.home() / "Documents"),
            default_filename=default_filename(),
            allowed_suffixes={".md", ".txt"},
        ),
    )

    def open_pick_dialog() -> None:
        items: list[tuple[str, str]] = [("__NEW__", "➕ Enter a new URL…")]
        items.extend((c.url, c.title) for c in choices)

        def accepted(value: str | None) -> None:
            if value is None or value == "__NEW__":
                app.layout.focus(url_input)
                return
            url_input.text = value
            app.layout.focus(url_input)

        ModalRadioDialog(
            app=app,
            root_container=root,
            title="YouTube Source",
            text="Pick a cached video (title shown), or enter a new URL:",
            values=items,
            on_accept=accepted,
        ).open()

    def open_output_dialog() -> None:
        def accepted(value: str | None) -> None:
            if not value:
                return
            state.output_type = value
            if state.url:
                fetch_and_render(state.url)
                app.layout.focus(output)

        ModalRadioDialog(
            app=app,
            root_container=root,
            title="Output Type",
            text=f"Choose output format (current: {state.output_type})",
            values=[
                ("json", "JSON (segments)"),
                ("transcript", "Transcript (single block)"),
                ("sentences", "sentences (wrapped)"),
            ],
            on_accept=accepted,
            initial=state.output_type,
        ).open()

    def any_modal_open() -> bool:
        return save_dialog.is_open

    @kb.add("enter")
    def _enter(event) -> None:  # noqa: ANN001
        if any_modal_open():
            return
        if event.app.layout.current_control != url_input.control:
            return

        try:
            url_input.buffer.validate()
        except ValidationError:
            return
        except Exception:
            return

        fetch_and_render(url_input.text)
        event.app.layout.focus(output)

    @kb.add("c-o")
    def _pick(event) -> None:  # noqa: ANN001
        if any_modal_open():
            return
        open_pick_dialog()

    @kb.add("c-t")
    def _type(event) -> None:  # noqa: ANN001
        if any_modal_open():
            return
        open_output_dialog()

    @kb.add("c-s")
    def _save(event) -> None:  # noqa: ANN001
        if any_modal_open():
            return
        save_dialog.set_filename(default_filename())
        save_dialog.open()

    @kb.add("c-q")
    def _quit(event) -> None:  # noqa: ANN001
        event.app.exit()

    app.layout.focus(url_input)
    return app


def main() -> None:
    build_app().run()


if __name__ == "__main__":
    main()
