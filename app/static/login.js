/* Login page: password show/hide toggle + "forgot password" note.
 * External file so it works under the strict CSP (script-src 'self').
 */
(function () {
  "use strict";

  var btn = document.getElementById("toggle-pw");
  var pw = document.getElementById("password");
  if (btn && pw) {
    btn.addEventListener("click", function () {
      var show = pw.type === "password";
      pw.type = show ? "text" : "password";
      btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
      var on = btn.querySelector(".eye-on");
      var off = btn.querySelector(".eye-off");
      if (on && off) { on.hidden = show; off.hidden = !show; }
      pw.focus();
    });
  }

  var link = document.getElementById("forgot-link");
  var note = document.getElementById("forgot-note");
  if (link && note) {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      note.hidden = !note.hidden;
    });
  }
})();
