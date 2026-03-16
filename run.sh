#!/bin/bash

# Set the name of the virtual environment
ENV_NAME=".venv"

# Create the virtual environment
python -m venv "$ENV_NAME"

# Activate the virtual environment
source "$ENV_NAME/bin/activate"

# Install requirements from the requirements.txt file
pip install -r requirements.txt

# Install the "spacecat" program
pip install -e .[all]

# Run the "spacecat" program
spacecat
