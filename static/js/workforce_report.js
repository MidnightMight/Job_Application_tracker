// Workforce Australia report: copy one row or the whole table to the clipboard.

(function () {
  var table = document.getElementById('reportTable');
  var toastEl = document.getElementById('copyToast');

  function headings() {
    return Array.prototype.map.call(table.querySelectorAll('thead th'), function (th) {
      return th.textContent.trim();
    }).slice(1);   // drop the "Copy" column
  }

  function cells(tr) {
    return Array.prototype.map.call(tr.querySelectorAll('td'), function (td) {
      return td.textContent.trim();
    }).slice(1);
  }

  // navigator.clipboard only works on https:// or localhost; a NAS reached
  // over plain http:// needs the older execCommand fallback.
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var area = document.createElement('textarea');
      area.value = text;
      area.setAttribute('readonly', '');
      area.style.position = 'fixed';
      area.style.opacity = '0';
      document.body.appendChild(area);
      area.select();
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      document.body.removeChild(area);
      ok ? resolve() : reject(new Error('copy failed'));
    });
  }

  function notify(message, ok) {
    document.getElementById('copyToastBody').textContent = message;
    toastEl.classList.toggle('text-bg-success', ok);
    toastEl.classList.toggle('text-bg-danger', !ok);
    bootstrap.Toast.getOrCreateInstance(toastEl, {delay: 2000}).show();
  }

  if (!table) {
    return;
  }

  // One row: "Heading: value" lines, ready to paste into a form, email or note.
  table.querySelectorAll('.copy-row-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var names = headings();
      var values = cells(btn.closest('tr'));
      var text = names.map(function (name, i) { return name + ': ' + values[i]; })
                      .filter(function (line, i) { return values[i] !== ''; })
                      .join('\n');
      copyText(text).then(
        function () { notify('Copied ' + (values[2] || 'application') + '.', true); },
        function () { notify('Could not copy — select the row and copy it by hand.', false); }
      );
    });
  });

  // Whole table: tab-separated, so it pastes into a spreadsheet as columns.
  document.getElementById('copyAllBtn').addEventListener('click', function () {
    var lines = [headings().join('\t')];
    table.querySelectorAll('tbody tr').forEach(function (tr) {
      lines.push(cells(tr).join('\t'));
    });
    copyText(lines.join('\n')).then(
      function () { notify('Copied ' + (lines.length - 1) + ' applications.', true); },
      function () { notify('Could not copy — download the CSV instead.', false); }
    );
  });
})();
