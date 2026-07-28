/* Bulk lookup page: input helpers (always) + interactive results (when present).
 * External file so it works under CSP (script-src 'self'). Data arrives as JSON
 * in #bulk-data; all values are written with textContent (no HTML injection).
 */
(function () {
  "use strict";

  /* ---- Input helpers (present on the empty page too) ---------------------- */
  var numbers = document.getElementById("numbers");
  var pasteCount = document.getElementById("paste-count");
  function countNumbers() {
    if (!numbers || !pasteCount) return;
    var parts = numbers.value.split(/[\s,;]+/).filter(function (x) { return x.trim(); });
    pasteCount.textContent = parts.length
      ? parts.length + " number" + (parts.length === 1 ? "" : "s") + " queued"
      : "";
  }
  if (numbers) { numbers.addEventListener("input", countNumbers); countNumbers(); }

  var fileInput = document.getElementById("listfile");
  var dz = document.getElementById("dropzone");
  var dzSub = document.getElementById("dz-sub");
  if (fileInput && dzSub) {
    fileInput.addEventListener("change", function () {
      if (fileInput.files && fileInput.files.length) dzSub.textContent = fileInput.files[0].name;
    });
  }
  if (dz && fileInput) {
    ["dragenter", "dragover"].forEach(function (ev) {
      dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.add("drag"); });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.remove("drag"); });
    });
    dz.addEventListener("drop", function (e) {
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
        fileInput.files = e.dataTransfer.files;
        if (dzSub) dzSub.textContent = e.dataTransfer.files[0].name;
      }
    });
  }

  /* ---- Results (only when data is present) -------------------------------- */
  var dataEl = document.getElementById("bulk-data");
  if (!dataEl) return;
  var rows = [];
  try { rows = JSON.parse(dataEl.textContent) || []; } catch (e) { rows = []; }

  var tbody = document.getElementById("bulk-tbody");
  var filterInput = document.getElementById("bulk-filter");
  var tabs = document.getElementById("bulk-tabs");
  var emptyMsg = document.getElementById("bulk-empty-filter");
  var detail = document.getElementById("bulk-detail");
  if (!tbody || !detail) return;

  var statusFilter = "all";
  var query = "";
  var selectedNorm = null;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function matches(r) {
    if (statusFilter === "found" && !r.found) return false;
    if (statusFilter === "notfound" && r.found) return false;
    if (query) {
      var hay = (r.input + " " + r.nia + " " + r.name + " " + r.ssnit + " " + r.employer).toLowerCase();
      if (hay.indexOf(query) === -1) return false;
    }
    return true;
  }

  function renderTable() {
    tbody.textContent = "";
    var shown = 0;
    rows.forEach(function (r) {
      if (!matches(r)) return;
      shown++;
      var tr = el("tr", "bulk-row" + (r.found ? "" : " bulk-row-miss") +
        (r.norm === selectedNorm ? " selected" : ""));
      tr.appendChild(el("td", "c-nia mono", r.nia));
      var m = el("td", "c-member");
      m.appendChild(el("span", r.found ? "m-name" : "m-miss", r.found ? r.name : "Not found"));
      tr.appendChild(m);
      tr.appendChild(el("td", "c-ssnit mono", r.found ? (r.ssnit || "—") : "—"));
      tr.appendChild(el("td", "c-emp", r.found ? (r.employer || "—") : "—"));
      tr.addEventListener("click", function () { select(r.norm); });
      tbody.appendChild(tr);
    });
    if (emptyMsg) emptyMsg.hidden = shown !== 0;
  }

  function findRow(norm) {
    for (var i = 0; i < rows.length; i++) if (rows[i].norm === norm) return rows[i];
    return null;
  }

  function section(title, pairs) {
    if (!pairs.some(function (p) { return p[1]; })) return null;
    var frag = document.createDocumentFragment();
    frag.appendChild(el("h2", "detail-sec", title));
    var dl = el("dl", "detail-dl");
    pairs.forEach(function (p) {
      if (!p[1]) return;
      dl.appendChild(el("dt", null, p[0]));
      dl.appendChild(el("dd", p[2] ? "mono" : null, p[1]));
    });
    frag.appendChild(dl);
    return frag;
  }

  function renderDetail(r) {
    detail.textContent = "";
    if (!r) {
      detail.appendChild(el("div", "detail-empty", "Select a row to preview the record."));
      return;
    }
    var head = el("div", "detail-head");
    head.appendChild(el("div", "detail-avatar", r.found ? (r.initials || "—") : "?"));
    var idw = el("div", "detail-idw");
    idw.appendChild(el("div", "detail-name", r.found ? r.name : r.input));
    idw.appendChild(el("div", r.found ? "detail-nia mono" : "detail-nia-miss",
      r.found ? r.nia : "Not found"));
    head.appendChild(idw);
    detail.appendChild(head);

    if (!r.found) return;

    var id = section("Identity", [
      ["SSNIT no.", r.ssnit, true], ["Date of birth", r.dob, false],
      ["Gender", r.gender, false], ["Telephone", r.phone, true],
    ]);
    if (id) detail.appendChild(id);
    var emp = section("Employment", [
      ["Employer", r.employer, false], ["EER no.", r.eerno, true], ["Sector", r.sector, false],
    ]);
    if (emp) detail.appendChild(emp);

    var link = el("a", "detail-link", "Open full record →");
    link.href = "/search?nia=" + encodeURIComponent(r.norm);
    detail.appendChild(link);
  }

  function select(norm) {
    selectedNorm = norm;
    renderTable();
    renderDetail(findRow(norm));
  }

  if (filterInput) {
    filterInput.addEventListener("input", function () {
      query = filterInput.value.trim().toLowerCase();
      renderTable();
    });
  }
  if (tabs) {
    tabs.addEventListener("click", function (e) {
      var b = e.target.closest ? e.target.closest(".seg-btn") : null;
      if (!b) return;
      statusFilter = b.getAttribute("data-status");
      var all = tabs.querySelectorAll(".seg-btn");
      for (var i = 0; i < all.length; i++) all[i].classList.toggle("active", all[i] === b);
      renderTable();
    });
  }

  // Auto-select the first found row (or the first row).
  var first = null;
  for (var i = 0; i < rows.length; i++) { if (rows[i].found) { first = rows[i]; break; } }
  if (!first && rows.length) first = rows[0];
  selectedNorm = first ? first.norm : null;
  renderTable();
  renderDetail(first);
})();
