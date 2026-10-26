/* Application add/edit form — AI fit analysis (loaded only when fit analysis is enabled).
 * Configuration comes from window.APP_FORM_CONFIG, set in application_form.html.
 */
// ── Fit analysis ─────────────────────────────────────────────────────────
const _FIT_APP_ID = window.APP_FORM_CONFIG.fitAppId;

async function runFitAnalysis(jobDescription) {
  const card    = document.getElementById('fitAnalysisCard');
  const spinner = document.getElementById('fitAnalysisSpinner');
  const content = document.getElementById('fitAnalysisContent');
  const errDiv  = document.getElementById('fitAnalysisError');

  if (!card) return;

  card.classList.remove('d-none');
  spinner.style.display   = '';
  content.style.display   = 'none';
  errDiv.classList.add('d-none');
  card.scrollIntoView({behavior:'smooth', block:'start'});

  try {
    const resp = await fetch(window.APP_FORM_CONFIG.urls.aiFit, {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify({job_description: jobDescription}),
    });
    const data = await resp.json();

    spinner.style.display = 'none';

    if (!data.ok) {
      errDiv.innerHTML = `<i class="bi bi-exclamation-circle me-1"></i>${escHtmlFit(data.error)}`;
      errDiv.classList.remove('d-none');
      return;
    }

    // Score badge.
    const scoreBadge = document.getElementById('fitScoreBadge');
    if (scoreBadge) scoreBadge.textContent = data.fit_score + '%';

    // Verdict badge colour.
    const verdictBadge = document.getElementById('fitVerdictBadge');
    if (verdictBadge) {
      verdictBadge.textContent = data.verdict;
      const colours = {
        'Strong Fit':   'bg-success',
        'Good Fit':     'bg-primary',
        'Moderate Fit': 'bg-warning text-dark',
        'Weak Fit':     'bg-secondary',
        'Not a Fit':    'bg-danger',
      };
      verdictBadge.className = 'badge fs-6 ' + (colours[data.verdict] || 'bg-secondary');
    }

    // Progress bar.
    const bar   = document.getElementById('fitProgressBar');
    const label = document.getElementById('fitProgressLabel');
    if (bar) {
      const pct = data.fit_score + '%';
      bar.style.width       = pct;
      bar.setAttribute('aria-valuenow', data.fit_score);
      if (label) label.textContent = pct;
      bar.className = 'progress-bar ' + (
        data.fit_score >= 75 ? 'bg-success' :
        data.fit_score >= 50 ? 'bg-primary' :
        data.fit_score >= 30 ? 'bg-warning'  : 'bg-danger'
      );
    }

    // Matching skills list.
    const matchList = document.getElementById('matchingSkillsList');
    if (matchList) {
      matchList.innerHTML = (data.matching_skills || []).length
        ? data.matching_skills.map(s =>
            `<li class="list-group-item py-1 small"><i class="bi bi-check-circle-fill text-success me-1"></i>${escHtmlFit(s)}</li>`
          ).join('')
        : '<li class="list-group-item py-1 small text-muted">None identified</li>';
    }

    // Skill gaps list.
    const gapList = document.getElementById('skillGapsList');
    if (gapList) {
      gapList.innerHTML = (data.skill_gaps || []).length
        ? data.skill_gaps.map(s =>
            `<li class="list-group-item py-1 small"><i class="bi bi-exclamation-triangle-fill text-warning me-1"></i>${escHtmlFit(s)}</li>`
          ).join('')
        : '<li class="list-group-item py-1 small text-muted">No significant gaps identified</li>';
    }

    // Recommendation.
    const recDiv = document.getElementById('fitRecommendation');
    if (recDiv) {
      recDiv.innerHTML = `<i class="bi bi-lightbulb me-1 text-primary"></i>${escHtmlFit(data.recommendation)}`;
    }

    // Populate hidden form fields so fit data is submitted with the form.
    const hidScore    = document.getElementById('hid_fit_score');
    const hidVerdict  = document.getElementById('hid_fit_verdict');
    const hidMatching = document.getElementById('hid_matching_skills');
    const hidGaps     = document.getElementById('hid_skill_gaps');
    const hidRec      = document.getElementById('hid_recommendation');
    if (hidScore)    hidScore.value    = data.fit_score;
    if (hidVerdict)  hidVerdict.value  = data.verdict;
    if (hidMatching) hidMatching.value = JSON.stringify(data.matching_skills || []);
    if (hidGaps)     hidGaps.value     = JSON.stringify(data.skill_gaps || []);
    if (hidRec)      hidRec.value      = data.recommendation || '';

    // Show append-to-notes button.
    const appendBtn = document.getElementById('appendFitToNotesBtn');
    if (appendBtn) {
      appendBtn.style.display = '';
      appendBtn._fitData = data;
    }

    content.style.display = '';

    // Persist to DB if editing an existing application.
    if (_FIT_APP_ID) {
      fetch(window.APP_FORM_CONFIG.urls.aiFitSave, {
        method:  'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          app_id:          _FIT_APP_ID,
          fit_score:       data.fit_score,
          verdict:         data.verdict,
          matching_skills: data.matching_skills,
          skill_gaps:      data.skill_gaps,
          recommendation:  data.recommendation,
        }),
      }).catch(() => {});  // fire-and-forget
    }

  } catch (err) {
    spinner.style.display = 'none';
    errDiv.innerHTML = `<i class="bi bi-exclamation-circle me-1"></i>Fit analysis failed: ${escHtmlFit(err.message)}`;
    errDiv.classList.remove('d-none');
  }
}

// Append AI fit summary to the Additional Notes textarea.
const _appendBtn = document.getElementById('appendFitToNotesBtn');
if (_appendBtn) {
  _appendBtn.addEventListener('click', function () {
    const d = this._fitData;
    if (!d) return;
    const ta = document.getElementById('additional_notes');
    if (!ta) return;
    const matchStr = (d.matching_skills || []).join(', ') || 'none identified';
    const gapStr   = (d.skill_gaps || []).join(', ') || 'none identified';
    const summary = [
      `\n--- AI Fit Analysis ---`,
      `Verdict: ${d.verdict} (${d.fit_score}%)`,
      `Matching skills: ${matchStr}`,
      `Skill gaps: ${gapStr}`,
      d.recommendation ? `Recommendation: ${d.recommendation}` : '',
      `------------------------`,
    ].filter(Boolean).join('\n');
    ta.value = ta.value + summary;
    ta.focus();
  });
}

function escHtmlFit(str) {
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
