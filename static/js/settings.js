/* Settings page — AI, profile upload and update checks.
 * Configuration comes from window.SETTINGS_CONFIG, set in settings.html.
 */
// ── Ollama test connection ────────────────────────────────────────────────
const testBtn = document.getElementById('testOllamaBtn');

function updateSettingsStatusBadge(ok) {
  const badge = document.getElementById('ollamaSettingsStatusBadge');
  if (!badge) return;
  if (ok) {
    badge.className = 'badge bg-success small';
    badge.innerHTML = '<i class="bi bi-circle-fill me-1" style="font-size:.55rem;vertical-align:middle;"></i>Online';
  } else {
    badge.className = 'badge bg-danger small';
    badge.innerHTML = '<i class="bi bi-circle-fill me-1" style="font-size:.55rem;vertical-align:middle;"></i>Offline';
  }
}

if (testBtn) {
  testBtn.addEventListener('click', async () => {
    const url = document.getElementById('ollama_url').value.trim();
    const result = document.getElementById('ollamaTestResult');
    const models = document.getElementById('availableModels');
    result.textContent = 'Testing connection…';
    result.className = 'form-text mt-1 text-muted';
    try {
      const resp = await fetch(window.SETTINGS_CONFIG.urls.ollamaTest, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content},
        body: JSON.stringify({url}),
      });
      const data = await resp.json();
      if (data.ok) {
        result.textContent = '✓ Connected successfully!';
        result.className = 'form-text mt-1 text-success';
        if (data.models && data.models.length) {
          models.textContent = ' Available: ' + data.models.join(', ');
        }
        updateSettingsStatusBadge(true);
      } else {
        result.textContent = '✗ Connection failed: ' + (data.error || 'unknown error');
        result.className = 'form-text mt-1 text-danger';
        updateSettingsStatusBadge(false);
      }
    } catch (e) {
      result.textContent = '✗ Request error: ' + e.message;
      result.className = 'form-text mt-1 text-danger';
      updateSettingsStatusBadge(false);
    }
  });
}

// ── Auto-ping on AI settings page load ──────────────────────────────────
(async function autoCheckStatus() {
  const badge = document.getElementById('ollamaSettingsStatusBadge');
  if (!badge) return;  // not on AI section or ollama disabled
  try {
    const resp = await fetch(window.SETTINGS_CONFIG.urls.ollamaStatus);
    const data = await resp.json();
    updateSettingsStatusBadge(data.ok);
    if (data.ok && data.models && data.models.length) {
      const modelsSpan = document.getElementById('availableModels');
      if (modelsSpan) modelsSpan.textContent = ' Available: ' + data.models.join(', ');
    }
  } catch {
    updateSettingsStatusBadge(false);
  }
})();

// ── Toggle profile card visibility when ai_fit_enabled changes ─────────
const fitToggle    = document.getElementById('ai_fit_enabled');
if (fitToggle) {
  // Profile card is always visible now; no-op kept for compatibility.
}

