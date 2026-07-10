/* Island Junk — Main Hub bridge.
 * Injected after the approved main-hub prototype (file untouched). Replaces its
 * client-side PIN check + localStorage session with the real API:
 *   - restore session via GET /auth/me
 *   - PIN login via POST /auth/login (hashed verification, sets the session cookie)
 *   - remap go(prototype.html) -> the served /app/<slug> routes
 *   - sign out via POST /auth/logout
 * The person-picker + access-gated tiles read the real roster (ij_employees_v1, no PINs).
 */
(function () {
  var FILE2SLUG = {
    "island-junk-owner-hub-v54.html": "owner-hub",
    "island-junk-management-hub-v83.html": "manager-hub",
    "island-junk-swing-board-v5.html": "swing-board",
    "island-junk-reminders-v1.html": "reminders",
    "island-junk-estimate-builder-v4.html": "estimate-builder",
    "island-junk-truck-hub-v54.html": "truck-hub",
    "island-junk-yard-processing-v28.html": "yard-processing",
    "island-junk-yard-hub-v19.html": "yard-hub",
    "island-junk-bin-tracker-v34.html": "bin-tracker",
    "island-junk-bin-registry-v6.html": "bin-registry",
    "island-junk-maintenance-hub-v12.html": "maintenance-hub",
    "island-junk-employee-hours-v6.html": "employee-hours",
    "island-junk-clock-out-v9.html": "clock-out",
    "island-junk-incident-report-v2.html": "incident-report",
  };

  // Navigate to the served route (real refs + bridges) instead of the raw prototype file.
  window.go = function (href) {
    var file = String(href || "").split("/").pop();
    var slug = FILE2SLUG[file];
    window.location.href = slug ? ("/app/" + slug) : ("/prototypes/" + file);
  };

  function toUser(j) { return { name: j.name, role: j.role, access: j.access || [], active: true }; }
  function render() { if (typeof window.render === "function") window.render(); }

  // Owner = all-access: the owner outranks the manager PIN, so unlock the PIN-gated hubs
  // (e.g. Manager Hub) for the owner only; restored for anyone else. HUBS is the prototype's
  // tile config — we toggle its `locked` flag without touching the file.
  function applyOwnerUnlock(user) {
    if (typeof HUBS === "undefined") return;
    var isOwner = !!user && (/owner/i.test(user.role || "") || (user.access || []).indexOf("owner") >= 0);
    HUBS.forEach(function (h) {
      if (h._origLocked === undefined) h._origLocked = !!h.locked;
      h.locked = isOwner ? false : h._origLocked;
    });
  }

  // Restore a real session on load.
  fetch("/auth/me", { credentials: "same-origin" })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (j) {
      if (j && typeof S !== "undefined") { S.user = toUser(j); applyOwnerUnlock(S.user); S.screen = "launch"; render(); }
    })
    .catch(function () {});

  // Real PIN login (called by the keypad when 4 digits are entered).
  window.submitPin = function () {
    var pin = S.pin, picked = S.sel;
    fetch("/auth/login", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin: pin, brand: "victoria" }),
    }).then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (!j) { S.err = "Wrong PIN — try again"; S.pin = ""; render(); return; }
        if (picked && j.name !== picked) {   // PIN belongs to a different person
          fetch("/auth/logout", { method: "POST", credentials: "same-origin" });
          S.err = "That PIN isn't " + picked + "'s"; S.pin = ""; render(); return;
        }
        S.user = toUser(j); applyOwnerUnlock(S.user); S.screen = "launch"; S.pin = ""; S.err = ""; render();
      }).catch(function () { S.err = "Login failed — try again"; S.pin = ""; render(); });
  };

  // Real sign out.
  window.signout = function () {
    fetch("/auth/logout", { method: "POST", credentials: "same-origin" })
      .then(function () {
        S = Object.assign(S, { screen: "login", user: null, sel: null, pin: "", err: "" });
        applyOwnerUnlock(null);   // restore the PIN locks for the next (non-owner) user
        render();
      });
  };
})();
