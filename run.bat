echo Creating virtual environment...
python3 -m venv .venv > /dev/null

echo Including Requirements...
SET PYTHON=.venv/bin/python3
%PYTHON% -m pip install -e . > /dev/null

cd spacecat
../%PYTHON% spacecat.py