from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from prompt_toolkit.layout.containers import Float, FloatContainer, HSplit
from prompt_toolkit.widgets import Button, Dialog, Label, RadioList, TextArea


@dataclass(slots=True)
class FileSaveDialogConfig:
    title: str = "Save As"
    start_dir: Path | None = None
    default_filename: str = ""
    allowed_suffixes: set[str] | None = None  # e.g. {".md", ".txt"}


class FileSaveDialog:
    """A simple in-app TUI file picker for saving (modal-ish)."""

    _UP = "__UP__"
    _EMPTY = "__EMPTY__"

    def __init__(
        self,
        *,
        app: Application,
        root_container: FloatContainer,
        on_accept: Callable[[Path], None],
        config: FileSaveDialogConfig | None = None,
    ) -> None:
        self.app = app
        self.root_container = root_container
        self.on_accept = on_accept
        self.config = config or FileSaveDialogConfig()

        self.cwd: Path = (self.config.start_dir or Path.cwd()).expanduser().resolve()

        self.path_label = Label(text="")
        self.status_label = Label(text="")

        self.filename_input = TextArea(height=1, multiline=False)
        self.filename_input.text = self.config.default_filename

        # Value is either:
        #   - FileSaveDialog._UP sentinel
        #   - FileSaveDialog._EMPTY sentinel
        #   - a Path (directory or file)
        self.list_widget = RadioList(values=[(self._EMPTY, "(empty)")])

        if hasattr(self.list_widget, "show_scrollbar"):
            setattr(self.list_widget, "show_scrollbar", True)

        self._kb = KeyBindings()

        # Directory entry triggers: Enter, Right Arrow, Space
        @self._kb.add("enter")
        def _enter(event) -> None:  # noqa: ANN001
            self._enter_on_selection()

        @self._kb.add("right")
        def _right(event) -> None:  # noqa: ANN001
            self._enter_on_selection()

        @self._kb.add("space")
        def _space(event) -> None:  # noqa: ANN001
            self._enter_on_selection()

        @self._kb.add("escape")
        def _esc(event) -> None:  # noqa: ANN001
            self.close()

        @self._kb.add("backspace")
        @self._kb.add("left")
        def _go_up(event) -> None:  # noqa: ANN001
            self._go_up()

        self._float: Float | None = None
        self._old_kb: KeyBindings | None = None
        self._old_focus = None

        self.dialog = Dialog(
            title=self.config.title,
            body=HSplit(
                [
                    self.path_label,
                    self.list_widget,
                    Label(text="File name:"),
                    self.filename_input,
                    self.status_label,
                ],
                padding=1,
            ),
            buttons=[
                Button(text="Save", handler=self._save_clicked),
                Button(text="Cancel", handler=self.close),
            ],
            with_background=True,
        )

    @property
    def is_open(self) -> bool:
        return self._float is not None

    def open(self) -> None:
        if self.is_open:
            return

        self.status_label.text = ""
        self._refresh_entries()

        self._float = Float(content=self.dialog)
        self.root_container.floats.append(self._float)

        # Save focus and keybindings so we can restore them
        self._old_focus = self.app.layout.current_window
        self._old_kb = self.app.key_bindings
        self.app.key_bindings = merge_key_bindings([kb for kb in (self._old_kb, self._kb) if kb is not None])

        # Ensure the list actually has focus first (so Enter/Right/Space hit our bindings)
        self.app.layout.focus(self.list_widget)
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

    def set_filename(self, name: str) -> None:
        self.filename_input.text = name

    def set_directory(self, directory: Path) -> None:
        self.cwd = directory.expanduser().resolve()

    def _refresh_entries(self) -> None:
        self.path_label.text = f"Folder: {self.cwd}"

        values: list[tuple[object, str]] = []
        parent = self.cwd.parent
        if parent != self.cwd:
            values.append((self._UP, "⬆️  .. (parent folder)"))

        dirs: list[Path] = []
        files: list[Path] = []

        try:
            for p in self.cwd.iterdir():
                if p.name.startswith("."):
                    continue
                if p.is_dir():
                    dirs.append(p)
                elif p.is_file():
                    if self.config.allowed_suffixes is None or p.suffix.lower() in self.config.allowed_suffixes:
                        files.append(p)
        except Exception as e:  # noqa: BLE001
            if not values:
                values = [(self._EMPTY, "(empty)")]
            self.list_widget.values = values
            self.list_widget.current_value = values[0][0]
            self.status_label.text = f"Cannot read folder: {e}"
            self.app.invalidate()
            return

        dirs.sort(key=lambda x: x.name.casefold())
        files.sort(key=lambda x: x.name.casefold())

        for d in dirs:
            values.append((d, f"📁  {d.name}"))
        for f in files:
            values.append((f, f"📄  {f.name}"))

        if not values:
            values = [(self._EMPTY, "(empty)")]

        self.list_widget.values = values

        valid_values = {v for v, _ in values}
        if self.list_widget.current_value not in valid_values:
            self.list_widget.current_value = values[0][0]

        self.app.invalidate()

    def _enter_on_selection(self) -> None:
        value = self.list_widget.current_value
        if value is None:
            self.app.layout.focus(self.filename_input)
            return

        if value == self._UP:
            self._go_up()
            return

        if value == self._EMPTY:
            self.app.layout.focus(self.filename_input)
            return

        if isinstance(value, Path):
            if value.is_dir():
                self.cwd = value
                self._refresh_entries()
                # keep focus in the list for fast navigation
                self.app.layout.focus(self.list_widget)
                return

            if value.is_file():
                self.filename_input.text = value.name
                self.app.layout.focus(self.filename_input)
                return

        # fallback
        self.app.layout.focus(self.filename_input)

    def _go_up(self) -> None:
        parent = self.cwd.parent
        if parent == self.cwd:
            return
        self.cwd = parent
        self._refresh_entries()
        self.app.layout.focus(self.list_widget)

    def _save_clicked(self) -> None:
        raw_name = self.filename_input.text.strip().strip('"')
        if not raw_name:
            self.status_label.text = "Enter a file name."
            self.app.invalidate()
            return

        candidate = Path(raw_name).expanduser()
        path = candidate if candidate.is_absolute() else (self.cwd / candidate)

        allowed = self.config.allowed_suffixes
        if allowed is not None:
            suffix = path.suffix.lower()
            if suffix not in allowed:
                if suffix == "":
                    preferred = ".md" if ".md" in allowed else sorted(allowed)[0]
                    path = path.with_suffix(preferred)
                else:
                    self.status_label.text = f"File must be one of: {', '.join(sorted(allowed))}"
                    self.app.invalidate()
                    return

        if path.exists() and path.is_dir():
            self.status_label.text = "That name points to a folder, not a file."
            self.app.invalidate()
            return

        if path.exists():
            self._confirm_overwrite(path)
            return

        self._do_save(path)

    def _do_save(self, path: Path) -> None:
        try:
            self.on_accept(path)
        except Exception as e:  # noqa: BLE001
            self.status_label.text = f"Save failed: {e}"
            self.app.invalidate()
            return

        self.close()

    def _confirm_overwrite(self, path: Path) -> None:
        confirm_float: Float | None = None

        def yes() -> None:
            self._do_save(path)
            if confirm_float is not None and confirm_float in self.root_container.floats:
                self.root_container.floats.remove(confirm_float)
            self.app.invalidate()

        def no() -> None:
            if confirm_float is not None and confirm_float in self.root_container.floats:
                self.root_container.floats.remove(confirm_float)
            self.app.layout.focus(self.filename_input)
            self.app.invalidate()

        confirm = Dialog(
            title="Overwrite?",
            body=Label(text=f"'{path.name}' already exists. Overwrite?"),
            buttons=[Button(text="Yes", handler=yes), Button(text="No", handler=no)],
            with_background=True,
        )
        confirm_float = Float(content=confirm)
        self.root_container.floats.append(confirm_float)
        self.app.layout.focus(confirm)
        self.app.invalidate()
