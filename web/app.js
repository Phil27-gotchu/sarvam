const state = {
  profile: {
    origin: "Australia",
    diet: "nonveg",
    max_spice: 3,
    avoid_allergens: [],
    ui_lang: "en-IN",
  },
  dishes: [],
  selectedDishId: "kombdi-vade",
  order: {},
  lastDraftOrder: null,
};

function showBanner(msg) {
  const el = document.getElementById("banner");
  if (!msg) {
    el.classList.add("hidden");
    return;
  }
  el.textContent = msg;
  el.classList.remove("hidden");
}

function switchScreen(screenId) {
  document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
  document.querySelectorAll(".tab").forEach((t) => {
    t.classList.toggle("active", t.dataset.screen === screenId);
  });
  const target = document.getElementById(`screen-${screenId}`);
  if (target) target.classList.add("active");
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
}

function playBase64Audio(b64, warning) {
  if (warning) showBanner(warning);
  if (!b64) return;
  const player = document.getElementById("audio-player");
  player.src = `data:audio/wav;base64,${b64}`;
  player.play().catch(() => {});
}

async function pronounceDish(dishId, text) {
  const res = await fetch("/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dish_id: dishId, text: text || null, lang: "mr-IN" }),
  });
  const data = await res.json();
  playBase64Audio(data.audio_base64, data.warning);
}

function spiceDots(n) {
  return "🌶️".repeat(n) + "·".repeat(Math.max(0, 5 - n));
}

