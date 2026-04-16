#!/bin/bash
# Wrapper script to run solace_config.py with the correct Python interpreter

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run the Python script using the venv's Python
"$DIR/venv/bin/python" "$DIR/solace_config.py" "$@"
