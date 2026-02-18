(function(){const n=document.createElement("link").relList;if(n&&n.supports&&n.supports("modulepreload"))return;for(const o of document.querySelectorAll('link[rel="modulepreload"]'))i(o);new MutationObserver(o=>{for(const r of o)if(r.type==="childList")for(const s of r.addedNodes)s.tagName==="LINK"&&s.rel==="modulepreload"&&i(s)}).observe(document,{childList:!0,subtree:!0});function e(o){const r={};return o.integrity&&(r.integrity=o.integrity),o.referrerPolicy&&(r.referrerPolicy=o.referrerPolicy),o.crossOrigin==="use-credentials"?r.credentials="include":o.crossOrigin==="anonymous"?r.credentials="omit":r.credentials="same-origin",r}function i(o){if(o.ep)return;o.ep=!0;const r=e(o);fetch(o.href,r)}})();const p=document.getElementById("app");if(!p)throw new Error("Missing app");p.innerHTML=`
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
`;function d(t,n){return t===n?`$${t.toFixed(2)}`:`$${t.toFixed(2)} - $${n.toFixed(2)}`}function a(t){const n=document.getElementById("results");if(!n)return;if(!(t!=null&&t.estimate)){n.innerHTML='<p class="muted">Run estimate_registration_cost to populate itemised fees.</p>';return}const e=t.estimate,i=e.line_items.map(o=>`<tr><td>${o.label}</td><td style="text-align:right">${d(o.amount_min,o.amount_max)}</td></tr>`).join("");n.innerHTML=`
    <table>${i}</table>
    <p><strong>Total:</strong> ${d(e.total_min,e.total_max)}</p>
    <p><strong>Confidence:</strong> ${e.confidence}</p>
    <p class="muted">Assumptions: ${e.assumptions.join("; ")||"None"}</p>
    <p class="muted">Concessions applied: ${e.concessions_applied.join(", ")||"None"}</p>
    <p class="muted">Last refresh: ${new Date(e.last_refresh).toLocaleDateString()}</p>
  `}function m(){const t=document.getElementById("transaction"),n=document.getElementById("category"),e=document.getElementById("make"),i=document.getElementById("model"),o=document.getElementById("year"),r=document.getElementById("fuel"),s=document.getElementById("term"),l=o!=null&&o.value.trim()?Number(o.value):void 0;return{transaction_type:(t==null?void 0:t.value)??"renewal",vehicle_category:(n==null?void 0:n.value)??"passenger_car",make:(e==null?void 0:e.value.trim())||void 0,model:(i==null?void 0:i.value.trim())||void 0,year:l&&!Number.isNaN(l)?l:void 0,fuel_type:(r==null?void 0:r.value.trim())||void 0,term_months:Number((s==null?void 0:s.value)??12)||12}}async function c(){const t=window.openai;if(!t)return;const n=m(),e=t.invokeTool??t.callTool;e&&await e("estimate_registration_cost",n),t.setWidgetState&&t.setWidgetState({...t.widgetState||{},lastEstimateRequest:n})}function f(){["transaction","category","make","model","year","fuel","term"].forEach(n=>{const e=document.getElementById(n);if(!e)return;const i=e.tagName==="SELECT"?"change":"blur";e.addEventListener(i,()=>{c()}),e.tagName!=="SELECT"&&e.addEventListener("keydown",o=>{o.key==="Enter"&&c()})})}function g(){const t=window.openai;if(!t)return;const n=e=>{const i="toolOutput"in e?e.toolOutput:e;a(i)};if(t.on){typeof t.on("toolOutput",n)!="function"&&t.on!==void 0&&t.on("widgetState",()=>{a(t.toolOutput)});return}typeof window.addEventListener=="function"&&window.addEventListener("message",e=>{if(!(e!=null&&e.data))return;const i=e.data;i.type!=="openai.toolOutput"||!i.toolOutput||a(i.toolOutput)})}document.getElementById("share").addEventListener("click",()=>{var n,e,i;const t=(e=(n=window.openai)==null?void 0:n.toolOutput)==null?void 0:e.estimate;!t||!((i=window.openai)!=null&&i.setWidgetState)||window.openai.setWidgetState({...window.openai.widgetState||{},sharedQuote:t,sharedAt:new Date().toISOString()})});f();g();var u;a((u=window.openai)==null?void 0:u.toolOutput);
