(function () {
  const pageEl = document.querySelector(".page-session");
  const sid = pageEl.dataset.sessionId;
  const params = new URLSearchParams(window.location.search);
  const role = params.get("role") === "A" ? "A" : "B";

  const screens = {};
  document.querySelectorAll(".screen").forEach((s) => (screens[s.id] = s));
  const roundPill = document.getElementById("round-pill");
  const globalError = document.getElementById("global-error");

  let pollTimer = null;
  let deck = null;

  function showScreen(id) {
    Object.values(screens).forEach((s) => s.classList.add("hidden"));
    screens[id].classList.remove("hidden");
  }

  function showFatalError(msg) {
    clearInterval(pollTimer);
    globalError.textContent = msg;
    globalError.classList.remove("hidden");
    showScreen("screen-loading");
    screens["screen-loading"].querySelector(".spinner").classList.add("hidden");
  }

  function setRoundPill(round) {
    if (!round) {
      roundPill.classList.add("hidden");
      return;
    }
    roundPill.textContent = round === 1 ? "Round 1" : "Round 2";
    roundPill.classList.remove("hidden");
  }

  async function fetchState() {
    return api.getJSON(`/api/session/${sid}/state?role=${role}`);
  }

  function pollUntil(predicate, onChange, intervalMs = 1800) {
    clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
      try {
        const state = await fetchState();
        if (predicate(state)) {
          clearInterval(pollTimer);
          onChange(state);
        }
      } catch (e) {
        // transient network hiccup — keep polling silently
      }
    }, intervalMs);
  }

  async function init() {
    showScreen("screen-loading");
    let state;
    try {
      state = await fetchState();
    } catch (e) {
      return showFatalError("This session doesn't exist or has expired.");
    }
    route(state);
  }

  function mySubmitted(state) {
    return role === "A" ? state.a_submitted : state.b_submitted;
  }

  function route(state) {
    if (!mySubmitted(state)) return showPreferenceForm();

    setRoundPill(state.status === "swiping" ? state.round : null);

    if (state.status === "awaiting_a" || state.status === "awaiting_b") {
      if (role === "A") showShareScreen(state);
      else {
        showScreen("screen-generating");
        document.getElementById("generating-text").textContent = "Waiting for your partner…";
      }
      pollUntil((s) => s.status !== state.status, route);
      return;
    }
    if (state.status === "generating") {
      showScreen("screen-generating");
      document.getElementById("generating-text").textContent = "Finding titles you'll both like…";
      pollUntil((s) => s.status !== "generating", route);
      return;
    }
    if (state.status === "swiping") return enterSwipeScreen(state);
    if (state.status === "matched") return showMatchScreen();
    if (state.status === "final_choice") return showTop5Screen();
    if (state.status === "finalized") return showScreen("screen-done");
    showFatalError("Unexpected session state.");
  }

  function showPreferenceForm() {
    showScreen("screen-form");
    document.getElementById("form-heading").textContent =
      role === "A" ? "What are you in the mood for?" : "Your turn — what are you in the mood for?";
    renderPreferenceForm(document.getElementById("form-mount"), {
      onSubmit: async (profile) => {
        const state = await api.postJSON(`/api/session/${sid}/preferences`, { role, ...profile });
        route(state);
      },
    });
  }

  function showShareScreen(state) {
    showScreen("screen-share");
    const joinUrl = `${window.location.origin}/session/${sid}?role=B`;
    document.getElementById("share-link-input").value = joinUrl;
    document.getElementById("qr-image").src = `/api/session/${sid}/qr.png?url=${encodeURIComponent(joinUrl)}`;
    document.getElementById("couple-code-text").textContent = state.couple_code || "——";

    const copyBtn = document.getElementById("copy-link-btn");
    copyBtn.onclick = async () => {
      try {
        await navigator.clipboard.writeText(joinUrl);
        copyBtn.textContent = "Copied!";
        setTimeout(() => (copyBtn.textContent = "Copy"), 1500);
      } catch (e) {
        document.getElementById("share-link-input").select();
      }
    };

    const shareBtn = document.getElementById("share-image-btn");
    shareBtn.onclick = async () => {
      try {
        const resp = await fetch(document.getElementById("qr-image").src);
        const blob = await resp.blob();
        const file = new File([blob], "tonight-invite.png", { type: "image/png" });
        if (navigator.canShare && navigator.canShare({ files: [file] })) {
          await navigator.share({
            files: [file],
            title: "Pick tonight's watch with me",
            text: `Join my session: ${joinUrl}`,
          });
        } else if (navigator.share) {
          await navigator.share({ title: "Pick tonight's watch with me", text: joinUrl, url: joinUrl });
        } else {
          const a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = "tonight-invite.png";
          a.click();
        }
      } catch (e) {
        // user cancelled share sheet — nothing to do
      }
    };
  }

  async function enterSwipeScreen(state) {
    showScreen("screen-swipe");
    setRoundPill(state.round);
    document.getElementById("swipe-round-caption").textContent =
      state.round === 1 ? "Swipe right to like, left to pass" : "Round 2 — leaning into what you both liked";

    let poolData;
    try {
      poolData = await api.getJSON(`/api/session/${sid}/pool?role=${role}`);
    } catch (e) {
      return showFatalError(e.message);
    }

    if (poolData.total_in_round === 0) {
      return showFatalError(
        "We couldn't find enough titles matching everything you both picked. Try loosening a filter (language, era or minimum rating) and start a new session."
      );
    }

    if (poolData.remaining_count === 0) {
      return waitForOtherPartner(state, poolData.total_in_round);
    }

    const deckEl = document.getElementById("deck");
    const remainingEl = document.getElementById("deck-remaining");
    remainingEl.textContent = poolData.remaining_count;

    deck = new SwipeDeck(deckEl, {
      onSwipe: async (card, direction) => {
        remainingEl.textContent = Math.max(deck.remaining(), 0);
        try {
          const newState = await api.postJSON(`/api/session/${sid}/swipe`, {
            role,
            tmdb_id: card.tmdb_id,
            direction,
          });
          if (newState.status !== "swiping" || newState.round !== state.round) {
            route(newState);
          }
        } catch (e) {
          // keep swiping locally even if a single write hiccups
        }
      },
      onExhausted: () => {
        waitForOtherPartner(state, poolData.total_in_round);
      },
    });
    deck.setCards(poolData.titles);

    document.getElementById("pass-btn").onclick = () => deck.swipeTop("pass");
    document.getElementById("like-btn").onclick = () => deck.swipeTop("like");
  }

  function waitForOtherPartner(state, totalInRound) {
    showScreen("screen-waiting-swipes");
    document.getElementById("waiting-total-count").textContent = totalInRound ?? "";
    pollUntil(
      (s) => s.status !== "swiping" || s.round !== state.round,
      route
    );
  }

  async function showMatchScreen() {
    showScreen("screen-match");
    setRoundPill(null);
    let data;
    try {
      data = await api.getJSON(`/api/session/${sid}/match`);
    } catch (e) {
      return showFatalError(e.message);
    }
    const t = data.title;
    const matchCard = document.getElementById("match-card");
    const runtime = formatRuntime(t.runtime);
    matchCard.innerHTML = `
      <img src="${t.poster_url || ""}" alt="${t.title}">
      <div class="match-info">
        <h3>${t.title} ${t.year ? `(${t.year})` : ""}</h3>
        <p class="muted small">★ ${t.imdb_rating ?? "—"} ${runtime ? "· " + runtime : ""}</p>
        <p class="small">${t.synopsis || ""}</p>
      </div>`;
    const platformRow = document.getElementById("match-platforms");
    platformRow.innerHTML = (t.ott_platforms || [])
      .map((p) => (p.url || "").startsWith("http")
        ? `<a class="platform-chip" href="${p.url}" target="_blank" rel="noopener noreferrer">${p.name}</a>`
        : `<span class="platform-chip">${p.name}</span>`)
      .join("") || `<span class="muted small">Availability info not found — check your usual apps.</span>`;

    document.getElementById("rate-btn").onclick = () => showRateScreen(t.tmdb_id);
  }

  async function showTop5Screen() {
    showScreen("screen-top5");
    setRoundPill(null);
    let data;
    try {
      data = await api.getJSON(`/api/session/${sid}/top5`);
    } catch (e) {
      return showFatalError(e.message);
    }
    const grid = document.getElementById("top5-grid");
    grid.innerHTML = "";
    data.titles.forEach((t) => {
      const item = document.createElement("div");
      item.className = "top5-item";
      item.innerHTML = `
        <img src="${t.poster_url || ""}" alt="${t.title}">
        <div class="top5-info">
          <h4>${t.title}</h4>
          <span>${t.year || ""} · ★ ${t.imdb_rating ?? "—"}</span>
        </div>`;
      item.onclick = async () => {
        grid.querySelectorAll(".top5-item").forEach((i) => i.classList.remove("chosen"));
        item.classList.add("chosen");
        await api.postJSON(`/api/session/${sid}/finalize`, { tmdb_id: t.tmdb_id });
        showMatchScreen();
      };
      grid.appendChild(item);
    });
  }

  function showRateScreen(tmdbId) {
    showScreen("screen-rate");
    let rating = 0;
    const stars = document.querySelectorAll("#rate-stars button");
    stars.forEach((btn) => {
      btn.classList.remove("active");
      btn.onclick = () => {
        rating = Number(btn.dataset.star);
        stars.forEach((b) => b.classList.toggle("active", Number(b.dataset.star) <= rating));
      };
    });
    document.getElementById("rate-submit-btn").onclick = async () => {
      if (!rating) return;
      const note = document.getElementById("rate-note").value.trim();
      await api.postJSON(`/api/session/${sid}/rate`, { tmdb_id: tmdbId, rating, note });
      showScreen("screen-done");
    };
  }

  init();
})();
