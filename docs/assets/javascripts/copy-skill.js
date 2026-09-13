/*
 * Adds a "copy the whole skill" button on the coding-agent page.
 *
 * The button carries a `data-copy-skill` attribute pointing at the raw
 * SKILL.md served from the docs site. Material's instant navigation swaps
 * page content without a full reload, so we subscribe to `document$` and
 * guard against binding the same button twice.
 */
(function () {
  "use strict";

  function bind() {
    var buttons = document.querySelectorAll("[data-copy-skill]");
    buttons.forEach(function (button) {
      if (button.dataset.copyBound === "true") {
        return;
      }
      button.dataset.copyBound = "true";
      button.addEventListener("click", function (event) {
        event.preventDefault();
        var source = button.getAttribute("data-copy-skill");
        var original = button.getAttribute("data-label") || button.textContent;
        button.setAttribute("data-label", original);

        fetch(source, { cache: "no-cache" })
          .then(function (response) {
            if (!response.ok) {
              throw new Error("HTTP " + response.status);
            }
            return response.text();
          })
          .then(function (text) {
            return navigator.clipboard.writeText(text);
          })
          .then(function () {
            button.textContent = "Copied to clipboard";
            window.setTimeout(function () {
              button.textContent = original;
            }, 2000);
          })
          .catch(function () {
            // Clipboard or fetch unavailable: fall back to opening the raw file.
            window.open(source, "_blank", "noopener");
          });
      });
    });
  }

  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(bind);
  } else {
    document.addEventListener("DOMContentLoaded", bind);
  }
})();