// ── Per-user AI provider selector ────────────────────────────────────────
(function () {
  const toggle         = document.getElementById('useAdminAiToggle');
  const hiddenInput    = document.getElementById('useAdminAiInput');
  const adminBanner    = document.getElementById('adminAiBanner');
  const ownSection     = document.getElementById('ownProviderSection');
  const sel            = document.getElementById('aiProviderSelect');
  const apiSection     = document.getElementById('providerApiSection');
  const apiKeyRow      = document.getElementById('apiKeyRow');
  const customUrlRow   = document.getElementById('customUrlRow');
  const modelInput     = document.getElementById('aiModelInput');
  const modelHint      = document.getElementById('modelHint');
  const apiUrlInput    = document.querySelector('#customUrlRow input[name="api_url"]');
  const apiKeyInput    = document.querySelector('#apiKeyRow input[name="api_key"]');
  const profileFieldset = document.getElementById('profileCardFieldset');
  const profileCard    = document.getElementById('profileCard');
  const adminToggle    = document.getElementById('ollama_enabled');
  const adminAiEnabledStatic = window.SETTINGS_CONFIG.adminAiEnabled;

  const modelPlaceholders = {
    ollama:    'llama3',
    openai:    'gpt-4o-mini',
    anthropic: 'claude-3-haiku-20240307',
    custom:    'e.g. mistral, llama3',
  };
  const modelHints = {
    ollama:    'Any model available on your personal Ollama server (e.g. llama3).',
    openai:    'e.g. gpt-4o-mini, gpt-4o, gpt-3.5-turbo',
    anthropic: 'e.g. claude-3-haiku-20240307, claude-3-sonnet-20240229',
    custom:    'Model name accepted by your custom API server.',
  };

  function updateProviderUI() {
    if (!sel) return;
    const provider = sel.value;
    if (customUrlRow) customUrlRow.style.display = (provider === 'custom' || provider === 'ollama') ? '' : 'none';
    if (apiKeyRow) apiKeyRow.style.display = (provider === 'openai' || provider === 'anthropic' || provider === 'custom') ? '' : 'none';
    if (modelInput) modelInput.placeholder = modelPlaceholders[provider] || '';
    if (modelHint)  modelHint.textContent  = modelHints[provider] || '';
    updateProfileCardState();
  }

  function ownProviderConfigured() {
    if (!toggle || !sel || !apiUrlInput || !apiKeyInput) return false;
    if (toggle.checked) return false; // using admin server
    const provider = sel.value;
    if (provider === 'ollama' || provider === 'custom') return !!apiUrlInput.value.trim();
    return !!apiKeyInput.value.trim();
  }

  function updateProfileCardState() {
    if (!profileFieldset || !profileCard) return;
    const adminEnabled = adminToggle ? adminToggle.checked : adminAiEnabledStatic;
    const enabled = adminEnabled || ownProviderConfigured();
    profileFieldset.disabled = !enabled;
    profileCard.classList.toggle('profile-card-disabled', !enabled);
  }

  function applyToggle(useAdmin) {
    if (hiddenInput)  hiddenInput.value        = useAdmin ? '1' : '0';
    if (adminBanner)  adminBanner.style.display = useAdmin ? '' : 'none';
    if (ownSection)   ownSection.style.display  = useAdmin ? 'none' : '';
    updateProfileCardState();
  }

  if (toggle) {
    toggle.addEventListener('change', function () {
      applyToggle(this.checked);
    });
    // Initialise to match current state (driven by server-rendered checked attribute).
    applyToggle(toggle.checked);
  }

  if (sel) sel.addEventListener('change', updateProviderUI);
  if (apiUrlInput) apiUrlInput.addEventListener('input', updateProfileCardState);
  if (apiKeyInput) apiKeyInput.addEventListener('input', updateProfileCardState);
  if (adminToggle) adminToggle.addEventListener('change', updateProfileCardState);
  updateProviderUI();
  updateProfileCardState();
})();

// ── PDF profile upload ────────────────────────────────────────────────
const uploadBtn     = document.getElementById('uploadPdfBtn');
const pdfInput      = document.getElementById('profilePdfInput');
const pdfSpinner    = document.getElementById('pdfUploadSpinner');
const pdfResult     = document.getElementById('pdfUploadResult');
const summaryField  = document.getElementById('user_profile_summary');

