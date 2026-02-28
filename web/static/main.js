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
const portInput = document.getElementById('port');
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

uploadBtn.addEventListener('click', () => {
  uploadForm.classList.remove('hidden');
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
