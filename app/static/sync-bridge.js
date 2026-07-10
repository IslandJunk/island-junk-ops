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
    ij_maint_v2: 1, ij_fixes_v1: 1, ij_fixes_resolved_v1: 1, ij_reminders_v1: 1, ij_rates_v1: 1,
    ij_customers_v1: 1, ij_company_customers_v1: 1, ij_pm_db_v2: 1, ij_contracts_v1: 1,
    ij_binday_v1: 1, ij_tares_v1: 1, ij_weighins_v1: 1, ij_tooldaily_v1: 1,
    ij_dayboard_status_v1: 1, ij_dayboard_notes_v1: 1, ij_dayboard_sitelog_v1: 1,
    ij_attendance_v1: 1, ij_breaks_v1: 1, ij_daynotes_v1: 1, ij_binsout_cfg_v1: 1,
    ij_reviews_v1: 1, ij_usage_v1: 1, ij_precheck_v1: 1,
    ij_fleet_v1: 1, ij_colourmap_v1: 1, ij_checklists_v1: 1, ij_po_needed_v1: 1
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
        // Tag the write with the brand this page was served with (never-mix, §15).
        body: JSON.stringify({ key: key, value: value, brand: window.__IJ_BRAND || null }),
      }).catch(function () {});
    }, 400);
  };
})();
