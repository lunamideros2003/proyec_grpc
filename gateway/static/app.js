const catalogGrid = document.getElementById("catalogGrid");
const detailBox = document.getElementById("detailBox");
const searchInput = document.getElementById("searchInput");
const typeFilter = document.getElementById("typeFilter");
const habitableOnly = document.getElementById("habitableOnly");
const planetA = document.getElementById("planetA");
const planetB = document.getElementById("planetB");
const compareResult = document.getElementById("compareResult");
const originSelect = document.getElementById("originSelect");
const destinationSelect = document.getElementById("destinationSelect");
const spacecraftSelect = document.getElementById("spacecraftSelect");
const missionResult = document.getElementById("missionResult");
const quizBox = document.getElementById("quizBox");
const quizResult = document.getElementById("quizResult");
const favoritesGrid = document.getElementById("favoritesGrid");
const progressBox = document.getElementById("progressBox");

let allObjects = [];
let currentQuestions = [];
let favorites = new Set();

document.querySelectorAll(".tabs button").forEach(button => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tabs button").forEach(item => item.classList.remove("active"));
    document.querySelectorAll(".panel").forEach(panel => panel.classList.remove("active"));
    button.classList.add("active");
    document.getElementById("tab-" + button.dataset.tab).classList.add("active");
  });
});

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error("Error de red");
  }
  return response.json();
}

function typeLabel(type) {
  const labels = { PLANET: "Planeta", STAR: "Estrella", GALAXY: "Galaxia", PHENOMENON: "Fenómeno" };
  return labels[type] || type;
}

function cardHtml(item) {
  const marked = favorites.has(item.id) ? "★" : "☆";
  return "<div class='card'>"
    + "<span class='badge'>" + typeLabel(item.type) + "</span>"
    + "<h3>" + item.name + "</h3>"
    + "<p>" + item.description_es + "</p>"
    + "<div class='actions'>"
    + "<button data-detail='" + item.id + "'>Ver detalle</button>"
    + "<button data-favorite='" + item.id + "'>" + marked + " Favorito</button>"
    + "</div></div>";
}

function bindCardButtons(container) {
  container.querySelectorAll("[data-detail]").forEach(button => {
    button.addEventListener("click", () => showDetail(button.dataset.detail));
  });
  container.querySelectorAll("[data-favorite]").forEach(button => {
    button.addEventListener("click", () => toggleFavorite(button.dataset.favorite));
  });
}

async function loadCatalog() {
  const params = new URLSearchParams({
    search: searchInput.value,
    type_filter: typeFilter.value,
    habitable_only: habitableOnly.checked
  });
  allObjects = await fetchJson("/api/objects?" + params.toString());
  catalogGrid.innerHTML = allObjects.map(cardHtml).join("");
  bindCardButtons(catalogGrid);
  fillSelectors();
}

function fillSelectors() {
  const planets = allObjects.filter(item => item.type === "PLANET");
  const options = planets.map(item => "<option value='" + item.id + "'>" + item.name + "</option>").join("");
  planetA.innerHTML = options;
  planetB.innerHTML = options;
  if (planets.length > 1) {
    planetB.selectedIndex = 1;
  }
  const every = allObjects.map(item => "<option value='" + item.id + "'>" + item.name + "</option>").join("");
  originSelect.innerHTML = every;
  destinationSelect.innerHTML = every;
  if (allObjects.length > 3) {
    destinationSelect.selectedIndex = 3;
  }
}

async function showDetail(objectId) {
  const item = await fetchJson("/api/objects/" + objectId);
  detailBox.classList.remove("hidden");
  detailBox.innerHTML = "<h3>" + item.name + " " + typeLabel(item.type) + "</h3>"
    + "<p>" + item.description_es + "</p>"
    + "<table><tr><th>Métrica</th><th>Valor</th></tr>"
    + "<tr><td>Distancia (años luz)</td><td>" + item.distance_ly + "</td></tr>"
    + "<tr><td>Diámetro (km)</td><td>" + item.diameter_km + "</td></tr>"
    + "<tr><td>Gravedad (m/s²)</td><td>" + item.gravity_ms2 + "</td></tr>"
    + "<tr><td>Periodo orbital (días)</td><td>" + item.orbital_period_days + "</td></tr>"
    + "<tr><td>Temperatura media (°C)</td><td>" + item.mean_temp_c + "</td></tr>"
    + "<tr><td>Habitable</td><td>" + (item.habitable ? "Sí" : "No") + "</td></tr></table>";
  detailBox.scrollIntoView({ behavior: "smooth" });
}

async function toggleFavorite(objectId) {
  const result = await fetchJson("/api/favorites/toggle", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: objectId })
  });
  if (result.is_favorite) {
    favorites.add(objectId);
  } else {
    favorites.delete(objectId);
  }
  loadCatalog();
}

async function loadFavorites() {
  const items = await fetchJson("/api/favorites");
  favorites = new Set(items.map(item => item.id));
  favoritesGrid.innerHTML = items.length ? items.map(cardHtml).join("") : "<p>No tienes favoritos todavía. Marca una estrella ☆ en el catálogo.</p>";
  bindCardButtons(favoritesGrid);
}

