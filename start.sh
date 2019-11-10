#!/bin/bash
set -e

VENV_PATH=$(dirname $0)/.venv

if [ ! -d $VENV_PATH ]; then  
	python3 -m venv $VENV_PATH
	. $VENV_PATH/bin/activate
	python3 -m pip install PyQt5
else
	. $VENV_PATH/bin/activate
fi

python3 $(dirname $0)/disk_cleanup.py


