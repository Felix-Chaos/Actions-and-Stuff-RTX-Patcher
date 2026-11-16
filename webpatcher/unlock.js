// Web Patcher preview switch, shared by the homepage and /webpatcher/.
// Open any page once with ?webpatcher=<token> to unlock this browser,
// ?webpatcher=0 to lock it again. Only the token's SHA-256 is in the source.
// A convenience gate for testers, not access control: the files are public.
(() => {
  const HASH = "bca9046e22c36436ac5294fb3fa2ae4dc949384cb34eadd7e3248ad0d5745db6";
  const KEY = "rtx-webpatcher";

  const sha256 = async (text) => {
    const d = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text)));
    return Array.from(d, (b) => b.toString(16).padStart(2, "0")).join("");
  };
  const store = {
    get: () => { try { return localStorage.getItem(KEY); } catch (_) { return null; } },
    set: (v) => { try { localStorage.setItem(KEY, v); } catch (_) {} },
    del: () => { try { localStorage.removeItem(KEY); } catch (_) {} },
  };

  window.rtxWebPatcherUnlocked = (async () => {
    if (!window.crypto || !crypto.subtle) return false;
    const url = new URL(location.href);
    const q = url.searchParams.get("webpatcher");
    if (q !== null) {
      if (q === "0") store.del();
      else if ((await sha256(q)) === HASH) store.set(q);
      // Keep the token out of the address bar, history and shared links.
      url.searchParams.delete("webpatcher");
      history.replaceState(history.state, "", url.pathname + url.search + url.hash);
    }
    const saved = store.get();
    if (!saved) return false;
    if ((await sha256(saved)) === HASH) return true;
    store.del(); // stale token from an older build, or the old "1" flag
    return false;
  })().catch(() => false);
})();
