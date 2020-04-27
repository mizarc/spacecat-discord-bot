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
    display_instances()
    while True:
        instances = instance.get_all()
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
            'n': create_instance_menu,
            'r': rename_instance_menu,
            'd': destroy_instance_menu,
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


def display_instances():
    """Prints a list of instances and other instance editing options"""
    instances = instance.get_all()
    
    # Add list of instances, plus extra options
    print("[Available Instances]")
    formatted_instances = []
    for index, inst in enumerate(instances):
        formatted_instances.append(f'{index + 1}. {inst}')
    print('\n'.join(formatted_instances))

    print("\n[Other Options]")
    print("n. NEW INSTANCE")
    print("r. REMOVE INSTANCE")
    print("x. EXIT\n")


def create_instance_menu():
    """A menu which prompts the user for the name of the new instance"""
    name = input("Specify the new instance name: ")
    print('--------------------\n')

    instance.create(name)
    display_instances()
    return name


def rename_instance_menu():
    """A menu which prompts the user to rename an instance"""
    pass


def destroy_instance_menu(instances):
    """Deletes an instance folder by the index"""
    while True:
        index = int(input("Specify the instance number to delete: "))
        print('--------------------\n')

        # Check if selected instance is valid
        try:
            selected_instance = instances[index - 1]
        except IndexError:
            print("Invalid instance number. Moved back to main menu.\n")
            display_instances()
            return

        # Ask to confirm instance deletion
        confirm = input("Are you sure you want to delete that instance? (y/n): ")
        print('--------------------\n')

        if confirm == 'y':
            break
        elif confirm == 'n':
            return
        else:
            print("Invalid option.")


def main():
    print(
        " ___  ___   ___  _                   _   ___      _\n"
        "/ __|/ __| |   \(_)___ __ ___ _ _ __| | | _ ) ___| |_\n"
        "\__ \ (__  | |) | (_-</ _/ _ \ '_/ _` | | _ \/ _ \  _|\n"
        "|___/\___| |___/|_/__/\__\___/_| \__,_| |___/\___/\__|\n"
    )
    logger()
    args = parse_args()

    # Create data folder
    if not os.path.exists(constants.DATA_DIR):
        os.mkdir(constants.DATA_DIR)

    # Select instance folder
    if not args.instance:
        instance = select_instance()
    else:
        instance = parse_args()
    constants.instance_location(instance)

    # Run config creator if config file doesn't exist
    try:
        config_data = toml.load(constants.DATA_DIR + 'config.toml')
        config_data['base']['apikey']
        first_run = False
    except (FileNotFoundError, KeyError):
        config.apply_arguments(config_data, args)
        first_run = spacecat.introduction(config)

    spacecat.run(firstrun=first_run)