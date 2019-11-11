# File Duplicate Analysis Tool

## Introduction

This is a simple tool to search for dupliacte files in a given dircectory. The directory is searched recursively and an on-screen and a JSON repor is produced containin the list of duplicate files. Right now only report will be generated.

Future features planned:

1.) Managing files from the tool. (delete)
2.) Mark files to be excluded from future reports

## Installation

The tool shall pretty much work out of the box. But Python 3 has to be installed. It has been tested with Python 3.8 so far.

To install Python 3.8

For Windows -> download and install from here:

    https://www.python.org/downloads/release/python-380/

For Linux:

     you can install by executing: sudo apt-get install python3

### Further Requirement

Software is based on PyQt5. So PyQt5 has to be installed:

    python -m pip install PyQt5

## Running the code

If python3 is installed, you can launch the app by running start.bat (Windows) or start.sh (Linux) It shall set up virtual environment and install PyQt5

If the script fails or you are in a more adventorous mood, assuming that PyQt5 was installed it can be also launched by executing:

    python disk_cleanup.py

or

    python3 disk_cleanup.py (sometimes on Linux)
