/* Island Junk — bin-tracker bridge.
 *
 * The bin-tracker prototype builds its fleet in memory (`let bins = seed()`) and never
 * reads or writes `ij_bins_v1`, so every driver action (drop / pick / return / weigh /
 * mark-fixed) vanished on reload. This bridge:
 *   1. replaces that seed with the REAL fleet injected as `ij_bins_full_v1` (the rich
 *      tracker shape from build_bins_full_v1), by reassigning the shared `bins` binding
 *      and repainting; and
 *   2. persists every subsequent mutation by wrapping `render()` (the choke point every
 *      board action funnels through) to write `bins` back to `ij_bins_v1` — which the
 *      sync bridge then POSTs to /sync -> apply_bins.
 *
 * Both prototype scripts are classic (sloppy-mode), so `bins` / `render` / `mk` / `bdBoot`
 * are shared globals this appended script can reference and reassign. Loads AFTER the
 * sync bridge, so our setItem writes are intercepted + synced.
 */
(function () {
  function get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } }

  var full = get("ij_bins_full_v1");
  if (!Array.isArray(full) || !full.length) return;   // no real fleet -> keep the prototype's seed()
  if (typeof bins === "undefined") return;             // prototype not loaded as expected

  // Rich DB record -> a tracker bin object. Start from the prototype's own defaults (mk)
  // so any field the tool touches but the DB omits keeps a sane default, then overlay the
  // real values.
  function toBin(rec) {
    var parts = String(rec.code || "0-00").split("-");
    var size = rec.size || parseInt(parts[0], 10) || 0;
    var n = parseInt(parts[1], 10) || 0;
    var base = (typeof mk === "function") ? mk(size, n, rec.lidded) : {};
    var o = Object.assign(base, rec);
    o.photos = Array.isArray(o.photos) ? o.photos : [];
    o.contactLog = Array.isArray(o.contactLog) ? o.contactLog : [];
    return o;
  }

  try {
    bins = full.map(toBin);   // reassign the shared `let bins` — every closure sees the real fleet
  } catch (e) { return; }

  // Persist on change only. Snapshot the injected fleet first so the initial repaint (which
  // shows exactly what's already in the DB) never echoes; only real mutations differ.
  var lastSnap = "";
  try { lastSnap = JSON.stringify(bins); } catch (e) {}
  function persist() {
    var s;
    try { s = JSON.stringify(bins); } catch (e) { return; }
    if (s === lastSnap) return;      // nothing actually changed
    lastSnap = s;
    try { localStorage.setItem("ij_bins_v1", s); } catch (e) {}   // -> sync bridge -> apply_bins
  }

  if (typeof render === "function") {
    var _render = render;
    render = function () {
      var r = _render.apply(this, arguments);
      persist();
      return r;
    };
  }

  // Repaint with the real fleet (the prototype already painted once from seed()).
  try {
    if (typeof bdBoot === "function") bdBoot();
    else if (typeof render === "function") render();
  } catch (e) {}
})();
