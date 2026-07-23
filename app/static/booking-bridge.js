/* Island Junk — booking bridge.
 * Injected after the approved booking prototype (file untouched). When any lane's
 * "Job ready" modal opens, it adds a "Book it" button that POSTs to /booking — the
 * engine creates the job and writes ONE event to the TEST calendar. Reuses the
 * prototype's own globals (curType, val, bookDate) and its computed CALENDAR HEADLINE
 * so the calendar event matches the prototype exactly.
 *
 * Manager-gated server-side: log in (PIN) first so the session cookie rides along.
 */
(function () {
  var ACCT = { collect: "residential", invoiced: "commercial", contracts: "commercial", pallet: "commercial", pm: "property_mgmt" };

  // ── Wire the booking's hardcoded rates to the owner's saved rate sheet ──────────
  // The prototype bakes in residential load prices (const RES) and bin base/surcharges
  // (binBase / binSurFor). Point them at the injected ij_rates_v1 so an owner's rate-sheet
  // edits flow through to booking estimates. RES is a const object — we mutate its props
  // (allowed); binBase/binSurFor are functions we override. Runs once at load, before the
  // user opens a lane (collectFlowHTML rebuilds from RES each time; bin math calls the fns).
  function applyRateSheet() {
    var R;
    try { R = JSON.parse(localStorage.getItem("ij_rates_v1") || "null"); } catch (e) { return; }
    if (!R) return;
    try {
      if (typeof RES !== "undefined" && RES) {
        if (R.residentialLoads) {
          RES.loads = ["1/8", "1/4", "1/3", "1/2", "2/3", "3/4", "7/8", "full"]
            .filter(function (k) { return R.residentialLoads[k] != null; })
            .map(function (k) { return [k, R.residentialLoads[k]]; });
        }
        if (R.residentialMin) {
          RES.min = [R.residentialMin.low, R.residentialMin.mid, R.residentialMin.high]
            .filter(function (v) { return v != null; });
        }
        if (R.labourRate != null) RES.labour = R.labourRate;
        if (R.gstPct != null) RES.gst = R.gstPct / 100;
        if (R.parking && R.parking.chargeHr != null) RES.parkHr = R.parking.chargeHr;
        if (Array.isArray(R.items) && R.items.length) {
          RES.items = R.items.map(function (it) {
            return {
              id: String(it.n || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, ""),
              nm: it.n, price: +it.price || 0, unit: it.unit || "each",
            };
          });
        }
      }
      // commercial lane load prices + included minutes (const COMM.loads = [[key,price,incMin]])
      if (typeof COMM !== "undefined" && COMM && R.commercialLoads) {
        var im = R.commercialIncludedMin || {};
        COMM.loads = ["min", "1/8", "1/4", "1/3", "1/2", "2/3", "3/4", "7/8", "full"]
          .filter(function (k) { return R.commercialLoads[k] != null; })
          .map(function (k) { return [k, R.commercialLoads[k], im[k] != null ? im[k] : 0]; });
        if (R.labourRate != null) COMM.labour = R.labourRate;
      }
      var bin = R.bin || {};
      window.binBase = function (bt) {
        return bt === "Roofing" ? (bin.roofingBase != null ? bin.roofingBase : 250)
                                : (bin.base != null ? bin.base : 225);
      };
      if (R.surcharges) {
        window.binSurFor = function (bt, town) {
          var map = (bt === "Roofing" && R.roofingSurcharges) ? R.roofingSurcharges : R.surcharges;
          return (town in map) ? map[town] : null;   // area not on the sheet => call for quote
        };
      }
    } catch (e) {}
  }
  applyRateSheet();

  // ── Retire the baked-in demo customers once real ones are injected ─────────────
  // QB_CUST (4 residential) + QB_COMM (5 commercial) are const demo arrays the prototype
  // concats with the real data. Empty them in place so only the imported customers show.
  // Guarded: only when real data is present, so an empty brand keeps its demo. Setting the
  // comm-seeded flag stops commLoad() from merging QB_COMM back in (which would also sync it).
  function retireDemoCustomers() {
    try {
      var res = JSON.parse(localStorage.getItem("ij_customers_v1") || "[]");
      if (Array.isArray(res) && res.length && typeof QB_CUST !== "undefined" && Array.isArray(QB_CUST)) {
        QB_CUST.length = 0;
      }
      var co = JSON.parse(localStorage.getItem("ij_company_customers_v1") || "[]");
      if (Array.isArray(co) && co.length && typeof QB_COMM !== "undefined" && Array.isArray(QB_COMM)) {
        QB_COMM.length = 0;
        try { localStorage.setItem("ij_comm_seeded_v1", "1"); } catch (e) {}
      }
    } catch (e) {}
  }
  retireDemoCustomers();

  function ymd(d) {
    try {
      var x = (d instanceof Date) ? d : new Date(d);
      if (isNaN(x)) return null;
      return x.getFullYear() + "-" + String(x.getMonth() + 1).padStart(2, "0") + "-" + String(x.getDate()).padStart(2, "0");
    } catch (e) { return null; }
  }

  // "8" -> "08:00", "1230" -> "12:30", "8-9" -> "08:00" (start). null if none.
  // ---- Slot time (the calendar's positional start/end; the REAL time is the headline) ----
  // The arrival-window options carry am/pm ("5:00–7:00 PM", "10:00 AM–12:00 PM"); we must honour it
  // or a 5pm job lands at 5am and sorts to the TOP of the day's stack. A bare "hard time" has no
  // am/pm, so the fixed workday decides: hours 1–6 are afternoon (1:30 -> 13:30), matching the board.
  function _pad2(n) { return String(n).padStart(2, "0"); }
  function _ampm(s) { var m = /(am|pm)/i.exec(String(s)); return m ? m[1].toLowerCase() : ""; }
  function _hm(s) {
    var d = String(s).replace(/[^0-9]/g, ""); if (!d) return null;
    var hh, mm;
    if (d.length <= 2) { hh = parseInt(d, 10); mm = 0; }
    else { hh = parseInt(d.slice(0, d.length - 2), 10); mm = parseInt(d.slice(-2), 10); }
    return isNaN(hh) ? null : { hh: hh, mm: mm };
  }
  function _to24(o, ap) { var h = o.hh % 12; if (ap === "pm") h += 12; return _pad2(h) + ":" + _pad2(o.mm); }
  function parseWindow() {  // arrival window -> {start, end}, honouring am/pm on either side
    var w = ""; try { w = val("pickWin") || ""; } catch (e) {}
    if (!w) return null;
    var parts = String(w).split(/[-–—]/);
    var endAP = _ampm(parts[1] || ""), startAP = _ampm(parts[0] || "") || endAP;  // start inherits the end's am/pm
    var s = _hm(parts[0] || ""), e = _hm(parts[1] || "");
    if (!s) return null;
    return { start: _to24(s, startAP), end: e ? _to24(e, endAP) : null };
  }
  function parseHard() {  // a single exact "hard time" (no am/pm) -> fixed-workday 24h, or null
    var t = ""; try { t = val("hardTime") || ""; } catch (e) {}
    var o = t ? _hm(String(t).split(/[-–—]/)[0]) : null;
    if (!o) return null;
    var h = (o.hh >= 1 && o.hh <= 6) ? o.hh + 12 : o.hh;   // 1–6 = afternoon
    return _pad2(h) + ":" + _pad2(o.mm);
  }
  function parseStart() { return parseHard() || (parseWindow() || {}).start || null; }
  function parseEnd() { return parseHard() ? null : ((parseWindow() || {}).end || null); }

  function anyVal() {
    for (var i = 0; i < arguments.length; i++) { try { var v = val(arguments[i]); if (v) return v; } catch (e) {} }
    return "";
  }

  function lane() { try { return curType || "collect"; } catch (e) { return "collect"; } }

  function customerFor(t) {
    try {
      if (t === "collect") return [val("fname"), val("lname")].filter(Boolean).join(" ");
      if (t === "invoiced") return val("company");
      if (t === "bins") return val("binCust");
      if (t === "pallet") return val("palCo");
      if (t === "pm") return (typeof curCompany !== "undefined" ? curCompany : "") || val("cust");
      if (t === "contracts") { var cc = cAll()[curContract]; if (cc) return cc.name; }
    } catch (e) {}
    return anyVal("company", "cust", "fname", "binCust", "palCo");
  }

  // The prototype already computed and printed the exact CALENDAR HEADLINE in #mBody.
  function headlineFromBody() {
    var pre = document.querySelector("#mBody"); if (!pre) return null;
    var line = pre.textContent.split("\n").find(function (l) { return /^\s*CALENDAR HEADLINE:/.test(l); });
    return line ? line.replace(/^\s*CALENDAR HEADLINE:\s*/, "").trim() : null;
  }

  function payload() {
    var t = lane();
    var d = (typeof bookDate !== "undefined") ? bookDate : new Date();
    var pf = window.__ijEventPrefill || null;   // backwards booking: completing a hand-made event
    return {
      brand: "victoria", on_date: (pf && pf.on_date) || ymd(d),
      booking_lane: t, account_type: ACCT[t] || null,
      customer_name: customerFor(t) || null,
      customer_phone: val("phone") || null, customer_email: val("email") || null,
      address: anyVal("addr", "cbAddr", "siteAddr", "binAddr") || null,
      time_start: parseStart() || (pf && pf.time_start) || null,
      time_end: parseEnd() || (pf && pf.time_end) || null,
      headline: headlineFromBody(),
      notes: (document.querySelector("#mBody") || {}).textContent || null,
      into_event_id: (pf && pf.into_event_id) || null,   // complete THIS event in place, no duplicate
    };
  }

  // Compress a booking photo (an object-URL from the prototype's mgrPhotos) to a small JPEG
  // data-URL, then file it onto the job so the crew see it on the Day Board (§8). The phone-side
  // downscale keeps the stored bytes small.
  function compressToDataUrl(srcUrl) {
    return new Promise(function (resolve, reject) {
      var img = new Image();
      img.onload = function () {
        var maxDim = 1600, w = img.width || 1, h = img.height || 1;
        var scale = Math.min(1, maxDim / Math.max(w, h));
        var cw = Math.max(1, Math.round(w * scale)), ch = Math.max(1, Math.round(h * scale));
        var c = document.createElement("canvas"); c.width = cw; c.height = ch;
        c.getContext("2d").drawImage(img, 0, 0, cw, ch);
        try { resolve(c.toDataURL("image/jpeg", 0.7)); } catch (e) { reject(e); }
      };
      img.onerror = reject;
      img.src = srcUrl;
    });
  }
  function uploadBookingPhotos(jobId, btn) {
    if (!jobId) return;
    var photos = [];
    try { photos = mgrPhotos || []; } catch (e) { photos = []; }   // prototype global (shared scope)
    if (!photos.length) return;
    var total = photos.length, done = 0, ok = 0;
    btn.textContent = "Filing " + total + " photo" + (total > 1 ? "s" : "") + "…";
    photos.forEach(function (p, i) {
      compressToDataUrl(p.url).then(function (dataUrl) {
        return fetch("/jobs/" + encodeURIComponent(jobId) + "/photos", {
          method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ filename: p.name || ("photo" + (i + 1) + ".jpg"), data_url: dataUrl }),
        });
      }).then(function (r) { if (r && r.ok) ok++; }).catch(function () {}).then(function () {
        done++;
        if (done === total) {
          btn.textContent = "✓ Booked — " + ok + "/" + total + " photo" + (total > 1 ? "s" : "") + " filed to the job";
        }
      });
    });
  }

  function addBookBtn() {
    var modal = document.querySelector("#ovl .modal");
    if (!modal || modal.querySelector("#ijBookBtn")) return;
    var close = modal.querySelector("#mClose"); if (!close) return;
    var btn = document.createElement("button");
    btn.id = "ijBookBtn"; btn.className = "close";
    btn.style.cssText = "background:#F05014;color:#fff;margin-right:8px";
    btn.textContent = "Book it — writes to TEST calendar";
    btn.onclick = function () {
      btn.disabled = true; btn.textContent = "Booking…";
      fetch("/booking", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload()),
      }).then(function (r) {
        if (r.status === 401 || r.status === 403) { throw new Error("auth"); }
        return r.json().catch(function () { return {}; }).then(function (j) { return { ok: r.ok, j: j }; });
      }).then(function (res) {
        var j = res.j || {};
        if (!res.ok) {   // real server error — previously this faked a green "Booked"
          btn.disabled = false; btn.style.background = "#C0392B";
          var det = j.detail, msg;
          if (typeof det === "string") { msg = det; }
          else if (Array.isArray(det) && det[0]) { msg = (det[0].loc ? det[0].loc[det[0].loc.length - 1] + ": " : "") + (det[0].msg || "invalid"); }
          else { msg = "server error — try again"; }
          btn.textContent = "Booking failed: " + msg;
          return;
        }
        if (j.calendar_error) {   // Job saved but the calendar event didn't write — surface why
          btn.style.background = "#E8A317";
          btn.textContent = "Job saved, calendar write FAILED: " + j.calendar_error;
          return;
        }
        btn.textContent = "✓ Booked (" + lane() + ") — event " + (j.gcal_event_id || "?") + " on TEST";
        btn.style.background = "#3CA03C";
        uploadBookingPhotos(j && j.id, btn);   // best-effort: file the attached photos onto the job
        enableTextBtn(j && j.id);              // job now exists — light up the "text customer" button
      }).catch(function (e) {
        btn.disabled = false;
        btn.textContent = (e && e.message === "auth") ? "Log in as a manager first" : "Error — retry";
      });
    };
    close.parentNode.insertBefore(btn, close);
    addTextBtn();   // show the "Text customer" option beside it now, disabled until the job is booked
  }

  // The "text the customer" button sits beside Book it from the start (Wes: an option beside
  // confirm/cancel), DISABLED until the job is booked — you can't text before the job exists. The
  // booking confirmation is never auto-sent; the manager taps this when he wants to.
  function addTextBtn() {
    var modal = document.querySelector("#ovl .modal");
    if (!modal || modal.querySelector("#ijTextBtn")) return;
    var close = modal.querySelector("#mClose"); if (!close) return;
    var tb = document.createElement("button");
    tb.id = "ijTextBtn"; tb.className = "close";
    tb.style.cssText = "background:#E8A317;color:#fff;margin-right:8px;opacity:.5";
    tb.textContent = "Text customer (after booking)";
    tb.disabled = true;
    close.parentNode.insertBefore(tb, close);
  }
  function enableTextBtn(jobId) {   // once the job exists, light it up and wire the send
    var tb = document.querySelector("#ijTextBtn");
    if (!tb || !jobId) return;
    tb.disabled = false; tb.style.opacity = "1"; tb.textContent = "Text customer the booking";
    tb.onclick = function () {
      tb.disabled = true; tb.textContent = "Texting…";
      var d = (typeof bookDate !== "undefined") ? bookDate : new Date();
      fetch("/booking/" + encodeURIComponent(jobId) + "/text-confirmation", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ on_date: ymd(d) }),
      }).then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (j) { return { ok: r.ok, j: j }; });
      }).then(function (res) {
        var j = res.j || {};
        if (res.ok && j.sent) { tb.textContent = "✓ Text sent to customer"; tb.style.background = "#3CA03C"; }
        else if (res.ok) { tb.disabled = false; tb.textContent = "Not sent: " + (j.detail || "?"); tb.style.background = "#C0392B"; }
        else { tb.disabled = false; tb.textContent = "Text failed — retry"; tb.style.background = "#C0392B"; }
      }).catch(function () { tb.disabled = false; tb.textContent = "Text failed — retry"; });
    };
  }

  var ovl = document.querySelector("#ovl");
  if (ovl) {
    new MutationObserver(function () {
      if (!ovl.classList.contains("show")) return;
      var t = document.querySelector("#mTitle");
      if (t && /job ready/i.test(t.textContent)) addBookBtn();
    }).observe(ovl, { attributes: true, attributeFilter: ["class"] });
  }
})();

