(() => {
  const items = window.GALLERY || [];

  // ---- work strip arrows (computer)
  const strip = document.querySelector(".strip");
  const prevBtn = document.querySelector(".strip-prev");
  const nextBtn = document.querySelector(".strip-next");
  if (strip && prevBtn && nextBtn) {
    const step = () => Math.max(strip.clientWidth * 0.8, 300);
    const update = () => {
      prevBtn.disabled = strip.scrollLeft <= 2;
      nextBtn.disabled = strip.scrollLeft + strip.clientWidth >= strip.scrollWidth - 2;
    };
    prevBtn.addEventListener("click", () => strip.scrollBy({ left: -step() }));
    nextBtn.addEventListener("click", () => strip.scrollBy({ left: step() }));
    strip.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    update();
  }

  // ---- viewer
  const dialog = document.getElementById("viewer");
  if (!dialog || !items.length) return;
  const stage = dialog.querySelector(".v-stage");
  const count = dialog.querySelector(".v-count");
  const title = dialog.querySelector(".v-title");
  const prev = dialog.querySelector(".v-prev");
  const next = dialog.querySelector(".v-next");
  let current = 0;

  const wrap = (i) => (i + items.length) % items.length;

  function show(i) {
    current = wrap(i);
    const it = items[current];
    let el;
    if (it.video) {
      el = document.createElement("video");
      el.src = it.src;
      el.poster = it.poster;
      el.controls = true;
      el.autoplay = true;
      el.playsInline = true;
    } else {
      el = document.createElement("img");
      el.src = it.src;
      el.alt = it.title;
    }
    stage.replaceChildren(el);
    count.textContent = `${current + 1} / ${items.length}`;
    title.textContent = it.year ? `${it.title} · ${it.year}` : it.title;
    prev.querySelector("img").src = items[wrap(current - 1)].thumb;
    next.querySelector("img").src = items[wrap(current + 1)].thumb;
    // preload neighbours so browsing feels instant
    [wrap(current + 1), wrap(current - 1)].forEach((n) => { if (!items[n].video) new Image().src = items[n].src; });
  }

  function go(delta) {
    next.classList.add("seen");
    const btn = delta > 0 ? next : prev;
    btn.classList.remove("flash");
    void btn.offsetWidth;
    btn.classList.add("flash");
    setTimeout(() => btn.classList.remove("flash"), 180);
    show(current + delta);
  }

  document.querySelectorAll(".card").forEach((card) =>
    card.addEventListener("click", () => {
      show(Number(card.dataset.index));
      dialog.showModal();
      next.focus({ preventScroll: true });
    })
  );
  dialog.querySelector(".v-close").addEventListener("click", () => dialog.close());
  prev.addEventListener("click", () => go(-1));
  next.addEventListener("click", () => go(1));
  dialog.addEventListener("close", () => stage.replaceChildren());
  dialog.addEventListener("click", (e) => { if (e.target === dialog || e.target === stage) dialog.close(); });

  // capture phase so arrow keys browse items instead of seeking the video
  document.addEventListener("keydown", (e) => {
    if (!dialog.open) return;
    if (e.key === "ArrowRight") { e.preventDefault(); e.stopPropagation(); go(1); }
    if (e.key === "ArrowLeft") { e.preventDefault(); e.stopPropagation(); go(-1); }
  }, true);

  let startX = null;
  stage.addEventListener("touchstart", (e) => { startX = e.touches[0].clientX; }, { passive: true });
  stage.addEventListener("touchend", (e) => {
    if (startX === null) return;
    const dx = e.changedTouches[0].clientX - startX;
    if (Math.abs(dx) > 50) go(dx < 0 ? 1 : -1);
    startX = null;
  });
})();
