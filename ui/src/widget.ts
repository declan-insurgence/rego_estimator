type EstimateLineItem = {
  key: string;
  label: string;
  amount_min: number;
  amount_max: number;
  notes?: string;
};

type EstimatePayload = {
  estimate?: {
    line_items: EstimateLineItem[];
    total_min: number;
    total_max: number;
    confidence: string;
    assumptions: string[];
    concessions_applied: string[];
    last_refresh: string;
    source_urls: string[];
  };
};

declare global {
  interface Window {
    openai?: {
      toolOutput?: EstimatePayload;
      widgetState?: Record<string, unknown>;
      setWidgetState?: (state: Record<string, unknown>) => void;
    };
  }
}

const app = document.getElementById('app');
if (!app) throw new Error('Missing app');

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
    <section class="card">
      <h3>Vic Rego Estimator</h3>
      <label>Transaction type</label><select id="transaction"><option>renewal</option><option>new_registration</option><option>transfer</option></select>
      <label>Vehicle category</label><select id="category"><option>passenger_car</option><option>motorcycle</option><option>light_commercial_ute</option><option>heavy_vehicle_truck</option><option>trailer</option><option>caravan</option><option>bus</option></select>
      <label>Make</label><input id="make" placeholder="Toyota" />
      <label>Model</label><input id="model" placeholder="Corolla" />
      <label>Year</label><input id="year" type="number" placeholder="2021" />
      <label>Fuel type</label><input id="fuel" placeholder="Petrol" />
      <label>Term</label><select id="term"><option>3</option><option>6</option><option selected>12</option></select>
      <button id="share">Share quote</button>
      <p class="muted">Estimate only; confirm on VicRoads. Fee tables refreshed monthly.</p>
    </section>
    <section class="card">
      <h3>Results</h3>
      <div id="results">Waiting for tool output...</div>
    </section>
  </div>
`;

function formatCurrency(min: number, max: number): string {
  if (min === max) return `$${min.toFixed(2)}`;
  return `$${min.toFixed(2)} - $${max.toFixed(2)}`;
}

function renderResults(payload?: EstimatePayload): void {
  const results = document.getElementById('results');
  if (!results) return;
  if (!payload?.estimate) {
    results.innerHTML = '<p class="muted">Run estimate_registration_cost to populate itemised fees.</p>';
    return;
  }
  const estimate = payload.estimate;
  const rows = estimate.line_items
    .map((item) => `<tr><td>${item.label}</td><td style="text-align:right">${formatCurrency(item.amount_min, item.amount_max)}</td></tr>`)
    .join('');

  results.innerHTML = `
    <table>${rows}</table>
    <p><strong>Total:</strong> ${formatCurrency(estimate.total_min, estimate.total_max)}</p>
    <p><strong>Confidence:</strong> ${estimate.confidence}</p>
    <p class="muted">Assumptions: ${estimate.assumptions.join('; ') || 'None'}</p>
    <p class="muted">Concessions applied: ${estimate.concessions_applied.join(', ') || 'None'}</p>
    <p class="muted">Last refresh: ${new Date(estimate.last_refresh).toLocaleDateString()}</p>
  `;
}

(document.getElementById('share') as HTMLButtonElement).addEventListener('click', () => {
  const estimate = window.openai?.toolOutput?.estimate;
  if (!estimate || !window.openai?.setWidgetState) return;
  window.openai.setWidgetState({
    ...(window.openai.widgetState || {}),
    sharedQuote: estimate
  });
});

renderResults(window.openai?.toolOutput);
