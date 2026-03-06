from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import os
import sys
import shutil
import subprocess
import glob
import logging
import json

# Allow importing arduino_translator from project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from arduino_translator import get_openai_client, translate_to_arduino, save_code_to_file

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger('cursorbot')

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
    logger.info('generate request: model=%s prompt=%r', model, prompt[:80])
    if not prompt:
        return jsonify({'error': 'Prompt is required'}), 400

    try:
        client = get_openai_client()
        code = translate_to_arduino(client, prompt, model)
        filepath = save_code_to_file(code, prompt)
        logger.info('generated code saved to %s', filepath)
        return jsonify({'code': code, 'filepath': filepath})
    except Exception as e:
        logger.exception('generate failed')
        return jsonify({'error': str(e)}), 500


@app.route('/api/ports')
def api_ports():
    """Return a list of connected Arduino boards/ports via arduino-cli."""
    if shutil.which('arduino-cli') is None:
        logger.warning('arduino-cli not found on PATH')
        return jsonify({'error': 'arduino-cli not found on PATH'}), 500

    try:
        proc = subprocess.run(
            ['arduino-cli', 'board', 'list', '--format', 'json'],
            capture_output=True, text=True, timeout=10,
        )
        logger.debug('arduino-cli board list stdout: %s', proc.stdout)
        logger.debug('arduino-cli board list stderr: %s', proc.stderr)

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

        logger.info('found %d port(s): %s', len(detected), detected)
        return jsonify({'ports': detected})
    except subprocess.TimeoutExpired:
        logger.error('arduino-cli board list timed out')
        return jsonify({'error': 'arduino-cli timed out'}), 500
    except Exception as e:
        logger.exception('ports endpoint failed')
        return jsonify({'error': str(e)}), 500


def _scan_serial_ports_direct():
    """Scan for serial ports via pyserial (works on Mac, Linux, Windows) when arduino-cli misses them."""
    boards = []
    skip_substrings = ('bluetooth', 'wlan-debug', 'debug', 'debug-console')
    try:
        import serial.tools.list_ports
        all_ports = list(serial.tools.list_ports.comports())
        logger.debug('pyserial list_ports: %s', [p.device for p in all_ports])
        for port in all_ports:
            path = port.device
            desc = (port.description or '').lower()
            if any(s in desc or s in path.lower() for s in skip_substrings):
                continue
            boards.append({
                'port': path,
                'fqbn': 'arduino:avr:uno',
                'name': 'Arduino (' + (port.description or path) + ')',
            })
    except Exception as e:
        logger.warning('pyserial scan failed: %s', e)
    if not boards and sys.platform != 'win32':
        for pat in ['/dev/cu.usbmodem*', '/dev/cu.usbserial*', '/dev/tty.usbmodem*', '/dev/tty.usbserial*', '/dev/ttyACM*', '/dev/ttyUSB*']:
            found = glob.glob(pat)
            if found:
                logger.debug('glob %s -> %s', pat, found)
            for path in found:
                if os.path.exists(path) and 'Bluetooth' not in path and 'wlan' not in path:
                    boards.append({
                        'port': path,
                        'fqbn': 'arduino:avr:uno',
                        'name': 'Arduino (' + os.path.basename(path) + ')',
                    })
                    break
    logger.info('_scan_serial_ports_direct found %s boards: %s', len(boards), [b['port'] for b in boards])
    return boards


