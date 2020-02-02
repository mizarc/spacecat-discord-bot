echo Creating virtual environment...
py -3 -m venv .venv

echo Including Requirements...
SET PYTHON=.venv\Scripts\python.exe
%PYTHON% -m pip install -e .

cd spacecat
..\%PYTHON% spacecat.py %*