/* Island Junk — Manager Hub bridge.
 * Wires the follow-up-reviews board's "Send review" button to actually SEND (it only
 * marked sent before). POST /reviews/send does the real work — resolves the customer's
 * phone, sends from the updates line, and dedups (never asks a customer twice). The
 * prototype's own mark-sent still runs on success so the board updates instantly.
 * Additive + best-effort; the approved prototype is untouched.
 */
(function () {
  function say(msg) { try { if (typeof toast === "function") return toast(msg); } catch (e) {} alert(msg); }

  if (typeof mhRevSend === "function") {
    var _markSent = mhRevSend;   // prototype: marks reviewSent + re-renders
    window.mhRevSend = function (id) {
      fetch("/reviews/send", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_id: id }),
      }).then(function (r) { return r.ok ? r.json() : null; }).then(function (res) {
        if (!res) { say("Couldn't send the review — try again."); return; }
        if (res.sent) {
          _markSent(id);
          say("✓ Review sent to " + (res.name || "the customer"));
        } else if (res.reason === "already_sent" || res.reason === "customer_already_asked") {
          _markSent(id);   // it IS sent — reflect that on the board
          say((res.name || "This customer") + " was already asked" + (res.at ? " (" + res.at.slice(0, 10) + ")" : "") + ".");
        } else if (res.reason === "no_phone") {
          say("No phone on file for " + (res.name || "this customer") + ". Add their number to send the review.");
        } else {
          say("Couldn't send the review right now.");
        }
      }).catch(function () { say("Couldn't reach the server to send the review."); });
    };
  }
})();
