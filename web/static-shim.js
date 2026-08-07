/* Static-build shim.
 *
 * Lets the exact same frontend run on a plain static host (GitHub Pages) with
 * no Python backend. It intercepts the app's `/api/...` calls: when a real
 * backend answers, nothing changes; when there isn't one, it serves the
 * pre-rendered snapshot from `data/api/<path>.json` instead.
 *
 * Loaded before every other script, so the patch is in place before the first
 * request goes out. Harmless when a backend is present — the real response
 * always wins.
 */
(function () {
  "use strict";

  var orig = window.fetch.bind(window);

  // null = unknown, true = static build (no backend), false = backend present.
  var isStatic = null;

  // /api/summary/2025?x=1  ->  data/api/summary/2025.json   (relative, so it
  // resolves under the repo subpath on Pages, e.g. /F1_ML_project/data/...)
  function staticUrl(url) {
    var i = url.indexOf("/api/");
    if (i < 0) return null;
    var path = url.slice(i + 5).split("?")[0].replace(/\/$/, "");
    return "data/api/" + path + ".json";
  }

  window.fetch = function (input, init) {
    var url = typeof input === "string" ? input : (input && input.url) || "";
    if (url.indexOf("/api/") < 0) return orig(input, init);

    // Only GETs have a snapshot; POSTs (console, racing-line) are backend-only.
    var method = ((init && init.method) ||
      (typeof input === "object" && input.method) || "GET").toUpperCase();
    if (method !== "GET") return orig(input, init);

    // Route deterministically once we know the mode; if the very first calls
    // race the probe, wait for it so we never fire a doomed absolute request.
    if (isStatic === null) return probe.then(function () { return route(input, init, url); });
    return route(input, init, url);
  };

  // Send a GET to the snapshot (static build) or the real backend, with a
  // 404 → snapshot fallback as a safety net.
  function route(input, init, url) {
    if (isStatic) {
      var direct = staticUrl(url);
      if (direct) return orig(direct, { method: "GET" });
    }
    return orig(input, init).then(function (res) {
      if (res.ok) return res;
      var alt = staticUrl(url);
      return alt ? orig(alt, { method: "GET" }) : res;
    }, function (err) {
      var alt = staticUrl(url);
      if (alt) return orig(alt, { method: "GET" });
      throw err;
    });
  }

  // Probe once, eagerly, so `isStatic` is set before the app's first API burst.
  // The live backend answers this with {"static": false}; the pre-rendered
  // build ships a real file saying {"static": true}.
  var probe = orig("data/static.json").then(function (r) {
    return r.ok ? r.json() : { static: false };
  }).then(function (j) {
    isStatic = !!(j && j.static);
    return isStatic;
  }, function () { isStatic = false; return false; });

  // On the static build, tell the user which tabs need the live app.
  function addNotices() {
    if (isStatic !== true) return;
    document.body.setAttribute("data-static", "1");
    var backendOnly = {
      "view-telemetry": "Live telemetry duels need the Python backend.",
      "view-strategy": "Tyre-stint & race-pace data need the Python backend.",
      "view-raceline": "The racing-line analyzer runs OpenCV on the backend.",
      "view-console": "The command console is disabled on the public build."
    };
    Object.keys(backendOnly).forEach(function (id) {
      var view = document.getElementById(id);
      if (!view || view.querySelector(".static-note")) return;
      var note = document.createElement("div");
      note.className = "static-note";
      note.setAttribute("role", "note");
      note.innerHTML = "<strong>Backend feature.</strong> " +
        backendOnly[id] +
        " Run it locally with <code>f1ml serve</code> — everything else here " +
        "(standings, model, predictions, the weekend hub) is live from the snapshot.";
      var head = view.querySelector(".section-head");
      if (head && head.nextSibling) view.insertBefore(note, head.nextSibling);
      else view.appendChild(note);
    });
  }

  function whenReady() { probe.then(addNotices); }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", whenReady);
  } else {
    whenReady();
  }
})();
