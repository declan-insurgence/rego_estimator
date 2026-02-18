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

type WidgetFormData = {
  transaction_type: string;
  vehicle_category: string;
  make?: string;
  model?: string;
  year?: number;
  fuel_type?: string;
  term_months: number;
};

type HostUpdatePayload = {
  toolOutput?: EstimatePayload;
};

type HostEventHandler = (payload: HostUpdatePayload | EstimatePayload) => void;

type OpenAIHostBridge = {
  toolOutput?: EstimatePayload;
  widgetState?: Record<string, unknown>;
  setWidgetState?: (state: Record<string, unknown>) => void;
  invokeTool?: (name: string, payload: Record<string, unknown>) => Promise<unknown>;
  callTool?: (name: string, payload: Record<string, unknown>) => Promise<unknown>;
  on?: (eventName: string, handler: HostEventHandler) => (() => void) | void;
  off?: (eventName: string, handler: HostEventHandler) => void;
};

declare global {
  interface Window {
    openai?: OpenAIHostBridge;
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

function readFormData(): WidgetFormData {
  const transaction = document.getElementById('transaction') as HTMLSelectElement | null;
  const category = document.getElementById('category') as HTMLSelectElement | null;
  const make = document.getElementById('make') as HTMLInputElement | null;
  const model = document.getElementById('model') as HTMLInputElement | null;
  const year = document.getElementById('year') as HTMLInputElement | null;
  const fuel = document.getElementById('fuel') as HTMLInputElement | null;
  const term = document.getElementById('term') as HTMLSelectElement | null;

  const parsedYear = year?.value.trim() ? Number(year.value) : undefined;

  return {
    transaction_type: transaction?.value ?? 'renewal',
    vehicle_category: category?.value ?? 'passenger_car',
    make: make?.value.trim() || undefined,
    model: model?.value.trim() || undefined,
    year: parsedYear && !Number.isNaN(parsedYear) ? parsedYear : undefined,
    fuel_type: fuel?.value.trim() || undefined,
    term_months: Number(term?.value ?? 12) || 12,
  };
}

async function invokeEstimateTool(): Promise<void> {
  const bridge = window.openai;
  if (!bridge) return;

  const payload = readFormData();
  const runTool = bridge.invokeTool ?? bridge.callTool;

  if (runTool) {
    await runTool('estimate_registration_cost', payload);
  }

  if (bridge.setWidgetState) {
    bridge.setWidgetState({
      ...(bridge.widgetState || {}),
      lastEstimateRequest: payload,
    });
  }
}

function bindFormBridge(): void {
  const triggerIds = ['transaction', 'category', 'make', 'model', 'year', 'fuel', 'term'];

  triggerIds.forEach((id) => {
    const element = document.getElementById(id) as HTMLInputElement | HTMLSelectElement | null;
    if (!element) return;

    const eventType = element.tagName === 'SELECT' ? 'change' : 'blur';
    element.addEventListener(eventType, () => {
      void invokeEstimateTool();
    });

    if (element.tagName !== 'SELECT') {
      element.addEventListener('keydown', (event) => {
        if ((event as KeyboardEvent).key !== 'Enter') return;
        void invokeEstimateTool();
      });
    }
  });
}

function subscribeToHostUpdates(): void {
  const bridge = window.openai;
  if (!bridge) return;

  const updateHandler: HostEventHandler = (payload) => {
    const maybeToolOutput = 'toolOutput' in payload ? payload.toolOutput : payload;
    renderResults(maybeToolOutput);
  };

  if (bridge.on) {
    const unsubscribe = bridge.on('toolOutput', updateHandler);
    if (typeof unsubscribe !== 'function' && bridge.on !== undefined) {
      bridge.on('widgetState', () => {
        renderResults(bridge.toolOutput);
      });
    }
    return;
  }

  if (typeof window.addEventListener === 'function') {
    window.addEventListener('message', (event: MessageEvent) => {
      if (!event?.data) return;
      const data = event.data as { type?: string; toolOutput?: EstimatePayload };
      if (data.type !== 'openai.toolOutput' || !data.toolOutput) return;
      renderResults(data.toolOutput);
    });
  }
}

(document.getElementById('share') as HTMLButtonElement).addEventListener('click', () => {
  const estimate = window.openai?.toolOutput?.estimate;
  if (!estimate || !window.openai?.setWidgetState) return;
  window.openai.setWidgetState({
    ...(window.openai.widgetState || {}),
    sharedQuote: estimate,
    sharedAt: new Date().toISOString(),
  });
});

bindFormBridge();
subscribeToHostUpdates();
renderResults(window.openai?.toolOutput);
