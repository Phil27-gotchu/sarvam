const state = {
  profile: {
    origin: "Australia",
    diet: "nonveg",
    max_spice: 3,
    avoid_allergens: [],
    ui_lang: "en-IN",
  },
  dishes: [],
  roleFilter: "all",
  selectedDishId: "kombdi-vade",
  order: {},
  lastDraftOrder: null,
};

const ORIGIN_FLAGS = {
  Australia: "🇦🇺",
  UK: "🇬🇧",
  USA: "🇺🇸",
  Germany: "🇩🇪",
  Japan: "🇯🇵",
};

const PROTEIN_EMOJI = {
  chicken: "🍗",
  fish: "🐟",
  prawn: "🦐",
  crab: "🦀",
  mutton: "🍖",
  egg: "🥚",
  veg: "🥥",
};

let islandTimer = null;
function showIsland(msg, durationMs = 3400) {
  const island = document.getElementById("dynamic-island");
  const textEl = document.getElementById("island-text");
  if (!island || !textEl) return;
  textEl.textContent = msg;
  island.classList.add("active");
  if (islandTimer) clearTimeout(islandTimer);
  islandTimer = setTimeout(() => island.classList.remove("active"), durationMs);
}

function updateSummaryChip() {
  const p = state.profile;
  document.getElementById("chip-flag").textContent = ORIGIN_FLAGS[p.origin] || "🌏";
  document.getElementById("chip-diet").textContent =
    p.diet === "veg" ? "Veg" : p.diet === "vegan" ? "Vegan" : "Non-Veg";
  document.getElementById("chip-spice").textContent = `🌶️ ${p.max_spice}/5`;
}

function switchScreen(screenId) {
  document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
  document.querySelectorAll(".seg-item").forEach((t) => {
    t.classList.toggle("active", t.dataset.screen === screenId);
  });
  const target = document.getElementById(`screen-${screenId}`);
  if (target) target.classList.add("active");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function readProfileFromForm() {
  const origin = document.getElementById("origin-select").value;
  const diet = document.getElementById("diet-select").value;
  const max_spice = parseInt(document.getElementById("spice-range").value, 10);
  const ui_lang = document.getElementById("lang-select").value;
  const avoid_allergens = Array.from(
    document.querySelectorAll("#allergen-grid input:checked")
  ).map((el) => el.value);
  state.profile = { origin, diet, max_spice, avoid_allergens, ui_lang };
  updateSummaryChip();
}

function speakWithWebSpeech(text, romanText = "", lang = "mr-IN") {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const voices = window.speechSynthesis.getVoices();
  const hasIndicVoice = voices.some(
    (v) => v.lang.startsWith("mr") || v.lang.startsWith("hi") || v.lang === "en-IN"
  );
  const textToSpeak = hasIndicVoice ? (text || romanText) : (romanText || text);
  if (!textToSpeak) return;

  const utterance = new SpeechSynthesisUtterance(textToSpeak);
  utterance.lang = hasIndicVoice ? lang : "en-IN";
  utterance.rate = 0.88;

  const match =
    voices.find((v) => v.lang === "mr-IN" || v.lang === "mr_IN") ||
    voices.find((v) => v.lang.startsWith("hi")) ||
    voices.find((v) => v.lang === "en-IN");
  if (match) utterance.voice = match;
  window.speechSynthesis.speak(utterance);
}

function playBase64Audio(b64, labelText = "Speaking Marathi via Bulbul v3…", fallbackText = "", fallbackRoman = "") {
  showIsland(labelText, 4000);
  if (!b64) {
    if (fallbackText || fallbackRoman) speakWithWebSpeech(fallbackText, fallbackRoman, "mr-IN");
    return;
  }
  const player = document.getElementById("audio-player");
  player.src = `data:audio/wav;base64,${b64}`;
  player.load();
  const playPromise = player.play();
  if (playPromise !== undefined) {
    playPromise.catch((err) => {
      console.warn("Audio playback failed, falling back to Web Speech:", err);
      if (fallbackText || fallbackRoman) speakWithWebSpeech(fallbackText, fallbackRoman, "mr-IN");
    });
  }
}

async function pronounceDish(dishId, text) {
  const found = state.dishes.find((item) => item.dish.id === dishId);
  const mrText = text || (found ? found.dish.name_mr : "");
  const romanText = found ? (found.dish.name_roman || found.dish.phonetic) : (text || dishId);
  const displayLabel = found ? `${found.dish.name_roman} (${found.dish.name_mr})` : (text || dishId);

  showIsland(`Pronouncing: ${displayLabel}…`, 3000);

  try {
    const res = await fetch("/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dish_id: dishId, text: text || null, lang: "mr-IN" }),
    });
    if (!res.ok) {
      throw new Error(`TTS endpoint returned ${res.status}`);
    }
    const data = await res.json();
    const label = data.warning || `Speaking: ${data.text} (${data.phonetic || "mr-IN"})`;

    if (data.is_mock) {
      speakWithWebSpeech(data.text || mrText, romanText, "mr-IN");
      showIsland(label, 4000);
    } else if (data.audio_base64) {
      playBase64Audio(data.audio_base64, label, data.text || mrText, romanText);
    } else {
      speakWithWebSpeech(data.text || mrText, romanText, "mr-IN");
      showIsland(label, 4000);
    }
  } catch (err) {
    console.warn("pronounceDish error:", err);
    speakWithWebSpeech(mrText, romanText, "mr-IN");
    showIsland(`Pronouncing: ${displayLabel}`, 3000);
  }
}