function renderDishList(filterText = "") {
  const container = document.getElementById("dish-list");
  const q = filterText.trim().toLowerCase();
  const filtered = state.dishes.filter(({ dish }) => {
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
      return `
      <div class="dish-item">
        <div>
          <div class="row spread">
            <strong><span class="dot ${vegClass}"></span>${dish.name_roman}</strong>
            <span class="badge ${safety.status}">${safety.status}</span>
          </div>
          <div class="native">${dish.name_mr} <span class="badge unverified">unverified KB</span></div>
          <div class="phonetic">/${dish.phonetic}/</div>
          <p style="font-size:0.85rem;margin:0.35rem 0;">${dish.description}</p>
          <div style="font-size:0.8rem;">Spice: ${spiceDots(dish.spice)}</div>
          <div>${dish.allergens.map((a) => `<span class="allergen-chip">${a}</span>`).join("")}</div>
          ${safety.reasons.length ? `<div style="font-size:0.78rem;color:var(--muted);margin-top:0.25rem;">${safety.reasons.join("; ")}</div>` : ""}
        </div>
        <div class="row">
          <button class="btn" onclick="pronounceDish('${dish.id}')">🔊 Hear</button>
          <button class="btn" onclick="openDishDetail('${dish.id}')">Bridge &amp; Coach</button>
          <button class="btn primary" onclick="addToOrder('${dish.id}')">+ Order</button>
        </div>
      </div>`;
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
  renderDishList(document.getElementById("search-input").value);
}

async function openDishDetail(dishId) {
  state.selectedDishId = dishId;
  switchScreen("detail");
  const box = document.getElementById("detail-content");
  box.innerHTML = "<p>Loading dish card &amp; cultural bridge…</p>";
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
  const card = await cardRes.json();
  const bridge = await bridgeRes.json();
  const d = card.dish;
  const s = card.safety;

  box.innerHTML = `
    <div class="row spread">
      <div>
        <h2><span class="dot ${d.veg ? "veg" : "nonveg"}"></span>${d.name_roman} <span class="native">${d.name_mr}</span></h2>
        <div class="phonetic">Say it: <strong>${d.phonetic}</strong></div>
      </div>
      <span class="badge ${s.status}">${s.status}</span>
    </div>
    <p>${d.description}</p>
    <div class="row">
      <button class="btn primary" onclick="pronounceDish('${d.id}')">🔊 Play Native Pronunciation</button>
      <button class="btn" onclick="addToOrder('${d.id}')">+ Add to My Order</button>
    </div>
    <p><strong>Spice:</strong> ${spiceDots(d.spice)} (${d.spice}/5) · <strong>Richness:</strong> ${d.richness}/5</p>
    <p><strong>Ingredients:</strong> ${d.ingredients.join(", ")}</p>
    <p><strong>Allergens:</strong> ${d.allergens.length ? d.allergens.map((a) => `<span class="allergen-chip">${a}</span>`).join(" ") : "None listed"}</p>
    ${s.reasons.length ? `<div class="reply-box"><strong>Safety Reasons:</strong> ${s.reasons.join(" · ")}</div>` : ""}
    <p><strong>Pairs well with:</strong> ${(card.pairings || []).map((x) => x.name_roman).join(", ") || "Sol Kadhi"}</p>
    <hr />
    <h3>🌉 Cultural Bridge for ${bridge.origin}</h3>
    <p><strong>Closest Home Match:</strong> ${bridge.closest.name} (score ${bridge.closest.score})</p>
    <p>${bridge.explanation}</p>
    ${bridge.translated ? `<p><em>${bridge.translated}</em></p>` : ""}
    <p><strong>Similar in:</strong> ${(bridge.similar_in || []).join(", ")}</p>
    <p><strong>Different in:</strong> ${(bridge.different_in || []).join(", ")}</p>
    <p><strong>Spice Calibration:</strong> ${bridge.spice_calibration}</p>
    <div class="row">
      <span>Helpful analogy?</span>
      <button class="btn" onclick="sendFeedback('${d.id}', '${bridge.origin}', 'up')">👍 Yes</button>
      <button class="btn" onclick="sendFeedback('${d.id}', '${bridge.origin}', 'down')">👎 No</button>
      <span id="fb-msg"></span>
    </div>
    <hr />
    <h3>🎙️ Pronunciation Coach (Saaras Translit + Syllable Scorer)</h3>
    <p>Practice saying <strong>${d.phonetic}</strong> by voice or quick phonetic test:</p>
    <div class="row">
      <input id="coach-text-input" type="text" value="${d.phonetic}" />
      <button class="btn primary" onclick="runCoach('${d.id}')">Score My Pronunciation</button>
    </div>
    <div id="coach-result" class="reply-box hidden"></div>
    <p class="disclaimer">${card.safety_disclaimer}</p>
  `;
}

async function sendFeedback(dishId, origin, vote) {
  const res = await fetch("/bridge/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dish_id: dishId, origin, vote }),
  });
  const data = await res.json();
  const el = document.getElementById("fb-msg");
  if (el) el.textContent = `Saved (${data.total_feedback} total)`;
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
    <strong>Score: ${data.score} / 100</strong><br/>
    <span>Heard: <code>${data.heard}</code> · Target: <code>${data.target}</code></span><br/>
    ${data.mismatched_syllables.length ? `<span>Mismatched syllables: ${data.mismatched_syllables.join(", ")}</span><br/>` : ""}
    <span>Tip: ${data.tip}</span>
  `;
}

function addToOrder(dishId) {
  state.order[dishId] = (state.order[dishId] || 0) + 1;
  updateOrderUI();
}

function updateOrderUI() {
  const count = Object.values(state.order).reduce((a, b) => a + b, 0);
  document.getElementById("order-count").textContent = count;
  const container = document.getElementById("order-items");
  const entries = Object.entries(state.order);
  if (!entries.length) {
    container.innerHTML = "<p>No dishes added yet. Tap '+ Order' on any dish.</p>";
    return;
  }
  container.innerHTML = entries
    .map(([id, qty]) => {
      const found = state.dishes.find((x) => x.dish.id === id);
      const name = found ? `${found.dish.name_roman} (${found.dish.name_mr})` : id;
      return `<div class="row spread" style="padding:0.4rem 0;border-bottom:1px solid var(--border);">
        <span><strong>${qty}×</strong> ${name}</span>
        <button class="btn" onclick="delete state.order['${id}']; updateOrderUI();">Remove</button>
      </div>`;
    })
    .join("");
}

async function draftOrder() {
  const entries = Object.entries(state.order).map(([dish_id, qty]) => ({ dish_id, qty }));
  if (!entries.length) {
    entries.push({ dish_id: "kombdi-vade", qty: 1 }, { dish_id: "sol-kadhi", qty: 1 });
  }
  const res = await fetch("/order/draft", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items: entries, profile: state.profile }),
  });
  const data = await res.json();
  state.lastDraftOrder = data;
  const box = document.getElementById("drafted-order-box");
  box.classList.remove("hidden");
  box.innerHTML = `
    <p class="native" style="font-size:1.1rem;">${data.marathi_text}</p>
    <p class="phonetic">${data.phonetic}</p>
    <p><strong>Meaning:</strong> ${data.english_meaning}</p>
    ${data.safety_warnings.length ? `<p style="color:var(--block-fg);"><strong>Warnings:</strong> ${data.safety_warnings.join(" | ")}</p>` : ""}
    <button class="btn primary" onclick="playBase64Audio('${data.audio_base64}', '${data.tts_warning || ""}')">🔊 Speak Order in Marathi</button>
  `;
  document.getElementById("waiter-mr-text").textContent = data.marathi_text;
}

document.addEventListener("DOMContentLoaded", async () => {
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => switchScreen(btn.dataset.screen));
  });
  const spiceRange = document.getElementById("spice-range");
  spiceRange.addEventListener("input", () => {
    document.getElementById("spice-val").textContent = spiceRange.value;
  });
  document.getElementById("save-profile-btn").addEventListener("click", async () => {
    readProfileFromForm();
    await loadDishes();
    switchScreen("browse");
  });
  document.getElementById("search-input").addEventListener("input", (e) => {
    renderDishList(e.target.value);
  });
  document.getElementById("scan-btn").addEventListener("click", async () => {
    readProfileFromForm();
    const fileInput = document.getElementById("menu-file");
    const fd = new FormData();
    if (fileInput.files[0]) fd.append("image", fileInput.files[0]);
    fd.append("profile_json", JSON.stringify(state.profile));
    const res = await fetch("/menu/scan", { method: "POST", body: fd });
    const data = await res.json();
    const out = document.getElementById("scan-results");
    out.innerHTML = (data.items || [])
      .map((item) => {
        if (item.in_kb) {
          return `<div class="dish-item">
            <div class="row spread">
              <strong>${item.dish.name_roman} (${item.price || ""})</strong>
              <span class="badge ${item.safety.status}">${item.safety.status}</span>
            </div>
            <div class="native">${item.dish.name_mr}</div>
            <p style="font-size:0.84rem;">${item.dish.description}</p>
            <div class="row">
              <button class="btn" onclick="openDishDetail('${item.dish.id}')">Inspect</button>
              <button class="btn primary" onclick="addToOrder('${item.dish.id}')">+ Order</button>
            </div>
          </div>`;
        }
        return `<div class="dish-item">
          <div class="row spread">
            <strong>${item.menu_name} (${item.price || ""})</strong>
            <span class="badge WARN">${item.badge_text}</span>
          </div>
          <p style="font-size:0.84rem;">${item.explanation}</p>
        </div>`;
      })
      .join("");
  });
  document.getElementById("ask-btn").addEventListener("click", async () => {
    const text = document.getElementById("ask-input").value;
    const res = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, profile: state.profile, want_tts: false }),
    });
    const data = await res.json();
    const box = document.getElementById("ask-output");
    box.classList.remove("hidden");
    box.innerHTML = `<p>${data.answer}</p><p class="disclaimer">${data.disclaimer}</p>`;
  });
  document.getElementById("draft-order-btn").addEventListener("click", draftOrder);
  document.getElementById("play-order-tts").addEventListener("click", async () => {
    if (state.lastDraftOrder && state.lastDraftOrder.audio_base64) {
      playBase64Audio(state.lastDraftOrder.audio_base64, state.lastDraftOrder.tts_warning);
    } else {
      await pronounceDish(null, "नमस्कार दादा, आम्हाला एक प्लेट कोंबडी वडे आणि सोलकढी द्या.");
    }
  });
  document.getElementById("waiter-mic-btn").addEventListener("click", async () => {
    const res = await fetch("/order/listen-json", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: state.profile }),
    });
    const data = await res.json();
    document.getElementById("waiter-en-text").textContent = data.waiter_meaning;
    document.getElementById("waiter-alts").innerHTML = `
      <p><strong>Suggested Safe Alternatives:</strong> ${(data.suggested_alternatives || []).join(", ")}</p>
      <p><strong>Suggested Marathi Reply:</strong> <span class="native">${data.followup_marathi}</span> (${data.followup_english})</p>
    `;
  });

  const health = await fetch("/health").then((r) => r.json());
  document.getElementById("mode-pill").textContent = health.mock_sarvam
    ? "MOCK_SARVAM=1 (Offline Ready)"
    : "LIVE SARVAM API";
  await loadDishes();
  updateOrderUI();
});
