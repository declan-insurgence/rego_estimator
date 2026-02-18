(function () {
  const app = document.getElementById('app');
  app.innerHTML = `
  <style>
    body { font-family: Inter, sans-serif; margin: 0; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .card { border: 1px solid #ddd; border-radius: 8px; padding: 12px; }
    label { display:block; font-size: 12px; margin-bottom:4px; }
    input, select { width:100%; padding:6px; }
    table { width:100%; border-collapse: collapse; }
    td { padding: 6px 0; border-bottom: 1px solid #eee; }
    .muted { color: #666; font-size: 12px; }
  </style>
  <div class="grid">
    <section class="card"><h3>Vic Rego Estimator</h3><p class="muted">Estimate only; confirm on VicRoads. Fee tables refreshed monthly.</p><button id="share">Share quote</button></section>
    <section class="card"><h3>Results</h3><div id="results">Waiting for tool output...</div></section>
  </div>`;

  const payload = window.openai && window.openai.toolOutput;
  const results = document.getElementById('results');
  if (payload && payload.estimate) {
    results.innerHTML = `<p><strong>Total:</strong> $${payload.estimate.total_min} - $${payload.estimate.total_max}</p><p>Confidence: ${payload.estimate.confidence}</p>`;
  }

  document.getElementById('share').addEventListener('click', function () {
    if (!window.openai || !window.openai.setWidgetState || !payload || !payload.estimate) return;
    window.openai.setWidgetState(Object.assign({}, window.openai.widgetState || {}, { sharedQuote: payload.estimate }));
  });
})();
