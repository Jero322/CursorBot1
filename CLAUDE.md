# CursorBot — Arduino Code Translator

## Project Overview
CursorBot translates natural language descriptions into Arduino `.ino` code using OpenAI's API. It has two interfaces: a CLI (`arduino_translator.py`) and a Flask web app (`web/app.py`).

## Architecture

```
arduino_translator.py   # Core logic + CLI entrypoint
run.sh                  # Shell helper (activates venv, runs translator)
requirements.txt        # Python dependencies
web/
  app.py               # Flask server (imports from arduino_translator.py)
  templates/index.html # Web UI
  static/main.js       # Frontend JS
  static/styles.css    # Frontend styles
arduino_code/           # Generated .ino files (gitignored)
```

The Flask app imports `get_openai_client`, `translate_to_arduino`, and `save_code_to_file` directly from `arduino_translator.py` — keep these functions stable and importable.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="your-key"   # or write key to .api_key file
```

## Running

**CLI:**
```bash
./run.sh "Blink an LED on pin 13"
python arduino_translator.py -i          # interactive mode
python arduino_translator.py "desc" -m gpt-4o  # different model
```

**Web server:**
```bash
cd web && python app.py   # runs on http://127.0.0.1:5000
```

## Key APIs

### `arduino_translator.py`
- `get_openai_client()` — reads key from `OPENAI_API_KEY` env var or `.api_key` file
- `translate_to_arduino(client, natural_language, model="gpt-4o-mini")` — returns raw Arduino code string (no markdown fences)
- `save_code_to_file(code, description, output_dir="arduino_code", custom_output=None)` — saves `.ino`, returns filepath
- `generate_filename(description, output_dir)` — sanitizes description into a timestamped filename

### Flask endpoints (`web/app.py`)
- `POST /api/generate` — `{prompt, model?}` → `{code, filepath}`
- `GET /api/download?path=...` — downloads `.ino` (restricted to `arduino_code/`)
- `POST /api/upload` — `{path, port, fqbn}` → compiles + uploads via `arduino-cli`

## Dependencies
- `openai>=1.0.0` — OpenAI Python SDK
- `Flask>=2.0.0` + `flask-cors>=3.0.10` — web server
- `python-dotenv>=0.21.0` — env var loading
- `pyserial>=3.0` — serial communication
- `arduino-cli` — external tool required for board upload (must be on PATH)

## Security Notes
- `.api_key` and `arduino_code/` are gitignored — never commit them
- `/api/download` validates that the requested path is inside `arduino_code/` to prevent directory traversal
- Flask runs in debug mode locally only (`host='127.0.0.1'`)

## Conventions
- Default OpenAI model: `gpt-4o-mini` (configurable via `-m` flag or `model` in API body)
- Generated code is always saved to `arduino_code/` unless `--no-save` is passed
- The system prompt instructs the model to return plain code without markdown fences
- Temperature is fixed at `0.3` for consistent code generation
