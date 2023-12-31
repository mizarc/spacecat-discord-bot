import glob

import toml

from spacecat.helpers import constants


def get():
    # Get all modules that are present in the folder
    modulelist = []
    for module in glob.glob(f'{constants.MAIN_DIR}/modules/*.py'):
        if module[17:] == "__init__.py":
            continue
        modulelist.append(module[17:-3])
    return modulelist


def get_enabled():
    # Fetch all modules and disabled modules
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
    try:
        config = toml.load(f'{constants.DATA_DIR}/config.toml')
        disabled_modules = config['base']['disabled_modules']
        return disabled_modules
    except (KeyError, FileNotFoundError):
        return None
