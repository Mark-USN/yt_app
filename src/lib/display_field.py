""" A DisplayField represents a single piece of information to be displayed in the UI.
    It combines data's title, a seperator and the formatted metadata and possibly units 
    into a single string that can be easily displayed in the UI. 
    It holds a reference to a StringVar that the UI widget binds to, and knows how to 
    format its value for display based on its metadata.

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NotRequired, TypedDict
from tkinter import StringVar
from yt_lib.utils.log_utils import get_logger
from lib.app_context import RunContextStore

logger = get_logger(__name__)


class DisplayFieldData(TypedDict):
    """ TypedDict for initializing a DisplayField from a dictionary. """
    ctx: RunContextStore
    label: str
    var: StringVar | None
    sep: NotRequired[str]
    units: NotRequired[str]
    decimals: NotRequired[int]
    is_int: NotRequired[bool]


@dataclass(slots=True)
class DisplayField:
    """ A DisplayField represents a single piece of information to be displayed in the UI.
        It lncludes the label, separator, units, and formatting options for the value.
        It holds a reference to a StringVar that the UI widget binds to, and knows how to 
        format its value for display based on its metadata.
    """
    ctx: RunContextStore
    label: str
    var: StringVar | None = None
    sep: str = ": "
    units: str = ""
    decimals: int = 2
    is_int: bool = False
    _value: float | int | str | None = field(default=None, init=False, repr=False)

    def set(self, value: float | int | str | None) -> None:
        """ Set the underlying value of the field and update the StringVar if it exists. """
        self._value = value
        if self.var is not None:
            self.var.set(self.render())

    def get(self) -> float | int | str | None:
        """ Get the underlying value of the field. """
        return self._value

    def render(self) -> str:
        """ Render the field's value as a string for display. """
        if self._value is None:
            value_text = ""
        elif isinstance(self._value, float):
            if self.is_int:
                value_text = self.ctx.format_number(
                    value=self._value,
                    decimals=0,
                    as_int=True,
                )
            else:
                value_text = self.ctx.format_number(
                    value=self._value,
                    decimals=self.decimals,
                )
        elif isinstance(self._value, int):
            value_text = self.ctx.format_number(
                value=self._value,
                decimals=0,
                as_int=True,
            )
        else:
            value_text = str(self._value)

        if self.units and value_text:
            return f"{self.label}{self.sep}{value_text} {self.units}"
        return f"{self.label}{self.sep}{value_text}"

    @classmethod
    def from_dict(cls, data: DisplayFieldData) -> DisplayField:
        """ Create a DisplayField from a dictionary of data. """
        return cls(
            ctx=data["ctx"],
            label=data["label"],
            var=data["var"],
            sep=data.get("sep", ": "),
            units=data.get("units", ""),
            decimals=data.get("decimals", 2),
            is_int=data.get("is_int", False),
        )

def format_hms(seconds: float | int | None) -> str:
    """ Format a duration in seconds into a human-readable string (H:MM:SS or M:SS). 
        Args:
            seconds: The duration in seconds to format. Can be a float, int, or None.
        Returns:
                A string representing the formatted duration.
        Notes:
            Solves a couple of issues with the built-in time formatting functions:
                Avoids leading zeros for hours and minutes, but always uses two digits for seconds.
                Does not wrap at 24 hours, so durations longer than 24 hours will show the total
                hours.
        """
    if seconds is None:
        return ""

    total = int(round(seconds))
    sign = "-" if total < 0 else ""
    total = abs(total)

    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)

    if hours:
        return f"{sign}{hours}:{minutes:02}:{secs:02}"
    return f"{sign}{minutes}:{secs:02}"

@dataclass(slots=True)
class DurationField(DisplayField):
    """ A specialized DisplayField for formatting durations in seconds into H:MM:SS format. """

    def get(self) -> float | None:
        """ Get the underlying value of the field as a float representing seconds. """
        value = self._value
        return float(value) if value is not None else None

    def render(self) -> str:
        """ Render the field's value as a formatted duration string. """
        value = self.get()
        dur_str:str = format_hms(value)
        return f"{self.label}{self.sep}{dur_str}"



@dataclass(slots=True)
class FileSizeField(DisplayField):
    """ A specialized DisplayField for formatting file sizes in bytes into human-readable strings
        with appropriate units. 
    """

    def get(self) -> int | None:
        """ Get the underlying value of the field as an integer representing bytes. """
        value = self._value
        return int(value) if value is not None else None

    def render(self) -> str:
        """ Render the field's value as a formatted file size string with appropriate units. """
        size = self.get()
        kb = 1024
        mb = kb * 1024
        if size is None:
            return "0"
        if size < kb:
            return f"{self.label}{self.sep}{self.ctx.format_number(size, as_int=True)} bytes"
        if size < mb:
            return f"{self.label}{self.sep}{self.ctx.format_number(size / kb, decimals=3)} KB"
        return f"{self.label}{self.sep}{self.ctx.format_number(size / mb, decimals=3)} MB"

@dataclass(slots=True)
class BitRateField(DisplayField):
    """ A specialized DisplayField for formatting bit rates in bits per second into
        human-readable strings with appropriate units. 
    """
    def get(self) -> int | None:
        """ Get the underlying value of the field as an integer representing bits per second. """
        value = self._value
        return int(value) if value is not None else None
