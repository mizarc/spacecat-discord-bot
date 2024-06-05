"""
Holds constant values that can be used throughout the program.

This currently has uses for finding directories, as well as icon values
and emoji name conversions.
"""

from __future__ import annotations

import enum
from typing import Self

import discord

MAIN_DIR = "spacecat/"
ASSETS_DIR = "assets/"
CACHE_DIR = "cache/"
DATA_DIR = "data/"


class EmbedStatus(enum.Enum):
    """
    An enum of statuses used for the colour of discord embeds.

    Each status is represented by a `discord.Color` object. This allows
    for a consistent colour scheme between embeds of the same type.
    """

    YES = discord.Color.from_rgb(67, 160, 71)
    NO = discord.Color.from_rgb(218, 120, 16)
    INFO = discord.Color.from_rgb(3, 169, 244)
    GAME = discord.Color.from_rgb(229, 226, 41)
    FAIL = discord.Color.from_rgb(211, 47, 47)
    SPECIAL = discord.Color.from_rgb(103, 58, 183)


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
