/* Island Junk — Residential Calculator bridge.
 * Adds two "send from the Island Junk updates line" buttons to the crew's completion modal,
 * so a customer text is tracked + sent from the app instead of the crew's own phone:
 *
 *   1. REVIEW modal (paid-on-site "ask for a review now") → POST /reviews/send (tracked +
 *      deduped, §11).
 *   2. e-TRANSFER modal (the completion text: price + GST + e-transfer email) → POST
 *      /sms/completion (spec §2). The calc has no phone field, so we add a confirm-number
 *      input; if left blank the server resolves the number by a unique customer-name match.
 *
 * Both are additive + best-effort; the approved calculator (incl. its own "Open in Messages"
 * fallback) is untouched. The prototype rebuilds the modal on each #doMsg click, so we run
 * just after and add our control only on the matching modal.
 */
(function () {
  var trigger = document.getElementById("doMsg");
  if (!trigger) return;

  // The finished calc totals, from the prototype's own globals (classic script, shared scope).
  function calcTotals() {
    try {
      var r = (typeof mdFinished !== "undefined" && mdFinished) ? mdFinished
            : (typeof calc === "function" ? calc() : null);
      if (r) return r;   // {sub, gst, fee, total, ccOn}
    } catch (e) {}
    return null;
  }
  function etransferEmail() { try { return (typeof ETRANSFER !== "undefined" && ETRANSFER) || ""; } catch (e) { return ""; } }
  function crewName() { try { return (typeof crewSign === "function") ? (crewSign() || "") : ""; } catch (e) { return ""; } }
  function custName() { var el = document.getElementById("cust"); return el ? (el.value || "").trim() : ""; }

  // ---- REVIEW modal (unchanged behaviour) ----------------------------------------------
  function addReviewButton(actions) {
    if (document.getElementById("mAppReview")) return;
    var name = custName(), crew = crewName();
    var b = document.createElement("button");
    b.id = "mAppReview";
    b.className = "send";
    b.textContent = "📱 Send review from the Island Junk line";
    b.style.cssText = "margin-bottom:8px";
    b.addEventListener("click", function () {
      b.disabled = true;
      b.textContent = "Sending…";
      fetch("/reviews/send", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name, account: "residential", crew: crew }),
      }).then(function (r) { return r.ok ? r.json() : null; }).then(function (res) {
        if (res && res.sent) { b.textContent = "✓ Review sent to " + (res.name || "the customer"); }
        else if (res && (res.reason === "already_sent" || res.reason === "customer_already_asked")) {
          b.textContent = "✓ Already asked (won't re-send)";
        } else if (res && res.reason === "no_phone") {
          b.disabled = false;
          b.textContent = "No number on file — use Messages instead";
        } else { b.disabled = false; b.textContent = "Couldn't send — try again"; }
      }).catch(function () { b.disabled = false; b.textContent = "Couldn't reach the server"; });
    });
    actions.insertBefore(b, actions.firstChild);
  }

  // ---- e-TRANSFER completion modal (new) -----------------------------------------------
  function addCompletionButton(actions) {
    if (document.getElementById("mAppComplete")) return;
    var totals = calcTotals();
    if (!totals) return;   // nothing priced yet — leave the modal as the prototype built it
    var name = custName(), crew = crewName(), etransfer = etransferEmail();

    var wrap = document.createElement("div");
    wrap.id = "mAppComplete";
    wrap.style.cssText = "margin-bottom:10px";

    var phone = document.createElement("input");
    phone.id = "mAppPhone";
    phone.type = "tel";
    phone.placeholder = "Customer's mobile # (to text it now)";
    phone.autocomplete = "off";
    phone.style.cssText = "width:100%;box-sizing:border-box;padding:12px;border:1.5px solid #d8d3cc;border-radius:12px;font-size:15px;margin-bottom:6px";

    var b = document.createElement("button");
    b.id = "mAppCompleteBtn";
    b.className = "send";
    b.style.cssText = "width:100%";
    b.textContent = "📱 Text the e-Transfer info from the Island Junk line";

    var note = document.createElement("div");
    note.style.cssText = "font-size:12px;color:#8a857e;margin-top:5px";
    note.textContent = "Leave the number blank to reach a saved customer by name.";

    b.addEventListener("click", function () {
      b.disabled = true;
      b.textContent = "Sending…";
      fetch("/sms/completion", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name,
          phone: (phone.value || "").trim(),
          total: totals.total,
          gst: totals.gst,
          subtotal: totals.sub,
          card_fee: totals.ccOn ? totals.fee : null,
          etransfer_email: etransfer,
        }),
      }).then(function (r) { return r.ok ? r.json() : null; }).then(function (res) {
        if (res && res.sent) { phone.style.display = "none"; note.style.display = "none"; b.textContent = "✓ Texted the customer"; }
        else if (res && res.dry_run) { b.textContent = "✓ Composed (texting not live yet)"; }
        else if (res && res.skipped === "opted_out") { b.textContent = "Customer opted out of texts"; }
        else if (res && res.reason === "no_phone") {
          b.disabled = false;
          b.textContent = "Enter the customer's number above";
          phone.focus();
        } else { b.disabled = false; b.textContent = "Couldn't send — try again"; }
      }).catch(function () { b.disabled = false; b.textContent = "Couldn't reach the server"; });
    });

    wrap.appendChild(phone);
    wrap.appendChild(b);
    wrap.appendChild(note);
    // Insert above the prototype's own action row (Open in Messages / Copy / Close).
    actions.parentNode.insertBefore(wrap, actions);
  }

  trigger.addEventListener("click", function () {
    // The prototype rebuilds the modal on click; add our control just after it settles.
    setTimeout(function () {
      var title = (document.getElementById("mTitle") || {}).textContent || "";
      var actions = document.getElementById("mActions");
      if (!actions) return;
      // Our completion block is a SIBLING of #mActions, so the prototype's innerHTML rebuild
      // of #mActions doesn't clear it — remove any stale one before deciding what to add, so
      // it can't leak onto the review modal. (The review button lives inside #mActions, which
      // the prototype always resets, so it cleans itself up.)
      var stale = document.getElementById("mAppComplete");
      if (stale) stale.remove();
      if (/review/i.test(title)) addReviewButton(actions);
      else if (/e-?transfer/i.test(title)) addCompletionButton(actions);
    }, 40);
  }, false);
})();
