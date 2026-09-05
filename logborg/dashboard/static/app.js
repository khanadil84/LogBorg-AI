const phases = ["INGEST","DIAGNOSE","REPAIR","VERIFY","RECOVERED"];
const state = {
  phases: Object.fromEntries(phases.map(p => [p, {state:"pending"}])),
  edges: {},
  events: [],
  overall_status: "IDLE",
  message: "Awaiting recovery run.",
  evidence: null
};

const topology = document.getElementById("topology");
const statusEl = document.getElementById("status");
const messageEl = document.getElementById("message");
const eventsEl = document.getElementById("events");
const evidenceEl = document.getElementById("evidence");

function esc(v){
  return String(v ?? "").replace(/[&<>"']/g, c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[c]));
}

function colorFor(s){
  if(s==="failed") return "#fb7185";
  if(s==="active") return "#38bdf8";
  if(s==="success") return "#34d399";
  if(s==="skipped") return "#475569";
  return "#64748b";
}

function render(){
  const W = 1100, H = 610;
  const xs = [90, 320, 550, 780, 1010];
  const y = 300;

  let svg = `
  <svg viewBox="0 0 ${W} ${H}" width="100%" height="100%"
       xmlns="http://www.w3.org/2000/svg"
       role="img" aria-label="Live LogBorg execution topology">
    <defs>
      <filter id="glow">
        <feGaussianBlur stdDeviation="8" result="b"/>
        <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
      <linearGradient id="line" x1="0" x2="1">
        <stop offset="0" stop-color="#38bdf8"/>
        <stop offset="1" stop-color="#34d399"/>
      </linearGradient>
      <pattern id="grid" width="34" height="34" patternUnits="userSpaceOnUse">
        <path d="M34 0H0V34" fill="none" stroke="#334155" stroke-opacity=".18"/>
      </pattern>
    </defs>
    <rect width="1100" height="610" fill="url(#grid)" opacity=".65"/>
    <text x="38" y="48" fill="#64748b" font-size="11" letter-spacing="3">
      AUTONOMOUS EXECUTION FABRIC
    </text>
    <text x="38" y="76" fill="#cbd5e1" font-size="18" font-weight="700" letter-spacing="2">
      REAL-TIME RECOVERY PATH
    </text>`;

  for(let i=0;i<phases.length-1;i++){
    const edge = state.edges[`${phases[i]}->${phases[i+1]}`];
    const flowing = edge?.state === "flowing";
    const failed = edge?.state === "failed";
    const complete = edge?.state === "complete";
    const c = failed ? "#fb7185" : complete ? "#34d399" : flowing ? "#38bdf8" : "#263449";

    svg += `
      <path d="M ${xs[i]+72} ${y} C ${xs[i]+125} ${y-95}, ${xs[i+1]-125} ${y+95}, ${xs[i+1]-72} ${y}"
        fill="none" stroke="${c}" stroke-opacity=".18" stroke-width="14" filter="url(#glow)"/>
      <path d="M ${xs[i]+72} ${y} C ${xs[i]+125} ${y-95}, ${xs[i+1]-125} ${y+95}, ${xs[i+1]-72} ${y}"
        fill="none" stroke="${c}" stroke-width="2.5"
        stroke-dasharray="${flowing ? "8 9" : "none"}"
        ${flowing ? 'class="flow"' : ""}/>
      ${flowing ? `<circle r="5" fill="#e0f2fe"><animateMotion dur="1.2s" repeatCount="indefinite"
        path="M ${xs[i]+72} ${y} C ${xs[i]+125} ${y-95}, ${xs[i+1]-125} ${y+95}, ${xs[i+1]-72} ${y}"/></circle>` : ""}`;
  }

  phases.forEach((p,i)=>{
    const s = state.phases[p]?.state || "pending";
    const c = colorFor(s);
    const active = s==="active";
    const success = s==="success";

    svg += `
      <g>
        ${active ? `<circle cx="${xs[i]}" cy="${y}" r="76" fill="none" stroke="${c}" stroke-opacity=".18" stroke-width="10">
          <animate attributeName="r" values="70;82;70" dur="1.8s" repeatCount="indefinite"/>
          <animate attributeName="opacity" values=".7;.15;.7" dur="1.8s" repeatCount="indefinite"/>
        </circle>` : ""}
        <polygon points="
          ${xs[i]-62},${y-36} ${xs[i]-32},${y-62} ${xs[i]+32},${y-62}
          ${xs[i]+62},${y-36} ${xs[i]+62},${y+36} ${xs[i]+32},${y+62}
          ${xs[i]-32},${y+62} ${xs[i]-62},${y+36}"
          fill="rgba(10,20,35,.94)" stroke="${c}" stroke-width="${active||success?3:2}"
          ${active||success ? 'filter="url(#glow)"' : ""}/>
        <circle cx="${xs[i]}" cy="${y}" r="27" fill="${c}" fill-opacity=".10" stroke="${c}" stroke-opacity=".45"/>
        <text x="${xs[i]}" y="${y+5}" text-anchor="middle" fill="${c}" font-size="13" font-weight="800">
          ${i+1}
        </text>
        <text x="${xs[i]}" y="${y+94}" text-anchor="middle" fill="#e2e8f0" font-size="12" font-weight="700" letter-spacing="2">
          ${p}
        </text>
        <text x="${xs[i]}" y="${y+113}" text-anchor="middle" fill="${c}" font-size="9" letter-spacing="1.5">
          ${s.toUpperCase()}
        </text>
      </g>`;
  });

  svg += `</svg>`;
  topology.innerHTML = svg;

  statusEl.textContent = state.overall_status || "IDLE";
  messageEl.textContent = state.message || "";

  eventsEl.innerHTML = (state.events || []).slice(-12).reverse()
    .map(e => `<div class="event"><b>${esc(e.phase)}</b> · ${esc(e.kind)}<br>${esc(e.message)}</div>`)
    .join("") || `<div class="event">Waiting for runtime events…</div>`;

  evidenceEl.innerHTML = state.evidence
    ? `<pre>${esc(JSON.stringify(state.evidence,null,2))}</pre>`
    : `<div class="message">No runtime evidence yet.</div>`;
}

function apply(snapshot){
  Object.assign(state, snapshot);
  render();
}

fetch("/api/state").then(r=>r.json()).then(apply);

const stream = new EventSource("/api/events");
stream.onmessage = e => {
  try { apply(JSON.parse(e.data)); } catch {}
};

document.getElementById("run").onclick = async () => {
  await fetch("/api/recover", {method:"POST"});
};

render();

const incidentsEl = document.getElementById("incidents");

async function loadIncidents(){
  if(!incidentsEl) return;

  try{
    const incidents = await fetch("/api/incidents", {cache:"no-store"}).then(r => r.json());

    incidentsEl.innerHTML = incidents.length
      ? incidents.map(i => {
          const m = i.manifest || {};
          const d = m.diagnosis || {};
          const v = m.verification || {};

          return `<div class="event incident">
            <b>${esc(i.run_id)}</b><br>
            ${esc(d.fault || "UNKNOWN")} · ${esc(d.severity || "UNKNOWN")} ·
            <span>${esc(m.incident?.lifecycle || "UNKNOWN")}</span><br>
            Verification: ${v.passed ? "PASSED" : "FAILED"}
          </div>`;
        }).join("")
      : `<div class="event">No preserved incidents.</div>`;
  }catch{
    incidentsEl.innerHTML = `<div class="event">Incident history unavailable.</div>`;
  }
}

loadIncidents();
setInterval(loadIncidents, 3000);
