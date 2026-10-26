/* Application add/edit form — AI fill panel (loaded only when AI is available).
 * Configuration comes from window.APP_FORM_CONFIG, set in application_form.html.
 */
(function () {
  const fillBtn      = document.getElementById('aiFillBtn');
  const clearBtn     = document.getElementById('aiClearBtn');
  const textarea     = document.getElementById('aiJobDesc');
  const spinner      = document.getElementById('aiSpinner');
  const statusDiv    = document.getElementById('aiStatus');
  const chevron      = document.getElementById('aiFillChevron');
  const offlineOverlay = document.getElementById('aiOfflineOverlay');

  // ── Server status badge ────────────────────────────────────────────────
  const serverBadge = document.getElementById('ollamaServerBadge');

  function setServerBadge(state) {
    // state: 'checking' | 'online' | 'offline'
    serverBadge.style.display = '';
    if (state === 'checking') {
      serverBadge.className = 'badge ms-2 small bg-secondary';
      serverBadge.innerHTML = '<span class="spinner-grow spinner-grow-sm me-1" style="width:.5rem;height:.5rem;" role="status"></span>Checking…';
    } else if (state === 'online') {
      serverBadge.className = 'badge ms-2 small bg-success';
      serverBadge.innerHTML = '<i class="bi bi-circle-fill me-1" style="font-size:.55rem;vertical-align:middle;"></i>Server online';
    } else {
      serverBadge.className = 'badge ms-2 small bg-danger';
      serverBadge.innerHTML = '<i class="bi bi-circle-fill me-1" style="font-size:.55rem;vertical-align:middle;"></i>Server offline';
    }
  }

  function applyOfflineState(isOffline) {
    if (!offlineOverlay) return;
    if (isOffline) {
      // Show overlay and collapse the body so it's minimised by default.
      offlineOverlay.style.display = '';
      offlineOverlay.setAttribute('aria-hidden', 'false');
      if (fillBtn)  { fillBtn.disabled  = true; }
      if (clearBtn) { clearBtn.disabled = true; }
      if (textarea) { textarea.disabled = true; }
    } else {
      offlineOverlay.style.display = 'none';
      offlineOverlay.setAttribute('aria-hidden', 'true');
      if (fillBtn)  { fillBtn.disabled  = false; }
      if (clearBtn) { clearBtn.disabled = false; }
      if (textarea) { textarea.disabled = false; }
    }
  }

  async function checkServerStatus() {
    setServerBadge('checking');
    try {
      const resp = await fetch(window.APP_FORM_CONFIG.urls.ollamaStatus);
      const data = await resp.json();
      setServerBadge(data.ok ? 'online' : 'offline');
      applyOfflineState(!data.ok);
      if (!data.ok) {
        // Collapse the panel so it appears minimised; user can still open it to see the overlay.
        const body = document.getElementById('aiFillBody');
        if (body && body.classList.contains('show')) {
          const bsCollapse = bootstrap.Collapse.getOrCreateInstance(body, {toggle: false});
          bsCollapse.hide();
        }
      }
    } catch {
      setServerBadge('offline');
      applyOfflineState(true);
    }
  }

  // Check on load and when the panel is expanded.
  checkServerStatus();
  document.getElementById('aiFillBody').addEventListener('show.bs.collapse', () => {
    chevron.className = 'bi bi-chevron-up';
    checkServerStatus();
  });
  document.getElementById('aiFillBody').addEventListener('hide.bs.collapse', () => {
    chevron.className = 'bi bi-chevron-down';
  });

  clearBtn.addEventListener('click', () => {
    textarea.value = '';
    statusDiv.innerHTML = '';
  });

  fillBtn.addEventListener('click', async () => {
    const jd = textarea.value.trim();
    if (!jd) {
      statusDiv.innerHTML = '<span class="text-danger small"><i class="bi bi-exclamation-circle me-1"></i>Please paste a job description first.</span>';
      return;
    }

    fillBtn.disabled = true;
    spinner.classList.remove('d-none');
    statusDiv.innerHTML = '';

    try {
      const resp = await fetch(window.APP_FORM_CONFIG.urls.aiFill, {
        method:  'POST',
        headers: {'Content-Type': 'application/json'},
        body:    JSON.stringify({job_description: jd}),
      });
      const data = await resp.json();

      if (!data.ok) {
        statusDiv.innerHTML = `<span class="text-danger small"><i class="bi bi-exclamation-circle me-1"></i>${escHtml(data.error)}</span>`;
        return;
      }

      const f = data.fields;
      const filled = [];

      // Map returned fields to form inputs.
      if (f.job_desc)  { setField('job_desc',  f.job_desc);  filled.push('Role');    }
      if (f.company)   { setField('company',   f.company);   filled.push('Company'); }
      if (f.team)      { setField('team',      f.team);      filled.push('Team');    }
      if (f.link)      { setField('link',      f.link);      filled.push('Link');    }
      if (f.comment)   { setField('comment',   f.comment);   filled.push('Comments');}

      if (filled.length) {
        statusDiv.innerHTML = `
          <div class="alert alert-success py-2 small mb-0">
            <i class="bi bi-check-circle me-1"></i>
            AI filled: <strong>${filled.join(', ')}</strong>.
            Please review the values and adjust if needed before saving.
          </div>`;
        // Scroll the main form into view so the user can see the filled fields.
        document.getElementById('appFormCardHeader').scrollIntoView({behavior:'smooth', block:'start'});
        // Trigger fit analysis if enabled.
        if (typeof runFitAnalysis === 'function') runFitAnalysis(jd);
      } else {
        statusDiv.innerHTML = '<span class="text-warning small"><i class="bi bi-question-circle me-1"></i>AI responded but could not extract any fields. Try pasting more of the job description.</span>';
      }

    } catch (err) {
      statusDiv.innerHTML = `<span class="text-danger small"><i class="bi bi-exclamation-circle me-1"></i>Request failed: ${escHtml(err.message)}</span>`;
    } finally {
      fillBtn.disabled = false;
      spinner.classList.add('d-none');
    }
  });

  function setField(id, value) {
    const el = document.getElementById(id);
    if (!el || !value) return;
    if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
      el.value = value;
      // Briefly highlight the field so the user notices the change.
      el.classList.add('border-warning');
      setTimeout(() => el.classList.remove('border-warning'), 2500);
    }
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
})();
