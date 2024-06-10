"""
This module allow for the checking of modules and their enabled state.

It currently only provides getter methods, but may be reworked to work
with modification in the future, as it is currently unregulated.
"""

from __future__ import annotations

from pathlib import Path

import toml

from spacecat.helpers import constants


def get() -> list[str]:
    """
    Retrieves a list of all valid modules present in the folder.

    Returns:
        list[str]: A list of module names.
    """
    # Get all valid modules that are present in the folder
    modulelist = []
    for module in Path(f"{constants.MAIN_DIR}/modules").glob("*.py"):
        if module.name == "__init__.py":
            continue
        modulelist.append(module.stem)

    # Get all directories that have a file.py with the same name
    for directory in Path(f"{constants.MAIN_DIR}/modules").glob("*"):
        module = directory.name
        if (
            module != "__pycache__"
            and module != "__init__.py"
            and (directory / (module + ".py")).exists()
        ):
            modulelist.append(module)

    return modulelist


def get_enabled() -> list[str]:
    """
    Get a list of enabled modules.

    This function fetches all modules and disabled modules from the
    configuration file. It then compares the list of modules with the
    list of disabled modules to determine which ones are enabled.

    Returns:
        list[str]: A list of enabled modules.

    """
    # Fetch all modules and disabled modules
    modules = get()
    disabled_modules = get_disabled()
    enabled_modules: list[str] = []

    # Compare with disabled modules list to determine which ones are enabled
    try:
        enabled_modules = [module for module in modules if module not in disabled_modules]
    except TypeError:
        enabled_modules = modules

    return enabled_modules


def get_disabled() -> list[str]:
    """
    Get a list of disabled modules from the config file.

    This function fetches the list of disabled modules from the config
    file located at the instance's `config.toml` file.

    Returns:
        list[str]: A list of disabled modules, empty if no modules are
            disabled.
    """
    # Fetch disabled modules from config file
    try:
        config = toml.load(f"{constants.DATA_DIR}/config.toml")
        return config["base"]["disabled_modules"]
    except (KeyError, FileNotFoundError):
        return []
