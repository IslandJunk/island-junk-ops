/* Island Junk — Save-card bridge (WS3 card-on-file capture).
 * Loads Square's Web Payments SDK, renders Square's OWN secure card field (an iframe — the raw
 * card never touches us), and on save tokenizes -> POST /square/save-card. The app stores only
 * the returned token + brand/last4 (never the PAN/CVV). Sandbox vs production SDK is chosen from
 * /square/status. No astral emojis anywhere (they corrupt to lone surrogates on serve here).
 */
(function () {
  var statusEl = document.getElementById("ij-card-status");
  var saveBtn = document.getElementById("ij-save");
  var resultEl = document.getElementById("ij-result");

  function say(msg, cls) {
    if (!resultEl) return;
    resultEl.textContent = msg || "";
    resultEl.className = "result" + (cls ? " " + cls : "");
  }
  function cardStatus(msg) { if (statusEl) statusEl.textContent = msg; }

  fetch("/square/status", { credentials: "same-origin" })
    .then(function (r) {
      if (r.status === 401 || r.status === 403) return { __notauth: true };
      return r.ok ? r.json() : null;
    })
    .then(function (st) {
      if (st && st.__notauth) {
        cardStatus("Please sign in first — open the Main Hub, log in, then reopen this page.");
        return;
      }
      if (!st || !st.configured || !st.application_id || !st.location_id) {
        cardStatus("Square isn't connected yet — a card can't be saved until it is.");
        return;
      }
      var sdkUrl = (st.environment === "production")
        ? "https://web.squarecdn.com/v1/square.js"
        : "https://sandbox.web.squarecdn.com/v1/square.js";
      var s = document.createElement("script");
      s.src = sdkUrl;
      s.onload = function () { initSquare(st.application_id, st.location_id); };
      s.onerror = function () { cardStatus("Couldn't load Square's card field. Check the connection and reload."); };
      document.head.appendChild(s);
    })
    .catch(function () { cardStatus("Couldn't reach the server."); });

  function initSquare(appId, locId) {
    if (!window.Square) { cardStatus("Square SDK didn't load."); return; }
    var payments;
    try { payments = window.Square.payments(appId, locId); }
    catch (e) { cardStatus("Square init failed: " + (e && e.message)); return; }
    payments.card().then(function (card) {
      return card.attach("#ij-card-container").then(function () { return card; });
    }).then(function (card) {
      if (statusEl && statusEl.parentNode) statusEl.parentNode.removeChild(statusEl); // clear the "loading" note
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.addEventListener("click", function () { saveCard(card); });
      }
    }).catch(function (e) { cardStatus("Card field error: " + (e && e.message)); });
  }

  function saveCard(card) {
    var nameEl = document.getElementById("ij-cust");
    var authEl = document.getElementById("ij-auth");
    var name = nameEl ? (nameEl.value || "").trim() : "";
    if (!name) { say("Enter the customer's name first.", "warn"); if (nameEl) nameEl.focus(); return; }
    if (authEl && !authEl.checked) { say("Please confirm the customer authorized card-on-file.", "warn"); return; }
    saveBtn.disabled = true;
    saveBtn.textContent = "Saving…";
    say("");
    card.tokenize().then(function (result) {
      if (result.status !== "OK") {
        var m = (result.errors && result.errors[0] && result.errors[0].message) || "Card entry isn't complete.";
        throw new Error(m);
      }
      return fetch("/square/save-card", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: result.token, customer_name: name,
          auth_note: "Authorized card-on-file + 48h charge (+2.4%)" }),
      });
    }).then(function (r) { return r.ok ? r.json() : null; }).then(function (res) {
      if (res && res.saved) {
        say("Card saved: " + (res.brand || "card") + " " + String.fromCharCode(8226, 8226) + (res.last4 || "")
          + " on file for " + name + ".", "ok");
        saveBtn.textContent = "Saved";
      } else {
        saveBtn.disabled = false; saveBtn.textContent = "Save card on file";
        say("Couldn't save the card — try again.", "warn");
      }
    }).catch(function (e) {
      saveBtn.disabled = false; saveBtn.textContent = "Save card on file";
      say((e && e.message) || "Card error — try again.", "warn");
    });
  }
})();
