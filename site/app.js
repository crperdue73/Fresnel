/* Fresnel — renders site/services.json, optionally merges site/status.json.
   Read-only by design: nothing here ever writes back to the catalogue. */

(() => {
  "use strict";

  const catalogue = document.getElementById("catalogue");
  const loading = document.getElementById("loading");
  const form = document.getElementById("search-form");
  const query = document.getElementById("q");
  const titleEl = document.getElementById("title");
  const subtitleEl = document.getElementById("subtitle");
  const countEl = document.getElementById("count");
  const generatedEl = document.getElementById("generated");
  const themeColor = document.querySelector('meta[name="theme-color"]');

  const SEARCH_URLS = {
    duckduckgo: "https://duckduckgo.com/?q=",
    google: "https://www.google.com/search?q=",
    bing: "https://www.bing.com/search?q=",
    none: null,
  };

  let data = null;
  let live = {};          // name -> { state, ms, detail }
  let tiles = [];

  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  };

  const ago = (iso) => {
    const then = new Date(iso).getTime();
    if (!Number.isFinite(then)) return "just now";
    const mins = Math.round((Date.now() - then) / 60000);
    if (mins < 1) return "just now";
    if (mins === 1) return "1 min ago";
    if (mins < 60) return `${mins} min ago`;
    const hours = Math.round(mins / 60);
    return hours === 1 ? "1 hour ago" : `${hours} hours ago`;
  };

  const markStyle = (hue) => {
    const a = `hsl(${hue} 62% 58%)`;
    const b = `hsl(${(hue + 40) % 360} 58% 40%)`;
    return [
      `background: linear-gradient(145deg, color-mix(in srgb, ${a} 26%, transparent), color-mix(in srgb, ${b} 18%, transparent))`,
      `color: color-mix(in srgb, ${a} 78%, var(--ink))`,
    ].join(";");
  };

  /* icon chain: declared icon -> host favicon -> monogram */
  const buildMark = (service) => {
    const mark = el("span", "mark");
    mark.style.cssText = markStyle(service.hue);

    const candidates = [];
    if (service.icon) candidates.push(service.icon);
    if (service.icon_host) candidates.push(`https://${service.icon_host}/favicon.ico`);

    if (!candidates.length) {
      mark.textContent = service.monogram;
      return mark;
    }

    const img = el("img");
    img.alt = "";
    img.loading = "lazy";
    let index = 0;

    const next = () => {
      if (index >= candidates.length) {
        img.remove();
        mark.textContent = service.monogram;
        return;
      }
      img.src = candidates[index++];
    };

    img.addEventListener("error", next);
    mark.appendChild(img);
    next();
    return mark;
  };

  const buildTile = (service, isPinned) => {
    const a = el("a", "tile");
    a.href = service.url;
    a.rel = "noreferrer";
    a.dataset.search = [
      service.name,
      service.description,
      service.tags.join(" "),
      service.url,
    ].join(" ").toLowerCase();

    const top = el("div", "tile-top");
    const name = el("span", "tile-name");
    name.append(document.createTextNode(service.name));

    const probed = live[service.name];
    if (probed) {
      const dot = el("span", "live");
      dot.dataset.state = probed.state;
      dot.title = `${probed.state}${probed.ms != null ? ` · ${probed.ms} ms` : ""}${
        probed.detail ? ` · ${probed.detail}` : ""
      }`;
      name.append(dot);
    }

    top.append(buildMark(service), name);
    a.append(top);

    if (service.description) a.append(el("p", "tile-desc", service.description));
    if (service.status) {
      const pill = el("span", "pill", service.status);
      pill.dataset.status = service.status;
      a.append(pill);
    }

    if (isPinned) a.dataset.pinned = "true";
    return a;
  };

  const section = (label, services, { pinned = false, accent = null } = {}) => {
    const wrap = el("section", pinned ? "category pinned" : "category");
    if (accent) wrap.style.setProperty("--accent", accent);

    const head = el("div", "category-head");
    const heading = el("h2");
    heading.append(document.createTextNode(label));
    heading.append(el("span", "tally", String(services.length).padStart(2, "0")));
    head.append(heading);

    const grid = el("div", "grid");
    for (const service of services) {
      const tile = buildTile(service, pinned);
      grid.append(tile);
      tiles.push({ tile });
    }

    wrap.append(head, grid);
    return wrap;
  };

  const render = () => {
    catalogue.textContent = "";
    tiles = [];

    if (data.pinned.length) {
      catalogue.append(section("Pinned", data.pinned, { pinned: true, accent: data.accent }));
    }

    for (const category of data.categories) {
      catalogue.append(section(category.name, category.services, { accent: category.accent }));
    }

    document.documentElement.dataset.theme = data.theme || "dark";
    document.body.style.setProperty("--accent", data.accent);
    titleEl.textContent = data.title;
    document.title = data.title;
    if (themeColor) themeColor.setAttribute("content", data.theme === "light" ? "#f6f4ef" : "#080b0f");

    if (data.subtitle) {
      subtitleEl.textContent = data.subtitle;
      subtitleEl.hidden = false;
    }

    const probed = Object.keys(live).length;
    countEl.textContent = `${data.count} services${probed ? ` · ${probed} probed` : ""}`;
    generatedEl.textContent = `built ${new Date(data.generated_at).toLocaleString()}`;
  };

  const applyFilter = () => {
    const term = query.value.trim().toLowerCase();

    for (const { tile } of tiles) {
      tile.hidden = Boolean(term) && !tile.dataset.search.includes(term);
    }

    for (const box of catalogue.querySelectorAll(".category")) {
      const visible = box.querySelectorAll(".tile:not([hidden])").length;
      box.hidden = visible === 0;
      const tally = box.querySelector(".tally");
      if (tally) tally.textContent = String(visible).padStart(2, "0");
    }

    const existing = document.getElementById("no-hits");
    const anyVisible = catalogue.querySelector(".tile:not([hidden])");
    if (!anyVisible && term) {
      if (!existing) {
        const note = el("p", "empty");
        note.id = "no-hits";
        note.append(document.createTextNode("Nothing called "));
        note.append(el("strong", null, `“${query.value.trim()}”`));
        note.append(document.createTextNode(
          SEARCH_URLS[data.search_provider] ? " — press Enter to search the web for it." : "."
        ));
        catalogue.append(note);
      } else {
        existing.querySelector("strong").textContent = `“${query.value.trim()}”`;
      }
    } else if (existing) {
      existing.remove();
    }
  };

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const term = query.value.trim();
    if (!term) return;

    const first = catalogue.querySelector(".tile:not([hidden])");
    if (first) {
      window.location.href = first.href;
      return;
    }
    const base = SEARCH_URLS[data?.search_provider];
    if (base) window.location.href = base + encodeURIComponent(term);
  });

  query.addEventListener("input", applyFilter);

  document.addEventListener("keydown", (event) => {
    const typing = /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName);
    if (event.key === "/" && !typing) {
      event.preventDefault();
      query.focus();
      query.select();
    } else if (event.key === "Escape" && document.activeElement === query) {
      query.value = "";
      applyFilter();
      query.blur();
    }
  });

  let statusChecked = null;

  const loadStatus = () =>
    fetch("status.json", { cache: "no-cache" })
      .then((response) => (response.ok ? response.json() : null))
      .then((json) => {
        live = json?.services || {};
        statusChecked = json?.checked_at || null;
      })
      .catch(() => {
        live = {};
        statusChecked = null;
      });

  fetch("services.json", { cache: "no-cache" })
    .then((response) => {
      if (!response.ok) throw new Error(`services.json returned ${response.status}`);
      return response.json();
    })
    .then(async (json) => {
      data = json;
      await loadStatus();
      render();
      loading?.remove();
      if (statusChecked) generatedEl.textContent += ` · probed ${ago(statusChecked)}`;
    })
    .catch((error) => {
      loading?.remove();
      const box = el("div", "error");
      box.append(document.createTextNode("The catalogue did not load. "));
      box.append(el("code", null, error.message));
      box.append(document.createElement("br"));
      box.append(document.createTextNode(
        "Run `make build` — the page reads a generated file, it cannot create one."
      ));
      catalogue.append(box);
    });
})();
