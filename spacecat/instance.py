import shutil
import os

from spacecat.helpers import config, constants


def get_all():
    """Checks for a config file in each subfolder to detect an instance"""
    folders = os.listdir(constants.DATA_DIR)
    instances = []
    for folder in folders:
        instances.append(folder)

    return instances


def get_by_index(index):
    """Get a specific instance by the index obtained by get_all()"""
    instances = get_all()
    try:
        instance = instances[index]
    except (IndexError, TypeError):
        return False

    return instance


def create(name):
    """Creates a new instance folder"""
    try:
        os.mkdir(f'{constants.DATA_DIR}{name}')
    except FileExistsError:
        return False

    return True


def rename(index, name):
    instance = get_by_index(index)
    if not instance:
        raise IndexError

    instances = get_all()
    if name in instances:
        return False

    shutil.move(
        f'{constants.DATA_DIR}{instance}', f'{constants.DATA_DIR}{name}')
    return True
    

def destroy(index):
    """Deletes an instance folder by the index"""
    instance = get_by_index(index)
    if not instance:
        raise IndexError

    shutil.rmtree(f'{constants.DATA_DIR}{instance}')
    return True