#!/bin/bash

# Set the name of the virtual environment
ENV_NAME=".venv"

# Create the virtual environment
python -m venv "$ENV_NAME"

# Activate the virtual environment
source "$ENV_NAME/Scripts/activate"

# Install requirements from the requirements.txt file
pip install -r requirements.txt

# Install the "spacecat" program
pip install -e .

# Run the "spacecat" program
python -m spacecat

# Deactivate the virtual environment
deactivate
