// UrbanPulse frontend. Plain JavaScript with no build step; it talks to the REST API under /api.
"use strict";

const API_BASE = "/api";

const els = {
  minWalk: document.getElementById("minWalk"),
  maxRent: document.getElementById("maxRent"),
  sortBy: document.getElementById("sortBy"),
  walkValue: document.getElementById("walkValue"),
  rentValue: document.getElementById("rentValue"),
  status: document.getElementById("status"),
  rows: document.getElementById("rows"),
  count: document.getElementById("count"),
  datasets: document.getElementById("datasets"),
  ingestion: document.getElementById("ingestion"),
};

const map = L.map("map").setView([-37.84, 144.98], 10);
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
      radius: 6 + Math.sqrt(s.population) / 40,
      color: "#ffffff",
      weight: 1,
      fillColor: scoreColour(s.liveability_score),
      fillOpacity: 0.85,
    }).bindPopup(
      `<strong>${escapeHtml(s.name)}</strong><br>` +
        `Liveability: <b>${s.liveability_score}</b><br>` +
        `Walk score: ${s.walk_score} &middot; Green: ${s.green_space_pct}%<br>` +
        `PT stops: ${s.pt_stops} &middot; Rent: $${s.median_weekly_rent}/wk`
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
        <td>${s.walk_score}</td>
        <td>${s.green_space_pct}</td>
        <td>${s.pt_stops}</td>
        <td>$${fmt.format(s.median_weekly_rent)}</td>
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
  const minWalk = Number(els.minWalk.value);
  const maxRent = Number(els.maxRent.value);
  els.walkValue.textContent = minWalk;
  els.rentValue.textContent = maxRent >= Number(els.maxRent.max) ? "any" : `$${maxRent}`;

  const params = new URLSearchParams({ sort_by: els.sortBy.value, order: els.sortBy.value === "name" ? "asc" : "desc" });
  if (minWalk > 0) params.set("min_walk_score", minWalk);
  if (maxRent < Number(els.maxRent.max)) params.set("max_rent", maxRent);

  try {
    const suburbs = await getJson(`/suburbs?${params}`);
    renderMap(suburbs);
    renderTable(suburbs);
    renderChart(suburbs);
    els.status.textContent = suburbs.length ? "" : "No suburbs match these filters.";
    els.status.classList.remove("error");
  } catch (err) {
    els.status.textContent = `Could not load suburbs: ${err.message}`;
    els.status.classList.add("error");
  }
}

async function loadExtras() {
  try {
    renderDatasets(await getJson("/datasets"));
  } catch (err) {
    els.datasets.innerHTML = `<li>Dataset catalogue unavailable (${escapeHtml(err.message)})</li>`;
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
for (const input of [els.minWalk, els.maxRent, els.sortBy]) {
  input.addEventListener("input", () => {
    clearTimeout(debounce);
    debounce = setTimeout(loadSuburbs, 150);
  });
}

loadSuburbs();
loadExtras();
