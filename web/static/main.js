(function () {
  'use strict';

  async function postJSON(url, data) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return res.json();
  }

  let lastFilepath = null;
  let boardsList = [];

  function init() {
    const promptEl = document.getElementById('prompt');
    const generateBtn = document.getElementById('generate');
    const codeEl = document.getElementById('code');
    const downloadBtn = document.getElementById('download');
    const uploadBtn = document.getElementById('upload');
    const statusEl = document.getElementById('status');
    const uploadForm = document.getElementById('upload-form');
    const boardSelect = document.getElementById('board-select');
    const toggleManual = document.getElementById('toggle-manual');
    const manualInputs = document.getElementById('manual-inputs');
    const portInput = document.getElementById('port');
    const fqbnInput = document.getElementById('fqbn');
    const doUploadBtn = document.getElementById('do-upload');

    if (!uploadBtn || !uploadForm) return;

    function showUploadForm() {
      uploadForm.classList.remove('hidden');
      uploadForm.style.display = 'block';
      uploadForm.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    if (generateBtn && promptEl && codeEl && statusEl) {
      generateBtn.addEventListener('click', async () => {
        const prompt = promptEl.value.trim();
        if (!prompt) { alert('Please enter a description.'); return; }
        statusEl.textContent = 'Generating...';
        try {
          const result = await postJSON('/api/generate', { prompt });
          if (result.error) {
            statusEl.textContent = 'Error: ' + result.error;
            return;
          }
          codeEl.textContent = result.code;
          lastFilepath = result.filepath || null;
          if (downloadBtn) downloadBtn.disabled = false;
          statusEl.textContent = 'Generated and saved: ' + (result.filepath || '');
        } catch (e) {
          statusEl.textContent = 'Error: ' + e.message;
        }
      });
    }

    if (downloadBtn) {
      downloadBtn.addEventListener('click', () => {
        if (!lastFilepath) return;
        window.location.href = '/api/download?path=' + encodeURIComponent(lastFilepath);
      });
    }

    function loadBoards() {
      if (!boardSelect) return;
      boardSelect.innerHTML = '<option value="">— Loading… —</option>';
      if (statusEl) statusEl.textContent = '';

      fetch('/api/boards')
        .then(function (res) { return res.json(); })
        .then(function (data) {
          boardsList = data.boards || [];
          boardSelect.innerHTML = boardsList.length ? '<option value="">— Select connected board —</option>' : '<option value="">— No boards detected —</option>';
          boardsList.forEach(function (b, i) {
            const opt = document.createElement('option');
            opt.value = String(i);
            opt.textContent = (b.name || 'Board') + ' (' + (b.port || '') + ')';
            boardSelect.appendChild(opt);
          });
          if (boardsList.length === 1) {
            boardSelect.value = '0';
            if (statusEl) statusEl.textContent = 'Board detected and selected. Click "Upload to board" below (no typing needed).';
          } else if (boardsList.length > 1 && statusEl) {
            statusEl.textContent = boardsList.length + ' boards detected. Select one from the dropdown, then click "Upload to board".';
          } else if (boardsList.length === 0 && data.error && statusEl) {
            statusEl.textContent = data.error + ' Or enter Port and FQBN manually below.';
          }
        })
        .catch(function (e) {
          boardSelect.innerHTML = '<option value="">— Error loading boards —</option>';
          if (statusEl) statusEl.textContent = 'Could not load boards: ' + e.message + ' You can enter port and FQBN manually below.';
        });
    }

    uploadBtn.addEventListener('click', function () {
      showUploadForm();
      if (!lastFilepath && statusEl) {
        statusEl.textContent = 'Generate code first (enter a description and click Generate Code). Then select a board and click "Upload to board".';
      }
      loadBoards();
    });

    var refreshBtn = document.getElementById('refresh-boards');
    if (refreshBtn) refreshBtn.addEventListener('click', loadBoards);

    if (doUploadBtn && boardSelect && portInput && fqbnInput && statusEl) {
      doUploadBtn.addEventListener('click', async function () {
        if (!lastFilepath) {
          alert('No file to upload. Generate code first (enter a description and click Generate Code).');
          return;
        }
        var port, fqbn;
        var sel = boardSelect.value;
        if (sel !== '' && boardsList[Number(sel)]) {
          var b = boardsList[Number(sel)];
          port = b.port;
          fqbn = b.fqbn;
        } else {
          port = portInput.value.trim();
          fqbn = fqbnInput.value.trim();
        }
        if (!port || !fqbn) {
          alert('Select a board from the dropdown, or use "enter port & FQBN manually" and fill Port and FQBN.');
          return;
        }
        statusEl.textContent = 'Compiling and uploading…';
        try {
          var result = await postJSON('/api/upload', { path: lastFilepath, port: port, fqbn: fqbn });
          if (result.error) {
            var msg = 'Upload error: ' + result.error;
            if (result.output) msg += '\n' + result.output;
            if (result.current_ports && result.current_ports.length > 0) {
              msg += '\n\nCurrent ports: ' + result.current_ports.join(', ') + '. Click Refresh and select your board again.';
            }
            statusEl.textContent = msg;
          } else {
            statusEl.textContent = 'Upload successful. Code is running on your board.';
          }
        } catch (e) {
          statusEl.textContent = 'Upload error: ' + e.message;
        }
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