function spicePips(n) {
  return "🌶️".repeat(n) + `<span style="opacity:0.22">${"🌶️".repeat(Math.max(0, 5 - n))}</span>`;
}

function dishEmoji(dish) {
  if (dish.flavor_dna.meal_role === "drink") return "🥤";
  if (dish.flavor_dna.meal_role === "dessert") return "🍮";
  if (dish.flavor_dna.format === "flatbread") return "🫓";
  return PROTEIN_EMOJI[dish.flavor_dna.protein] || "🍛";
}

function renderDishList() {
  const container = document.getElementById("dish-list");
  const q = (document.getElementById("search-input").value || "").trim().toLowerCase();
  const role = state.roleFilter;

  const filtered = state.dishes.filter(({ dish, safety }) => {
    if (role === "safe" && safety.status !== "SAFE") return false;
    if (role !== "all" && role !== "safe" && dish.flavor_dna.meal_role !== role) return false;
    if (!q) return true;
    return (
      dish.name_roman.toLowerCase().includes(q) ||
      dish.name_mr.includes(q) ||
      dish.description.toLowerCase().includes(q) ||
      dish.ingredients.some((i) => i.toLowerCase().includes(q))
    );
  });

  container.innerHTML = filtered
    .map(({ dish, safety }) => {
      const vegClass = dish.veg ? "veg" : "nonveg";
      const fmtClass = `vis-${dish.flavor_dna.format}`;
      return `
      <article class="dish-card">
        <div class="dish-visual ${fmtClass}" onclick="openDishDetail('${dish.id}')" style="cursor:pointer">
          <span class="vis-emoji">${dishEmoji(dish)}</span>
          <span class="badge ${safety.status}">${safety.status}</span>
        </div>
        <div class="dish-body">
          <div>
            <div class="dish-title">
              <span class="dot ${vegClass}"></span>
              <span>${dish.name_roman}</span>
            </div>
            <div class="dish-devanagari">${dish.name_mr}</div>
            <div class="phonetic-tag">/${dish.phonetic}/</div>
            <p class="dish-copy">${dish.description}</p>
          </div>
          <div>
            <div class="card-meta-row">
              <span>${spicePips(dish.spice)}</span>
              <span>${dish.allergens.length ? dish.allergens.join(" · ") : "No major allergens"}</span>
            </div>
            ${safety.reasons.length ? `<div style="font-size:0.74rem;color:var(--block-fg);margin-top:0.35rem;font-weight:600;">⚠️ ${safety.reasons[0]}</div>` : ""}
          </div>
        </div>
        <div class="card-footer-actions">
          <button class="apple-btn sm" onclick="pronounceDish('${dish.id}')" title="Hear Marathi">🔊</button>
          <button class="apple-btn sm" onclick="openDishDetail('${dish.id}')">Bridge &amp; Coach</button>
          <button class="apple-btn primary sm" onclick="addToOrder('${dish.id}')">+ Add</button>
        </div>
      </article>`;
    })
    .join("");
}

