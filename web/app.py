from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import os
import sys
import shutil
import subprocess
import logging
import json

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('cursorbot')

# Allow importing arduino_translator from project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from arduino_translator import get_openai_client, translate_to_arduino, save_code_to_file

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/generate', methods=['POST'])
def api_generate():
    data = request.get_json() or {}
    prompt = data.get('prompt', '').strip()
    model = data.get('model') or 'gpt-4o-mini'
    log.info('generate request: model=%s prompt=%r', model, prompt[:80])
    if not prompt:
        return jsonify({'error': 'Prompt is required'}), 400

    try:
        client = get_openai_client()
        code = translate_to_arduino(client, prompt, model)
        filepath = save_code_to_file(code, prompt)
        log.info('generated code saved to %s', filepath)
        return jsonify({'code': code, 'filepath': filepath})
    except Exception as e:
        log.exception('generate failed')
        return jsonify({'error': str(e)}), 500


@app.route('/api/ports')
def api_ports():
    """Return a list of connected Arduino boards/ports via arduino-cli."""
    if shutil.which('arduino-cli') is None:
        log.warning('arduino-cli not found on PATH')
        return jsonify({'error': 'arduino-cli not found on PATH'}), 500

    try:
        proc = subprocess.run(
            ['arduino-cli', 'board', 'list', '--format', 'json'],
            capture_output=True, text=True, timeout=10,
        )
        log.debug('arduino-cli board list stdout: %s', proc.stdout)
        log.debug('arduino-cli board list stderr: %s', proc.stderr)

        detected = []
        if proc.stdout.strip():
            raw = json.loads(proc.stdout)
            # arduino-cli >= 0.35 wraps results under "detected_ports"
            entries = raw.get('detected_ports', raw if isinstance(raw, list) else [])
            for entry in entries:
                port_info = entry.get('port') or entry
                address = port_info.get('address') or port_info.get('label', '')
                protocol = port_info.get('protocol', '')
                boards = entry.get('matching_boards') or []
                fqbn = boards[0].get('fqbn', '') if boards else ''
                name = boards[0].get('name', '') if boards else ''
                if address:
                    detected.append({'port': address, 'protocol': protocol, 'fqbn': fqbn, 'name': name})

        log.info('found %d port(s): %s', len(detected), detected)
        return jsonify({'ports': detected})
    except subprocess.TimeoutExpired:
        log.error('arduino-cli board list timed out')
        return jsonify({'error': 'arduino-cli timed out'}), 500
    except Exception as e:
        log.exception('ports endpoint failed')
        return jsonify({'error': str(e)}), 500


@app.route('/api/download')
def api_download():
    path = request.args.get('path')
    if not path:
        return jsonify({'error': 'path query parameter required'}), 400

    # Security: ensure path is inside project arduino_code folder
    abs_path = os.path.abspath(path)
    allowed_dir = os.path.abspath(os.path.join(PROJECT_ROOT, 'arduino_code'))
    if not abs_path.startswith(allowed_dir):
        log.warning('download rejected for path outside allowed dir: %s', abs_path)
        return jsonify({'error': 'invalid path'}), 400

    if not os.path.exists(abs_path):
        return jsonify({'error': 'file not found'}), 404

    log.info('download: %s', abs_path)
    return send_file(abs_path, as_attachment=True)


@app.route('/api/upload', methods=['POST'])
def api_upload():
    data = request.get_json() or {}
    path = data.get('path')
    port = data.get('port')
    fqbn = data.get('fqbn')  # fully qualified board name
    log.info('upload request: port=%s fqbn=%s path=%s', port, fqbn, path)

    if not path or not port or not fqbn:
        return jsonify({'error': 'path, port, and fqbn are required'}), 400

    # Ensure arduino-cli is installed
    if shutil.which('arduino-cli') is None:
        log.error('arduino-cli not found on PATH')
        return jsonify({'error': 'arduino-cli not found on PATH'}), 500

    # Validate port exists on the system
    if not os.path.exists(port):
        log.error('port does not exist: %s', port)
        # Fetch available ports to help the user
        try:
            proc = subprocess.run(
                ['arduino-cli', 'board', 'list', '--format', 'json'],
                capture_output=True, text=True, timeout=10,
            )
            available = []
            if proc.stdout.strip():
                raw = json.loads(proc.stdout)
                entries = raw.get('detected_ports', raw if isinstance(raw, list) else [])
                for entry in entries:
                    port_info = entry.get('port') or entry
                    address = port_info.get('address') or port_info.get('label', '')
                    if address:
                        available.append(address)
            log.info('available ports: %s', available)
        except Exception:
            available = []

        msg = f"Port '{port}' not found."
        if available:
            msg += f" Available ports: {', '.join(available)}"
        else:
            msg += " No Arduino boards detected. Check your USB connection."
        return jsonify({'error': msg}), 400

    # arduino-cli expects a sketch folder; use the directory containing the .ino
    sketch_dir = os.path.dirname(os.path.abspath(path))

    try:
        compile_cmd = ['arduino-cli', 'compile', '--fqbn', fqbn, sketch_dir]
        upload_cmd = ['arduino-cli', 'upload', '-p', port, '--fqbn', fqbn, sketch_dir]

        log.info('compiling: %s', ' '.join(compile_cmd))
        compile_proc = subprocess.run(compile_cmd, capture_output=True, text=True)
        log.debug('compile stdout: %s', compile_proc.stdout)
        log.debug('compile stderr: %s', compile_proc.stderr)
        if compile_proc.returncode != 0:
            log.error('compile failed (exit %d): %s', compile_proc.returncode, compile_proc.stderr)
            return jsonify({'error': 'compile failed', 'output': compile_proc.stderr}), 500

        log.info('uploading: %s', ' '.join(upload_cmd))
        upload_proc = subprocess.run(upload_cmd, capture_output=True, text=True)
        log.debug('upload stdout: %s', upload_proc.stdout)
        log.debug('upload stderr: %s', upload_proc.stderr)
        if upload_proc.returncode != 0:
            log.error('upload failed (exit %d): %s', upload_proc.returncode, upload_proc.stderr)
            return jsonify({'error': 'upload failed', 'output': upload_proc.stderr}), 500

        log.info('upload successful')
        return jsonify({'message': 'uploaded', 'compile': compile_proc.stdout, 'upload': upload_proc.stdout})

    except Exception as e:
        log.exception('upload endpoint failed')
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='127.0.0.1', port=port, debug=True)
