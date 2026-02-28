from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import os
import sys
import shutil
import subprocess

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
    if not prompt:
        return jsonify({'error': 'Prompt is required'}), 400

    try:
        client = get_openai_client()
        code = translate_to_arduino(client, prompt, model)
        filepath = save_code_to_file(code, prompt)
        return jsonify({'code': code, 'filepath': filepath})
    except Exception as e:
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
        return jsonify({'error': 'invalid path'}), 400

    if not os.path.exists(abs_path):
        return jsonify({'error': 'file not found'}), 404

    return send_file(abs_path, as_attachment=True)


@app.route('/api/upload', methods=['POST'])
def api_upload():
    data = request.get_json() or {}
    path = data.get('path')
    port = data.get('port')
    fqbn = data.get('fqbn')  # fully qualified board name

    if not path or not port or not fqbn:
        return jsonify({'error': 'path, port, and fqbn are required'}), 400

    # Ensure arduino-cli is installed
    if shutil.which('arduino-cli') is None:
        return jsonify({'error': 'arduino-cli not found on PATH'}), 500

    # arduino-cli expects a sketch folder; use the directory containing the .ino
    sketch_dir = os.path.dirname(os.path.abspath(path))

    try:
        compile_cmd = ['arduino-cli', 'compile', '--fqbn', fqbn, sketch_dir]
        upload_cmd = ['arduino-cli', 'upload', '-p', port, '--fqbn', fqbn, sketch_dir]

        compile_proc = subprocess.run(compile_cmd, capture_output=True, text=True)
        if compile_proc.returncode != 0:
            return jsonify({'error': 'compile failed', 'output': compile_proc.stderr}), 500

        upload_proc = subprocess.run(upload_cmd, capture_output=True, text=True)
        if upload_proc.returncode != 0:
            return jsonify({'error': 'upload failed', 'output': upload_proc.stderr}), 500

        return jsonify({'message': 'uploaded', 'compile': compile_proc.stdout, 'upload': upload_proc.stdout})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Development server
    app.run(host='127.0.0.1', port=5000, debug=True)
