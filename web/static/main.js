async function postJSON(url, data) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return res.json();
}

const promptEl = document.getElementById('prompt');
const generateBtn = document.getElementById('generate');
const codeEl = document.getElementById('code');
const downloadBtn = document.getElementById('download');
const uploadBtn = document.getElementById('upload');
const statusEl = document.getElementById('status');
const uploadForm = document.getElementById('upload-form');
const portSelect = document.getElementById('port-select');
const portInput = document.getElementById('port');
const refreshPortsBtn = document.getElementById('refresh-ports');
const fqbnInput = document.getElementById('fqbn');
const doUploadBtn = document.getElementById('do-upload');

let lastFilepath = null;

generateBtn.addEventListener('click', async () => {
  const prompt = promptEl.value.trim();
  if (!prompt) return alert('Please enter a description.');

  statusEl.textContent = 'Generating...';
  const result = await postJSON('/api/generate', { prompt });

  if (result.error) {
    statusEl.textContent = 'Error: ' + result.error;
    return;
  }

  codeEl.textContent = result.code;
  lastFilepath = result.filepath;
  downloadBtn.disabled = false;
  uploadBtn.disabled = false;
  statusEl.textContent = 'Generated and saved: ' + result.filepath;
});

downloadBtn.addEventListener('click', () => {
  if (!lastFilepath) return;
  const url = '/api/download?path=' + encodeURIComponent(lastFilepath);
  window.location = url;
});

async function loadPorts() {
  portSelect.innerHTML = '<option value="">-- loading... --</option>';
  try {
    const res = await fetch('/api/ports');
    const data = await res.json();
    portSelect.innerHTML = '';
    if (data.error) {
      portSelect.innerHTML = `<option value="">${data.error}</option>`;
      return;
    }
    if (!data.ports || data.ports.length === 0) {
      portSelect.innerHTML = '<option value="">No boards detected — check USB</option>';
      return;
    }
    data.ports.forEach(p => {
      const label = p.name ? `${p.port} (${p.name})` : p.port;
      const opt = new Option(label, p.port);
      opt.dataset.fqbn = p.fqbn || '';
      portSelect.appendChild(opt);
    });
    // Pre-fill the manual input and fqbn from first result
    const first = data.ports[0];
    portInput.value = first.port;
    if (first.fqbn) fqbnInput.value = first.fqbn;
  } catch (e) {
    portSelect.innerHTML = `<option value="">Error: ${e.message}</option>`;
  }
}

portSelect.addEventListener('change', () => {
  const opt = portSelect.selectedOptions[0];
  if (opt && opt.value) {
    portInput.value = opt.value;
    if (opt.dataset.fqbn) fqbnInput.value = opt.dataset.fqbn;
  }
});

refreshPortsBtn.addEventListener('click', loadPorts);

uploadBtn.addEventListener('click', () => {
  uploadForm.classList.remove('hidden');
  loadPorts();
});

doUploadBtn.addEventListener('click', async () => {
  if (!lastFilepath) return alert('No file to upload');
  const port = portInput.value.trim();
  const fqbn = fqbnInput.value.trim();
  if (!port || !fqbn) return alert('Port and FQBN required');

  statusEl.textContent = 'Uploading...';
  const result = await postJSON('/api/upload', { path: lastFilepath, port, fqbn });
  if (result.error) {
    statusEl.textContent = 'Upload error: ' + result.error + (result.output ? '\n' + result.output : '');
  } else {
    statusEl.textContent = 'Upload successful';
  }
});