async function loadDishes() {
  const p = state.profile;
  const qs = new URLSearchParams({
    max_spice: p.max_spice,
    diet: p.diet,
    avoid_allergens: p.avoid_allergens.join(","),
    origin: p.origin,
  });
  const res = await fetch(`/dishes?${qs.toString()}`);
  const data = await res.json();
  state.dishes = data.items || [];
  renderDishList();
}

async function openDishDetail(dishId) {
  state.selectedDishId = dishId;
  switchScreen("detail");
  const box = document.getElementById("detail-content");
  box.innerHTML = `<div class="glass-sheet"><p class="sheet-sub">Loading Dish Card &amp; Cultural Bridge…</p></div>`;

  try {
    const p = state.profile;
    const qs = new URLSearchParams({
      max_spice: p.max_spice,
      diet: p.diet,
      avoid_allergens: p.avoid_allergens.join(","),
      origin: p.origin,
    });
    const [cardRes, bridgeRes] = await Promise.all([
      fetch(`/dishes/${dishId}?${qs.toString()}`),
      fetch(`/bridge/${dishId}?origin=${encodeURIComponent(p.origin)}&lang=${encodeURIComponent(p.ui_lang)}`),
    ]);

    if (!cardRes.ok) {
      throw new Error(`Failed to load dish details: ${cardRes.status}`);
    }
    const card = await cardRes.json();
    let bridge = {
      matches: [],
      closest: { name: "Home Comfort Food" },
      explanation: "",
      spice_calibration: "",
      origin: p.origin,
    };
    if (bridgeRes.ok) {
      bridge = await bridgeRes.json();
    }

    const d = card.dish;
    const s = card.safety;
    const fmtClass = `vis-${d.flavor_dna?.format || "curry"}`;

    const matchesHtml = (bridge.matches || [])
      .map(
        (m, idx) => `
        <div class="match-item">
          <div class="row-between">
            <strong>#${idx + 1} · ${m.name}</strong>
            <span style="font-size:0.78rem;font-weight:700;color:var(--accent)">${Math.round((m.score || 0) * 100)}% Flavor Match</span>
          </div>
          <div class="progress-track"><div class="progress-fill" style="width:${Math.max(18, Math.round((m.score || 0) * 100))}%"></div></div>
          <div style="font-size:0.76rem;color:var(--text-secondary)">
            <strong>Shared:</strong> ${(m.similar_in || []).join(", ")} · <strong>Differs:</strong> ${(m.different_in || []).join(", ")}
          </div>
        </div>`
      )
      .join("");

    const pairingButtons = (card.pairings || [])
      .map(
        (x) =>
          `<button class="prompt-chip" onclick="openDishDetail('${x.id}')">${dishEmoji(x)} ${x.name_roman} (${x.name_mr})</button>`
      )
      .join("");

    box.innerHTML = `
      <div class="detail-hero-card">
        <div class="detail-banner ${fmtClass}">
          <div>
            <span style="font-size:0.72rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;opacity:0.9;">
              ${d.flavor_dna?.meal_role || "Mains"} · ${d.flavor_dna?.method || "Coastal"} · AUTHENTIC MALWANI
            </span>
            <h1>${dishEmoji(d)} ${d.name_roman} <span style="font-weight:500;opacity:0.92">${d.name_mr}</span></h1>
            <div style="font-family:var(--font-mono);font-size:0.95rem;opacity:0.95;">Say it: /${d.phonetic}/</div>
          </div>
          <span class="badge ${s.status}" style="font-size:0.85rem;padding:0.4rem 0.9rem;">${s.status}</span>
        </div>

        <div class="detail-body">
          <p style="font-size:1.05rem;margin:0 0 1.1rem;">${d.description}</p>
          <div class="control-row" style="flex-wrap:wrap;margin-bottom:1.1rem;">
            <button class="apple-btn primary" onclick="pronounceDish('${d.id}')">🔊 Hear Native Marathi Audio</button>
            <button class="apple-btn secondary" onclick="addToOrder('${d.id}')">+ Add to My Order</button>
            <button class="apple-btn ghost" onclick="switchScreen('browse')">← Back to 30 Dishes</button>
          </div>

          ${s.reasons.length ? `<div class="sommelier-reply" style="border-color:var(--block-fg);color:var(--block-fg);margin-bottom:1.1rem;"><strong>Safety Engine Assessment:</strong> ${s.reasons.join(" · ")}</div>` : ""}

          <div class="bento-2col" style="margin-bottom:0;">
            <div class="glass-sheet">
              <span class="kicker">CULINARY ANATOMY</span>
              <h3 style="margin:0.2rem 0 0.7rem;">Ingredients &amp; Pairings</h3>
              <p class="sheet-sub"><strong>Spice Level:</strong> ${spicePips(d.spice)} (${d.spice}/5) · <strong>Richness:</strong> ${d.richness}/5</p>
              <p class="sheet-sub"><strong>Key Ingredients:</strong> ${d.ingredients.join(", ")}</p>
              <p class="sheet-sub"><strong>Allergens:</strong> ${d.allergens.length ? d.allergens.join(", ") : "None listed"}</p>
              <div style="margin-top:0.75rem;">
                <strong style="font-size:0.82rem;display:block;margin-bottom:0.35rem;">Classic Coastal Pairings (tap to jump):</strong>
                <div class="quick-prompts">${pairingButtons || "Sol Kadhi"}</div>
              </div>
            </div>

            <div class="glass-sheet">
              <span class="kicker">CULTURAL BRIDGE · ${ORIGIN_FLAGS[bridge.origin] || "🌏"} ${bridge.origin.toUpperCase()}</span>
              <h3 style="margin:0.2rem 0 0.5rem;">Closest to: ${bridge.closest?.name || "Home Comfort Food"}</h3>
              <p class="sheet-sub" style="font-size:0.95rem;line-height:1.5;color:var(--text);">${bridge.explanation}</p>
              ${bridge.translated ? `<p class="sheet-sub"><em>${bridge.translated}</em></p>` : ""}
              <p class="sheet-sub"><strong>Spice Calibration:</strong> ${bridge.spice_calibration}</p>
              <div class="match-rank-list">${matchesHtml}</div>
              <div class="control-row" style="margin-top:0.65rem;">
                <button class="apple-btn sm" onclick="sendFeedback('${d.id}', '${bridge.origin}', 'up')">👍 Spot-on analogy</button>
                <button class="apple-btn sm" onclick="sendFeedback('${d.id}', '${bridge.origin}', 'down')">👎 Needs work</button>
                <span id="fb-msg" style="font-size:0.76rem;color:var(--text-secondary);"></span>
              </div>
            </div>
          </div>

          <div class="glass-sheet" style="margin-top:1.15rem;">
            <div class="row-between">
              <div>
                <span class="kicker">SAARAS V3 PRONUNCIATION COACH</span>
                <h3 style="margin:0.2rem 0 0.3rem;">Practice Saying “${d.phonetic}”</h3>
              </div>
              <span class="feature-tag">Levenshtein Syllable Scorer</span>
            </div>
            <p class="sheet-sub">Test how closely your pronunciation matches native Marathi syllables (aspirated &amp; retroflex tolerant):</p>
            <div class="control-row">
              <input id="coach-text-input" class="apple-input" type="text" value="${d.phonetic}" />
              <button class="apple-btn primary" onclick="runCoach('${d.id}')">Score My Pronunciation</button>
            </div>
            <div id="coach-result" class="sommelier-reply hidden"></div>
          </div>
          <p class="legal-note">${card.safety_disclaimer}</p>
        </div>
      </div>
    `;
  } catch (err) {
    console.error("openDishDetail error:", err);
    box.innerHTML = `
      <div class="glass-sheet">
        <h3 style="color:var(--block-fg)">Unable to load Dish Card</h3>
        <p class="sheet-sub">${err.message || "An unexpected error occurred."}</p>
        <div class="control-row" style="margin-top:1rem;">
          <button class="apple-btn primary" onclick="openDishDetail('${dishId}')">Retry</button>
          <button class="apple-btn ghost" onclick="switchScreen('browse')">Back to Explore</button>
        </div>
      </div>`;
  }
}

