VENV ?= venv
PYTHON = ${VENV}/bin/python3
DAEMON ?= spacecat

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

setup: ${VENV}/bin/activate ## Sets up the virtual environment with dependencies (Automatically called on run)
	${PYTHON} -m pip install -U pip flake8
	${PYTHON} -m pip install -e .

${VENV}/bin/activate: setup.py ## Create virtual environment if it doesn't exist
	python3 -m venv .venv
	
clean: ## Cleans up all build and environment files
	rm --force --recursive dist/
	rm --force --recursive *.egg-info
	rm --force --recursive .venv/
	
run: setup ## Runs the program
	${PYTHON} -m spacecat

run-daemon: setup ## Uses screen to run the program as a daemon (Linux only)
	screen -dmS ${DAEMON} ${PYTHON} -m spacecat

dist: setup ## Packages the software in a distributable format
	${PYTHON} setup.py sdist
	