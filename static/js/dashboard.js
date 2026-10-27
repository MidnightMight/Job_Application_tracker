// Dashboard charts, drawn in the theme's colours and redrawn when the theme changes.

(function () {
  var config = window.DASHBOARD_CONFIG || {};
  var charts = [];

  function css(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function axes(extra) {
    var grid = { color: css('--ml-line'), drawTicks: false };
    var ticks = { color: css('--ml-muted'), padding: 6 };
    return Object.assign({
      x: { grid: { display: false }, border: { display: false }, ticks: ticks },
      y: { beginAtZero: true, grid: grid, border: { display: false }, ticks: Object.assign({ precision: 0 }, ticks) }
    }, extra || {});
  }

  function draw() {
    charts.forEach(function (c) { c.destroy(); });
    charts = [];
    if (typeof Chart === 'undefined') { return; }

    Chart.defaults.font.family = css('--bs-font-sans-serif') || 'sans-serif';
    Chart.defaults.color = css('--ml-muted');
    var blue = css('--ml-blue');
    var amber = css('--ml-amber');
    var ink = css('--ml-ink');
    var common = { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } };

    var yearEl = document.getElementById('yearChart');
    if (yearEl) {
      charts.push(new Chart(yearEl, {
        type: 'bar',
        data: {
          labels: Object.keys(config.perYear || {}),
          datasets: [{ label: 'Applications', data: Object.values(config.perYear || {}),
                       backgroundColor: blue, borderRadius: 6, maxBarThickness: 48 }]
        },
        options: Object.assign({ scales: axes() }, common)
      }));
    }

    var successEl = document.getElementById('successChart');
    if (successEl) {
      charts.push(new Chart(successEl, {
        type: 'line',
        data: {
          labels: Object.keys(config.successPerYear || {}),
          datasets: [{ label: 'Offer rate (%)', data: Object.values(config.successPerYear || {}),
                       borderColor: amber, backgroundColor: amber, borderWidth: 3, tension: 0.25,
                       pointRadius: 5, pointBackgroundColor: amber, pointBorderColor: ink, pointBorderWidth: 2 }]
        },
        options: Object.assign({
          scales: axes({ y: { beginAtZero: true, suggestedMax: 100, grid: { color: css('--ml-line') }, border: { display: false },
                              ticks: { color: css('--ml-muted'), callback: function (v) { return v + '%'; } } } })
        }, common)
      }));
    }

    var keywordEl = document.getElementById('keywordChart');
    if (keywordEl) {
      charts.push(new Chart(keywordEl, {
        type: 'bar',
        data: {
          labels: Object.keys(config.keywords || {}),
          datasets: [{ label: 'Companies', data: Object.values(config.keywords || {}),
                       backgroundColor: amber, borderColor: ink, borderWidth: 1.5, borderRadius: 6, maxBarThickness: 22 }]
        },
        options: Object.assign({
          indexAxis: 'y',
          scales: {
            x: { beginAtZero: true, grid: { color: css('--ml-line') }, border: { display: false },
                 ticks: { precision: 0, color: css('--ml-muted') } },
            y: { grid: { display: false }, border: { display: false }, ticks: { color: css('--ml-text') } }
          }
        }, common)
      }));
    }
  }

  draw();
  document.addEventListener('jt-theme', draw);
})();
