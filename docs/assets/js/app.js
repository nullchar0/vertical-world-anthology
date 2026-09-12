(() => {
  const I18N = {
    ru: {
      brand: "Вертикальный мир",
      brandSub: "Антология 1900–2026",
      loading: "Загрузка…",
      toc: "Оглавление",
      footerCredits:
        "Портреты показываются только при лицензии, допускающей повторное использование. У каждого изображения указаны автор/правообладатель и ссылка на первоисточник.",
      footerMedia: "Каталог медиа: ",
      noPortrait: "Нет свободного портрета",
      creditPrefix: "Источник",
      licensePrefix: "Лицензия",
      close: "Закрыть",
      enlarge: "Открыть портрет крупнее",
    },
    en: {
      brand: "Vertical World",
      brandSub: "Anthology 1900–2026",
      loading: "Loading…",
      toc: "Contents",
      footerCredits:
        "Portraits appear only when a license allows reuse. Each image shows credit and a link to the original source.",
      footerMedia: "Media catalog: ",
      noPortrait: "No freely licensed portrait",
      creditPrefix: "Source",
      licensePrefix: "License",
      close: "Close",
      enlarge: "View larger portrait",
    },
  };

  const state = {
    lang: localStorage.getItem("vw-lang") || detectLang(),
    catalog: {},
    people: [],
    lastFocus: null,
  };

  const lightbox = document.getElementById("lightbox");
  const lightboxImg = document.getElementById("lightbox-img");
  const lightboxMeta = document.getElementById("lightbox-meta");
  const lightboxClose = document.getElementById("lightbox-close");

  function detectLang() {
    const q = new URLSearchParams(location.search).get("lang");
    if (q === "ru" || q === "en") return q;
    return (navigator.language || "en").toLowerCase().startsWith("ru") ? "ru" : "en";
  }

  function applyChrome() {
    const t = I18N[state.lang];
    document.documentElement.lang = state.lang;
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (!t[key]) return;
      el.textContent = t[key];
    });
    document.querySelectorAll(".lang-btn").forEach((btn) => {
      btn.setAttribute("aria-pressed", String(btn.dataset.lang === state.lang));
    });
    const url = new URL(location.href);
    url.searchParams.set("lang", state.lang);
    history.replaceState(null, "", url);
  }

  function wikiKeyFromHref(href) {
    try {
      const u = new URL(href);
      if (!u.hostname.includes("wikipedia.org")) return null;
      let title = u.pathname.split("/wiki/")[1];
      if (!title) return null;
      title = decodeURIComponent(title.split("#")[0]);
      return "wiki:" + title;
    } catch {
      return null;
    }
  }

  function findPortrait(href) {
    const key = wikiKeyFromHref(href);
    if (key && state.catalog[key]) return state.catalog[key];
    const byUrl = state.people.find((p) => (p.urls || []).includes(href));
    if (byUrl && state.catalog[byUrl.id]) return state.catalog[byUrl.id];
    if (byUrl && byUrl.slug && state.catalog["slug:" + byUrl.slug]) {
      return state.catalog["slug:" + byUrl.slug];
    }
    return null;
  }

  function creditHTML(meta) {
    const t = I18N[state.lang];
    const credit = meta.artist || meta.credit || "Unknown";
    const source = meta.source_url || meta.commons_url || "#";
    const license = meta.license || meta.license_short || "";
    const licenseUrl = meta.license_url || "";
    const licenseBit = license
      ? ` · ${t.licensePrefix}: ${
          licenseUrl
            ? `<a href="${licenseUrl}" target="_blank" rel="noopener noreferrer">${escapeHtml(license)}</a>`
            : escapeHtml(license)
        }`
      : "";
    return `${t.creditPrefix}: ${escapeHtml(credit)}
      · <a href="${source}" target="_blank" rel="noopener noreferrer">original</a>${licenseBit}`;
  }

  function portraitHTML(meta) {
    const t = I18N[state.lang];
    if (!meta || !meta.file) {
      return `<div class="portrait-missing">${t.noPortrait}</div>`;
    }
    return `<figure class="portrait">
      <button type="button" class="portrait-zoom" data-full="${escapeHtml(meta.file)}" aria-label="${t.enlarge}">
        <img src="${meta.file}" alt="" loading="lazy" decoding="async" />
      </button>
      <figcaption>${creditHTML(meta)}</figcaption>
    </figure>`;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function openLightbox(src, captionHTML) {
    state.lastFocus = document.activeElement;
    lightboxImg.src = src;
    lightboxMeta.innerHTML = captionHTML || "";
    lightbox.hidden = false;
    document.body.classList.add("lightbox-open");
    lightboxClose.focus();
  }

  function closeLightbox() {
    if (lightbox.hidden) return;
    lightbox.hidden = true;
    document.body.classList.remove("lightbox-open");
    lightboxImg.removeAttribute("src");
    lightboxMeta.innerHTML = "";
    if (state.lastFocus && typeof state.lastFocus.focus === "function") {
      state.lastFocus.focus();
    }
  }

  function enhancePersonBlocks(root) {
    const nodes = [...root.querySelectorAll("p, li")];
    nodes.forEach((node) => {
      const first = node.querySelector(":scope > strong > a, :scope > a");
      if (!first) return;
      const href = first.getAttribute("href") || "";
      const looksPerson =
        href.includes("wikipedia.org") ||
        href.includes("alpklubspb") ||
        href.includes("russianclimb") ||
        href.includes("babanov.com");
      if (!looksPerson) return;
      if (node.closest(".person-card")) return;

      const meta = findPortrait(href);
      const card = document.createElement("div");
      card.className = "person-card";
      const media = document.createElement("div");
      media.innerHTML = portraitHTML(meta);
      const body = document.createElement("div");
      body.className = "person-body";
      node.parentNode.insertBefore(card, node);
      body.appendChild(node);
      card.appendChild(media);
      card.appendChild(body);
    });
  }

  function buildToc(root, tocEl) {
    tocEl.innerHTML = "";
    root.querySelectorAll("h2").forEach((h, i) => {
      if (!h.id) h.id = "sec-" + i;
      const a = document.createElement("a");
      a.href = "#" + h.id;
      a.textContent = h.textContent;
      tocEl.appendChild(a);
    });
  }

  async function loadMarkdown() {
    const res = await fetch(`content/${state.lang}.md`);
    if (!res.ok) throw new Error("Failed to load content");
    return res.text();
  }

  async function loadMedia() {
    const [catalogRes, peopleRes] = await Promise.all([
      fetch("media/catalog.json"),
      fetch("media/people_index.json"),
    ]);
    const catalogArr = catalogRes.ok ? await catalogRes.json() : [];
    const people = peopleRes.ok ? await peopleRes.json() : [];
    const catalog = {};
    (Array.isArray(catalogArr) ? catalogArr : []).forEach((item) => {
      if (item.id) catalog[item.id] = item;
      if (item.slug) catalog["slug:" + item.slug] = item;
    });
    state.catalog = catalog;
    state.people = people;
  }

  async function render() {
    applyChrome();
    const article = document.getElementById("anthology");
    const toc = document.getElementById("toc");
    article.innerHTML = `<p class="loading">${I18N[state.lang].loading}</p>`;
    try {
      if (typeof marked === "undefined") {
        await waitForMarked();
      }
      const md = await loadMarkdown();
      article.innerHTML = marked.parse(md, { mangle: false, headerIds: true });
      enhancePersonBlocks(article);
      buildToc(article, toc);
    } catch (err) {
      article.innerHTML = `<p class="loading">${escapeHtml(String(err))}</p>`;
    }
  }

  function waitForMarked() {
    return new Promise((resolve, reject) => {
      let n = 0;
      const t = setInterval(() => {
        n += 1;
        if (typeof marked !== "undefined") {
          clearInterval(t);
          resolve();
        } else if (n > 100) {
          clearInterval(t);
          reject(new Error("Markdown library failed to load"));
        }
      }, 50);
    });
  }

  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.lang = btn.dataset.lang;
      localStorage.setItem("vw-lang", state.lang);
      render();
    });
  });

  document.getElementById("anthology").addEventListener("click", (e) => {
    const btn = e.target.closest(".portrait-zoom");
    if (!btn) return;
    const fig = btn.closest(".portrait");
    const caption = fig ? fig.querySelector("figcaption") : null;
    openLightbox(btn.dataset.full, caption ? caption.innerHTML : "");
  });

  lightboxClose.addEventListener("click", closeLightbox);
  lightbox.addEventListener("click", (e) => {
    if (e.target === lightbox) closeLightbox();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeLightbox();
  });

  loadMedia().finally(render);
})();
