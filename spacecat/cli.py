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


def load_modules():
    """Loads all modules from the modules folder for the bot"""
    # Enable enabled modules from list
    self.bot.add_cog(SpaceCat(self.bot))
    modules = module_handler.get_enabled()
    for module in modules:
        module = f'{constants.MAIN_DIR}.modules.' + module
        try:
            self.bot.load_extension(module)
        except Exception as exception:
            print(
                f"Failed to load extension {module}\n"
                f"{type(exception).__name__}: {exception}\n")

    self.modules = modules


def create_config(args):
    """
    Creates the base empty config file
    If an instance is provided as an argument, a subfolder will be created
    to house the config
    """
    # Create data folder and optional instance folder if it doesn't exist
    if not os.path.exists(constants.DATA_DIR):
        os.mkdir(constants.DATA_DIR)
    if args.instance:
        if not os.path.exists(f"{constants.DATA_DIR}/{args.instance}"):
            os.mkdir(f"{constants.DATA_DIR}/{args.instance}")

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


def main():
    logger()
    load_modules()
    args = parse_args()

    # Append New APIKey to config if specified by argument
    if len(sys.argv) > 1:
        try:
            config = toml.load(constants.DATA_DIR + 'config.toml')
        except FileNotFoundError:
            config = create_config(args)
        config_arguments(config, args)

    # Check if config exists and run config creator if it doesn't
    try:
        config = toml.load(constants.DATA_DIR + 'config.toml')
        config['base']['apikey']
        first_run = False
    except (FileNotFoundError, KeyError):
        first_run = spacecat.introduction()

    spacecat.run(firstrun=first_run)