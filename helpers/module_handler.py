import glob
import os

import discord
import toml

def get():
    # Get all modules that are present in the folder
    modulelist = []
    for module in glob.glob('modules/*.py'):
        if module == "modules/__init__.py":
            continue
        modulelist.append(module[8:-3])
    return modulelist

def get_enabled():
    # Fetch all modules and disable modules
    modules = get()
    disabled_modules = get_disabled()
    enabled_modules = []

    # Compare with disabled modules list to determine which ones are enabled
    try:
        for module in modules:
            if module not in disabled_modules:
                enabled_modules.append(module)
    except TypeError:
        enabled_modules = modules
    return enabled_modules

def get_disabled():
    # Fetch disabled modules from config file
    config = toml.load('config.toml')
    try:
        disabled_modules = config['base']['disabled_modules']
        return disabled_modules
    except KeyError:
        return None

