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

  // BIN-xxxx rental code — the QuickBooks PO/reference the owner pastes into the invoice so
  // QuickBooks-sync (WS4) can match the sent/paid invoice back to this bin. One-tap copy.
  window.__ijCopyRef = function (btn, code) {
    try { navigator.clipboard.writeText(code); btn.textContent = "Copied " + code; }
    catch (e) { btn.textContent = code; }
  };
  function refChip(code) {
    if (!code) return "";
    return '<div class="meta" style="margin-top:6px">QuickBooks PO: '
      + '<b style="font-family:ui-monospace,Menlo,monospace">' + esc(code) + "</b> "
      + '<button class="btn2" style="font-size:11.5px;padding:3px 8px;margin-left:4px" onclick="__ijCopyRef(this,'
      + JSON.stringify(code).replace(/"/g, "&quot;") + ')">Copy</button></div>';
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
          + 'Payment link: <a href="' + esc(res.url) + '" target="_blank" rel="noopener">' + esc(res.url) + "</a></div>";
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

  window.__ijStartCcClock = function (btn, customer, address, ref) {
    btn.disabled = true;
    btn.textContent = "Starting…";
    fetch("/reminders/cc-charge", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: customer || null, addr: address || null, reference_code: ref || null }),
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
        + ',' + JSON.stringify(x.address || "").replace(/"/g, "&quot;")
        + ',' + JSON.stringify(x.reference_code || "").replace(/"/g, "&quot;") + ')">'
        + "Residential? Start 48-hour e-transfer clock</button>";
      rows += card('<b>Bin ' + esc(x.code) + "</b> · " + esc(x.customer || "")
        + (x.waste_class ? ('<br><span style="color:var(--muted);font-size:12.5px">' + esc(x.waste_class) + "</span>") : "")
        + '<div class="meta" style="margin-top:6px;color:#3CA03C;font-weight:700">'
        + (x.charge != null ? ("disposal " + money(x.charge)) : "priced by weight")
        + (x.margin != null ? (" · margin " + money(x.margin)) : "") + " — ready to invoice</div>"
        + refChip(x.reference_code)
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

  // Residential-bin "awaiting payment" queue (WS1): the bins you've invoiced whose 48-hour
  // e-transfer clock is running. "Received as e-transfer" closes it out via POST
  // /reminders/{id}/done (which also turns its reminder-calendar event purple). "Charge card on
  // file" is added with the card-on-file build (WS3). No auto-charge — one owner tap (§2).
  window.__ijMarkPaid = function (btn, id) {
    btn.disabled = true;
    btn.textContent = "Saving…";
    fetch("/reminders/" + encodeURIComponent(id) + "/done", { method: "POST", credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; }).then(function (res) {
        if (res && res.done) {
          btn.parentNode.innerHTML = '<div class="meta" style="margin-top:8px;color:#3CA03C;font-weight:700">'
            + "✓ Paid by e-transfer — closed out"
            + (res.calendar_updated ? " (calendar → purple)" : "") + ".</div>";
        } else { btn.disabled = false; btn.textContent = "Received as e-transfer"; }
      }).catch(function () { btn.disabled = false; btn.textContent = "Received as e-transfer"; });
  };

  // "Charge card on file" (WS3, OWNER-ONLY) — check the customer's saved card, take the invoice
  // total, charge it +2.4% (POST /square/charge-card-on-file), then close the reminder. The
  // amount + card are shown before it fires; no auto-charge — one deliberate owner tap (§2).
  window.__ijChargeCard = function (btn, reminderId, name, jobId) {
    btn.disabled = true;
    btn.textContent = "Checking card…";
    fetch("/square/card-on-file?customer_name=" + encodeURIComponent(name || ""), { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; }).then(function (cof) {
        if (!cof || !cof.on_file) { btn.disabled = false; btn.textContent = "No card on file (save one at booking)"; return; }
        var host = btn.parentNode;
        host.innerHTML = "";
        var lbl = document.createElement("div");
        lbl.className = "meta"; lbl.style.cssText = "margin-top:8px;font-weight:700";
        lbl.textContent = "Card on file: " + (cof.brand || "card") + " ••" + (cof.last4 || "");
        var amt = document.createElement("input");
        amt.type = "text"; amt.inputMode = "decimal"; amt.placeholder = "Invoice total $ (card adds 2.4%)";
        amt.style.cssText = "width:100%;box-sizing:border-box;padding:11px;border:1.5px solid #d8d3cc;border-radius:10px;font-size:15px;margin:6px 0";
        var go = document.createElement("button");
        go.className = "btn2"; go.style.cssText = "font-size:12.5px;padding:7px 10px"; go.textContent = "Charge card";
        amt.addEventListener("input", function () {
          var v = parseFloat(amt.value);
          go.textContent = (v > 0) ? ("Charge $" + (v * 1.024).toFixed(2) + " to " + (cof.brand || "card") + " ••" + (cof.last4 || "")) : "Charge card";
        });
        go.addEventListener("click", function () {
          var v = parseFloat(amt.value);
          if (!(v > 0)) { amt.focus(); return; }
          var total = Math.round(v * 1.024 * 100) / 100;
          go.disabled = true; go.textContent = "Charging…";
          fetch("/square/charge-card-on-file", {
            method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ customer_name: name, amount: total, job_id: jobId || null, note: "Residential bin — card on file" }),
          }).then(function (r) { return r.ok ? r.json() : null; }).then(function (res) {
            if (res && res.charged) {
              fetch("/reminders/" + encodeURIComponent(reminderId) + "/done", { method: "POST", credentials: "same-origin" }).catch(function () {});
              host.innerHTML = '<div class="meta" style="margin-top:8px;color:#3CA03C;font-weight:700">✓ Charged '
                + esc(res.brand || "card") + " ••" + esc(res.last4 || "") + " $" + total.toFixed(2) + " — closed out.</div>";
            } else if (res && res.reason === "no_card_on_file") {
              go.disabled = false; go.textContent = "No card on file";
            } else {
              go.disabled = false; go.textContent = "Try again";
              var d = document.createElement("div"); d.className = "meta"; d.style.cssText = "margin-top:6px;color:#C0392B;font-weight:700";
              d.textContent = "Declined: " + ((res && res.reason) ? String(res.reason) : "charge failed"); host.appendChild(d);
            }
          }).catch(function () { go.disabled = false; go.textContent = "Couldn’t reach the server"; });
        });
        host.appendChild(lbl); host.appendChild(amt); host.appendChild(go); amt.focus();
      }).catch(function () { btn.disabled = false; btn.textContent = "Charge card on file"; });
  };

  function awaitingSheet(rems) {
    var rows = (rems || []).map(function (r) {
      var due = r.due ? ('<div class="meta" style="margin-top:6px;color:#E8A317;font-weight:700">e-transfer due '
        + esc(r.due) + " — else charge card on file +2.4%</div>") : "";
      var paidBtn = '<button class="btn2" style="margin-top:9px;font-size:12.5px;padding:7px 10px"'
        + ' onclick="__ijMarkPaid(this,' + JSON.stringify(String(r.id)).replace(/"/g, "&quot;") + ')">'
        + "Received as e-transfer</button>";
      var chargeBtn = '<div style="margin-top:2px"><button class="btn2" style="font-size:12.5px;padding:7px 10px"'
        + ' onclick="__ijChargeCard(this,' + JSON.stringify(String(r.id)).replace(/"/g, "&quot;")
        + ',' + JSON.stringify(r.name || "").replace(/"/g, "&quot;")
        + ',' + JSON.stringify(r.job_id || "").replace(/"/g, "&quot;") + ')">Charge card on file</button></div>';
      return card("<b>" + esc(r.name || r.text || "Residential bin") + "</b>"
        + (r.addr ? ('<br><span style="color:var(--muted);font-size:12.5px">' + esc(r.addr) + "</span>") : "")
        + refChip(r.reference_code) + due + paidBtn + chargeBtn);
    }).join("");
    if (!rows) rows = '<div class="meta" style="margin-top:10px">No bins awaiting payment.</div>';
    window.sheet("Bins awaiting payment (48h)",
      '<div class="note" style="margin-top:6px">Residential bins you’ve invoiced — within 48 hours they '
      + "e-transfer, else you charge the card on file (+2.4%). One tap when the money’s in.</div>" + rows
      + '<button class="btn2" onclick="closeSheet()" style="margin-top:12px">Close</button>');
  }

  // ── QuickBooks (WS4) — connect + read-only status + auto-sync toggle (owner) ──
  // Connect is a top-level navigation (OAuth needs a full redirect, not fetch). Disconnect /
  // toggle are same-origin POSTs. Read-only: the app never creates or sends an invoice.
  window.__ijQboConnect = function () { window.location.href = "/quickbooks/connect"; };
  window.__ijQboDisconnect = function (btn) {
    btn.disabled = true; btn.textContent = "Disconnecting…";
    fetch("/quickbooks/disconnect", { method: "POST", credentials: "same-origin" })
      .then(function () { window.location.reload(); })
      .catch(function () { btn.disabled = false; btn.textContent = "Disconnect"; });
  };
  window.__ijQboToggle = function (btn) {
    btn.disabled = true;
    fetch("/quickbooks/sync-toggle", { method: "POST", credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; }).then(function (res) {
        btn.disabled = false;
        if (res) btn.textContent = res.auto_sync_enabled ? "Auto-sync: ON (tap to turn off)" : "Auto-sync: OFF (tap to turn on)";
      }).catch(function () { btn.disabled = false; });
  };
  // READ-ONLY sync: scan QuickBooks invoices, start/clear the 48h clock by BIN-#### match. Never
  // writes to QuickBooks, never charges. Shows a one-line summary on the button.
  window.__ijQboSync = function (btn) {
    btn.disabled = true; btn.textContent = "Syncing…";
    fetch("/quickbooks/sync", { method: "POST", credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; }).then(function (res) {
        btn.disabled = false;
        if (res && res.ok) {
          btn.textContent = "Synced: " + res.started + " clock(s) started, " + res.paid + " marked paid";
        } else {
          btn.textContent = "Sync failed" + (res && res.reason ? (": " + res.reason) : "");
        }
      }).catch(function () { btn.disabled = false; btn.textContent = "Sync QuickBooks now"; });
  };
  function qboSheet(QB) {
    var body;
    if (!QB || !QB.configured) {
      body = '<div class="meta" style="margin-top:10px">QuickBooks isn\'t set up on the server yet (no app credentials).</div>';
    } else if (QB.connected) {
      body = card("<b>Connected</b> &middot; " + esc(QB.company_name || "QuickBooks company")
        + '<div class="meta" style="margin-top:6px;color:#3CA03C;font-weight:700">' + esc(QB.environment) + " &middot; read-only</div>"
        + (QB.connected_by ? ('<div class="meta" style="margin-top:4px">by ' + esc(QB.connected_by) + "</div>") : ""))
        + '<div style="margin-top:9px"><button class="btn2" style="font-size:12.5px;padding:7px 10px" onclick="__ijQboSync(this)">Sync QuickBooks now</button></div>'
        + '<button class="btn2" style="margin-top:9px;font-size:12.5px;padding:7px 10px" onclick="__ijQboToggle(this)">'
        + (QB.auto_sync_enabled ? "Auto-sync: ON (tap to turn off)" : "Auto-sync: OFF (tap to turn on)") + "</button>"
        + '<div style="margin-top:2px"><button class="btn2" style="font-size:12.5px;padding:7px 10px" onclick="__ijQboDisconnect(this)">Disconnect</button></div>';
    } else {
      body = '<div class="meta" style="margin-top:10px">Not connected. Connect your QuickBooks company so the app can watch for invoice-sent + paid &mdash; read-only, it never creates or sends invoices.</div>'
        + '<button class="btn2" style="margin-top:10px" onclick="__ijQboConnect()">Connect QuickBooks (' + esc(QB.environment) + ")</button>";
    }
    window.sheet("QuickBooks",
      '<div class="note" style="margin-top:6px">Read-only sync: detect when you send an invoice (start the 48-hour clock) and when it is paid (clear it). Your manual buttons keep working with this off.</div>'
      + body + '<button class="btn2" onclick="closeSheet()" style="margin-top:12px">Close</button>');
  }

  Promise.all([
    fetch("/invoice-queue", { credentials: "same-origin" }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }),
    fetch("/reminders?kind=cc_charge", { credentials: "same-origin" }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }),
    fetch("/quickbooks/status", { credentials: "same-origin" }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }),
  ]).then(function (out) {
    var Q = out[0], R = out[1], QB = out[2];
    if (typeof OWNER_ALERTS === "undefined") return;
    window.__ijQueue = Q;
    window.__ijAwaiting = (R && R.reminders) || [];
    window.__ijQbo = QB;
    var alerts = [];
    if (QB && QB.configured) {
      alerts.push({ k: "oa_qbo", dot: QB.connected ? "#3CA03C" : "#8a8a8a", nm: "QuickBooks",
        sb: QB.connected ? ((QB.company_name || "Connected") + (QB.auto_sync_enabled ? " · auto-sync ON" : " · manual")) : "Not connected — tap to connect",
        count: "" });
    }
    if (Q && Q.counts.ready > 0) {
      alerts.push({ k: "oa_invoice", dot: "#3CA03C", nm: "Ready to invoice", sb: "Completed jobs, all captured", count: String(Q.counts.ready) });
    }
    if (window.__ijAwaiting.length > 0) {
      alerts.push({ k: "oa_awaiting", dot: "#E8A317", nm: "Bins awaiting payment", sb: "Invoiced · 48-hour clock", count: String(window.__ijAwaiting.length) });
    }
    if (Q && Q.counts.bins_overdue > 0) {
      alerts.push({ k: "oa_bins", dot: "#E8A317", nm: "Bins to bill / overdue", sb: "Out 14+ days", count: String(Q.counts.bins_overdue) });
    }
    OWNER_ALERTS.victoria = alerts;   // replace the demo; unpaid-invoices needs QuickBooks

    var orig = window.ownerAlert;
    window.ownerAlert = function (k) {
      if (k === "oa_qbo") return qboSheet(window.__ijQbo);
      if (k === "oa_invoice" && window.__ijQueue) return invoiceSheet(window.__ijQueue);
      if (k === "oa_awaiting") return awaitingSheet(window.__ijAwaiting);
      if (k === "oa_bins" && window.__ijQueue) return overdueSheet(window.__ijQueue);
      return orig.apply(this, arguments);
    };
    if (typeof renderHub === "function") renderHub();
  }).catch(function () {});
})();
