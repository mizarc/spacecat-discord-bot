import shutil
import os

from spacecat.helpers import config, constants


def display():
    """Prints a list of instances and other instance editing options"""
    instances = get()
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
    constants.data_location(name)
    config.create()
    constants.data_location('')
    display()
    return name
    

def destroy(instances):
    """Deletes an instance folder by the index"""
    index = int(input("Specify the instance number to delete: "))
    print('--------------------\n')
    selected_instance = instances[index - 1]
    shutil.rmtree(constants.DATA_DIR + selected_instance)
    display()
    return