/* Backwards booking: /app/new-booking?event=<id> completes a HAND-MADE calendar event in place.
   Asks Residential vs Commercial, opens that flow, pre-fills the date + time (via payload) + the event's
   Location as the address, and shows the title/notes so the manager copies the name in. payload() sends
   into_event_id, so Book it fills the SAME event (no duplicate). */
(function () {
  var m = /[?&]event=([^&]+)/.exec(location.search || "");
  if (!m) return;
  var eventId = decodeURIComponent(m[1]);
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  fetch("/booking/from-event/" + encodeURIComponent(eventId), { credentials: "same-origin" })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (p) {
      if (!p) { alert("Couldn't load that calendar event."); return; }
      if (p.already_booked) { alert("This calendar event is already booked in the app."); return; }
      window.__ijEventPrefill = { into_event_id: eventId, on_date: p.on_date, time_start: p.time_start,
        time_end: p.time_end, title: p.title, address: p.address, description: p.description };
      showPrompt(p);
    })
    .catch(function () {});

  function showPrompt(p) {
    var info = [p.title && "<b>" + esc(p.title) + "</b>",
      p.on_date && ("Date: " + esc(p.on_date) + (p.time_start ? (" · " + esc(p.time_start) + (p.time_end ? ("–" + esc(p.time_end)) : "")) : "")),
      p.address && ("Address: " + esc(p.address)),
      p.description && ("Notes: " + esc(p.description))].filter(Boolean).join("<br>");
    var ov = document.createElement("div");
    ov.id = "ijFinishPrompt";
    ov.style.cssText = "position:fixed;inset:0;z-index:9500;background:rgba(20,20,20,.72);display:flex;align-items:center;justify-content:center;padding:18px";
    var card = document.createElement("div");
    card.style.cssText = "background:#fff;color:#141414;border-radius:16px;max-width:440px;width:100%;padding:20px;font-family:Inter,system-ui,sans-serif";
    card.innerHTML =
      '<div style="font-family:Anton,sans-serif;text-transform:uppercase;letter-spacing:.02em;font-size:21px;margin-bottom:8px">Finish this booking</div>'
      + '<div style="font-size:12.5px;color:#666;line-height:1.5;margin-bottom:8px">From your calendar event — the date, time and address carry over. Copy the customer name into the form.</div>'
      + '<div style="background:#F4F3F1;border-radius:10px;padding:11px 12px;font-size:13px;line-height:1.65;margin-bottom:16px">' + (info || "(no details on the event)") + '</div>'
      + '<div style="font-weight:800;font-size:13px;margin-bottom:9px">Is this residential or commercial?</div>'
      + '<div style="display:flex;gap:10px"><button id="ijPickRes" style="flex:1;padding:14px;border:none;border-radius:11px;background:#3CA03C;color:#fff;font-weight:800;font-size:15px;cursor:pointer;font-family:inherit">Residential</button>'
      + '<button id="ijPickComm" style="flex:1;padding:14px;border:none;border-radius:11px;background:#F05014;color:#fff;font-weight:800;font-size:15px;cursor:pointer;font-family:inherit">Commercial</button></div>';
    ov.appendChild(card);
    if (document.body) document.body.appendChild(ov);
    var res = document.getElementById("ijPickRes"), comm = document.getElementById("ijPickComm");
    if (res) res.onclick = function () { pick("collect"); };
    if (comm) comm.onclick = function () { pick("invoiced"); };
  }

  function pick(type) {
    var ov = document.getElementById("ijFinishPrompt"); if (ov && ov.parentNode) ov.parentNode.removeChild(ov);
    var pf = window.__ijEventPrefill || {};
    try { if (typeof openType === "function") openType(type); } catch (e) {}
    var ref = [pf.title, pf.description].filter(Boolean).join(" · ");   // sticky reference for copying the name
    if (ref && document.body) {
      var b = document.createElement("div");
      b.style.cssText = "position:sticky;top:0;z-index:8000;background:#141414;color:#fff;font-size:12.5px;padding:8px 14px;line-height:1.4";
      b.textContent = "Calendar event — copy the name/details in: " + ref;
      document.body.insertBefore(b, document.body.firstChild);
    }
    setTimeout(function () {   // fill after the flow has rendered + its wire set bookDate
      try {
        if (pf.on_date && typeof bookDate !== "undefined") {
          try { bookDate = new Date(pf.on_date + "T00:00:00"); if (typeof bookMoved !== "undefined") bookMoved = true; if (typeof paintDate === "function") paintDate(); } catch (e) {}
        }
        var addr = document.getElementById("addr"); if (addr && pf.address && !addr.value) addr.value = pf.address;
        var scope = document.getElementById("scope"); if (scope && pf.title && !scope.value) scope.value = pf.title;
      } catch (e) {}
    }, 50);
  }
})();