async function sendFeedback(dishId, origin, vote) {
  const res = await fetch("/bridge/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dish_id: dishId, origin, vote }),
  });
  const data = await res.json();
  const el = document.getElementById("fb-msg");
  if (el) el.textContent = `Thank you! (${data.total_feedback} ratings saved)`;
  showIsland("Feedback saved to data/feedback.json", 2200);
}

async function runCoach(dishId) {
  const heard = document.getElementById("coach-text-input").value;
  const res = await fetch("/coach/json", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dish_id: dishId, heard_text: heard }),
  });
  const data = await res.json();
  const box = document.getElementById("coach-result");
  box.classList.remove("hidden");
  box.innerHTML = `
    <div class="row-between">
      <strong style="font-size:1.05rem;">Pronunciation Score: ${data.score} / 100</strong>
      <span class="badge ${data.score >= 80 ? "SAFE" : "WARN"}">${data.score >= 80 ? "EXCELLENT" : "KEEP PRACTICING"}</span>
    </div>
    <div class="progress-track" style="margin:0.5rem 0;"><div class="progress-fill" style="width:${data.score}%"></div></div>
    <p class="sheet-sub" style="margin:0.25rem 0;">Heard: <code>${data.heard}</code> · Target: <code>${data.target}</code></p>
    ${data.mismatched_syllables.length ? `<p class="sheet-sub" style="margin:0.2rem 0;">Syllables to emphasize: <strong>${data.mismatched_syllables.join(" · ")}</strong></p>` : ""}
    <p style="margin:0.35rem 0 0;font-weight:700;">💡 ${data.tip}</p>
  `;
}

