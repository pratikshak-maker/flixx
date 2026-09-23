const OTT_ICON = "▶";

function formatRuntime(min) {
  if (!min) return null;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h ? `${h}h ${m}m` : `${m}m`;
}

function cardInnerHTML(card) {
  const runtime = formatRuntime(card.runtime);
  const meta = [card.year, runtime, card.media_type === "tv" ? "Series" : "Movie"].filter(Boolean);
  return `
    <div class="stamp stamp-like">LIKE</div>
    <div class="stamp stamp-pass">PASS</div>
    <img class="poster" src="${card.poster_url || ""}" alt="${card.title}" draggable="false"
         onerror="this.style.opacity=0.15">
    <div class="info">
      <div class="title-row">
        <h3>${card.title}</h3>
        <span class="rating-badge">★ ${card.imdb_rating ?? "—"}</span>
      </div>
      <div class="meta-row"><span>${meta.join(" · ")}</span></div>
      <p class="synopsis">${card.synopsis || ""}</p>
    </div>
  `;
}

class SwipeDeck {
  constructor(container, { onSwipe, onExhausted, stackDepth = 3 } = {}) {
    this.container = container;
    this.onSwipe = onSwipe || (() => {});
    this.onExhausted = onExhausted || (() => {});
    this.stackDepth = stackDepth;
    this.cards = [];
    this.index = 0;
  }

  setCards(cards) {
    this.cards = cards;
    this.index = 0;
    this._renderStack();
  }

  remaining() {
    return Math.max(this.cards.length - this.index, 0);
  }

  _renderStack() {
    this.container.innerHTML = "";
    this.topEl = null;
    const slice = this.cards.slice(this.index, this.index + this.stackDepth);
    if (!slice.length) {
      this.onExhausted();
      return;
    }
    // Render back-to-front so DOM order matches visual stacking; slice[0] —
    // the next card to act on — ends up on top, at depth 0, and draggable.
    for (let i = slice.length - 1; i >= 0; i -= 1) {
      const card = slice[i];
      const depth = i;
      const elCard = document.createElement("div");
      elCard.className = "swipe-card";
      elCard.innerHTML = cardInnerHTML(card);
      elCard.style.transform = `translateY(${depth * 10}px) scale(${1 - depth * 0.035})`;
      elCard.style.zIndex = String(100 - depth);
      this.container.appendChild(elCard);
      if (depth === 0) {
        this.topEl = elCard;
        this.topCard = card;
        this._makeDraggable(elCard, card);
      }
    }
  }

  _makeDraggable(cardEl, cardData) {
    let dragging = false;
    let startX = 0, startY = 0, dx = 0, dy = 0;
    const likeStamp = cardEl.querySelector(".stamp-like");
    const passStamp = cardEl.querySelector(".stamp-pass");

    const onDown = (e) => {
      dragging = true;
      cardEl.style.transition = "none";
      const p = e.touches ? e.touches[0] : e;
      startX = p.clientX;
      startY = p.clientY;
      cardEl.setPointerCapture && e.pointerId !== undefined && cardEl.setPointerCapture(e.pointerId);
    };
    const onMove = (e) => {
      if (!dragging) return;
      const p = e.touches ? e.touches[0] : e;
      dx = p.clientX - startX;
      dy = p.clientY - startY;
      const rotate = dx / 18;
      cardEl.style.transform = `translate(${dx}px, ${dy}px) rotate(${rotate}deg)`;
      const strength = Math.min(Math.abs(dx) / 100, 1);
      likeStamp.style.opacity = dx > 0 ? strength : 0;
      passStamp.style.opacity = dx < 0 ? strength : 0;
    };
    const onUp = () => {
      if (!dragging) return;
      dragging = false;
      const threshold = 100;
      if (Math.abs(dx) > threshold) {
        this._flyOut(cardEl, dx > 0 ? "like" : "pass", cardData);
      } else {
        cardEl.style.transition = "transform 0.3s ease";
        cardEl.style.transform = "translate(0,0) rotate(0)";
        likeStamp.style.opacity = 0;
        passStamp.style.opacity = 0;
      }
      dx = 0;
      dy = 0;
    };

    cardEl.addEventListener("pointerdown", onDown);
    cardEl.addEventListener("pointermove", onMove);
    cardEl.addEventListener("pointerup", onUp);
    cardEl.addEventListener("pointercancel", onUp);
    cardEl.addEventListener("pointerleave", (e) => {
      if (dragging && e.buttons === 0) onUp();
    });
  }

  _flyOut(cardEl, direction, cardData) {
    const distance = window.innerWidth;
    const x = direction === "like" ? distance : -distance;
    cardEl.style.transition = "transform 0.4s ease";
    cardEl.style.transform = `translate(${x}px, -40px) rotate(${direction === "like" ? 30 : -30}deg)`;
    setTimeout(() => {
      this.index += 1;
      this.onSwipe(cardData, direction);
      this._renderStack();
    }, 220);
  }

  swipeTop(direction) {
    if (!this.topEl) return;
    this._flyOut(this.topEl, direction, this.topCard);
  }
}
