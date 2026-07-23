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
          phone: j.customer_phone || "",   // from the linked booked Job — for the "on our way" text
          addr: j.address || "",
          type: typeFor(j),
          bin: j.booking_lane === "bins" || undefined,
          status: "scheduled",
          office: [j.scope, j.manager_notes].filter(Boolean).join("\n"),   // scope + the manager's calendar NOTES → crew office notes
          job_id: j.job_id || null,        // linked Job — the crew fetch reference photos by this
          photos_link: j.photos_link || "",   // the job's Dropbox folder (manager adds photos via the calendar link)
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
  function _esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function _section(title, count, inner) {
    return '<details' + (count ? ' open' : '') + ' style="background:#1c1917;border:1px solid #2c2824;border-radius:12px;margin-bottom:10px">'
      + '<summary style="cursor:pointer;font-weight:800;font-size:12.5px;letter-spacing:.03em;text-transform:uppercase;color:#F4F1EC;padding:12px 14px">'
      + _esc(title) + ' <span style="color:#9a938a">(' + count + ')</span></summary>'
      + '<div style="padding:0 14px 10px">' + inner + '</div></details>';
  }
  // Manager Day Board extras (Wes): a "not assigned yet" list (uncoloured events, each with a Finish
  // button) + the `#` calendar notes the board otherwise hides. Injected above #board from the board data.
  function renderExtras() {
    var board = window.__ijDayBoard || {};
    var host = document.getElementById("board");
    if (!host) return;
    var wrap = document.getElementById("ijExtras");
    if (!wrap) { wrap = document.createElement("div"); wrap.id = "ijExtras"; wrap.style.cssText = "margin:0 0 14px"; host.parentNode.insertBefore(wrap, host); }
    var un = board.unassigned || [], notes = board.notes || [];
    var unHtml = un.length ? un.map(function (j) {
      var meta = [j.customer || j.headline, j.address].filter(Boolean).map(_esc).join(" · ");
      var fin = j.job_id ? "" : '<a href="/app/new-booking?event=' + encodeURIComponent(j.event_id || "")
        + '" style="display:inline-block;margin-top:7px;background:#F05014;color:#fff;text-decoration:none;font-weight:800;font-size:12.5px;border-radius:9px;padding:8px 12px">▶ Finish this booking</a>';
      return '<div style="border-top:1px solid #2c2824;padding:10px 0"><div style="font-weight:700;color:#F4F1EC">'
        + _esc(j.headline || j.customer || "(event)") + '</div>'
        + (meta ? '<div style="color:#9a938a;font-size:12px;margin-top:2px">' + meta + '</div>' : '') + fin + '</div>';
    }).join("") : '<div style="color:#9a938a;font-size:12.5px;padding:8px 0">Everything on this day already has a truck colour.</div>';
    var noteHtml = notes.length ? notes.map(function (n) {
      return '<div style="border-top:1px solid #2c2824;padding:10px 0"><div style="font-weight:700;color:#F4F1EC">'
        + _esc(n.title || n.raw || "(note)") + '</div>'
        + (n.description ? '<div style="color:#9a938a;font-size:12px;margin-top:2px;white-space:pre-wrap">' + _esc(n.description) + '</div>' : '') + '</div>';
    }).join("") : '<div style="color:#9a938a;font-size:12.5px;padding:8px 0">No # notes on this day.</div>';
    wrap.innerHTML = _section("Not assigned yet", un.length, unHtml) + _section("Calendar notes (# only)", notes.length, noteHtml);
  }
  function render() {
    try {
      if (typeof ST !== "undefined") { ST.view = "manager"; ST.truck = "all"; }
      if (typeof renderTrucks === "function") renderTrucks();
      if (typeof applyChrome === "function") applyChrome();
      if (typeof renderBoard === "function") renderBoard();
      renderExtras();
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

  // "On our way" (SMS spec §2): when the crew taps it on a stop, text that customer from the
  // updates line. Best-effort + non-blocking — the prototype's own button feedback runs first;
  // we only add the send. Dry-run until Twilio creds, and skipped if the stop has no phone
  // (e.g. a manager-created calendar event with no booked Job behind it).
  function wireOnOurWay() {
    if (typeof sendOnWay !== "function") return;
    var _send = sendOnWay;
    window.sendOnWay = function () {
      var r = _send.apply(this, arguments);
      try {
        var s = (typeof CURRENT !== "undefined") ? CURRENT : null;
        if (s && s.phone) {
          fetch("/sms/send", {
            method: "POST", credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ to: s.phone, kind: "on_our_way", params: { name: (s.cust || "").split(" ")[0] } }),
          }).catch(function () {});
        }
      } catch (e) {}
      return r;
    };
  }

  // Next-customer ETA (SMS spec §2): the crew finishes a stop and texts the NEXT stop their
  // estimated arrival (the crew's own estimate, never raw map distance). We inject the
  // affordance into the job-detail sheet just under the "on our way" button. The next stop is
  // the following stop in the SAME truck + day that still has a customer phone behind it.
  function nextStopWithPhone(cur) {
    if (!cur) return null;
    var lane = (window.STOPS || []).filter(function (s) { return s.truck === cur.truck && s.day === cur.day; });
    var i = -1;
    for (var k = 0; k < lane.length; k++) { if (lane[k].id === cur.id) { i = k; break; } }
    if (i < 0) return null;
    for (var j = i + 1; j < lane.length; j++) { if (lane[j].phone) return lane[j]; }
    return null;
  }
  function showEtaInput(wrap, nxt, nm) {
    wrap.innerHTML = "";
    var inp = document.createElement("input");
    inp.id = "ijEtaTime"; inp.type = "text"; inp.placeholder = "ETA to " + nm + " — e.g. 2:45pm";
    inp.autocomplete = "off";
    inp.style.cssText = "width:100%;box-sizing:border-box;padding:12px;border:1.5px solid #d8d3cc;border-radius:12px;font-size:15px;margin:4px 0";
    var send = document.createElement("button");
    send.className = "s-onway"; send.textContent = "Send ETA to " + nm;
    send.onclick = function () {
      var v = (inp.value || "").trim();
      if (!v) { inp.focus(); return; }
      send.disabled = true; send.textContent = "Sending…";
      fetch("/sms/eta", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ to: nxt.phone, name: nm, eta: v }),
      }).then(function (r) { return r.ok ? r.json() : null; }).then(function (res) {
        if (res && res.sent) { done(wrap, "✓ ETA sent to " + nm); }
        else if (res && res.dry_run) { done(wrap, "✓ ETA composed (texting not live yet)"); }
        else if (res && res.skipped === "opted_out") { send.disabled = false; send.textContent = nm + " opted out of texts"; }
        else { send.disabled = false; send.textContent = "Couldn't send — try again"; }
      }).catch(function () { send.disabled = false; send.textContent = "Couldn't reach the server"; });
    };
    wrap.appendChild(inp); wrap.appendChild(send); inp.focus();
  }
  function done(wrap, msg) {
    wrap.innerHTML = "";
    var d = document.createElement("div");
    d.className = "s-onway sent"; d.textContent = msg;
    wrap.appendChild(d);
  }
  function injectEta() {
    var cur = (typeof CURRENT !== "undefined") ? CURRENT : null;
    var ow = document.getElementById("owBtn");
    if (!cur || !ow || document.getElementById("ijEtaWrap")) return;
    var nxt = nextStopWithPhone(cur);
    if (!nxt) return;   // last stop, or the next has no number — nothing to offer
    var nm = ((nxt.cust || "the next customer").split(" ")[0]) || "the next customer";
    var wrap = document.createElement("div");
    wrap.id = "ijEtaWrap";
    var btn = document.createElement("button");
    btn.className = "s-onway"; btn.id = "ijEtaBtn";
    btn.textContent = "📍 Text next stop (" + nm + ") your ETA";
    btn.onclick = function () { showEtaInput(wrap, nxt, nm); };
    wrap.appendChild(btn);
    ow.parentNode.insertBefore(wrap, ow.nextSibling);
  }
  // Reference photos (§8): the manager attaches the customer's photos at booking; the crew see
  // them right on the job here. Fetched per linked Job and shown as a tap-to-enlarge strip above
  // the "on our way" button. Silent when a stop has no linked Job or no photos.
  function openPhoto(url) {
    var ov = document.createElement("div");
    ov.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.9);z-index:99999;display:flex;align-items:center;justify-content:center;padding:16px";
    ov.onclick = function () { if (ov.parentNode) ov.parentNode.removeChild(ov); };
    var im = document.createElement("img");
    im.src = url;
    im.style.cssText = "max-width:100%;max-height:100%;border-radius:8px";
    ov.appendChild(im); document.body.appendChild(ov);
  }
  function injectPhotos() {
    var cur = (typeof CURRENT !== "undefined") ? CURRENT : null;
    var ow = document.getElementById("owBtn");
    if (!cur || !cur.job_id || !ow || document.getElementById("ijPhotoWrap")) return;
    var wrap = document.createElement("div");
    wrap.id = "ijPhotoWrap"; wrap.style.cssText = "margin:4px 0 12px";
    ow.parentNode.insertBefore(wrap, ow);   // above the "on our way" button
    fetch("/jobs/" + encodeURIComponent(cur.job_id) + "/photos", { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (res) {
        var photos = (res && res.photos) || [];
        if (!photos.length) { if (wrap.parentNode) wrap.parentNode.removeChild(wrap); return; }
        var lbl = document.createElement("div");
        lbl.textContent = "Reference photos (" + photos.length + ") - tap to enlarge";
        lbl.style.cssText = "font-weight:700;font-size:13px;margin-bottom:6px;color:#141414";
        var strip = document.createElement("div");
        strip.style.cssText = "display:flex;gap:8px;overflow-x:auto;padding-bottom:4px";
        photos.forEach(function (p) {
          var im = document.createElement("img");
          im.src = p.url; im.alt = p.filename || "photo"; im.loading = "lazy";
          im.style.cssText = "height:96px;width:96px;object-fit:cover;border-radius:10px;border:1px solid #d8d3cc;flex:0 0 auto;cursor:pointer";
          im.onclick = function () { openPhoto(p.url); };
          strip.appendChild(im);
        });
        wrap.appendChild(lbl); wrap.appendChild(strip);
      }).catch(function () { if (wrap.parentNode) wrap.parentNode.removeChild(wrap); });
  }
  // The job's Dropbox photo folder (§10): the manager drops photos into it via the calendar link;
  // give the crew a tap-through to the SAME folder here. Silent when the job has no folder link.
  function injectPhotosFolder() {
    var cur = (typeof CURRENT !== "undefined") ? CURRENT : null;
    var ow = document.getElementById("owBtn");
    if (!cur || !cur.photos_link || !ow || document.getElementById("ijFolderWrap")) return;
    var wrap = document.createElement("div");
    wrap.id = "ijFolderWrap"; wrap.style.cssText = "margin:4px 0 12px";
    var a = document.createElement("a");
    a.href = cur.photos_link; a.target = "_blank"; a.rel = "noopener";
    a.textContent = "📁 Open the job's photo folder";
    a.style.cssText = "display:inline-block;font-weight:700;font-size:13px;color:#F05014;text-decoration:none;border:1px solid #d8d3cc;border-radius:10px;padding:8px 12px";
    wrap.appendChild(a);
    ow.parentNode.insertBefore(wrap, ow);   // above the "on our way" button, near the reference photos
  }
  // Backwards booking: a stop that's a bare calendar event (no linked Job yet) gets a prominent
  // "Finish this booking in the app" button — opens the booking screen scoped to THIS event so
  // completing it fills the same event (no duplicate). Right on the board, no Calendar round-trip.
  function injectFinishBooking() {
    var cur = (typeof CURRENT !== "undefined") ? CURRENT : null;
    var ow = document.getElementById("owBtn");
    if (!cur || cur.job_id || !cur.id || !ow || document.getElementById("ijFinishWrap")) return;
    var wrap = document.createElement("div");
    wrap.id = "ijFinishWrap"; wrap.style.cssText = "margin:2px 0 12px";
    var a = document.createElement("a");
    a.href = "/app/new-booking?event=" + encodeURIComponent(cur.id);
    a.textContent = "▶ Finish this booking in the app";
    a.style.cssText = "display:block;text-align:center;font-weight:800;font-size:14px;color:#fff;"
      + "background:#F05014;text-decoration:none;border-radius:11px;padding:13px";
    wrap.appendChild(a);
    ow.parentNode.insertBefore(wrap, ow);   // top of the stop's actions
  }
  function wireNextEta() {
    if (typeof openStop !== "function") return;
    var _open = openStop;
    window.openStop = function () {
      var r = _open.apply(this, arguments);
      try { injectFinishBooking(); } catch (e) {}
      try { injectEta(); } catch (e) {}
      try { injectPhotos(); } catch (e) {}
      try { injectPhotosFolder(); } catch (e) {}
      return r;
    };
  }

  function start() {
    // Re-fetch a day whenever the manager switches the day tab.
    if (typeof setDay === "function") {
      var _sd = setDay;
      window.setDay = function (i) { _sd(i); loadDay(i).then(function () { rebuild(); render(); }); };
    }
    wireOnOurWay();
    wireNextEta();
    refresh();  // no-op board if not logged in yet; call __ijDayRefresh() after login
  }
  if (document.readyState !== "loading") start();
  else document.addEventListener("DOMContentLoaded", start);
})();
