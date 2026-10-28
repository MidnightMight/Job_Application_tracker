// Insights charts: "Where they are now" doughnut and "How they got there" flow.
// Data comes from window.INSIGHTS_CONFIG (see templates/insights.html).
(function () {
  'use strict';
  var cfg = window.INSIGHTS_CONFIG;
  if (!cfg) return;

  var SVG_NS = 'http://www.w3.org/2000/svg';
  var doughnut = null;

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  function colour(kind) { return cssVar('--ml-out-' + kind) || '#888'; }

  // ── Doughnut ──────────────────────────────────────────────────────────────
  function drawDoughnut() {
    var canvas = document.getElementById('outcomeChart');
    if (!canvas || typeof Chart === 'undefined') return;
    if (doughnut) doughnut.destroy();
    var total = cfg.outcomes.reduce(function (sum, o) { return sum + o.value; }, 0);
    doughnut = new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: cfg.outcomes.map(function (o) { return o.label; }),
        datasets: [{
          data: cfg.outcomes.map(function (o) { return o.value; }),
          backgroundColor: cfg.outcomes.map(function (o) { return colour(o.key); }),
          borderColor: cssVar('--ml-surface') || '#fff',
          borderWidth: 2,
          hoverOffset: 6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '68%',
        plugins: {
          legend: { display: false },  // the list beside it is the legend
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return ' ' + ctx.label + ': ' + ctx.parsed + ' (' + Math.round(ctx.parsed * 100 / total) + '%)';
              },
            },
          },
        },
      },
    });
  }

  // ── Flow diagram ──────────────────────────────────────────────────────────
  function el(name, attrs, parent) {
    var node = document.createElementNS(SVG_NS, name);
    Object.keys(attrs).forEach(function (k) { node.setAttribute(k, attrs[k]); });
    if (parent) parent.appendChild(node);
    return node;
  }

  function drawFlow() {
    var svg = document.getElementById('flowChart');
    if (!svg) return;
    while (svg.firstChild) svg.removeChild(svg.firstChild);

    var width = Math.max(svg.clientWidth, 700);
    var height = svg.clientHeight || 340;
    var pad = { top: 8, bottom: 8, left: 2, right: 140 };
    var nodeWidth = 12;
    var gap = 14;

    var byId = {};
    var columns = [];
    cfg.nodes.forEach(function (n) {
      byId[n.id] = n;
      (columns[n.column] = columns[n.column] || []).push(n);
    });
    var lastColumn = columns.length - 1;
    var total = byId.all ? byId.all.value : 1;
    var tallest = Math.max.apply(null, columns.map(function (c) { return c ? c.length : 0; }));
    var scale = (height - pad.top - pad.bottom - gap * (tallest - 1)) / total;
    var step = lastColumn ? (width - pad.left - pad.right - nodeWidth) / lastColumn : 0;

    columns.forEach(function (col, c) {
      var y = pad.top;
      (col || []).forEach(function (n) {
        n.x = pad.left + c * step;
        n.y = y;
        n.h = Math.max(n.value * scale, 2);
        n.outY = n.y;
        n.inY = n.y;
        y += n.h + gap;
      });
    });

    var links = el('g', {}, svg);
    cfg.links.forEach(function (l) {
      var s = byId[l.source], t = byId[l.target];
      if (!s || !t) return;
      var h = Math.max(l.value * scale, 1);
      var x0 = s.x + nodeWidth, x1 = t.x, xm = (x0 + x1) / 2;
      var sy = s.outY, ty = t.inY;
      s.outY += h;
      t.inY += h;
      var d = 'M' + x0 + ',' + sy +
              ' C' + xm + ',' + sy + ' ' + xm + ',' + ty + ' ' + x1 + ',' + ty +
              ' L' + x1 + ',' + (ty + h) +
              ' C' + xm + ',' + (ty + h) + ' ' + xm + ',' + (sy + h) + ' ' + x0 + ',' + (sy + h) + ' Z';
      var path = el('path', { d: d, fill: colour(t.kind), class: 'ml-flow-link' }, links);
      el('title', {}, path).textContent = s.label + ' → ' + t.label + ': ' + l.value;
    });

    var nodes = el('g', {}, svg);
    var surface = cssVar('--ml-surface') || '#fff';
    cfg.nodes.forEach(function (n) {
      var rect = el('rect', { x: n.x, y: n.y, width: nodeWidth, height: n.h, rx: 3,
                              fill: colour(n.kind) }, nodes);
      el('title', {}, rect).textContent = n.label + ': ' + n.value;
      // Labels sit beside the node, with a halo so they read over the bands.
      var text = el('text', { x: n.x + nodeWidth + 6, y: n.y + n.h / 2, dy: '0.35em',
                              stroke: surface, 'stroke-width': 4, 'paint-order': 'stroke',
                              'stroke-linejoin': 'round' }, nodes);
      text.textContent = n.label + ' ';
      var count = el('tspan', { class: 'ml-flow-count' }, text);
      count.textContent = n.value;
    });
  }

  function drawAll() { drawDoughnut(); drawFlow(); }

  drawAll();
  var resizeTimer = null;
  window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(drawFlow, 150);
  });
  // Redraw in the new colours when the theme is switched.
  new MutationObserver(drawAll).observe(document.documentElement,
    { attributes: true, attributeFilter: ['data-bs-theme'] });
})();
