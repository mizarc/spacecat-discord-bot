import shutil
import os

from spacecat.helpers import config, constants


def get():
    """Checks for a config file in each subfolder to detect an instance"""
    folders = os.listdir(constants.DATA_DIR)
    instances = []
    for folder in folders:
        if os.path.isfile(f'{constants.DATA_DIR}{folder}/config.toml'):
            instances.append(folder)
            
    return instances


def create(name):
    """Creates a new instance folder"""
    try:
        os.mkdir(f'{constants.DATA_DIR}{name}')
    except FileExistsError:
        return False

    return True
    

def destroy(instances, index):
    """Deletes an instance folder by the index"""
    # Check if selected instance is valid
    try:
        selected_instance = instances[index - 1]
    except IndexError:
        return False

    shutil.rmtree(f'{constants.DATA_DIR}{selected_instance}')
    return True