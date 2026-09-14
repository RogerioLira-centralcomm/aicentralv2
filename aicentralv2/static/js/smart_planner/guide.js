(function () {
  var dialog = document.getElementById("sp-guide");
  if (!dialog) return;
  document.querySelectorAll("[data-sp-guide]").forEach(function (button) {
    button.addEventListener("click", function () {
      if (typeof dialog.showModal === "function") {
        dialog.showModal();
        var title = document.getElementById("sp-guide-title");
        if (title) title.focus();
      }
    });
  });
  dialog.addEventListener("click", function (event) {
    var box = dialog.getBoundingClientRect();
    var outside =
      event.clientX < box.left ||
      event.clientX > box.right ||
      event.clientY < box.top ||
      event.clientY > box.bottom;
    if (outside) dialog.close();
  });
})();
