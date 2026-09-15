// A&S RTX Patcher site: release lookup, showcase player, lightbox and nav.
(() => {
  const REPO = "Felix-Chaos/Actions-and-Stuff-RTX-Patcher";
  const CACHE_KEY = "asrtx-releases";
  const CACHE_TTL = 30 * 60 * 1000;

  /* ---------- Mobile navigation ---------- */
  const toggle = document.querySelector(".nav__toggle");
  const menu = document.getElementById("nav-menu");
  const setMenu = (open) => {
    menu.classList.toggle("is-open", open);
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
  };
  toggle.addEventListener("click", () => setMenu(!menu.classList.contains("is-open")));
  menu.addEventListener("click", (e) => { if (e.target.closest("a")) setMenu(false); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") setMenu(false); });

  /* ---------- Active nav link while scrolling ---------- */
  const navLinks = [...document.querySelectorAll('.nav-link[href^="#"]')];
  const sections = navLinks.map((a) => document.querySelector(a.getAttribute("href"))).filter(Boolean);
  if ("IntersectionObserver" in window) {
    const spy = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        navLinks.forEach((a) => a.classList.toggle("nav-link--active", a.getAttribute("href") === `#${entry.target.id}`));
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    sections.forEach((s) => spy.observe(s));

    const reveal = new IntersectionObserver((entries, obs) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        obs.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -8% 0px" });
    document.querySelectorAll(".section__head, .card, .repo, .person, .step, .phases li, .pipeline")
      .forEach((el) => { el.classList.add("reveal"); reveal.observe(el); });
  }

  /* ---------- Showcase video picker ---------- */
  const video = document.getElementById("player-video");
  document.querySelectorAll(".video-picker__item").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".video-picker__item").forEach((b) => b.classList.toggle("is-active", b === btn));
      if (video.getAttribute("src") !== btn.dataset.src) {
        video.poster = btn.dataset.poster;
        video.src = btn.dataset.src;
      }
      video.play().catch(() => {});
    });
  });

  /* ---------- Screenshot lightbox ---------- */
  const lightbox = document.getElementById("lightbox");
  const lightboxImg = document.getElementById("lightbox-img");
  document.querySelectorAll(".gallery__item").forEach((btn) => {
    btn.addEventListener("click", () => {
      const img = btn.querySelector("img");
      lightboxImg.src = btn.dataset.full;
      lightboxImg.alt = img ? img.alt : "";
      if (typeof lightbox.showModal === "function") lightbox.showModal();
      else window.open(btn.dataset.full, "_blank", "noopener");
    });
  });
  lightbox.addEventListener("click", (e) => { if (e.target === lightbox) lightbox.close(); });

  /* ---------- Latest release lookup ---------- */
  const $ = (key) => document.querySelector(`[data-release="${key}"]`);

  // Prefer the NSIS installer, then the MSI, then any Windows binary.
  const pickAsset = (release) => {
    const assets = release.assets || [];
    return assets.find((a) => /-setup\.exe$/i.test(a.name))
      || assets.find((a) => /\.msi$/i.test(a.name))
      || assets.find((a) => /\.exe$/i.test(a.name))
      || null;
  };

  const formatDate = (iso) => {
    try {
      return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
    } catch { return ""; }
  };

  const render = (releases) => {
    const published = releases.filter((r) => !r.draft);
    const stable = published.find((r) => !r.prerelease);
    const beta = published.find((r) => r.prerelease);
    const main = stable || beta;
    if (!main) return;

    const asset = pickAsset(main);
    $("version").textContent = main.tag_name;
    $("date").textContent = formatDate(main.published_at);
    $("download").href = asset ? asset.browser_download_url : main.html_url;
    if (!stable) $("download-label").textContent = "Download beta for Windows";

    // Only surface the beta when it is newer than the stable build.
    if (stable && beta && new Date(beta.published_at) > new Date(stable.published_at)) {
      const betaAsset = pickAsset(beta);
      const link = $("beta");
      link.href = betaAsset ? betaAsset.browser_download_url : beta.html_url;
      link.textContent = `Beta ${beta.tag_name}`;
      link.title = "Newer pre-release build, may contain bugs";
      link.hidden = false;
    }
  };

  const readCache = () => {
    try {
      const cached = JSON.parse(sessionStorage.getItem(CACHE_KEY) || "null");
      return cached && Date.now() - cached.time < CACHE_TTL ? cached.data : null;
    } catch { return null; }
  };
  const writeCache = (data) => {
    try { sessionStorage.setItem(CACHE_KEY, JSON.stringify({ time: Date.now(), data })); } catch { /* storage unavailable */ }
  };

  const cached = readCache();
  if (cached) {
    render(cached);
  } else {
    fetch(`https://api.github.com/repos/${REPO}/releases?per_page=15`, { headers: { Accept: "application/vnd.github+json" } })
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then((data) => {
        // Keep only the fields the page needs so the cache stays small.
        const slim = data.map((r) => ({
          tag_name: r.tag_name, draft: r.draft, prerelease: r.prerelease,
          published_at: r.published_at, html_url: r.html_url,
          assets: (r.assets || []).map((a) => ({ name: a.name, browser_download_url: a.browser_download_url })),
        }));
        writeCache(slim);
        render(slim);
      })
      // Offline or rate-limited: the static links to /releases/latest still work.
      .catch(() => {});
  }
})();
