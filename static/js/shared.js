const api = {
  async postJSON(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "Something went wrong.");
    return data;
  },
  async getJSON(url) {
    const res = await fetch(url);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "Something went wrong.");
    return data;
  },
};

const MOODS = [
  { value: "light_fun", label: "Light & fun" },
  { value: "intense_gripping", label: "Intense & gripping" },
  { value: "scary", label: "Scary" },
  { value: "romantic", label: "Romantic" },
  { value: "other", label: "Other" },
];
const LANGUAGES = [
  { value: "hindi", label: "Hindi" },
  { value: "english", label: "English" },
  { value: "tamil", label: "Tamil" },
  { value: "telugu", label: "Telugu" },
  { value: "kannada", label: "Kannada" },
  { value: "any", label: "Any" },
];
const CONTENT_TYPES = [
  { value: "movies_only", label: "Movies only" },
  { value: "include_series", label: "Include series" },
];
const MIN_RATINGS = [6, 7, 8, 9];
const ERAS = [
  { value: "any", label: "Any" },
  { value: "classic", label: "Classic (pre-2000)" },
  { value: "2000_2020", label: "2000–2020" },
  { value: "recent", label: "Recent (2021–2026)" },
];

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

function chipRow(name, options, { multi, exclusiveValue } = {}) {
  const row = el(`<div class="chip-row" data-field="${name}"></div>`);
  const selected = new Set();
  options.forEach((opt) => {
    const value = String(typeof opt === "object" ? opt.value : opt);
    const label = typeof opt === "object" ? opt.label : opt;
    const chip = el(`<button type="button" class="chip" data-value="${value}">${label}</button>`);
    chip.addEventListener("click", () => {
      if (multi) {
        if (exclusiveValue && value === exclusiveValue) {
          selected.clear();
          selected.add(value);
        } else {
          if (exclusiveValue) selected.delete(exclusiveValue);
          if (selected.has(value)) selected.delete(value);
          else selected.add(value);
        }
      } else {
        selected.clear();
        selected.add(value);
      }
      row.querySelectorAll(".chip").forEach((c) => {
        c.classList.toggle("selected", selected.has(c.dataset.value));
      });
    });
    row.appendChild(chip);
  });
  row.getValue = () => Array.from(selected);
  return row;
}

function renderPreferenceForm(mount, { onSubmit }) {
  mount.innerHTML = "";

  const moodField = el(`<div class="field-group"><span class="field-label">Mood</span></div>`);
  const moodChips = chipRow("mood", MOODS, { multi: true });
  moodField.appendChild(moodChips);
  mount.appendChild(moodField);

  const moodTextField = el(`
    <div class="field-group">
      <span class="field-label">Describe what you're in the mood for tonight <span class="field-hint" style="display:inline">(optional)</span></span>
      <textarea id="mood-text" maxlength="500" placeholder="e.g. something with a twist ending, nothing too heavy tonight…"></textarea>
    </div>`);
  mount.appendChild(moodTextField);

  const langField = el(`<div class="field-group"><span class="field-label">Language</span></div>`);
  const langChips = chipRow("languages", LANGUAGES, { multi: true, exclusiveValue: "any" });
  langField.appendChild(langChips);
  mount.appendChild(langField);

  const typeField = el(`<div class="field-group"><span class="field-label">Content type</span></div>`);
  const typeChips = chipRow("content_type", CONTENT_TYPES, { multi: false });
  typeField.appendChild(typeChips);
  mount.appendChild(typeField);

  const ratingField = el(`
    <div class="field-group">
      <span class="field-label">Minimum IMDb rating<span id="rating-caveat" class="field-caveat hidden">very few titles</span></span>
    </div>`);
  const ratingChips = chipRow("min_rating", MIN_RATINGS.map((r) => ({ value: r, label: `${r}+` })), { multi: false });
  ratingField.appendChild(ratingChips);
  mount.appendChild(ratingField);
  const caveat = ratingField.querySelector("#rating-caveat");
  ratingChips.addEventListener("click", () => {
    caveat.classList.toggle("hidden", ratingChips.getValue()[0] !== "9");
  });

  const eraField = el(`<div class="field-group"><span class="field-label">Era</span></div>`);
  const eraChips = chipRow("eras", ERAS, { multi: true, exclusiveValue: "any" });
  eraField.appendChild(eraChips);
  mount.appendChild(eraField);

  const errorEl = el(`<p class="error hidden"></p>`);
  mount.appendChild(errorEl);

  const submitBtn = el(`<button type="button" class="btn btn-primary">Continue</button>`);
  mount.appendChild(submitBtn);

  submitBtn.addEventListener("click", () => {
    const profile = {
      mood: moodChips.getValue(),
      mood_text: mount.querySelector("#mood-text").value.trim(),
      languages: langChips.getValue(),
      content_type: typeChips.getValue()[0] || null,
      min_rating: ratingChips.getValue()[0] ? Number(ratingChips.getValue()[0]) : null,
      eras: eraChips.getValue(),
    };
    if (!profile.mood.length) return showError("Pick at least one mood.");
    if (!profile.languages.length) return showError("Pick at least one language.");
    if (!profile.content_type) return showError("Choose a content type.");
    if (!profile.min_rating) return showError("Choose a minimum rating.");
    if (!profile.eras.length) return showError("Pick at least one era.");
    errorEl.classList.add("hidden");
    submitBtn.disabled = true;
    submitBtn.textContent = "Saving…";
    Promise.resolve(onSubmit(profile)).catch((e) => {
      showError(e.message);
      submitBtn.disabled = false;
      submitBtn.textContent = "Continue";
    });
  });

  function showError(msg) {
    errorEl.textContent = msg;
    errorEl.classList.remove("hidden");
  }
}

function sessionIdFromInput(raw) {
  const trimmed = (raw || "").trim();
  if (!trimmed) return null;
  const match = trimmed.match(/session\/([a-zA-Z0-9-]+)/);
  if (match) return match[1];
  if (/^[a-zA-Z0-9-]{6,}$/.test(trimmed)) return trimmed;
  return null;
}
