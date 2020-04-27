import argparse
import functools
import logging
import os
import shutil
import sys
import toml

from spacecat import spacecat
from spacecat import instance
from spacecat.helpers import constants, config


def logger():
    """Outputs data from the bot into a file"""
    # Create log folder if it doesn't exist
    if not os.path.exists('logs'):
        os.mkdir('logs')

    # Setup file logging
    logger = logging.getLogger('discord')
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(
        filename='logs/latest.log',
        encoding='utf-8',
        mode='w'
    )
    handler.setFormatter(logging.Formatter(
        '%(asctime)s:%(levelname)s:%(name)s: %(message)s')
    )
    logger.addHandler(handler)


def parse_args():
    """Add command line argument options"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--instance', '-i', help='instance help', type=str)
    parser.add_argument('--apikey', '-a', help='apikey help', type=str)
    parser.add_argument('--user', '-u', help='user help', type=int)
    parser.add_argument('--prefix', '-p', help='prefix help', type=str)
    args = parser.parse_args()
    return args


def select_instance():
    """Prompt the user to select an instance"""
    instance.display()
    while True:
        instances = instance.get()
        choice = input("Select an instance or option: ")
        print('--------------------\n')

        # Attempt to get a valid instance by index
        try:
            selected_instance = instances[int(choice) - 1]
            break
        except (ValueError, IndexError):
            pass

        # Attempt to get a valid option
        switch = {
            'n': instance.create,
            'r': instance.rename,
            'd': functools.partial(instance.destroy, instances),
            'x': quit
        }
        try:
            selected_instance = switch[choice]()
            continue
        except KeyError:
            pass

        # Alert if no valid option has been selected
        print(
            "Invalid selection. Please select a valid instance number or an "
            "option letter."
        )
    return selected_instance


def main():
    print(
        " ___  ___   ___  _                   _   ___      _\n"
        "/ __|/ __| |   \(_)___ __ ___ _ _ __| | | _ ) ___| |_\n"
        "\__ \ (__  | |) | (_-</ _/ _ \ '_/ _` | | _ \/ _ \  _|\n"
        "|___/\___| |___/|_/__/\__\___/_| \__,_| |___/\___/\__|\n"
    )
    logger()
    args = parse_args()

    # Select instance folder to store data in
    if not args.instance:
        instance = select_instance()
    else:
        instance = parse_args()
    constants.data_location(instance)

    # Run config creator if config file doesn't exist
    try:
        config_data = toml.load(constants.DATA_DIR + 'config.toml')
        config_data['base']['apikey']
        first_run = False
    except (FileNotFoundError, KeyError):
        config.apply_arguments(config_data, args)
        first_run = spacecat.introduction(config)

    spacecat.run(firstrun=first_run)