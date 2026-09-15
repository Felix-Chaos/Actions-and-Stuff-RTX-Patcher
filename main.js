// A&S RTX Patcher site: release lookup, channel switch, showcase player, lightbox and nav.
(() => {
  const REPO = "Felix-Chaos/Actions-and-Stuff-RTX-Patcher";
  const RELEASES_URL = `https://github.com/${REPO}/releases`;
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

  /* ---------- Active nav tab while scrolling ---------- */
  const navTabs = [...document.querySelectorAll('.nav-tab[href^="#"]')];
  const sections = navTabs.map((a) => document.querySelector(a.getAttribute("href"))).filter(Boolean);
  if ("IntersectionObserver" in window) {
    const spy = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        navTabs.forEach((a) => a.classList.toggle("active", a.getAttribute("href") === `#${entry.target.id}`));
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
    document.querySelectorAll(".section__head, .feature, .repo, .person, .step, .phases li, .pipeline")
      .forEach((el) => { el.classList.add("reveal"); reveal.observe(el); });
  }

  /* ---------- Showcase video picker ---------- */
  const video = document.getElementById("player-video");
  const pickers = document.querySelectorAll(".video-picker__item");
  pickers.forEach((btn) => {
    btn.addEventListener("click", () => {
      pickers.forEach((b) => b.classList.toggle("is-active", b === btn));
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

  /* ---------- Releases & channel switch ---------- */
  const $ = (key) => document.querySelector(`[data-release="${key}"]`);
  const channelButtons = document.querySelectorAll(".switch-option[data-channel]");
  const channels = { stable: null, beta: null };

  // Prefer the NSIS installer, then the MSI, then any Windows binary.
  const pickInstaller = (release) => {
    const assets = release.assets || [];
    return assets.find((a) => /-setup\.exe$/i.test(a.name))
      || assets.find((a) => /\.msi$/i.test(a.name))
      || assets.find((a) => /\.exe$/i.test(a.name))
      || null;
  };
  const pickPortable = (release) => (release.assets || []).find((a) => /portable.*\.zip$/i.test(a.name)) || null;

  const formatDate = (iso) => {
    try {
      return new Date(iso).toLocaleDateString("en-GB", { year: "numeric", month: "short", day: "numeric" });
    } catch { return ""; }
  };

  const showChannel = (name) => {
    const release = channels[name];
    if (!release) return;

    channelButtons.forEach((b) => {
      const on = b.dataset.channel === name;
      b.classList.toggle("active", on);
      b.setAttribute("aria-checked", String(on));
    });

    const installer = pickInstaller(release);
    const portable = pickPortable(release);

    $("version").textContent = release.tag_name;
    const kind = !installer ? "" : /-setup\.exe$/i.test(installer.name) ? "Setup .exe" : /\.msi$/i.test(installer.name) ? ".msi installer" : ".exe";
    $("details").textContent = [formatDate(release.published_at), kind].filter(Boolean).join(" · ");
    $("download").href = installer ? installer.browser_download_url : release.html_url;
    $("download-label").textContent = name === "beta" ? "Download Beta for Windows" : "Download for Windows";
    $("beta-warning").hidden = name !== "beta";

    const portableLink = $("portable");
    portableLink.hidden = !portable;
    if (portable) portableLink.href = portable.browser_download_url;
  };

  channelButtons.forEach((b) => b.addEventListener("click", () => { if (!b.disabled) showChannel(b.dataset.channel); }));

  const render = (releases) => {
    const published = releases.filter((r) => !r.draft);
    const stable = published.find((r) => !r.prerelease) || null;
    const beta = published.find((r) => r.prerelease) || null;
    const status = $("status");

    if (!stable && !beta) {
      status.className = "update-badge state-error";
      status.textContent = "No releases";
      $("details").textContent = "";
      return;
    }

    channels.stable = stable || beta;
    // Offer the beta channel only when it is newer than the stable build.
    const betaIsNewer = stable && beta && new Date(beta.published_at) > new Date(stable.published_at);
    channels.beta = betaIsNewer ? beta : null;

    const betaButton = document.querySelector('.switch-option[data-channel="beta"]');
    betaButton.disabled = !channels.beta;
    betaButton.title = channels.beta ? `Pre-release ${channels.beta.tag_name}` : "No newer beta build right now";

    status.className = channels.beta ? "update-badge state-available" : "update-badge state-uptodate";
    status.textContent = channels.beta ? "Beta available" : "Latest";

    const navVersion = $("nav-version");
    navVersion.textContent = channels.stable.tag_name;
    navVersion.hidden = false;

    const navInstaller = pickInstaller(channels.stable);
    if (navInstaller) $("nav-download").href = navInstaller.browser_download_url;

    showChannel("stable");
  };

  const renderOffline = () => {
    const status = $("status");
    status.className = "update-badge state-error";
    status.textContent = "Offline";
    $("version").textContent = "Latest";
    $("details").textContent = "Couldn't reach GitHub, the buttons open the releases page.";
    $("download").href = RELEASES_URL + "/latest";
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
      .catch(renderOffline);
  }
})();
