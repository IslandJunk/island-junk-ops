/* Island Junk — Day Board bridge.
 * Injected after the approved day-board prototype (file untouched). Replaces the
 * prototype's mock `STOPS` with live routes read from the calendar via GET /day-board,
 * then re-renders. Reuses the prototype's own render (renderBoard) + colour→truck
 * lanes, so the approved board shows real data unchanged.
 *
 * Auth: GET /day-board is session-gated; the manager's PIN-login cookie carries
 * (same-origin). Call window.__ijDayRefresh() after logging in.
 */
(function () {
  function ymd(d) { return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
  function dateForDay(offset) { var t = new Date(); t.setHours(0, 0, 0, 0); t.setDate(t.getDate() + (offset || 0)); return t; }

  function timeStr(j) {
    if (j.untimed) return "";
    return j.time_end ? (j.time_start + "–" + j.time_end) : j.time_start;
  }
  function typeFor(j) {
    if (j.booking_lane === "pallet") return "pallet";
    if (j.booking_lane === "bins") return "drop";
    if (j.account_type === "commercial" || j.account_type === "property_mgmt") return "commercial";
    return "residential";
  }
  function stopsFromBoard(board, dayOffset) {
    var out = [];
    var trucks = (board && board.trucks) || {};
    Object.keys(trucks).forEach(function (key) {
      var num = key.replace(/^Truck\s+/, "");
      trucks[key].forEach(function (j) {
        out.push({
          id: j.event_id, truck: num, day: dayOffset, time: timeStr(j),
          cust: j.customer || j.headline || "Job",
          addr: j.address || "",
          type: typeFor(j),
          bin: j.booking_lane === "bins" || undefined,
          status: "scheduled",
          office: j.scope || "",
        });
      });
    });
    return out;
  }

  var cache = {};   // dayOffset -> stops
  function rebuild() {
    var all = [];
    Object.keys(cache).forEach(function (o) { all = all.concat(cache[o]); });
    window.STOPS = all;
  }
  function render() {
    try {
      if (typeof ST !== "undefined") { ST.view = "manager"; ST.truck = "all"; }
      if (typeof renderTrucks === "function") renderTrucks();
      if (typeof applyChrome === "function") applyChrome();
      if (typeof renderBoard === "function") renderBoard();
    } catch (e) {}
  }
  function loadDay(offset) {
    return fetch("/day-board?on=" + ymd(dateForDay(offset)), { credentials: "same-origin" })
      .then(function (r) { if (r.status === 401 || r.status === 403) throw new Error("auth"); return r.json(); })
      .then(function (board) { cache[offset] = stopsFromBoard(board, offset); window.__ijDayBoard = board; })
      .catch(function () { cache[offset] = cache[offset] || []; });
  }

  function refresh() {
    var offset = (typeof ST !== "undefined" && ST.day) || 0;
    return loadDay(offset).then(function () { rebuild(); render(); });
  }
  window.__ijDayRefresh = refresh;

  function start() {
    // Re-fetch a day whenever the manager switches the day tab.
    if (typeof setDay === "function") {
      var _sd = setDay;
      window.setDay = function (i) { _sd(i); loadDay(i).then(function () { rebuild(); render(); }); };
    }
    refresh();  // no-op board if not logged in yet; call __ijDayRefresh() after login
  }
  if (document.readyState !== "loading") start();
  else document.addEventListener("DOMContentLoaded", start);
})();
