/* "Copy details" button on the single-lookup result card.
 * Copies the plain-text block in #copy-src to the clipboard.
 * Uses the async Clipboard API when available (HTTPS / localhost) and falls
 * back to execCommand for plain-HTTP LAN use. External file (CSP: script-src 'self').
 */
(function () {
  "use strict";
  var btn = document.getElementById("copy-details");
  var src = document.getElementById("copy-src");
  if (!btn || !src) {
    return;
  }

  function flash(msg) {
    var original = btn.getAttribute("data-label") || btn.textContent;
    btn.setAttribute("data-label", original);
    btn.textContent = msg;
    setTimeout(function () { btn.textContent = original; }, 1300);
  }

  function fallbackCopy() {
    try {
      src.focus();
      src.select();
      var ok = document.execCommand("copy");
      window.getSelection && window.getSelection().removeAllRanges();
      flash(ok ? "Copied" : "Press Ctrl+C");
    } catch (e) {
      flash("Press Ctrl+C");
    }
  }

  btn.addEventListener("click", function () {
    var text = src.value != null ? src.value : src.textContent;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { flash("Copied"); }, fallbackCopy);
    } else {
      fallbackCopy();
    }
  });
})();
