document.addEventListener("DOMContentLoaded", () => {
  const rows = document.querySelectorAll(".clickable-row[data-href]");
  rows.forEach((row) => {
    row.addEventListener("click", (event) => {
      if (event.target && event.target.closest("a, button, input, select, textarea, label")) {
        return;
      }
      const href = row.getAttribute("data-href");
      if (href) {
        window.location.href = href;
      }
    });
  });
});