@app.route('/api/boards')
def api_boards():
    """List connected boards (port + fqbn) via arduino-cli, with direct /dev scan fallback."""
    boards = []
    cli_path = shutil.which('arduino-cli')
    used_cli = False
    logger.info('api_boards: arduino-cli path=%s', cli_path)

    if cli_path:
        try:
            out = subprocess.run(
                [cli_path, 'board', 'list', '--json', '--discovery-timeout', '10s'],
                capture_output=True,
                text=True,
                timeout=15,
                env=os.environ.copy(),
            )
            logger.debug('arduino-cli board list returncode=%s stdout_len=%s stderr=%s', out.returncode, len(out.stdout or ''), (out.stderr or '').strip() or None)
            if out.returncode == 0 and out.stdout.strip():
                import json as _json
                data = _json.loads(out.stdout)
                items = data.get('detected_ports', data) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                logger.debug('arduino-cli detected_ports count=%s', len(items) if isinstance(items, list) else 'n/a')
                skip_ports = ('/dev/cu.Bluetooth-Incoming-Port', '/dev/cu.wlan-debug', '/dev/tty.Bluetooth-Incoming-Port', '/dev/tty.wlan-debug')
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    port_info = item.get('port') or {}
                    port = port_info.get('address') or port_info.get('label') or ''
                    if not port or port in skip_ports:
                        continue
                    matching = item.get('matching_boards') or []
                    if matching:
                        for board in matching:
                            boards.append({
                                'port': port,
                                'fqbn': board.get('fqbn') or 'arduino:avr:uno',
                                'name': board.get('name') or 'Unknown',
                            })
                        used_cli = True
                    else:
                        if any(x in port.lower() for x in ('usbmodem', 'usbserial', 'ttyacm', 'ttyusb', 'wchusbserial')):
                            boards.append({
                                'port': port,
                                'fqbn': 'arduino:avr:uno',
                                'name': 'Arduino (port: ' + os.path.basename(port) + ')',
                            })
                            used_cli = True
        except subprocess.TimeoutExpired:
            logger.warning('arduino-cli board list timed out')
        except Exception as e:
            logger.warning('arduino-cli board list failed: %s', e)

    if not boards:
        boards = _scan_serial_ports_direct()
    else:
        logger.info('api_boards: using arduino-cli, boards=%s', [b['port'] for b in boards])

    err = None
    if not boards and not cli_path:
        err = 'arduino-cli not found. Install from https://arduino.github.io/arduino-cli/'
    elif not boards:
        err = 'No boards found. Connect Arduino via USB and click Refresh. Run: arduino-cli core install arduino:avr'

    logger.info('api_boards returning %s boards, error=%s', len(boards), err)
    return jsonify({'boards': boards, 'error': err})


@app.route('/api/download')
def api_download():
    path = request.args.get('path')
    if not path:
        return jsonify({'error': 'path query parameter required'}), 400

    # Security: ensure path is inside project arduino_code folder
    abs_path = os.path.abspath(path)
    allowed_dir = os.path.abspath(os.path.join(PROJECT_ROOT, 'arduino_code'))
    if not abs_path.startswith(allowed_dir):
        logger.warning('download rejected for path outside allowed dir: %s', abs_path)
        return jsonify({'error': 'invalid path'}), 400

    if not os.path.exists(abs_path):
        return jsonify({'error': 'file not found'}), 404

    logger.info('download: %s', abs_path)
    return send_file(abs_path, as_attachment=True)


