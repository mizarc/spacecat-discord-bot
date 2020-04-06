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
    print("x. EXIT\n")


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
    while True:
        index = int(input("Specify the instance number to delete: "))
        print('--------------------\n')

        # Check if selected instance is valid
        try:
            selected_instance = instances[index - 1]
        except IndexError:
            print("Invalid instance number. Moved back to main menu.\n")
            display()
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

    shutil.rmtree(constants.DATA_DIR + selected_instance)
    display()
    return