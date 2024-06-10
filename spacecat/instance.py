"""
This module provides functions for managing bot instances.

Bot instances are isolated configurations that can be utilised to
separate the data from one bot to another. This may be used to separate
dev and prod instances, as well as be used for hosting multiple bots on
the same host.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Self

import toml

from spacecat.helpers import constants


def get_all() -> list[str]:
    """
    Fetches all available bot instances.

    Instances exist as folders within the data directory and requires a
    valid config file.
    """
    return os.listdir(constants.DATA_DIR)


def get_by_index(index: int) -> str | None:
    """Get a specific instance by the index obtained by get_all()."""
    return get_all()[index]


def create(name: str) -> bool:
    """Creates a new instance folder."""
    try:
        Path(f"{constants.DATA_DIR}{name}").mkdir()
    except FileExistsError:
        return False

    return True


def rename(index: int, name: str) -> bool:
    """Renames an instance folder by the index."""
    instance = get_by_index(index)
    if not instance:
        raise IndexError

    instances = get_all()
    if name in instances:
        return False

    shutil.move(f"{constants.DATA_DIR}{instance}", f"{constants.DATA_DIR}{name}")
    return True


def destroy(index: int) -> bool:
    """Deletes an instance folder by the index."""
    instance = get_by_index(index)
    if not instance:
        raise IndexError

    shutil.rmtree(f"{constants.DATA_DIR}{instance}")
    return True


class InstanceNameNotSetError(ValueError):
    """
    Raised when the `instance_name` is not set.

    This is usually a sign that the instance name has not been
    set prior to calling the `instance_location` function, which is
    required to know where to store instance data.
    """


class Instance:
    """
    Class that holds instance specific data.

    This class is used to store the instance name, which is used to
    determine where instance data is stored.
    """

    def __init__(self: Instance, name: str) -> None:
        """Initialize the InstanceData class."""
        self._name: str = name
        self._init_config()

    @property
    def instance_name(self: Self) -> str:
        """
        Get the instance name.

        Returns:
            str: The name of the instance.
        """
        return self._name

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
        if self._name == "":
            raise InstanceNameNotSetError
        return f"{constants.DATA_DIR}{self._name}/"

    def get_config(self: Self) -> dict[str, Any]:
        """
        Read and return the config values.

        Returns:
            dict: The config dictionary.
        """
        return toml.load(self.instance_location + "config.toml")

    def save_config(self: Self, config: dict) -> None:
        """
        Write the config to the specified file.

        Args:
            path (str): The path to the config file.
            config (dict): The config dictionary.
        """
        with Path(self.instance_location + "config.toml").open("w") as config_file:
            toml.dump(config, config_file)

    def _init_config(self: Self) -> None:
        try:
            config = self.get_config()
        except FileNotFoundError:
            config = {}

        if "base" not in config:
            config["base"] = {}

        self.save_config(config)