@app.route('/api/upload', methods=['POST'])
def api_upload():
    data = request.get_json() or {}
    path = data.get('path')
    port = data.get('port')
    fqbn = data.get('fqbn')  # fully qualified board name

    logger.info('api_upload request: path=%s port=%s fqbn=%s', path, port, fqbn)

    if not path or not port or not fqbn:
        return jsonify({'error': 'path, port, and fqbn are required'}), 400

    # Log whether the requested port exists *before* we try to upload (helps diagnose stale port)
    port_exists = os.path.exists(port) if port else False
    logger.info('api_upload: port %s exists=%s', port, port_exists)
    if not port_exists:
        logger.warning('api_upload: requested port does not exist. Connect board and click Refresh, then select the board again.')
        # Build a list of current ports so the user can fix the issue
        current_ports = []
        if sys.platform != 'win32':
            for pat in ['/dev/cu.usbmodem*', '/dev/cu.usbserial*', '/dev/tty.usbmodem*', '/dev/tty.usbserial*', '/dev/ttyACM*', '/dev/ttyUSB*']:
                for p in glob.glob(pat):
                    if os.path.exists(p) and 'Bluetooth' not in p and 'wlan' not in p:
                        current_ports.append(p)
        return jsonify({
            'error': 'upload failed',
            'output': (
                f'Port "{port}" not found. '
                'The board may have been unplugged or the port changed (e.g. usbserial-10 → usbserial-110). '
                'Click "Refresh" next to the board list, then select your board again and try uploading.'
            ),
            'port_requested': port,
            'port_exists': False,
            'current_ports': current_ports,
        }), 500

    cli_path = shutil.which('arduino-cli')
    if cli_path is None:
        return jsonify({'error': 'arduino-cli not found on PATH'}), 500

    # Resolve the saved .ino path
    sketch_file = os.path.abspath(path)

    if not os.path.exists(sketch_file):
        return jsonify({'error': 'sketch file not found', 'path': sketch_file}), 400

    if not os.path.isfile(sketch_file) or not sketch_file.lower().endswith('.ino'):
        return jsonify({'error': 'path must point to a .ino file', 'path': sketch_file}), 400

    # Arduino CLI expects a "sketch folder" whose name matches the main .ino file.
    # To make this work no matter how/where we saved the file, stage it into a
    # temporary sketch directory with matching names, then compile/upload from there.
    tmp_root = os.path.join(PROJECT_ROOT, 'arduino_tmp')
    os.makedirs(tmp_root, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(sketch_file))[0]
    sketch_dir = os.path.join(tmp_root, base_name)

    # Ensure the sketch folder exists and contains base_name.ino
    os.makedirs(sketch_dir, exist_ok=True)
    staged_main = os.path.join(sketch_dir, base_name + '.ino')

    try:
        shutil.copyfile(sketch_file, staged_main)
    except Exception as e:
        return jsonify({'error': f'failed to stage sketch file: {e}'}), 500

    try:
        env = os.environ.copy()
        compile_cmd = [cli_path, 'compile', '--fqbn', fqbn, sketch_dir]
        upload_cmd = [cli_path, 'upload', '-p', port, '--fqbn', fqbn, sketch_dir]

        logger.info('api_upload: running compile command: %s', ' '.join(compile_cmd))
        compile_proc = subprocess.run(compile_cmd, capture_output=True, text=True, env=env)
        if compile_proc.returncode != 0:
            logger.error('api_upload: compile failed returncode=%s stderr=%s stdout=%s', compile_proc.returncode, compile_proc.stderr, compile_proc.stdout)
            return jsonify({
                'error': 'compile failed',
                'output': compile_proc.stderr or compile_proc.stdout,
                'command': ' '.join(compile_cmd),
                'sketch_dir': sketch_dir,
            }), 500

        logger.info('api_upload: running upload command: %s', ' '.join(upload_cmd))
        upload_proc = subprocess.run(upload_cmd, capture_output=True, text=True, env=env)
        if upload_proc.returncode != 0:
            logger.error('api_upload: upload failed returncode=%s stderr=%s stdout=%s', upload_proc.returncode, upload_proc.stderr, upload_proc.stdout)
            return jsonify({
                'error': 'upload failed',
                'output': upload_proc.stderr or upload_proc.stdout,
                'command': ' '.join(upload_cmd),
                'sketch_dir': sketch_dir,
            }), 500

        logger.info('api_upload: upload succeeded')
        return jsonify({
            'message': 'uploaded',
            'compile': compile_proc.stdout,
            'upload': upload_proc.stdout,
            'sketch_dir': sketch_dir,
        })

    except Exception as e:
        logger.exception('api_upload: exception')
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Development server
    port = int(os.environ.get('FLASK_PORT', 5000))
    app.run(host='127.0.0.1', port=port, debug=True)
