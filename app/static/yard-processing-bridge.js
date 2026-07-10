/* Island Junk — Yard Processing bridge.
 * The rich close-out record (stream %, waste class, extras, axle weights) lives in the
 * prototype's in-memory `bins`, never in localStorage — so the generic sync can't see
 * it. On the "Save → processed" (#wDone) click, after the prototype marks the bin
 * processed, this POSTs today's processed records to /yard-processing. Idempotent
 * (upsert by code + processed_date). Prototype file untouched.
 */
(function () {
  function processedToday() {
    try {
      if (typeof bins === "undefined") return [];
      var today = (typeof todayIso === "function") ? todayIso() : new Date().toISOString().slice(0, 10);
      return bins.filter(function (b) { return b && b.processed && b.processedDate === today; });
    } catch (e) { return []; }
  }

  function save() {
    var recs = processedToday();
    if (!recs.length) return;
    fetch("/yard-processing", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ records: recs }),
    }).catch(function () {});
  }

  // Delegated: the prototype's #wDone handler runs in the target phase (before this
  // bubble-phase listener), so the bin is already flagged processed when we save.
  document.addEventListener("click", function (e) {
    if (e.target && e.target.closest && e.target.closest("#wDone")) {
      setTimeout(save, 50);
    }
  }, false);
})();
