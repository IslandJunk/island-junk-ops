/* Island Junk — Owner Hub bridge.
 * Injected after the approved owner-hub prototype (file untouched). Replaces the
 * hardcoded demo OWNER_ALERTS ("Ready to invoice", "Bins to bill / overdue") with the
 * real ready-to-invoice queue from GET /invoice-queue, and swaps the placeholder detail
 * sheets for the real lists. Never invoices or charges — surfaces only (guardrail §2).
 * ("Unpaid invoices" is omitted: payment status lives in QuickBooks, not this app.)
 */
(function () {
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function money(v) { return (v == null) ? "" : ("$" + v); }
  function card(html) {
    return '<div style="border:1px solid var(--line);border-radius:12px;padding:12px;margin-top:9px">' + html + "</div>";
  }

  // Residential-bin 48-hour e-transfer clock (§9/§11): the owner taps this when he SENDS a
  // residential-bin invoice. Fires POST /reminders/cc-charge (idempotent per customer+addr+day);
  // the charge itself always stays manual (guardrail §2). The owner decides which bins are
  // residential — the app only surfaces the action.
  // Square payment link (§4/§10): the owner taps to create a pay-by-card link for a job
  // amount. The app NEVER charges — the customer pays via the link. Dry-run until Square creds.
  window.__ijSquareLink = function (btn, amount, name) {
    btn.disabled = true;
    btn.textContent = "Creating link…";
    fetch("/square/payment-link", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount: String(amount), name: name || "Island Junk" }),
    }).then(function (r) { return r.ok ? r.json() : null; }).then(function (res) {
      if (res && res.url) {
        btn.parentNode.innerHTML = '<div class="meta" style="margin-top:8px;font-weight:700">'
          + '💳 Payment link: <a href="' + esc(res.url) + '" target="_blank" rel="noopener">' + esc(res.url) + "</a></div>";
      } else if (res && res.dry_run) {
        btn.textContent = "Square not connected yet (dry-run)";
      } else {
        btn.disabled = false;
        btn.textContent = "Create Square payment link";
      }
    }).catch(function () { btn.disabled = false; btn.textContent = "Create Square payment link"; });
  };

  function squareBtn(amount, name) {
    if (amount == null) return "";
    return '<button class="btn2" style="margin-top:9px;font-size:12.5px;padding:7px 10px"'
      + ' onclick="__ijSquareLink(this,' + JSON.stringify(String(amount)).replace(/"/g, "&quot;")
      + ',' + JSON.stringify(name || "").replace(/"/g, "&quot;") + ')">Create Square payment link</button>';
  }

  window.__ijStartCcClock = function (btn, customer, address) {
    btn.disabled = true;
    btn.textContent = "Starting…";
    fetch("/reminders/cc-charge", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: customer || null, addr: address || null }),
    }).then(function (r) { return r.ok ? r.json() : null; }).then(function (rem) {
      if (rem && rem.due) {
        btn.parentNode.innerHTML = '<div class="meta" style="margin-top:8px;color:#E8A317;font-weight:700">'
          + "⏱ 48-hour clock started — e-transfer due " + esc(rem.due)
          + " (else charge card on file +2.4%, manual).</div>";
      } else {
        btn.disabled = false;
        btn.textContent = "Start 48-hour e-transfer clock";
      }
    }).catch(function () { btn.disabled = false; btn.textContent = "Start 48-hour e-transfer clock"; });
  };

  function invoiceSheet(Q) {
    var r = Q.ready_to_invoice, rows = "";
    (r.commercial || []).forEach(function (x) {
      rows += card('<b>' + esc(x.customer || "Commercial job") + "</b>"
        + (x.address ? ('<br><span style="color:var(--muted);font-size:12.5px">' + esc(x.address) + "</span>") : "")
        + '<div class="meta" style="margin-top:6px;color:#3CA03C;font-weight:700">Commercial · '
        + (x.total != null ? ("total " + money(x.total)) : "set the total") + " — ready to invoice</div>"
        + squareBtn(x.total, (x.customer || "Commercial job")));
    });
    (r.bins || []).forEach(function (x) {
      var ccBtn = '<button class="btn2" style="margin-top:9px;font-size:12.5px;padding:7px 10px"'
        + ' onclick="__ijStartCcClock(this,' + JSON.stringify(x.customer || "").replace(/"/g, "&quot;")
        + ',' + JSON.stringify(x.address || "").replace(/"/g, "&quot;") + ')">'
        + "Residential? Start 48-hour e-transfer clock</button>";
      rows += card('<b>Bin ' + esc(x.code) + "</b> · " + esc(x.customer || "")
        + (x.waste_class ? ('<br><span style="color:var(--muted);font-size:12.5px">' + esc(x.waste_class) + "</span>") : "")
        + '<div class="meta" style="margin-top:6px;color:#3CA03C;font-weight:700">'
        + (x.charge != null ? ("disposal " + money(x.charge)) : "priced by weight")
        + (x.margin != null ? (" · margin " + money(x.margin)) : "") + " — ready to invoice</div>"
        + ccBtn + squareBtn(x.charge, ("Bin " + x.code + (x.customer ? " — " + x.customer : ""))));
    });
    if (!rows) rows = '<div class="meta" style="margin-top:10px">Nothing ready right now.</div>';
    window.sheet("Ready to invoice",
      '<div class="note" style="margin-top:6px">Completed jobs with everything captured — crew, time, materials. '
      + "Invoice each in QuickBooks. Always one tap, never automatic.</div>" + rows
      + '<button class="btn2" onclick="closeSheet()" style="margin-top:12px">Close</button>');
  }

  function overdueSheet(Q) {
    var rows = (Q.bins_overdue || []).map(function (b) {
      return card('<b>Bin ' + esc(b.code) + "</b> · " + esc(b.customer || "")
        + '<div class="meta" style="margin-top:6px;color:#E8A317;font-weight:700">Out ' + b.days_out
        + " days · dropped " + esc(b.drop_date) + "</div>");
    }).join("");
    if (!rows) rows = '<div class="meta" style="margin-top:10px">No overdue bins.</div>';
    window.sheet("Bins to bill / overdue",
      '<div class="note" style="margin-top:6px">Roll-off bins out past 14 days — confirm the rental is still going '
      + "or bill the extra days.</div>" + rows
      + '<button class="btn2" onclick="closeSheet()" style="margin-top:12px">Close</button>');
  }

  // ── Global brand switch (§3) ──────────────────────────────────────────────
  // The owner-hub's Victoria/Nanaimo switch is THE owner workspace switch (Wes 2026-07):
  // everything the owner sees/edits follows it. Align the prototype's client `BRAND` to the
  // brand the server served this page with, then make a switch persist server-side + reload
  // so every screen (and every sync write) follows the new brand.
  (function () {
    var served = window.__IJ_BRAND;
    if (served && typeof BRAND !== "undefined" && (served === "victoria" || served === "nanaimo")) {
      if (BRAND !== served) { BRAND = served; }   // align; the gate/unlock render picks it up
    }
    if (typeof setBrand === "function") {
      var _setBrand = setBrand;
      window.setBrand = function (b) {
        if (b === window.__IJ_BRAND) { return _setBrand(b); }   // already active — just re-render
        // Persist the switch, THEN reload so the whole page (refs + client BRAND) re-serves
        // for the new brand. Owner-only server-side; crew never reach this screen.
        fetch("/auth/brand", {
          method: "POST", credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ brand: b }),
        }).then(function () { window.location.reload(); })
          .catch(function () { _setBrand(b); });   // offline fallback: at least switch the view
      };
    }
  })();

  fetch("/invoice-queue", { credentials: "same-origin" })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (Q) {
      if (!Q || typeof OWNER_ALERTS === "undefined") return;
      window.__ijQueue = Q;
      var alerts = [];
      if (Q.counts.ready > 0) {
        alerts.push({ k: "oa_invoice", dot: "#3CA03C", nm: "Ready to invoice", sb: "Completed jobs, all captured", count: String(Q.counts.ready) });
      }
      if (Q.counts.bins_overdue > 0) {
        alerts.push({ k: "oa_bins", dot: "#E8A317", nm: "Bins to bill / overdue", sb: "Out 14+ days", count: String(Q.counts.bins_overdue) });
      }
      OWNER_ALERTS.victoria = alerts;   // replace the demo; unpaid-invoices needs QuickBooks

      var orig = window.ownerAlert;
      window.ownerAlert = function (k) {
        var q = window.__ijQueue;
        if (q && k === "oa_invoice") return invoiceSheet(q);
        if (q && k === "oa_bins") return overdueSheet(q);
        return orig.apply(this, arguments);
      };
      if (typeof renderHub === "function") renderHub();
    })
    .catch(function () {});
})();
