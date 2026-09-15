// A&S RTX Patcher site: nav, scroll spy, release lookup, channel switch, showcase player,
// lightbox and the wiki's mode tabs. Every feature checks its elements exist, so the same
// script serves index.html and wiki.html.
(() => {
  const REPO = "Felix-Chaos/Actions-and-Stuff-RTX-Patcher";
  const RELEASES_URL = `https://github.com/${REPO}/releases`;
  const CACHE_KEY = "asrtx-releases";
  const CACHE_TTL = 30 * 60 * 1000;
  const hasObserver = "IntersectionObserver" in window;

  /* ---------- Mobile navigation ---------- */
  const toggle = document.querySelector(".nav__toggle");
  const menu = document.getElementById("nav-menu");
  if (toggle && menu) {
    const setMenu = (open) => {
      menu.classList.toggle("is-open", open);
      toggle.setAttribute("aria-expanded", String(open));
      toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    };
    toggle.addEventListener("click", () => setMenu(!menu.classList.contains("is-open")));
    menu.addEventListener("click", (e) => { if (e.target.closest("a")) setMenu(false); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") setMenu(false); });
  }

  /* ---------- Scroll spy: highlight the link of the section in view ---------- */
  const spyOn = (links, { rootMargin, onChange } = {}) => {
    const targets = links.map((a) => document.querySelector(a.getAttribute("href"))).filter(Boolean);
    if (!hasObserver || !targets.length) return;
    const spy = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const hash = `#${entry.target.id}`;
        links.forEach((a) => a.classList.toggle("active", a.getAttribute("href") === hash));
        if (onChange) onChange(hash);
      });
    }, { rootMargin: rootMargin || "-45% 0px -50% 0px" });
    targets.forEach((t) => spy.observe(t));
  };

  spyOn([...document.querySelectorAll('#nav-menu .nav-tab[href^="#"]')]);

  /* ---------- Reveal on scroll ---------- */
  if (hasObserver) {
    const reveal = new IntersectionObserver((entries, obs) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        obs.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -8% 0px" });
    document.querySelectorAll(".section__head, .feature, .repo, .person, .step, .phases li, .pipeline, .wiki-section")
      .forEach((el) => { el.classList.add("reveal"); reveal.observe(el); });
  }

  /* ---------- Showcase video picker ---------- */
  const video = document.getElementById("player-video");
  const pickers = document.querySelectorAll(".video-picker__item");
  if (video) {
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
  }

  /* ---------- Screenshot lightbox ---------- */
  const lightbox = document.getElementById("lightbox");
  const lightboxImg = document.getElementById("lightbox-img");
  if (lightbox && lightboxImg) {
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
  }

  /* ---------- Wiki: table of contents ---------- */
  const toc = document.querySelector(".wiki-toc");
  if (toc) {
    const tocLinks = [...toc.querySelectorAll('a[href^="#"]')];
    const mobile = window.matchMedia("(max-width: 960px)");
    // Collapsed by default on small screens, where it sits above the content.
    const syncToc = () => { toc.open = !mobile.matches; };
    syncToc();
    mobile.addEventListener("change", syncToc);
    toc.addEventListener("click", (e) => { if (e.target.closest("a") && mobile.matches) toc.open = false; });

    spyOn(tocLinks, {
      rootMargin: "-20% 0px -70% 0px",
      // A sub-section also keeps its parent "Tools Reference" tab highlighted.
      onChange: (hash) => {
        const sub = toc.querySelector(`.nav-subtab[href="${hash}"]`);
        if (sub) toc.querySelector('.nav-tab[href="#tools"]').classList.add("active");
      },
    });
  }

  /* ---------- Wiki: patch mode tabs (the patcher's mode radio cards) ---------- */
  const modeTabs = [...document.querySelectorAll('.mode-toggle-group [role="tab"]')];
  if (modeTabs.length) {
    const select = (tab, focus) => {
      modeTabs.forEach((t) => {
        const on = t === tab;
        t.classList.toggle("is-selected", on);
        t.setAttribute("aria-selected", String(on));
        t.tabIndex = on ? 0 : -1;
        document.getElementById(t.getAttribute("aria-controls")).hidden = !on;
      });
      if (focus) tab.focus();
    };
    modeTabs.forEach((tab, i) => {
      tab.addEventListener("click", () => select(tab));
      tab.addEventListener("keydown", (e) => {
        const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
        if (!step) return;
        e.preventDefault();
        select(modeTabs[(i + step + modeTabs.length) % modeTabs.length], true);
      });
    });
    select(modeTabs.find((t) => t.classList.contains("is-selected")) || modeTabs[0]);
  }

  /* ---------- Releases & channel switch ---------- */
  const $ = (key) => document.querySelector(`[data-release="${key}"]`);
  const setText = (key, text) => { const el = $(key); if (el) el.textContent = text; };
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
    if (!release || !$("download")) return;

    channelButtons.forEach((b) => {
      const on = b.dataset.channel === name;
      b.classList.toggle("active", on);
      b.setAttribute("aria-checked", String(on));
    });

    const installer = pickInstaller(release);
    const portable = pickPortable(release);
    const kind = !installer ? "" : /-setup\.exe$/i.test(installer.name) ? "Setup .exe" : /\.msi$/i.test(installer.name) ? ".msi installer" : ".exe";

    setText("version", release.tag_name);
    setText("details", [formatDate(release.published_at), kind].filter(Boolean).join(" · "));
    setText("download-label", name === "beta" ? "Download Beta for Windows" : "Download for Windows");
    $("download").href = installer ? installer.browser_download_url : release.html_url;
    $("beta-warning").hidden = name !== "beta";

    const portableLink = $("portable");
    portableLink.hidden = !portable;
    if (portable) portableLink.href = portable.browser_download_url;
  };

  channelButtons.forEach((b) => b.addEventListener("click", () => { if (!b.disabled) showChannel(b.dataset.channel); }));

  const setStatus = (state, text) => {
    const status = $("status");
    if (!status) return;
    status.className = `update-badge state-${state}`;
    status.textContent = text;
  };

  const render = (releases) => {
    const published = releases.filter((r) => !r.draft);
    const stable = published.find((r) => !r.prerelease) || null;
    const beta = published.find((r) => r.prerelease) || null;

    if (!stable && !beta) {
      setStatus("error", "No releases");
      setText("details", "");
      return;
    }

    channels.stable = stable || beta;
    // Offer the beta channel only when it is newer than the stable build.
    const betaIsNewer = stable && beta && new Date(beta.published_at) > new Date(stable.published_at);
    channels.beta = betaIsNewer ? beta : null;

    const betaButton = document.querySelector('.switch-option[data-channel="beta"]');
    if (betaButton) {
      betaButton.disabled = !channels.beta;
      betaButton.title = channels.beta ? `Pre-release ${channels.beta.tag_name}` : "No newer beta build right now";
    }
    setStatus(channels.beta ? "available" : "uptodate", channels.beta ? "Beta available" : "Latest");

    const navVersion = $("nav-version");
    if (navVersion) {
      navVersion.textContent = channels.stable.tag_name;
      navVersion.hidden = false;
    }
    const navInstaller = pickInstaller(channels.stable);
    if (navInstaller && $("nav-download")) $("nav-download").href = navInstaller.browser_download_url;

    showChannel("stable");
  };

  const renderOffline = () => {
    setStatus("error", "Offline");
    setText("version", "Latest");
    setText("details", "Couldn't reach GitHub, the buttons open the releases page.");
    if ($("download")) $("download").href = RELEASES_URL + "/latest";
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
