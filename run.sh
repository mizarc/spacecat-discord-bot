echo "Creating virtual environment..."
python3 -m venv .venv\

echo "Including Requirements..."
PYTHON=.venv/bin/python3
$PYTHON -m pip install -e .

cd spacecat
../$PYTHON spacecat.py