async function runCompare() {
  const payload = { planet_a_id: planetA.value, planet_b_id: planetB.value };
  const result = await fetchJson("/api/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const rows = result.diffs.map(diff => "<tr><td>" + diff.metric + "</td><td>" + diff.value_a.toExponential(3) + "</td><td>" + diff.value_b.toExponential(3) + "</td><td>" + diff.winner_id + "</td></tr>").join("");
  compareResult.innerHTML = "<h3>" + result.planet_a.name + " vs " + result.planet_b.name + "</h3>"
    + "<table><tr><th>Métrica</th><th>" + result.planet_a.name + "</th><th>" + result.planet_b.name + "</th><th>Ganador</th></tr>" + rows + "</table>";
}

async function loadPresets() {
  const presets = await fetchJson("/api/presets");
  spacecraftSelect.innerHTML = presets.map(name => "<option value='" + name + "'>" + name + "</option>").join("");
}

async function runSimulation() {
  const payload = {
    origin_id: originSelect.value,
    destination_id: destinationSelect.value,
    spacecraft: spacecraftSelect.value,
    speed_kms: parseFloat(document.getElementById("speedInput").value),
    payload_kg: parseFloat(document.getElementById("payloadInput").value),
    crew_size: parseInt(document.getElementById("crewInput").value, 10)
  };
  const result = await fetchJson("/api/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const stages = result.stages.map(stage => "<tr><td>" + stage.name_es + "</td><td>" + stage.duration_days.toFixed(1) + "</td><td>" + stage.fuel_tons.toFixed(2) + "</td><td>" + stage.status + "</td></tr>").join("");
  missionResult.innerHTML = "<h3>Resultado: " + result.difficulty_es + "</h3>"
    + "<p>" + result.summary_es + "</p>"
    + "<p><b>Distancia:</b> " + result.distance_km.toExponential(3) + " km · <b>Días:</b> " + result.travel_days.toFixed(1) + " · <b>Años:</b> " + result.travel_years.toFixed(2) + " · <b>Éxito:</b> " + result.success_rate.toFixed(1) + "%</p>"
    + "<table><tr><th>Etapa</th><th>Días</th><th>Combustible (t)</th><th>Estado</th></tr>" + stages + "</table>";
}

async function loadQuiz() {
  const difficulty = document.getElementById("difficultyFilter").value;
  currentQuestions = await fetchJson("/api/questions?difficulty=" + difficulty + "&limit=10");
  quizResult.innerHTML = "";
  quizBox.innerHTML = currentQuestions.map((item, index) => {
    const options = item.options_es.map((text, optionIndex) => "<label><input type='radio' name='q_" + item.id + "' value='" + optionIndex + "'> " + text + "</label>").join("");
    return "<div class='question'><p>" + (index + 1) + ". " + item.text_es + "</p>" + options + "</div>";
  }).join("") || "<p>No hay preguntas para ese filtro.</p>";
}

async function submitQuiz() {
  const userId = document.getElementById("userInput").value || "guest";
  const answers = currentQuestions.map(item => {
    const checked = document.querySelector("input[name='q_" + item.id + "']:checked");
    return { question_id: item.id, selected_index: checked ? parseInt(checked.value, 10) : -1 };
  });
  const result = await fetchJson("/api/quiz/submit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, answers: answers })
  });
  const lines = result.feedback.map(item => {
    const mark = item.is_correct ? "<span class='correct'>✔ Correcta</span>" : "<span class='wrong'>✘ Incorrecta</span>";
    return "<p>" + mark + " " + item.explanation_es + "</p>";
  }).join("");
  quizResult.innerHTML = "<h3>Obtuviste " + result.correct + " de " + result.total + " (" + result.score.toFixed(1) + "%)</h3>" + lines
    + "<p><b>Nivel:</b> " + result.progress.level_es + " · <b>Intentos:</b> " + result.progress.attempts + "</p>";
  refreshProgress();
}

async function refreshProgress() {
  const userId = document.getElementById("userInput").value || "guest";
  const progress = await fetchJson("/api/progress/" + userId);
  progressBox.innerHTML = "<h3>Progreso de " + progress.user_id + "</h3>"
    + "<p><b>Nivel:</b> " + progress.level_es + " · <b>Intentos:</b> " + progress.attempts + " · <b>Mejor:</b> " + progress.best_percent.toFixed(1) + "%</p>"
    + "<p><b>Respondidas:</b> " + progress.total_answered + " · <b>Correctas:</b> " + progress.total_correct + "</p>";
}

async function resetProgress() {
  const userId = document.getElementById("userInput").value || "guest";
  await fetchJson("/api/progress/" + userId + "/reset", { method: "POST" });
  refreshProgress();
}

document.getElementById("searchButton").addEventListener("click", loadCatalog);
document.getElementById("compareButton").addEventListener("click", runCompare);
document.getElementById("simulateButton").addEventListener("click", runSimulation);
document.getElementById("loadQuizButton").addEventListener("click", loadQuiz);
document.getElementById("submitQuizButton").addEventListener("click", submitQuiz);
document.getElementById("refreshFavoritesButton").addEventListener("click", loadFavorites);
document.getElementById("refreshProgressButton").addEventListener("click", refreshProgress);
document.getElementById("resetProgressButton").addEventListener("click", resetProgress);

loadCatalog();
loadPresets();
loadFavorites();
