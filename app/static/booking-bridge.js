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
  function parseStart() {
    var t = "";
    try { t = (val("hardTime") || "") || (val("pickWin") || ""); } catch (e) {}
    var digits = String(t).split(/[-–—]/)[0].replace(/[^0-9]/g, "");  // hyphen / en-dash / em-dash
    if (!digits) return null;
    var hh, mm;
    if (digits.length <= 2) { hh = parseInt(digits, 10); mm = 0; }
    else { hh = parseInt(digits.slice(0, digits.length - 2), 10); mm = parseInt(digits.slice(-2), 10); }
    if (isNaN(hh)) return null;
    return String(hh).padStart(2, "0") + ":" + String(mm || 0).padStart(2, "0");
  }

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
    return {
      brand: "victoria", on_date: ymd(d),
      booking_lane: t, account_type: ACCT[t] || null,
      customer_name: customerFor(t) || null,
      customer_phone: val("phone") || null, customer_email: val("email") || null,
      address: anyVal("addr", "cbAddr", "siteAddr", "binAddr") || null,
      time_start: parseStart(),
      headline: headlineFromBody(),
      notes: (document.querySelector("#mBody") || {}).textContent || null,
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
      }).catch(function (e) {
        btn.disabled = false;
        btn.textContent = (e && e.message === "auth") ? "Log in as a manager first" : "Error — retry";
      });
    };
    close.parentNode.insertBefore(btn, close);
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
