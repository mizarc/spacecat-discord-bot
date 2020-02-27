import argparse
import functools
import logging
import os
import shutil
import sys
import toml

from spacecat import spacecat
from spacecat import instance
from spacecat.helpers import constants


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


def select_instance():
    """Prompt the user to select an instance"""
    instances = instance.get()
    print("[Available Instances]")
    
    # Add list of instances, plus extra options
    formatted_instances = []
    for index, inst in enumerate(instances):
        formatted_instances.append(f'{index + 1}. {inst}')
    print('\n'.join(formatted_instances))
    print("\n[Other Options]")
    print("n. NEW INSTANCE")
    print("r. REMOVE INSTANCE")
    print("e. EXIT\n")

    # Run function if the selected option is valid
    while True:
        choice = input("Select an instance or option: ")
        print('--------------------\n')
        try:
            selected_instance = instances[int(choice) - 1]
            break
        except ValueError:
            switch = {
                'n': instance.create,
                'r': functools.partial(instance.destroy, instances),
                'e': quit
            }
            try:
                selected_instance = switch[choice]()
            except KeyError:
                pass
        except IndexError:
            pass
        print(
            "Invalid selection. Please select a valid instance number or an "
            "option letter.")
    return selected_instance


def main():
    print(r"""         ___  ___   ___  _                   _   ___      _
        / __|/ __| |   \(_)___ __ ___ _ _ __| | | _ ) ___| |_
        \__ \ (__  | |) | (_-</ _/ _ \ '_/ _` | | _ \/ _ \  _|
        |___/\___| |___/|_/__/\__\___/_| \__,_| |___/\___/\__|
        """)
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
        config = toml.load(constants.DATA_DIR + 'config.toml')
        config['base']['apikey']
        first_run = False
    except (FileNotFoundError, KeyError):
        config = create_config(args)
        config_arguments(config, args)
        first_run = spacecat.introduction(config)

    spacecat.run(firstrun=first_run)