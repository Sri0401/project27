// UrbanPulse frontend. Plain JavaScript with no build step; it talks to the REST API under /api.
"use strict";

const API_BASE = "/api";

const els = {
  search: document.getElementById("search"),
  minGreen: document.getElementById("minGreen"),
  maxRent: document.getElementById("maxRent"),
  sortBy: document.getElementById("sortBy"),
  greenValue: document.getElementById("greenValue"),
  rentValue: document.getElementById("rentValue"),
  status: document.getElementById("status"),
  rows: document.getElementById("rows"),
  count: document.getElementById("count"),
  datasets: document.getElementById("datasets"),
  provenance: document.getElementById("provenance"),
  ingestion: document.getElementById("ingestion"),
};

const map = L.map("map").setView([-37.82, 145.0], 9);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 18,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);
const markerLayer = L.layerGroup().addTo(map);
const markersByCode = new Map();
let chart;

async function getJson(path) {
  const response = await fetch(API_BASE + path, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText} for ${path}`);
  return response.json();
}

// Escape API text before putting it into HTML, so data cannot inject markup.
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

// Map a 0-100 score onto a red -> amber -> green ramp.
function scoreColour(score) {
  const stops = [[209, 73, 91], [237, 174, 73], [46, 158, 106]];
  const t = Math.max(0, Math.min(1, score / 100)) * 2;
  const [a, b] = t < 1 ? [stops[0], stops[1]] : [stops[1], stops[2]];
  const f = t < 1 ? t : t - 1;
  return `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * f)).join(",")})`;
}

const fmt = new Intl.NumberFormat("en-AU");

function renderMap(suburbs) {
  markerLayer.clearLayers();
  markersByCode.clear();
  for (const s of suburbs) {
    const marker = L.circleMarker([s.latitude, s.longitude], {
      radius: 4 + Math.sqrt(s.population) / 50,
      color: "#ffffff",
      weight: 1,
      fillColor: scoreColour(s.liveability_score),
      fillOpacity: 0.85,
    }).bindPopup(
      `<strong>${escapeHtml(s.name)}</strong> <span class="muted">SA2 ${escapeHtml(s.code)}</span><br>` +
        `Liveability score: <b>${s.liveability_score}</b><br>` +
        `Transport: ${s.pt_stops} stops (${s.pt_stops_per_sqkm}/km&sup2;)<br>` +
        `Green space: ${s.green_space_pct}% of land<br>` +
        `Rent: $${s.median_weekly_rent}/wk (${s.rent_to_income_pct}% of household income)<br>` +
        `Road crashes: ${s.road_crashes_per_year}/yr (${s.crashes_per_1000_residents} per 1,000 residents)<br>` +
        `Population: ${fmt.format(s.population)} (${fmt.format(Math.round(s.population_density))}/km&sup2;)`
    );
    marker.addTo(markerLayer);
    markersByCode.set(s.code, marker);
  }
}

function renderTable(suburbs) {
  els.count.textContent = `(${suburbs.length})`;
  els.rows.innerHTML = suburbs
    .map(
      (s) => `<tr data-code="${escapeHtml(s.code)}">
        <td>${escapeHtml(s.name)}</td>
        <td><span class="score-pill" style="background:${scoreColour(s.liveability_score)}">${s.liveability_score}</span></td>
        <td>${s.pt_stops_per_sqkm}</td>
        <td>${s.green_space_pct}</td>
        <td>$${fmt.format(s.median_weekly_rent)}</td>
        <td>${s.rent_to_income_pct}%</td>
        <td>${s.crashes_per_1000_residents}</td>
        <td>${fmt.format(s.population)}</td>
      </tr>`
    )
    .join("");
}

function renderChart(suburbs) {
  const top = [...suburbs].sort((a, b) => b.liveability_score - a.liveability_score).slice(0, 10);
  const data = {
    labels: top.map((s) => s.name),
    datasets: [{
      label: "Liveability score",
      data: top.map((s) => s.liveability_score),
      backgroundColor: top.map((s) => scoreColour(s.liveability_score)),
      borderRadius: 4,
    }],
  };
  if (chart) {
    chart.data = data;
    chart.update();
    return;
  }
  chart = new Chart(document.getElementById("chart"), {
    type: "bar",
    data,
    options: {
      indexAxis: "y",
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { min: 0, max: 100 } },
    },
  });
}

function renderDatasets(datasets) {
  els.datasets.innerHTML = datasets
    .map(
      (d) => `<li>
        <a href="${escapeHtml(d.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(d.title)}</a>
        <p>${escapeHtml(d.publisher)} &middot; ${escapeHtml(d.licence)}</p>
        <p>${escapeHtml(d.description)}</p>
        ${d.tags.map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join("")}
      </li>`
    )
    .join("");
}

async function loadSuburbs() {
  const minGreen = Number(els.minGreen.value);
  const maxRent = Number(els.maxRent.value);
  const search = els.search.value.trim();
  els.greenValue.textContent = `${minGreen}%`;
  els.rentValue.textContent = maxRent >= Number(els.maxRent.max) ? "any" : `$${maxRent}`;

  // Name, rent, rent-to-income and crashes read best low-to-high; everything else high-to-low.
  const ascending = ["name", "median_weekly_rent", "rent_to_income_pct", "crashes_per_1000_residents"].includes(
    els.sortBy.value
  );
  const params = new URLSearchParams({ sort_by: els.sortBy.value, order: ascending ? "asc" : "desc", limit: 1000 });
  if (search) params.set("q", search);
  if (minGreen > 0) params.set("min_green_space", minGreen);
  if (maxRent < Number(els.maxRent.max)) params.set("max_rent", maxRent);

  try {
    const suburbs = await getJson(`/suburbs?${params}`);
    renderMap(suburbs);
    renderTable(suburbs);
    renderChart(suburbs);
    els.status.textContent = suburbs.length ? "" : "No areas match these filters.";
    els.status.classList.remove("error");
  } catch (err) {
    els.status.textContent = `Could not load areas: ${err.message}`;
    els.status.classList.add("error");
  }
}

function renderProvenance(v) {
  const built = new Date(v.generated_at).toLocaleString("en-AU");
  const sources = v.sources
    .map(
      (s) => `<tr>
        <td><a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(s.name)}</a></td>
        <td>${escapeHtml(s.publisher)}</td>
        <td>${escapeHtml(s.retrieved_via)}${s.version ? ` (v${escapeHtml(s.version)})` : ""}</td>
        <td>${s.records_used == null ? "" : fmt.format(s.records_used)}</td>
        <td>${escapeHtml(s.licence)}</td>
      </tr>`
    )
    .join("");
  const skipped = v.skipped
    .map((s) => `<li>${escapeHtml(s.name)} <span class="muted">(${escapeHtml(s.code)})</span>: ${escapeHtml(s.reason)}</li>`)
    .join("");
  els.provenance.innerHTML = `
    <p>Built ${escapeHtml(built)} by pipeline v${escapeHtml(v.pipeline_version)} &middot;
      ${fmt.format(v.output.rows)} areas &middot; checksum <code>${escapeHtml(v.output.sha256.slice(0, 12))}</code></p>
    <div class="table-scroll"><table>
      <thead><tr><th>Source</th><th>Publisher</th><th>Retrieved via</th><th>Records used</th><th>Licence</th></tr></thead>
      <tbody>${sources}</tbody>
    </table></div>
    <details><summary>${v.skipped.length} areas excluded</summary><ul>${skipped}</ul></details>`;
}

async function loadExtras() {
  try {
    renderDatasets(await getJson("/datasets"));
  } catch (err) {
    els.datasets.innerHTML = `<li>Dataset catalogue unavailable (${escapeHtml(err.message)})</li>`;
  }
  try {
    renderProvenance(await getJson("/provenance"));
  } catch (err) {
    els.provenance.textContent = `Provenance unavailable (${err.message})`;
  }
  try {
    const run = await getJson("/ingestion/latest");
    els.ingestion.textContent = `Last ingestion: ${run.rows_loaded} rows from ${run.source} at ${new Date(run.finished_at).toLocaleString("en-AU")}`;
  } catch {
    els.ingestion.textContent = "No ingestion run recorded yet";
  }
}

els.rows.addEventListener("click", (event) => {
  const row = event.target.closest("tr[data-code]");
  if (!row) return;
  els.rows.querySelectorAll("tr.selected").forEach((r) => r.classList.remove("selected"));
  row.classList.add("selected");
  const marker = markersByCode.get(row.dataset.code);
  if (marker) {
    map.flyTo(marker.getLatLng(), 13);
    marker.openPopup();
  }
});

let debounce;
for (const input of [els.search, els.minGreen, els.maxRent, els.sortBy]) {
  input.addEventListener("input", () => {
    clearTimeout(debounce);
    debounce = setTimeout(loadSuburbs, 200);
  });
}

loadSuburbs();
loadExtras();
