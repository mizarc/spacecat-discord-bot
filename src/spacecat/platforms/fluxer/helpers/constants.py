"""
Holds constant values that can be used throughout the program.

This currently has uses for finding directories, as well as icon values
and emoji name conversions.
"""

from __future__ import annotations

import enum
from typing import Self

import fluxer

MAIN_DIR = "spacecat/"
ASSETS_DIR = "assets/"
CACHE_DIR = "cache/"
DATA_DIR = "data/"


class EmbedStatus(enum.Enum):
    """
    An enum of statuses used for the colour of embeds.

    Each status is represented by a color value. This allows
    for a consistent colour scheme between embeds of the same type.
    """

    YES = 0x43A047  # Green
    NO = 0xDA7810   # Orange  
    INFO = 0x03A9F4 # Blue
    GAME = 0xE5E229 # Yellow
    FAIL = 0xD32F2F # Red
    SPECIAL = 0x673AB7 # Purple


class EmbedIcon(enum.Enum):
    """
    Enum for the different icons used for the embeds.

    Each value is a string representing the icon to be used in the
    embed.
    """

    DEFAULT = ":bulb: "
    HELP = ":question: "
    MUSIC = ":musical_note: "
    DATABASE = ":cd: "

    def __str__(self: Self) -> str:
        """
        Returns the string representation of the enum value.

        Returns:
            str: The string representation of the enum value.
        """
        return self.value
