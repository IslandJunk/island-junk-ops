/* Island Junk — Residential Calculator bridge.
 * Adds a "Send from the Island Junk line" button to the crew's REVIEW modal (the paid-on-
 * site "ask for a review now" step). The prototype's own "Open in Messages" sends from the
 * crew's phone (untrackable); this sends from the updates line via POST /reviews/send, so it's
 * tracked + deduped (the app knows who's already been asked, §11). Additive + best-effort;
 * the approved calculator is untouched.
 */
(function () {
  var trigger = document.getElementById("doMsg");
  if (!trigger) return;

  trigger.addEventListener("click", function () {
    // The prototype rebuilds the modal on click; add our button just after, and only on the
    // REVIEW modal (not the e-Transfer completion — that review is sent later from the board).
    setTimeout(function () {
      var title = (document.getElementById("mTitle") || {}).textContent || "";
      var actions = document.getElementById("mActions");
      if (!actions || !/review/i.test(title) || document.getElementById("mAppReview")) return;

      var name = (document.getElementById("cust") || {}).value || "";
      var crew = "";
      try { if (typeof crewSign === "function") crew = crewSign(); } catch (e) {}

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
    }, 40);
  }, false);
})();
