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

  // ---- YouTube embeds (loaded only when a collage with one is opened)
  let ytReady = null;
  function loadYouTube() {
    if (!ytReady) {
      ytReady = new Promise((resolve) => {
        window.onYouTubeIframeAPIReady = resolve;
        const s = document.createElement("script");
        s.src = "https://www.youtube.com/iframe_api";
        document.head.append(s);
      });
    }
    return ytReady;
  }

  function youtubePanel(p) {
    const box = document.createElement("div");
    box.className = "c-yt";
    const mount = document.createElement("div");
    box.append(mount);
    loadYouTube().then(() => {
      if (!box.isConnected) return;
      new YT.Player(mount, {
        host: "https://www.youtube-nocookie.com",
        videoId: p.id,
        playerVars: { start: p.start, end: p.end, autoplay: 1, mute: 1, controls: 1, rel: 0, playsinline: 1 },
        events: {
          onReady: (e) => { coverYouTube(box); e.target.mute(); e.target.playVideo(); },
          // loop only the chosen segment
          onStateChange: (e) => { if (e.data === YT.PlayerState.ENDED) { e.target.seekTo(p.start, true); e.target.playVideo(); } },
        },
      });
    });
    return box;
  }

  function compositeEl(comp) {
    const wrapEl = document.createElement("div");
    wrapEl.className = "composite";
    wrapEl.dataset.aspect = comp.aspect;
    if (comp.header) {
      const h = document.createElement("img");
      h.className = "c-header";
      h.src = comp.header;
      h.alt = "";
      wrapEl.append(h);
    }
    const body = document.createElement("div");
    body.className = "c-body";
    for (const col of comp.columns) {
      const c = document.createElement("div");
      c.className = "c-col";
      c.style.flex = col.flex;
      for (const p of col.panels) {
        const cell = document.createElement("div");
        cell.className = "c-cell";
        cell.style.flex = p.flex;
        if (p.caption) {
          const cap = document.createElement("div");
          cap.className = "c-cap";
          cap.textContent = p.caption;
          cell.append(cap);
        }
        let media;
        if (p.type === "youtube") media = youtubePanel(p);
        else if (p.type === "video") {
          media = document.createElement("video");
          Object.assign(media, { src: p.src, poster: p.poster || "", autoplay: true, muted: false, loop: true, controls: true, playsInline: true });
        } else {
          media = document.createElement("img");
          media.src = p.src;
          media.alt = "";
        }
        media.classList.add("c-media");
        cell.append(media);
        c.append(cell);
      }
      body.append(c);
    }
    wrapEl.append(body);
    return wrapEl;
  }

  function fitComposite() {
    const el = stage.querySelector(".composite");
    if (!el) return;
    const ar = Number(el.dataset.aspect);
    const w = Math.min(stage.clientWidth, stage.clientHeight * ar);
    el.style.width = `${w}px`;
    el.style.height = `${w / ar}px`;
    el.style.fontSize = `${Math.max(9, w / 55)}px`;
    el.querySelectorAll(".c-yt").forEach(coverYouTube);
  }

  // scale the 16:9 player so it fills its whole cell (edges are cropped instead of letterboxed)
  function coverYouTube(box) {
    const player = box.firstElementChild;
    if (!player) return;
    const w = Math.max(box.clientWidth, box.clientHeight * 16 / 9);
    player.style.width = `${w}px`;
    player.style.height = `${w * 9 / 16}px`;
  }
  window.addEventListener("resize", fitComposite);

  function show(i) {
    current = wrap(i);
    const it = items[current];
    let el;
    if (it.composite) {
      el = compositeEl(it.composite);
    } else if (it.video) {
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
    fitComposite();
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
      fitComposite();
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
