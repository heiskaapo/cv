(() => {
  const items = window.GALLERY || [];
  const dialog = document.getElementById("viewer");
  if (!dialog || !items.length) return;
  const stage = dialog.querySelector(".stage");
  let current = 0;

  function show(i) {
    current = (i + items.length) % items.length;
    const it = items[current];
    stage.replaceChildren();
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
    }
    el.setAttribute("aria-label", it.label);
    el.alt = it.label;
    stage.append(el);
  }

  document.querySelectorAll(".tile").forEach((tile) =>
    tile.addEventListener("click", () => {
      show(Number(tile.dataset.index));
      dialog.showModal();
    })
  );
  dialog.querySelector(".close").addEventListener("click", () => dialog.close());
  dialog.querySelector(".prev").addEventListener("click", () => show(current - 1));
  dialog.querySelector(".next").addEventListener("click", () => show(current + 1));
  dialog.addEventListener("close", () => stage.replaceChildren());
  dialog.addEventListener("click", (e) => { if (e.target === dialog || e.target === stage) dialog.close(); });
  dialog.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") show(current - 1);
    if (e.key === "ArrowRight") show(current + 1);
  });

  let startX = null;
  stage.addEventListener("touchstart", (e) => { startX = e.touches[0].clientX; }, { passive: true });
  stage.addEventListener("touchend", (e) => {
    if (startX === null) return;
    const dx = e.changedTouches[0].clientX - startX;
    if (Math.abs(dx) > 50) show(current + (dx < 0 ? 1 : -1));
    startX = null;
  });
})();
