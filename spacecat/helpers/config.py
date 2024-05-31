"""
A collection of tools used to manage config files.

Configs use the TOML (Tom's Obvious, Minimal Language) specification
to easily read and write data to in dictionary form, while maintaining
file readability for manual editing. Functions found here provide
a consistent way to handle the data that the bot can read from.
"""

import argparse
from pathlib import Path

import toml

from spacecat.helpers import constants


def create() -> dict:
    """
    Create and return the base empty config file.

    If an instance is provided as an argument, a subfolder will be created
    to house the config
    """
    # Create config with just the base header
    config = {}
    config["base"] = {}
    with Path(constants.DATA_DIR + "config.toml").open("w") as config_file:
        toml.dump(config, config_file)
    return config


def apply_arguments(config: dict, args: argparse.Namespace) -> dict:
    """
    Apply argsparse arguments to the config.

    Arguments specified through argsparse can be forwarded to the config
    file to manually change data before the bot runs.
    """
    if args.apikey:
        config["base"]["apikey"] = args.apikey
    if args.prefix:
        config["base"]["prefix"] = args.prefix
    if args.user:
        try:
            users = config["base"]["adminuser"]
            if args.user not in users:
                config["base"]["adminuser"].append(args.user)
        except KeyError:
            config["base"]["adminuser"] = [args.user]

    with Path(constants.DATA_DIR + "config.toml").open("w") as config_file:
        toml.dump(config, config_file)
    return config
