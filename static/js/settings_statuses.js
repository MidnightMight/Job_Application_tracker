/* Settings page — status colour pickers and drag-to-reorder (statuses section only).
 * Configuration comes from window.SETTINGS_CONFIG, set in settings.html.
 */
// ── Add-status colour pickers: live preview ───────────────────────────────
(function () {
  var nameInput    = document.getElementById('newStatusName');
  var bgPicker     = document.getElementById('newBgColor');
  var bgHex        = document.getElementById('newBgHex');
  var textPicker   = document.getElementById('newTextColor');
  var textHex      = document.getElementById('newTextHex');
  var preview      = document.getElementById('newStatusPreview');

  function hexValid(v) { return /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(v.trim()); }

  function updatePreview() {
    if (preview) {
      var label = (nameInput ? nameInput.value.replace(/_/g, ' ') || 'New Status' : 'New Status');
      preview.textContent = label;
      preview.style.backgroundColor = bgPicker ? bgPicker.value : '#6c757d';
      preview.style.color           = textPicker ? textPicker.value : '#ffffff';
    }
  }

  // Sync colour picker → hex text input
  if (bgPicker)   bgPicker.addEventListener('input',   function () { if (bgHex)   bgHex.value   = bgPicker.value;   updatePreview(); });
  if (textPicker) textPicker.addEventListener('input', function () { if (textHex) textHex.value = textPicker.value; updatePreview(); });

  // Sync hex text input → colour picker
  if (bgHex) bgHex.addEventListener('input', function () {
    if (hexValid(bgHex.value) && bgPicker) { bgPicker.value = bgHex.value; updatePreview(); }
  });
  if (textHex) textHex.addEventListener('input', function () {
    if (hexValid(textHex.value) && textPicker) { textPicker.value = textHex.value; updatePreview(); }
  });

  if (nameInput) nameInput.addEventListener('input', updatePreview);

  updatePreview();
})();

// ── Inline colour pickers: live badge preview ─────────────────────────────
(function () {
  document.querySelectorAll('.colour-form').forEach(function (form) {
    var previewId = form.getAttribute('data-preview');
    var badge     = previewId ? document.getElementById(previewId) : null;
    var inputs    = form.querySelectorAll('.colour-input');
    inputs.forEach(function (inp) {
      inp.addEventListener('input', function () {
        if (!badge) return;
        var bg   = form.querySelector('[name="bg_color"]');
        var tc   = form.querySelector('[name="text_color"]');
        if (bg)   badge.style.backgroundColor = bg.value;
        if (tc)   badge.style.color           = tc.value;
      });
    });
  });
})();

// ── Clear-colour buttons ──────────────────────────────────────────────────
(function () {
  document.querySelectorAll('.clear-colour-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var name = btn.getAttribute('data-name');
      var form = document.createElement('form');
      form.method = 'post';
      form.action = window.SETTINGS_CONFIG.urls.statusesSection;
      [['action', 'update_status_colors'], ['name', name], ['bg_color', ''], ['text_color', '']].forEach(function (pair) {
        var inp = document.createElement('input');
        inp.type = 'hidden'; inp.name = pair[0]; inp.value = pair[1];
        form.appendChild(inp);
      });
      document.body.appendChild(form);
      form.submit();
    });
  });
})();

// ── Drag-and-drop reordering ──────────────────────────────────────────────
(function () {
  var tbody     = document.getElementById('statusTbody');
  if (!tbody) return;
  var dragging  = null;

  function getRows() { return Array.from(tbody.querySelectorAll('tr.status-row')); }

  function renumber() {
    getRows().forEach(function (row, i) {
      var cell = row.querySelector('.row-num');
      if (cell) cell.textContent = i + 1;
    });
  }

  tbody.addEventListener('dragstart', function (e) {
    dragging = e.target.closest('tr.status-row');
    if (dragging) {
      dragging.style.opacity = '0.5';
      e.dataTransfer.effectAllowed = 'move';
    }
  });

  tbody.addEventListener('dragend', function () {
    if (dragging) dragging.style.opacity = '';
    tbody.querySelectorAll('tr.status-row').forEach(function (r) { r.classList.remove('drag-over'); });
    dragging = null;
  });

  tbody.addEventListener('dragover', function (e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    var target = e.target.closest('tr.status-row');
    if (target && target !== dragging) {
      tbody.querySelectorAll('tr.status-row').forEach(function (r) { r.classList.remove('drag-over'); });
      target.classList.add('drag-over');
    }
  });

  tbody.addEventListener('drop', function (e) {
    e.preventDefault();
    var target = e.target.closest('tr.status-row');
    if (!target || target === dragging || !dragging) return;
    var rows = getRows();
    var fromIdx = rows.indexOf(dragging);
    var toIdx   = rows.indexOf(target);
    if (fromIdx < toIdx) {
      target.after(dragging);
    } else {
      target.before(dragging);
    }
    renumber();
    target.classList.remove('drag-over');
    saveOrder();
  });

  function saveOrder() {
    var names = getRows().map(function (r) { return r.getAttribute('data-name'); });
    fetch(window.SETTINGS_CONFIG.urls.reorderStatuses, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({names: names}),
    }).then(function (resp) {
      return resp.json();
    }).then(function (data) {
      if (!data.ok) {
        console.error('Reorder failed:', data.message);
      }
    }).catch(function (err) {
      console.error('Reorder request failed:', err);
    });
  }
})();
