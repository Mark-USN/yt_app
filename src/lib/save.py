""" Logic for saving the transcript and info as a markdown or text. """

from __future__ import annotations

from pathlib import Path
from yt_lib.utils.log_utils import get_logger
from lib.app_context import RunContextStore
from lib.ui_vars import UiVars

logger = get_logger(__name__)




###############################################################################
#
# Markdown/Text saving logic - creates the front matter and saves the file.
#
################################################################################
class FileSaver:
    """ Logic for saving the transcript and info as a markdown, text, or PDF file. 
        Holds references to the objects needed to create the menu system
        and perform the menu actions.
    """
    def __init__(
            self,
            ctx: RunContextStore,
            ui: UiVars,
        ) -> None:
        """ Initialize the FileSaver object.
            Args:
                root: The root Tkinter window.
                ctx: The RunContextStore object that holds the application's paths.
                ui: The UiVars object that holds the application's UI variables.
        """
        self.ctx = ctx
        self.ui = ui

    def create_front_matter(self, separator:str |None=None) -> list[str]:
        """ Create the front matter for the markdown file based on the UI variables.
            Args:
                    sep: An optional separator to use between the values in a line.
            Returns:
                A list of strings representing the lables and values contained in the "info" frame.
        """
        sep:str = " " * 4
        if separator is not None:
            sep = separator
        front_matter: list[str] = [
                "---",
                f"{self.ui.title.var.get().strip()}",
                f"{self.ui.url.var.get().strip()}",
                f"{self.ui.video_format.var.get().strip()}",
                f"{self.ui.video_id.var.get().strip()}" \
                f"{sep}{self.ui.transcript_type.var.get().strip()}" \
                f"{sep}{self.ui.ext.var.get().strip()}" \
                f"{sep}{self.ui.resolution.var.get().strip()}",
                # Start of the next line.
                f"{self.ui.file_size.var.get()}" \
                f"{sep}{self.ui.duration.var.get().strip()}" \
                f"{sep}{self.ui.fps.var.get()}" \
                f"{sep}{self.ui.bit_rate.var.get()}"
         ]
        front_matter.append("---\n")
        return front_matter


    def save_md(self, filepath:Path) -> None:
        """ Save the transcript and info as a markdown file.
            Args:
                filepath: The path to save the markdown file to.
        """

        front_matter = self.create_front_matter()

        body = (
            "\n".join(front_matter)
            + "## Description\n\n"
            + (self.ui.desc_txt.strip() + "\n\n" if
               self.ui.desc_txt.strip() else "\n")
            + "## Transcript / Output\n\n"
            + self.ui.transcript_txt.rstrip()
            + "\n"
        )
        filepath.write_text(body, encoding="utf-8")

    def save_txt(self, filepath:Path) -> None:
        """ Save the transcript and info as a text file.
            Args:
                filepath: The path to save the text file to.
        """

        front_matter = self.create_front_matter()
        # remove the first and last lines of the front matter, the '---' lines.
        front_matter = front_matter[1:-1]

        body = (
            "\n".join(front_matter)
            + "## Description\n\n"
            + (self.ui.desc_txt.strip() + "\n\n" if
               self.ui.desc_txt.strip() else "\n")
            + "## Transcript / Output\n\n"
            + self.ui.transcript_txt.rstrip()
            + "\n"
        )
        filepath.write_text(body, encoding="utf-8")