function addToOrder(dishId) {
  state.order[dishId] = (state.order[dishId] || 0) + 1;
  updateOrderUI();
  const found = state.dishes.find((x) => x.dish.id === dishId);
  showIsland(`Added ${found ? found.dish.name_roman : dishId} to Order`, 2200);
}

function changeQty(dishId, delta) {
  const next = (state.order[dishId] || 0) + delta;
  if (next <= 0) delete state.order[dishId];
  else state.order[dishId] = next;
  updateOrderUI();
}

function updateOrderUI() {
  const count = Object.values(state.order).reduce((a, b) => a + b, 0);
  document.getElementById("order-count").textContent = count;
  const container = document.getElementById("order-items");
  const entries = Object.entries(state.order);
  if (!entries.length) {
    container.innerHTML = `<p class="sheet-sub" style="margin-top:0.8rem;">No dishes in your tray yet. Tap "+ Add" on any card — or click below to draft a classic Kombdi Vade + Sol Kadhi order.</p>`;
    return;
  }
  container.innerHTML = entries
    .map(([id, qty]) => {
      const found = state.dishes.find((x) => x.dish.id === id);
      const name = found ? `${dishEmoji(found.dish)} <strong>${found.dish.name_roman}</strong> <span class="brand-native">${found.dish.name_mr}</span>` : id;
      return `<div class="setting-item">
        <div>${name}</div>
        <div class="control-row">
          <button class="apple-btn sm" onclick="changeQty('${id}', -1)">−</button>
          <strong style="min-width:22px;text-align:center;">${qty}</strong>
          <button class="apple-btn sm" onclick="changeQty('${id}', 1)">+</button>
        </div>
      </div>`;
    })
    .join("");
}

async function draftOrder() {
  const entries = Object.entries(state.order).map(([dish_id, qty]) => ({ dish_id, qty }));
  if (!entries.length) {
    entries.push({ dish_id: "kombdi-vade", qty: 1 }, { dish_id: "sol-kadhi", qty: 1 });
  }
  showIsland("Drafting polite Marathi order with Sarvam-105B…", 2800);
  const res = await fetch("/order/draft", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items: entries, profile: state.profile }),
  });
  const data = await res.json();
  state.lastDraftOrder = data;
  const box = document.getElementById("drafted-order-box");
  box.classList.remove("empty-state");
  box.innerHTML = `
    <span class="kicker">BULBUL V3 VOICE SCRIPT READY</span>
    <div class="wc-devanagari" style="margin-top:0.35rem;">${data.marathi_text}</div>
    <div class="wc-phonetic">/${data.phonetic}/</div>
    <p class="sheet-sub"><strong>English Translation:</strong> “${data.english_meaning}”</p>
    ${data.safety_warnings.length ? `<div class="sommelier-reply" style="color:var(--block-fg);border-color:var(--block-fg);margin-bottom:0.8rem;">⚠️ ${data.safety_warnings.join(" · ")}</div>` : ""}
    <div class="control-row" style="flex-wrap:wrap;margin-top:0.9rem;">
      <button class="apple-btn primary" onclick="playBase64Audio('${data.audio_base64}')">🔊 Speak Order in Marathi</button>
      <button class="apple-btn secondary" onclick="switchScreen('waiter')">Open Live Waiter Mode →</button>
    </div>
  `;
  document.getElementById("waiter-mr-text").textContent = data.marathi_text;
  document.getElementById("waiter-mr-phonetic").textContent = `/${data.phonetic}/`;
  document.getElementById("waiter-mr-sub").textContent = `“${data.english_meaning}”`;
}

