(function () {
  const bar = document.getElementById("mcCaduBar");
  if (!bar) return;

  const menus = Array.from(bar.querySelectorAll("details.mc-cadu-menu"));

  function closeAll(except) {
    menus.forEach((item) => {
      if (item !== except) item.removeAttribute("open");
    });
  }

  menus.forEach((item) => {
    item.addEventListener("toggle", () => {
      if (item.open) closeAll(item);
    });
  });

  document.addEventListener("pointerdown", (event) => {
    if (!bar.contains(event.target)) closeAll();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeAll();
  });
})();
