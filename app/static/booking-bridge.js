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
    var digits = String(t).split("-")[0].replace(/[^0-9]/g, "");
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
        return r.json();
      }).then(function (j) {
        btn.textContent = "✓ Booked (" + lane() + ") — event " + (j.gcal_event_id || "?") + " on TEST";
        btn.style.background = "#3CA03C";
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