if (uploadBtn) {
  uploadBtn.addEventListener('click', async () => {
    const file = pdfInput && pdfInput.files[0];
    if (!file) {
      pdfResult.innerHTML = '<span class="text-danger small"><i class="bi bi-exclamation-circle me-1"></i>Please select a PDF file first.</span>';
      return;
    }
    uploadBtn.disabled = true;
    pdfSpinner.classList.remove('d-none');
    pdfResult.innerHTML = '';

    const formData = new FormData();
    formData.append('pdf', file);

    try {
      const resp = await fetch(window.SETTINGS_CONFIG.urls.uploadProfilePdf, {
        method: 'POST',
        headers: {'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content},
        body: formData,
      });
      const data = await resp.json();
      if (data.ok) {
        if (summaryField) summaryField.value = data.preview + (data.char_count > 300 ? '\n…[truncated]' : '');
        pdfResult.innerHTML = `<div class="alert alert-success py-2 small mt-1">
          <i class="bi bi-check-circle me-1"></i>
          Extracted <strong>${data.char_count}</strong> characters from PDF.
          The summary field has been updated — save your profile to keep it.
        </div>`;
      } else {
        pdfResult.innerHTML = `<span class="text-danger small"><i class="bi bi-exclamation-circle me-1"></i>${escHtml(data.error)}</span>`;
      }
    } catch (e) {
      pdfResult.innerHTML = `<span class="text-danger small">Upload failed: ${escHtml(e.message)}</span>`;
    } finally {
      uploadBtn.disabled = false;
      pdfSpinner.classList.add('d-none');
    }
  });
}

function escHtml(str) {
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
const checkBtn = document.getElementById('checkUpdateBtn');
const deploymentMode = window.SETTINGS_CONFIG.deploymentMode;
if (checkBtn) {
  checkBtn.addEventListener('click', async () => {
    const div = document.getElementById('updateResult');
    div.innerHTML = '<span class="text-muted"><i class="bi bi-hourglass-split me-1"></i>Checking…</span>';
    try {
      const resp = await fetch(window.SETTINGS_CONFIG.urls.checkUpdate);
      const data = await resp.json();
      if (!data.ok) {
        div.innerHTML = `<div class="alert alert-warning py-2"><i class="bi bi-exclamation-triangle me-1"></i>${escHtml(data.error || 'Unknown error checking for updates.')}</div>`;
        return;
      }
      if (data.update_available) {
        const dockerSteps = `
          <ol class="mb-0 ps-3">
            <li>Pull the latest image and restart:<br>
              <code>docker compose pull &amp;&amp; docker compose up -d</code>
            </li>
            <li>If you build locally from source instead:<br>
              <code>git pull origin main &amp;&amp; docker compose up --build -d</code>
            </li>
          </ol>`;
        const localSteps = `
          <ol class="mb-0 ps-3">
            <li>Stop the running server</li>
            <li><code>git pull origin main</code></li>
            <li><code>pip install -r requirements.txt</code></li>
            <li>Restart the server</li>
          </ol>`;
        const steps = deploymentMode === 'docker' ? dockerSteps : localSteps;
        div.innerHTML = `
          <div class="alert alert-success py-2 mb-2">
            <i class="bi bi-arrow-up-circle me-1"></i>
            A new version <strong>v${escHtml(data.latest)}</strong> is available!
            <a href="${escHtml(data.html_url)}" target="_blank" rel="noopener" class="alert-link ms-2">
              View release notes <i class="bi bi-box-arrow-up-right"></i>
            </a>
          </div>
          <div class="alert alert-warning py-2 mb-2">
            <i class="bi bi-database-fill-exclamation me-1"></i>
            <strong>Back up your data before updating!</strong>
            Go to <strong>Export &rarr; Download Full Database</strong> to save a copy of your jobs database.
          </div>
          <div class="card card-body small py-2">
            <strong class="d-block mb-1"><i class="bi bi-terminal me-1"></i>How to update:</strong>
            ${steps}
          </div>`;
      } else {
        div.innerHTML = `<div class="alert alert-info py-2">
          <i class="bi bi-check-circle me-1"></i>
          You are running the latest version (v${escHtml(data.current)}).
        </div>`;
      }
    } catch (e) {
      div.innerHTML = `<div class="alert alert-danger py-2">Error: ${escHtml(e.message)}</div>`;
    }
  });
}

// ── Calendar feed: copy the private link ──────────────────────────────────
// navigator.clipboard needs https:// or localhost; plain http:// falls back to execCommand.
(function () {
  const btn = document.getElementById('copyCalendarUrl');
  const input = document.getElementById('calendarUrl');
  if (!btn || !input) return;
  btn.addEventListener('click', async () => {
    let ok = false;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(input.value);
        ok = true;
      } else {
        input.select();
        ok = document.execCommand('copy');
      }
    } catch (e) { ok = false; }
    btn.innerHTML = ok ? '<i class="bi bi-check2 me-1"></i>Copied'
                       : '<i class="bi bi-clipboard me-1"></i>Select and copy';
    if (!ok) { input.select(); }
  });
})();
