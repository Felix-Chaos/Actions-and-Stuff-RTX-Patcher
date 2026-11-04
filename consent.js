/* Consent for external content (GDPR / TTDSG §25).
 *
 * Nothing on this site contacts a third party until the visitor agrees:
 * - Crowdin translation badge (badges.crowdin.net)
 * - GIPHY cat GIFs on /uptodate (giphy.com)
 * Fonts are served from this site, so they need no consent.
 *
 * Elements with data-consent-src get their src only after consent.
 * Other scripts can ask window.rtxConsent.granted() / onGrant(fn).
 * The choice is kept in localStorage; "Privacy settings" in the footer
 * (any [data-consent-open]) shows the banner again to change it.
 */
(() => {
  const KEY = "rtx-consent-external";
  const read = () => { try { return localStorage.getItem(KEY); } catch { return null; } };
  const write = (v) => { try { localStorage.setItem(KEY, v); } catch { /* private mode: ask again next time */ } };
  const listeners = [];
  let state = read(); // "yes" | "no" | null

  const apply = () => {
    if (state !== "yes") return;
    document.querySelectorAll("[data-consent-src]").forEach((el) => {
      el.src = el.dataset.consentSrc;
      el.removeAttribute("data-consent-src");
      el.hidden = false;
    });
    while (listeners.length) listeners.shift()();
  };

  window.rtxConsent = {
    granted: () => state === "yes",
    onGrant: (fn) => { if (state === "yes") fn(); else listeners.push(fn); },
    open: () => showBanner(),
  };

  const style = document.createElement("style");
  style.textContent = `
    .consent{position:fixed;left:16px;right:16px;bottom:16px;z-index:9999;max-width:560px;margin:0 auto;
      background:#141414;color:#e5e7eb;border:2px solid #2a2a2a;border-radius:10px;padding:16px 18px;
      box-shadow:0 10px 30px rgba(0,0,0,.5);font:14px/1.5 Inter,system-ui,sans-serif}
    .consent p{margin:0 0 12px}
    .consent a{color:#4ade80}
    .consent__btns{display:flex;gap:10px;flex-wrap:wrap}
    .consent__btns button{font:inherit;font-weight:700;cursor:pointer;border-radius:8px;padding:8px 14px;border:2px solid #0f0f10}
    .consent__yes{background:#22c55e;color:#08210f}
    .consent__no{background:transparent;color:#e5e7eb;border-color:rgba(255,255,255,.2)!important}`;
  document.head.appendChild(style);

  function showBanner() {
    if (document.querySelector(".consent")) return;
    const box = document.createElement("div");
    box.className = "consent";
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-label", "Privacy settings");
    box.innerHTML = `
      <p><strong>External content</strong><br>
      This site uses no tracking or analytics cookies. With your consent it shows the Crowdin translation badge and,
      on the "up to date" page, cat GIFs from GIPHY. Loading them sends your IP address and browser details to
      Crowdin (Estonia) and GIPHY (USA). Your choice is stored only in your browser. Details:
      <a href="https://legal.chaosdev.dev/privacy#rtx-site" target="_blank" rel="noopener">Privacy Policy</a>.</p>
      <div class="consent__btns">
        <button type="button" class="consent__yes">Allow external content</button>
        <button type="button" class="consent__no">Only necessary</button>
      </div>`;
    box.querySelector(".consent__yes").onclick = () => { state = "yes"; write("yes"); box.remove(); apply(); };
    box.querySelector(".consent__no").onclick = () => {
      const revoked = state === "yes";
      state = "no"; write("no"); box.remove();
      if (revoked) location.reload(); // drop already-loaded external content
    };
    document.body.appendChild(box);
  }

  const init = () => {
    document.querySelectorAll("[data-consent-open]").forEach((el) =>
      el.addEventListener("click", (e) => { e.preventDefault(); showBanner(); }));
    if (state === null) showBanner();
    apply();
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
