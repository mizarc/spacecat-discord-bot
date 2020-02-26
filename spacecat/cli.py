import argparse
import logging
import os
import sys
import toml

from spacecat.helpers import constants
from spacecat import spacecat


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


def create_config(args):
    """
    Creates the base empty config file
    If an instance is provided as an argument, a subfolder will be created
    to house the config
    """
    # Create data folder and optional instance folder if it doesn't exist
    if not os.path.exists(constants.DATA_DIR):
        os.mkdir(constants.DATA_DIR)

    # Create config with just the base header
    config = {}
    config['base'] = {}
    with open(constants.DATA_DIR + "config.toml", "w") as config_file:
        toml.dump(config, config_file)
    return config


def config_arguments(config, args):
    """Applies the cmd arguments to the config file"""
    if args.apikey:
        config['base']['apikey'] = args.apikey
    if args.prefix:
        config['base']['prefix'] = args.prefix
    if args.user:
        try:
            users = config['base']['adminuser']
            if args.user not in users:
                config['base']['adminuser'].append(args.user)
        except KeyError:
            config['base']['adminuser'] = [args.user]

    with open(constants.DATA_DIR + "config.toml", "w") as config_file:
        toml.dump(config, config_file)
    return config

def get_instances():
    """Checks for a config file in each subfolder to detect an instance"""
    instances = []
    folders = os.listdir(constants.DATA_DIR)
    for content in folders:
        if os.path.isfile(f'{constants.DATA_DIR}{content}/config.toml'):
            instances.append(content)
    return instances


def select_instance():
    """Prompt the user to select an instance"""
    instances = get_instances()
    print("[Available Instances]")
    
    formatted_index = []
    for index, instance in enumerate(instances):
        formatted_index.append(f'{index + 1}. {instance}')
    print('\n'.join(formatted_index))
    print(f"{len(instances) + 1}. CREATE NEW INSTANCE\n")

    while True:
        choice = int(input("Select instance index: "))
        print('--------------------\n')

        try:
            if choice == (len(instances) + 1):
                pass
            selected_instance = instances[choice - 1]
            break
        except IndexError:
            print("Invalid instance. Select a valid number.")
    return selected_instance


def main():
    print(r"""         ___  ___   ___  _                   _   ___      _
        / __|/ __| |   \(_)___ __ ___ _ _ __| | | _ ) ___| |_
        \__ \ (__  | |) | (_-</ _/ _ \ '_/ _` | | _ \/ _ \  _|
        |___/\___| |___/|_/__/\__\___/_| \__,_| |___/\___/\__|
        """)
    logger()
    args = parse_args()

    if not args.instance:
        instance = select_instance()
    else:
        instance = parse_args()
    constants.data_location(instance)

    # Run config creator if config file doesn't exist
    try:
        config = toml.load(constants.DATA_DIR + 'config.toml')
        config['base']['apikey']
        first_run = False
    except (FileNotFoundError, KeyError):
        config = create_config(args)
        config_arguments(config, args)
        first_run = spacecat.introduction(config)

    spacecat.run(firstrun=first_run)