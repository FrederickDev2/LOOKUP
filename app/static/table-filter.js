/* Client-side filter for the bulk results table.
 * Filters the rendered rows across ALL columns as the user types.
 * No external dependencies; loaded with a normal <script src> (CSP: script-src 'self').
 */
(function () {
  "use strict";

  var input = document.getElementById("table-search");
  var table = document.getElementById("results-table");
  if (!input || !table || !table.tBodies.length) {
    return;
  }

  var rows = Array.prototype.slice.call(table.tBodies[0].rows);
  var counter = document.getElementById("filter-count");
  var noResults = document.getElementById("no-results");
  var total = rows.length;

  // Cache lowercased row text so filtering large tables stays fast.
  var haystacks = rows.map(function (row) {
    return (row.textContent || "").toLowerCase();
  });

  function apply() {
    var q = input.value.trim().toLowerCase();
    var shown = 0;
    for (var i = 0; i < rows.length; i++) {
      var match = q === "" || haystacks[i].indexOf(q) !== -1;
      rows[i].style.display = match ? "" : "none";
      if (match) {
        shown++;
      }
    }
    if (counter) {
      counter.textContent = q === "" ? "" : "Showing " + shown + " of " + total + " rows";
    }
    if (noResults) {
      noResults.hidden = shown !== 0;
    }
  }

  input.addEventListener("input", apply);
  // Support pressing Escape to clear the filter.
  input.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      input.value = "";
      apply();
    }
  });
})();
