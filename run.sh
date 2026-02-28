#!/bin/bash
# Helper script to run the Arduino translator bot

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the translator
python3 arduino_translator.py "$@"
