import shutil
import os

from spacecat.helpers import constants


def get():
    """Checks for a config file in each subfolder to detect an instance"""
    instances = []
    folders = os.listdir(constants.DATA_DIR)
    for content in folders:
        if os.path.isfile(f'{constants.DATA_DIR}{content}/config.toml'):
            instances.append(content)
    return instances


def create():
    """Creates a new instance folder"""
    name = input("Specify the new instance name: ")
    print('--------------------\n')
    return name
    

def destroy(instances):
    """Deletes an instance folder by the index"""
    index = int(input("Specify the instance number to delete: "))
    print('--------------------\n')
    selected_instance = instances[index - 1]
    shutil.rmtree(constants.DATA_DIR + selected_instance)
    return