document.addEventListener("DOMContentLoaded", async () => {
  // Navigation tabs
  document.querySelectorAll(".seg-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.screen === "detail" && state.selectedDishId) {
        openDishDetail(state.selectedDishId);
      } else {
        switchScreen(btn.dataset.screen);
      }
    });
  });

  // Theme toggle (Auto -> Dark -> Light)
  document.getElementById("theme-toggle").addEventListener("click", () => {
    const root = document.documentElement;
    const cur = root.getAttribute("data-theme") || "auto";
    const next = cur === "auto" ? "dark" : cur === "dark" ? "light" : "auto";
    root.setAttribute("data-theme", next);
    showIsland(`Appearance: ${next.toUpperCase()}`, 1800);
  });

  // Spice slider live readout
  const spiceRange = document.getElementById("spice-range");
  spiceRange.addEventListener("input", () => {
    document.getElementById("spice-val").textContent = spiceRange.value;
  });

  // Role filter pills
  document.querySelectorAll("#role-filters .filter-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      document.querySelectorAll("#role-filters .filter-pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      state.roleFilter = pill.dataset.role;
      renderDishList();
    });
  });

  // Quick sommelier prompt chips
  document.querySelectorAll(".prompt-chip[data-q]").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.getElementById("ask-input").value = chip.dataset.q;
      document.getElementById("ask-btn").click();
    });
  });

  // File input label
  const fileInput = document.getElementById("menu-file");
  fileInput.addEventListener("change", () => {
    const label = document.getElementById("file-label-text");
    label.textContent = fileInput.files[0]
      ? `📷 ${fileInput.files[0].name}`
      : "📷 Choose Menu Photo (or leave empty for Demo Scan)";
  });

  // Save profile
  document.getElementById("save-profile-btn").addEventListener("click", async () => {
    readProfileFromForm();
    await loadDishes();
    showIsland(`Passport saved · ${state.profile.origin}`, 2400);
    switchScreen("browse");
  });

  document.getElementById("search-input").addEventListener("input", () => renderDishList());

  // Scan Menu
  document.getElementById("scan-btn").addEventListener("click", async () => {
    readProfileFromForm();
    showIsland("Scanning menu with Sarvam Vision + rapidfuzz…", 2800);
    const fd = new FormData();
    if (fileInput.files[0]) fd.append("image", fileInput.files[0]);
    fd.append("profile_json", JSON.stringify(state.profile));
    const res = await fetch("/menu/scan", { method: "POST", body: fd });
    const data = await res.json();
    const out = document.getElementById("scan-results");
    out.innerHTML = (data.items || [])
      .map((item) => {
        if (item.in_kb) {
          return `<article class="dish-card">
            <div class="dish-body">
              <div>
                <div class="row-between">
                  <span class="dish-title">${dishEmoji(item.dish)} ${item.dish.name_roman} <small>${item.price || ""}</small></span>
                  <span class="badge ${item.safety.status}">${item.safety.status}</span>
                </div>
                <div class="dish-devanagari">${item.dish.name_mr}</div>
                <p class="dish-copy">${item.dish.description}</p>
              </div>
            </div>
            <div class="card-footer-actions">
              <button class="apple-btn sm" onclick="pronounceDish('${item.dish.id}')">🔊</button>
              <button class="apple-btn sm" onclick="openDishDetail('${item.dish.id}')">Inspect</button>
              <button class="apple-btn primary sm" onclick="addToOrder('${item.dish.id}')">+ Add</button>
            </div>
          </article>`;
        }
        return `<article class="dish-card">
          <div class="dish-body">
            <div>
              <div class="row-between">
                <span class="dish-title">✨ ${item.menu_name} <small>${item.price || ""}</small></span>
                <span class="badge WARN">${item.badge_text}</span>
              </div>
              <p class="dish-copy">${item.explanation}</p>
            </div>
          </div>
        </article>`;
      })
      .join("");
  });

  // Grounded Q&A
  document.getElementById("ask-btn").addEventListener("click", async () => {
    const text = document.getElementById("ask-input").value;
    showIsland("Consulting Sarvam-105B with Malwani KB…", 2400);
    const res = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, profile: state.profile, want_tts: false }),
    });
    const data = await res.json();
    const box = document.getElementById("ask-output");
    box.classList.remove("hidden");
    box.innerHTML = `<p style="margin:0 0 0.4rem;font-weight:500;">${data.answer}</p><small style="color:var(--text-tertiary);">${data.disclaimer}</small>`;
  });

  document.getElementById("draft-order-btn").addEventListener("click", draftOrder);

  document.getElementById("play-order-tts").addEventListener("click", async () => {
    if (state.lastDraftOrder && state.lastDraftOrder.audio_base64) {
      playBase64Audio(state.lastDraftOrder.audio_base64, "Speaking Marathi to waiter…", state.lastDraftOrder.marathi_text);
    } else {
      await pronounceDish(null, "नमस्कार दादा, आम्हाला एक प्लेट कोंबडी वडे आणि सोलकढी द्या.");
    }
  });

  // Tourist Speaks English -> Translates into Marathi voice
  async function handleTouristSpeak(text) {
    let englishText = (text || "").trim();
    if (!englishText) {
      const inp = document.getElementById("user-en-input");
      if (inp) englishText = inp.value.trim();
    }
    if (!englishText) {
      englishText = "Please make our food less spicy and bring extra rice.";
      const inp = document.getElementById("user-en-input");
      if (inp) inp.value = englishText;
    }

    showIsland("Translating English → Marathi Voice (Bulbul v3)…", 3200);
    const speakBtn = document.getElementById("user-speak-en-btn");
    if (speakBtn) speakBtn.disabled = true;

    try {
      const res = await fetch("/order/speak-english", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: englishText, profile: state.profile }),
      });
      const data = await res.json();

      // Update UI with Marathi translation and English text
      const mrTextEl = document.getElementById("waiter-mr-text");
      if (mrTextEl) mrTextEl.textContent = data.marathi_text;
      const subTextEl = document.getElementById("waiter-mr-sub");
      if (subTextEl) subTextEl.textContent = `“${data.english_text}”`;
      const phoneticEl = document.getElementById("waiter-mr-phonetic");
      if (phoneticEl) phoneticEl.textContent = "";

      // Store in state so replay button works
      state.lastDraftOrder = {
        marathi_text: data.marathi_text,
        english_meaning: data.english_text,
        audio_base64: data.audio_base64,
      };

      // Play the translated Marathi audio aloud to the waiter!
      if (data.audio_base64) {
        playBase64Audio(data.audio_base64, "Speaking to waiter in Marathi…", data.marathi_text);
      } else {
        speakWithWebSpeech(data.marathi_text, "", "mr-IN");
      }
    } catch (err) {
      console.error("Tourist speak error:", err);
      showIsland("Error generating Marathi speech", 2400);
    } finally {
      if (speakBtn) speakBtn.disabled = false;
    }
  }

  // Waiter Speaks Marathi -> Translates into English text
  async function handleWaiterListen(text) {
    const micLabel = document.getElementById("mic-label");
    if (micLabel) micLabel.textContent = "Translating Waiter's Marathi via Saaras v3…";
    showIsland("Listening to waiter (mr-IN → English)…", 2800);
    try {
      const res = await fetch("/order/listen-json", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text || undefined, profile: state.profile }),
      });
      const data = await res.json();
      const heardEl = document.getElementById("waiter-mr-heard");
      if (heardEl) heardEl.textContent = data.waiter_marathi || "";
      const enEl = document.getElementById("waiter-en-text");
      if (enEl) enEl.textContent = `“${data.waiter_english || data.waiter_meaning}”`;
      const altsEl = document.getElementById("waiter-alts");
      if (altsEl) {
        altsEl.innerHTML = `
          <div class="sommelier-reply" style="margin-top:0.8rem;">
            <div><strong>Safe KB Alternatives:</strong> ${(data.suggested_alternatives || []).join(" · ")}</div>
            <div style="margin-top:0.45rem;"><strong>Suggested Marathi Reply:</strong> <span class="brand-native">${data.followup_marathi}</span> — <em>“${data.followup_english}”</em></div>
            ${data.followup_audio_base64 ? `<button class="apple-btn sm primary" style="margin-top:0.55rem;" onclick="playBase64Audio('${data.followup_audio_base64}', 'Speaking Marathi reply…', '${data.followup_marathi}')">🔊 Speak Reply to Waiter</button>` : ""}
          </div>
        `;
      }
      showIsland("Waiter Marathi translated to English", 2400);
    } catch (err) {
      console.error("Waiter listen error:", err);
      showIsland("Error translating waiter speech", 2400);
    } finally {
      if (micLabel) micLabel.textContent = "Listen to Waiter (Marathi → English)";
    }
  }

  // Global triggers for HTML prompt chips
  window.quickSpeakEnglish = async function(text) {
    const inp = document.getElementById("user-en-input");
    if (inp) inp.value = text;
    await handleTouristSpeak(text);
  };

  window.simulateWaiter = async function(text) {
    await handleWaiterListen(text);
  };

  // Tourist text input and button
  const speakEnBtn = document.getElementById("user-speak-en-btn");
  if (speakEnBtn) {
    speakEnBtn.addEventListener("click", () => handleTouristSpeak());
  }
  const userEnInput = document.getElementById("user-en-input");
  if (userEnInput) {
    userEnInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleTouristSpeak();
      }
    });
  }

  // Tourist mic button (Web Speech recognition in English or fallback)
  const touristMicBtn = document.getElementById("tourist-mic-btn");
  if (touristMicBtn) {
    touristMicBtn.addEventListener("click", () => {
      const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (SpeechRec) {
        try {
          const rec = new SpeechRec();
          rec.lang = "en-IN";
          rec.continuous = false;
          rec.interimResults = false;
          const label = document.getElementById("tourist-mic-label");
          if (label) label.textContent = "Listening to you in English… 🎙️";
          rec.onresult = (e) => {
            const transcript = e.results[0][0].transcript;
            if (userEnInput) userEnInput.value = transcript;
            handleTouristSpeak(transcript);
          };
          rec.onerror = () => handleTouristSpeak();
          rec.onend = () => {
            if (label) label.textContent = "You Speak (English → Marathi Voice)";
          };
          rec.start();
          return;
        } catch (e) {
          console.warn("SpeechRec error, falling back to direct input:", e);
        }
      }
      handleTouristSpeak();
    });
  }

  // Waiter Listen Orb (Web Speech recognition in Marathi or server translation)
  const micBtn = document.getElementById("waiter-mic-btn");
  if (micBtn) {
    micBtn.addEventListener("click", () => {
      const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (SpeechRec) {
        try {
          const rec = new SpeechRec();
          rec.lang = "mr-IN";
          rec.continuous = false;
          rec.interimResults = false;
          const label = document.getElementById("mic-label");
          if (label) label.textContent = "Listening to Waiter in Marathi… 🎙️";
          rec.onresult = (e) => {
            const transcript = e.results[0][0].transcript;
            handleWaiterListen(transcript);
          };
          rec.onerror = () => handleWaiterListen();
          rec.onend = () => {
            if (label) label.textContent = "Listen to Waiter (Marathi → English)";
          };
          rec.start();
          return;
        } catch (e) {
          console.warn("Marathi SpeechRec error, falling back:", e);
        }
      }
      handleWaiterListen();
    });
  }

  const health = await fetch("/health").then((r) => r.json());
  const pill = document.getElementById("mode-pill");
  if (health.mock_sarvam) {
    pill.textContent = "Offline Mock Mode";
    pill.classList.remove("live");
  } else {
    pill.textContent = "● Live Sarvam AI";
    pill.classList.add("live");
  }
  updateSummaryChip();
  await loadDishes();
  updateOrderUI();
});
