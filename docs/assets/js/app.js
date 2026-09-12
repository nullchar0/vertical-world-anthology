(() => {
  const I18N = {
    ru: {
      brand: "История вертикального мира",
      brandSub: "Антология 1900–2026",
      loading: "Загрузка…",
      toc: "Оглавление",
      footerCredits:
        "Текст антологии — под лицензией CC BY-SA 4.0. Портреты показываются только при лицензии, допускающей повторное использование; у каждого изображения указаны автор и ссылка на первоисточник.",
      footerLicense: "Лицензия текста: ",
      footerRepo: "Репозиторий: ",
      noPortrait: "Нет свободного портрета",
      creditPrefix: "Источник",
      licensePrefix: "Лицензия",
      close: "Закрыть",
      enlarge: "Открыть портрет крупнее",
    },
    en: {
      brand: "History of the Vertical World",
      brandSub: "Anthology 1900–2026",
      loading: "Loading…",
      toc: "Contents",
      footerCredits:
        "Anthology text is licensed under CC BY-SA 4.0. Portraits appear only when a license allows reuse; each image shows credit and a link to the original source.",
      footerLicense: "Text license: ",
      footerRepo: "Repository: ",
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
    nameIndex: [],
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
    document.title =
      state.lang === "ru"
        ? "История вертикального мира — антология"
        : "History of the Vertical World — anthology";
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
      const u = new URL(href, location.href);
      if (!u.hostname.includes("wikipedia.org")) return null;
      let title = u.pathname.split("/wiki/")[1];
      if (!title) return null;
      title = decodeURIComponent(title.split("#")[0]);
      return "wiki:" + title;
    } catch {
      return null;
    }
  }

  function isPersonHref(href) {
    if (!href) return false;
    return (
      href.includes("wikipedia.org") ||
      href.includes("alpklubspb") ||
      href.includes("russianclimb") ||
      href.includes("babanov.com")
    );
  }

  function findPortrait(href) {
    const key = wikiKeyFromHref(href);
    if (key && state.catalog[key]) return state.catalog[key];
    // try underscore/space variants
    if (key) {
      const alt = key.includes("_")
        ? key.replace(/_/g, " ")
        : key.replace(/^wiki:/, "wiki:").replace(/ /g, "_");
      if (state.catalog[alt]) return state.catalog[alt];
    }
    const byUrl = state.people.find((p) => (p.urls || []).some((u) => urlsMatch(u, href)));
    if (byUrl && state.catalog[byUrl.id]) return state.catalog[byUrl.id];
    if (byUrl && byUrl.slug && state.catalog["slug:" + byUrl.slug]) {
      return state.catalog["slug:" + byUrl.slug];
    }
    if (key) {
      const title = key.slice(5);
      const byTitle = state.people.find((p) =>
        Object.values(p.wiki_titles || {}).some(
          (t) => decodeURIComponent(String(t).replace(/_/g, " ")) === title.replace(/_/g, " ")
        )
      );
      if (byTitle && state.catalog[byTitle.id]) return state.catalog[byTitle.id];
      if (byTitle && byTitle.slug && state.catalog["slug:" + byTitle.slug]) {
        return state.catalog["slug:" + byTitle.slug];
      }
    }
    return null;
  }

  function urlsMatch(a, b) {
    try {
      const ua = new URL(a);
      const ub = new URL(b);
      return (
        ua.hostname === ub.hostname &&
        decodeURIComponent(ua.pathname) === decodeURIComponent(ub.pathname)
      );
    } catch {
      return a === b;
    }
  }

  function personSlug(href, meta) {
    if (meta && meta.slug) return meta.slug;
    const byUrl = state.people.find((p) => (p.urls || []).some((u) => urlsMatch(u, href)));
    if (byUrl && byUrl.slug) return byUrl.slug;
    const key = wikiKeyFromHref(href);
    if (!key) return null;
    return key
      .slice(5)
      .toLowerCase()
      .replace(/\(.*?\)/g, "")
      .replace(/[^a-z0-9а-яё]+/gi, "-")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 80);
  }

  function mediaSrc(file) {
    if (!file) return "";
    if (/^https?:\/\//i.test(file)) return file;
    return file;
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
    const src = mediaSrc(meta.file);
    return `<figure class="portrait">
      <button type="button" class="portrait-zoom" data-full="${escapeHtml(src)}" aria-label="${t.enlarge}">
        <img src="${escapeHtml(src)}" alt="" loading="lazy" decoding="async" />
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

  function isPersonLead(node) {
    if (!node || node.closest(".person-card")) return false;
    const first = node.querySelector(":scope > strong > a, :scope > a, strong > a");
    if (!first) return false;
    // Prefer leads that start near the beginning of the node
    const href = first.getAttribute("href") || "";
    if (!isPersonHref(href)) return false;
    const prefix = (node.textContent || "").trim().slice(0, 80);
    const name = (first.textContent || "").trim();
    return !name || prefix.indexOf(name) <= 24;
  }

  function collectPersonHrefs(nodes) {
    const hrefs = [];
    nodes.forEach((node) => {
      node.querySelectorAll("a[href]").forEach((a) => {
        const href = a.getAttribute("href") || "";
        if (!isPersonHref(href)) return;
        if (!hrefs.some((h) => urlsMatch(h, href))) hrefs.push(href);
      });
    });
    return hrefs;
  }

  function enhancePersonBlocks(root) {
    const leads = [...root.querySelectorAll("p, li")].filter(isPersonLead);
    leads.forEach((lead) => {
      if (lead.closest(".person-card")) return;

      const pieces = [lead];
      if (lead.tagName === "P") {
        let sib = lead.nextElementSibling;
        while (sib) {
          if (sib.matches("h1, h2, h3, h4, hr, table")) break;
          if (sib.matches("p") && isPersonLead(sib)) break;
          if (sib.matches("ul, ol, blockquote")) {
            pieces.push(sib);
            sib = sib.nextElementSibling;
            continue;
          }
          if (sib.matches("p") && !isPersonLead(sib)) {
            pieces.push(sib);
            sib = sib.nextElementSibling;
            continue;
          }
          break;
        }
      }

      const hrefs = collectPersonHrefs(pieces);
      if (!hrefs.length) return;

      const card = document.createElement("article");
      card.className = "person-card";
      if (hrefs.length > 1) card.classList.add("person-card--multi");

      const primaryMeta = findPortrait(hrefs[0]);
      const slug = personSlug(hrefs[0], primaryMeta);
      if (slug) card.id = "person-" + slug;

      const media = document.createElement("div");
      media.className = "person-media";
      hrefs.forEach((href) => {
        const meta = findPortrait(href);
        const wrap = document.createElement("div");
        wrap.className = "person-media-item";
        const mslug = personSlug(href, meta);
        if (mslug) wrap.id = "person-" + mslug;
        wrap.innerHTML = portraitHTML(meta);
        media.appendChild(wrap);
      });

      const body = document.createElement("div");
      body.className = "person-body";

      const anchor = lead.parentNode;
      anchor.insertBefore(card, lead);
      pieces.forEach((el) => body.appendChild(el));
      card.appendChild(media);
      card.appendChild(body);
    });
  }

  function normalizeAlias(s) {
    return String(s)
      .toLowerCase()
      .replace(/ё/g, "е")
      .replace(/[“”"']/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function buildNameIndex() {
    const entries = [];
    const seen = new Set();
    const add = (alias, slug) => {
      const key = normalizeAlias(alias);
      if (key.length < 3) return;
      const id = key + "->" + slug;
      if (seen.has(id)) return;
      seen.add(id);
      entries.push({ alias: key, slug, len: key.length });
    };

    state.people.forEach((p) => {
      if (!p.slug) return;
      Object.values(p.names || {}).forEach((name) => {
        const clean = String(name).replace(/\s*\(.*?\)\s*/g, " ").replace(/\s+/g, " ").trim();
        add(clean, p.slug);
        const parts = clean.split(/\s+/).filter(Boolean);
        if (parts.length >= 2) {
          const surname = parts[parts.length - 1];
          if (surname.length >= 4) add(surname, p.slug); // surname
          add(parts[0] + " " + parts[parts.length - 1], p.slug);
        }
      });
      Object.values(p.wiki_titles || {}).forEach((title) => {
        const t = decodeURIComponent(String(title).replace(/_/g, " "))
          .replace(/\s*\(.*?\)\s*/g, " ")
          .replace(/,/g, " ")
          .replace(/\s+/g, " ")
          .trim();
        add(t, p.slug);
        const parts = t.split(/\s+/).filter(Boolean);
        if (parts.length && parts[0].length >= 4) add(parts[0], p.slug);
      });
    });

    // Short forms used in the philosophy matrix / era table
    const extras =
      state.lang === "ru"
        ? {
            винклер: "georg-winkler",
            прейсс: "paul-preuss-climber",
            месснер: "messner-rainhold",
            куртыка: "wojciech-kurtyka",
            лоретан: "erhard-loretan",
            хоннольд: "honnold-aleks",
            гарнбрет: "garnbret-yanya",
            пурджа: "purdzha-nirmal",
            табэи: "tabei-dzyunko",
            кукучка: "kukuchka-ezhi",
            маэстри: "maestri-chezare",
            уимпер: "edward-whymper",
            дибона: "angelo-dibona",
            херцог: "otto-herzog-bergsteiger",
            абалаковы: "abalakov-vitalii-mihailovich",
            крыленко: "krylenko-nikolai-vasilevich",
            хергиани: "hergiani-mihail-vissarionovich",
            шатаева: "shataeva-elvira-sergeevna",
            розов: "rozov-valerii-vladimirovich",
            моро: "simone-moro",
            леклерк: "marc-andre-leclerc",
            "ками рита": "kami-rita-sherpa",
            "апа шерпа": "apa-sherpa",
            "анг рита": "ang-rita",
            "пасанг лхаму": "pasang-lhamu-sherpa",
            лхакпа: "lhakpa-sherpa",
            "бабу чири": "babu-chiri-sherpa",
            бересиарту: "josune-bereziartu",
            мидтбё: "midtbe-magnus",
            балыбердин: "balyberdin-vladimir-sergeevich",
            балезин: "balezin-valerii-viktorovich",
            мамлеев: "mamleev-yurii-vitalevich",
            рулинг: "fred-rouhling",
            чесен: "tomo-cesen",
            "генри тодд": "henry-todd-mountaineer",
            тодд: "henry-todd-mountaineer",
          }
        : {
            winkler: "georg-winkler",
            preuss: "paul-preuss-climber",
            messner: "messner-rainhold",
            kurtyka: "wojciech-kurtyka",
            loretan: "erhard-loretan",
            honnold: "honnold-aleks",
            garnbret: "garnbret-yanya",
            purja: "purdzha-nirmal",
            tabei: "tabei-dzyunko",
            kukuczka: "kukuchka-ezhi",
            maestri: "maestri-chezare",
            whymper: "edward-whymper",
            dibona: "angelo-dibona",
            herzog: "otto-herzog-bergsteiger",
            abalakovs: "abalakov-vitalii-mihailovich",
            krylenko: "krylenko-nikolai-vasilevich",
            khergiani: "hergiani-mihail-vissarionovich",
            "kami rita": "kami-rita-sherpa",
            "apa sherpa": "apa-sherpa",
            "ang rita": "ang-rita",
            "pasang lhamu": "pasang-lhamu-sherpa",
            lhakpa: "lhakpa-sherpa",
            bereziartu: "josune-bereziartu",
            midtbø: "midtbe-magnus",
            midtbo: "midtbe-magnus",
            rouhling: "fred-rouhling",
            česen: "tomo-cesen",
            cesen: "tomo-cesen",
            todd: "henry-todd-mountaineer",
            leclerc: "marc-andre-leclerc",
            moro: "simone-moro",
          };

    Object.entries(extras).forEach(([alias, slug]) => add(alias, slug));
    entries.sort((a, b) => b.len - a.len);
    state.nameIndex = entries;
  }

  function linkifyTableNames(root) {
    const headings = [...root.querySelectorAll("h2")];
    const targets = [];
    headings.forEach((h) => {
      const t = (h.textContent || "").toLowerCase();
      if (
        t.includes("матрица") ||
        t.includes("matrix") ||
        t.includes("сравнительная") ||
        t.includes("comparative")
      ) {
        let el = h.nextElementSibling;
        while (el && !el.matches("h2")) {
          if (el.matches("table")) targets.push(el);
          el = el.nextElementSibling;
        }
      }
    });

    targets.forEach((table) => {
      table.querySelectorAll("td").forEach((td) => {
        // Prefer last columns (representatives / figures)
        const idx = td.cellIndex;
        if (idx < 2) return;
        if (td.querySelector("a.person-jump")) return;
        linkifyTextNode(td);
      });
    });
  }

  function linkifyTextNode(el) {
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
    const textNodes = [];
    while (walker.nextNode()) textNodes.push(walker.currentNode);

    textNodes.forEach((node) => {
      if (!node.nodeValue || !node.nodeValue.trim()) return;
      if (node.parentElement && node.parentElement.closest("a")) return;
      const out = node.nodeValue;
      const matches = [];
      state.nameIndex.forEach(({ alias, slug }) => {
        if (!document.getElementById("person-" + slug)) return;
        const re = new RegExp(
          `(^|[^\\p{L}\\p{N}])(${escapeRegExp(alias)})(?=[^\\p{L}\\p{N}]|$)`,
          "giu"
        );
        let m;
        while ((m = re.exec(out)) !== null) {
          matches.push({
            start: m.index + m[1].length,
            end: m.index + m[0].length,
            slug,
            text: m[2],
          });
        }
      });
      matches.sort((a, b) => a.start - b.start || b.end - a.end);
      const picked = [];
      matches.forEach((m) => {
        if (picked.some((p) => !(m.end <= p.start || m.start >= p.end))) return;
        picked.push(m);
      });
      if (!picked.length) return;
      picked.sort((a, b) => a.start - b.start);
      const frag = document.createDocumentFragment();
      let pos = 0;
      picked.forEach((m) => {
        if (m.start > pos) frag.appendChild(document.createTextNode(out.slice(pos, m.start)));
        const a = document.createElement("a");
        a.className = "person-jump";
        a.href = "#person-" + m.slug;
        a.textContent = m.text;
        frag.appendChild(a);
        pos = m.end;
      });
      if (pos < out.length) frag.appendChild(document.createTextNode(out.slice(pos)));
      node.parentNode.replaceChild(frag, node);
    });
  }

  function escapeRegExp(s) {
    return String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
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
      // also index decoded wiki ids with spaces
      if (item.id && item.id.startsWith("wiki:")) {
        catalog[item.id.replace(/_/g, " ")] = item;
      }
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
      buildNameIndex();
      linkifyTableNames(article);
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
