/* Application add/edit form — core behaviour.
 * Configuration comes from window.APP_FORM_CONFIG, set in application_form.html.
 */
// "Today" buttons — fill the linked date input with today's date.
document.querySelectorAll('.today-btn').forEach(function (btn) {
  btn.addEventListener('click', function () {
    var today = new Date();
    var yyyy  = today.getFullYear();
    var mm    = String(today.getMonth() + 1).padStart(2, '0');
    var dd    = String(today.getDate()).padStart(2, '0');
    document.getElementById(btn.dataset.target).value = yyyy + '-' + mm + '-' + dd;
  });
});

// Job expiry hint when status changes to Submitted.
(function () {
  const statusSel = document.querySelector('select[name="status"]');
  const expiryIn  = document.getElementById('job_expiry_date');
  if (statusSel && expiryIn) {
    statusSel.addEventListener('change', function () {
      if (this.value === 'Submitted' && !expiryIn.value) {
        expiryIn.classList.add('border-warning');
        expiryIn.title = 'Consider recording the job ad expiry date while you have it handy.';
        setTimeout(() => {
          expiryIn.classList.remove('border-warning');
          expiryIn.title = '';
        }, 5000);
      }
    });
  }
})();

// Submit validation — show modal listing any missing required fields.
document.getElementById('submitBtn').addEventListener('click', function () {
  var missing = [];
  if (!document.getElementById('job_desc').value.trim())
    missing.push('Job Description / Role');
  if (!document.getElementById('company').value.trim())
    missing.push('Company');

  if (missing.length) {
    var list = document.getElementById('missingFieldsList');
    list.innerHTML = missing
      .map(function (f) { return '<li class="text-danger fw-semibold">' + f + '</li>'; })
      .join('');
    new bootstrap.Modal(document.getElementById('validationModal')).show();
    return;
  }
  document.getElementById('appForm').submit();
});

// Force-add: set the hidden field and re-submit.
var forceAddBtn = document.getElementById('forceAddBtn');
if (forceAddBtn) {
  forceAddBtn.addEventListener('click', function () {
    document.getElementById('force_add').value = '1';
    document.getElementById('appForm').submit();
  });
}

// Auto-show duplicate warning modal on page load when the server flagged one.
if (window.APP_FORM_CONFIG && window.APP_FORM_CONFIG.duplicateWarning) {
  window.addEventListener('DOMContentLoaded', function () {
    new bootstrap.Modal(document.getElementById('duplicateModal')).show();
  });
}
