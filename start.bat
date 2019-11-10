@echo off
set venvpath=%cd%\.venv
IF not exist %venvpath% (
	python -m venv %venvpath%
	python -m pip install PyQt5
) else (
	python -m venv %venvpath%
)

python disk_cleanup.py