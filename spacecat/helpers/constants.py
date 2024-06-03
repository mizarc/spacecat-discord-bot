"""
This used to just hold constants, but got a little out of hand.

Needs to be reworked.
"""

from __future__ import annotations

import enum
from typing import Self

import discord

MAIN_DIR = "spacecat/"
ASSETS_DIR = "assets/"
CACHE_DIR = "cache/"
DATA_DIR = "data/"


class InstanceNameNotSetError(ValueError):
    """
    Raised when the `instance_name` is not set.

    This is usually a sign that the instance name has not been
    set prior to calling the `instance_location` function, which is
    required to know where to store instance data.
    """


class InstanceData:
    """
    Class that holds instance specific data.

    This class is used to store the instance name, which is used to
    determine where instance data is stored.
    """

    def __init__(self: InstanceData) -> None:
        """Initialize the InstanceData class."""
        self._instance_name: str = ""

    @property
    def instance_name(self: Self) -> str:
        """
        Get the instance name.

        Returns:
            str: The name of the instance.
        """
        return self._instance_name

    @instance_name.setter
    def instance_name(self: Self, name: str) -> None:
        """
        Set the instance name.

        Args:
            name (str): The name of the instance.
        """
        InstanceData._instance_name = name

    @property
    def instance_location(self: Self) -> str:
        """
        Returns the location of the instance data directory.

        This fetches the instance location by combining the data
        directory with the instance name. Instance name must be set
        prior to calling this.

        Returns:
            str: The location of the instance data directory.

        Raises:
            InstanceNameNotSetError: If the `instance_name` variable is
                empty.
        """
        if InstanceData._instance_name == "":
            raise InstanceNameNotSetError
        return f"{DATA_DIR}/{InstanceData._instance_name}/"


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
