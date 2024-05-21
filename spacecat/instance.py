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

from spacecat.helpers import constants


def get_all() -> list[str]:
    """
    Fetches all available bot instances.

    Instances exist as folders within the data directory and requires a
    valid config file.
    """
    return os.listdir(constants.GLOBAL_DATA_DIR)


def get_by_index(index: int) -> str | None:
    """Get a specific instance by the index obtained by get_all()."""
    return get_all()[index]


def create(name: str) -> bool:
    """Creates a new instance folder."""
    try:
        Path(f"{constants.GLOBAL_DATA_DIR}{name}").mkdir()
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

    shutil.move(f"{constants.GLOBAL_DATA_DIR}{instance}", f"{constants.GLOBAL_DATA_DIR}{name}")
    return True


def destroy(index: int) -> bool:
    """Deletes an instance folder by the index."""
    instance = get_by_index(index)
    if not instance:
        raise IndexError

    shutil.rmtree(f"{constants.GLOBAL_DATA_DIR}{instance}")
    return True
