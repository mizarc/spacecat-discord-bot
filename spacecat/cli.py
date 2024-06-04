"""
The main entry point of the program, used to start bots.

This module is a command line interface and argument parser that allows
for the creation and startup process for the bot.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Callable

from spacecat import instance, spacecat
from spacecat.helpers import config, constants


def logger() -> None:
    """Outputs data from the bot into a file."""
    # Create log folder if it doesn't exist
    if not Path("logs").exists():
        Path("logs").mkdir()

    # Setup file logging
    logger = logging.getLogger("discord")
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(filename="logs/latest.log", encoding="utf-8", mode="w")
    handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
    logger.addHandler(handler)


def parse_args() -> argparse.Namespace:
    """Add command line argument options."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", "-i", help="instance help", type=str)
    parser.add_argument("--apikey", "-a", help="apikey help", type=str)
    parser.add_argument("--user", "-u", help="user help", type=int)
    parser.add_argument("--prefix", "-p", help="prefix help", type=str)
    return parser.parse_args()


def select_instance() -> instance.Instance:
    """Prompt the user to select an instance."""
    options: dict[str, Callable] = {
        "n": create_instance_menu,
        "r": rename_instance_menu,
        "d": destroy_instance_menu,
        "x": sys.exit,
    }

    while True:
        display_instances(options)
        instances = instance.get_all()
        choice = input("Select an instance or option: ")
        print("--------------------\n")

        # Attempt to get a valid instance by index
        try:
            selected_instance = instances[int(choice) - 1]
            break
        except (ValueError, IndexError):
            pass

        # Attempt to get a valid option
        try:
            selected_instance = options[choice]()
            continue
        except KeyError:
            pass

        # Alert if no valid option has been selected
        print("Invalid selection. Please select a valid instance number or an " "option letter.\n")

    return instance.Instance(selected_instance)


def display_instances(options: dict) -> None:
    """Prints a list of instances and other instance editing options."""
    instances = instance.get_all()

    # Add list of instances, plus extra options
    print("[Available Instances]")
    formatted_instances = []
    for index, inst in enumerate(instances):
        formatted_instances.append(f"{index + 1}. {inst}")
    print("\n".join(formatted_instances))

    option_letters = list(options.keys())
    print("\n[Other Options]")
    print(f"{option_letters[0]}. NEW INSTANCE")
    print(f"{option_letters[1]}. RENAME INSTANCE")
    print(f"{option_letters[2]}. DELETE INSTANCE")
    print(f"{option_letters[3]}. EXIT\n")


def create_instance_menu() -> str:
    """
    A menu which prompts the user to name their instance.

    Returns:
        str: The name of the new instance
    """
    name = input("Specify the new instance name: ")
    print("--------------------\n")

    instance.create(name)
    print(f"A new instance by the name of '{name}' has been created.\n")
    return name


def rename_instance_menu() -> None:
    """A menu which prompts the user to rename an instance."""
    # Check if selected instance is valid
    try:
        index = int(input("Specify the instance number to rename: "))
        instance_name = instance.get_by_index(index - 1)
    except ValueError:
        instance_name = None
    print("--------------------\n")
    if not instance_name:
        print("Invalid instance number. Moved back to main menu.\n")
        return

    # Prompt to set the new instance name
    new_name = input(f"State the new name for instance {instance_name}: ")
    check = instance.rename(index - 1, new_name)
    print("--------------------\n")

    if not check:
        print("An instance of that name already exists. " "Moved back to main menu.\n")
    print(f"Instance '{instance_name}' has been renamed to '{new_name}'.\n")


def destroy_instance_menu() -> None:
    """A menu which prompts the user to delete an instance."""
    while True:
        # Check if selected instance is valid
        try:
            index = int(input("Specify the instance number to delete: "))
            instance_name = instance.get_by_index(index - 1)
        except ValueError:
            instance_name = None
        print("--------------------\n")
        if not instance_name:
            print("Invalid instance number. Moved back to main menu.\n")
            return

        # Ask to confirm instance deletion
        confirm = input(f"Are you sure you want to delete instance " f"'{instance_name}' (y/n): ")
        print("--------------------\n")
        if confirm == "y":
            instance.destroy(index - 1)
            print(f"Instance '{instance_name}' has been deleted.\n")
            return
        if confirm == "n":
            print("Instance deletion has been cancelled.\n")
            return
        print("Invalid option.")


def main() -> None:
    """
    The main function of the program.

    This function is the entry point of the program and is responsible
    for executing the main logic. Here are the simple initialisation
    steps that it performs:

    1. Prints fancy ASCII art logo.
    2. Initialises the logger.
    3. Parses command line arguments.
    4. Creates the data folder if it doesn't exist.
    5. Prompts users to select instance (if cmd line arg is not set.
    6. Fetches the configuration file attached to the instance.
    7. Runs the module (Runs introduction if it's the first time).
    """
    print(
        r" ___  ___   ___  _                   _   ___      _"
        "\n"
        r"/ __|/ __| |   \(_)___ __ ___ _ _ __| | | _ ) ___| |_"
        "\n"
        r"\__ \ (__  | |) | (_-</ _/ _ \ '_/ _` | | _ \/ _ \  _|"
        "\n"
        r"|___/\___| |___/|_/__/\__\___/_| \__,_| |___/\___/\__|"
        "\n"
    )
    logger()
    args = parse_args()

    # Create data folder
    if not Path(constants.DATA_DIR).exists:
        Path(constants.DATA_DIR).mkdir()

    # Select instance
    instance = select_instance() if not args.instance else args.instance

    # Fetch the APIKey from the config
    instance_config = instance.get_config()
    config.apply_arguments(instance_config, args)
    try:
        instance_config["base"]["apikey"]
        first_run = False
    except KeyError:
        spacecat.introduction(instance_config)
        first_run = True

    spacecat.run(instance, firstrun=first_run)
