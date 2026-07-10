/* Island Junk — localStorage -> Postgres sync bridge (injected on every served page).
 * Overrides localStorage.setItem: for the keys we model, it debounces a POST /sync so
 * the prototype's writes persist to the DB. Reads still come from the injected refs.
 *
 * The initial refs injection runs in <head> (before this bridge installs), so it never
 * echoes; and handlers upsert, so any later echo is a harmless no-op. Needs a session
 * (401 if not logged in — silently ignored).
 */
(function () {
  var SYNCED = {
    ij_bins_v1: 1, ij_employees_v1: 1, ij_incidents_v1: 1, ij_clock_log: 1, ij_jobs_v1: 1, ij_weighlog_v1: 1,
    ij_maint_v2: 1, ij_fixes_v1: 1, ij_fixes_resolved_v1: 1, ij_reminders_v1: 1
  };
  var timers = {};
  var orig = localStorage.setItem.bind(localStorage);

  localStorage.setItem = function (key, value) {
    orig(key, value);
    if (!SYNCED[key]) return;
    clearTimeout(timers[key]);
    timers[key] = setTimeout(function () {
      fetch("/sync", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: key, value: value }),
      }).catch(function () {});
    }, 400);
  };
})();
