/* ViralCut — клиент */
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const esc = (s) =>
  String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const fmtDur = (sec) => {
  sec = Math.max(0, Math.round(sec || 0));
  const m = Math.floor(sec / 60), s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
};

const plural = (n, one, few, many) => {
  const m10 = n % 10, m100 = n % 100;
  if (m10 === 0 || (m10 >= 5 && m10 <= 9) || (m100 >= 11 && m100 <= 14)) return many;
  if (m10 === 1) return one;
  return few;
};

const ICONS = {
  play: '<svg viewBox="0 0 24 24" fill="white"><path d="M8 5.14v13.72c0 .8.87 1.3 1.56.9l11.2-6.86a1.05 1.05 0 0 0 0-1.8L9.56 4.24A1.05 1.05 0 0 0 8 5.14z"/></svg>',
  download: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12m0 0 4-4m-4 4-4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></svg>',
  edit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>',
  copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/></svg>',
  zip: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8v13H3V8M1 3h22v5H1zM10 12h4"/></svg>',
  close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>',
  back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5m7-7-7 7 7 7"/></svg>',
  folder: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
  spark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1m0-12.8-2.1 2.1M7.7 16.3l-2.1 2.1"/></svg>'
};

const ACCENT_OPTIONS = [
  ["yellow", "#FFE24A", "Жёлтый"], ["gold", "#FFC53D", "Золото"],
  ["orange", "#FF8A3D", "Оранжевый"], ["coral", "#FF6B6B", "Коралл"],
  ["red", "#FF3D57", "Красный"], ["rose", "#FF5C8A", "Роза"],
  ["pink", "#FF6BD6", "Розовый"], ["magenta", "#E84BFF", "Маджента"],
  ["violet", "#B36BFF", "Фиолетовый"], ["purple", "#8B5CF6", "Пурпур"],
  ["indigo", "#6B7CFF", "Индиго"], ["blue", "#3D8BFF", "Синий"],
  ["sky", "#3DC8FF", "Небесный"], ["cyan", "#6BE8FF", "Циан"],
  ["teal", "#2DE0C8", "Бирюза"], ["mint", "#6BFFB0", "Мята"],
  ["green", "#6BFF8C", "Зелёный"], ["lime", "#C6FF4A", "Лайм"],
  ["peach", "#FFB38A", "Персик"], ["lavender", "#C9B6FF", "Лаванда"],
  ["white", "#FFFFFF", "Белый"]
];
const ACCENT_HEX = Object.fromEntries(ACCENT_OPTIONS.map(([k, c]) => [k, c]));

function swatchesHTML(selected) {
  return ACCENT_OPTIONS.map(([key, color, label]) =>
    `<button class="swatch ${selected === key ? "active" : ""}" data-val="${key}" style="background:${color}" title="${label}"></button>`
  ).join("");
}

const BUNDLED_FONT_OPTIONS = [
  { key: "montserrat", label: "Montserrat", group: "База" },
  { key: "inter", label: "Inter Black", group: "База" },
  { key: "manrope", label: "Manrope ExtraBold", group: "База" },
  { key: "robotocond", label: "Roboto Condensed", group: "База" },
  { key: "lato", label: "Lato Black", group: "База" },
  { key: "ptsans", label: "PT Sans Narrow", group: "Узкие" },
  { key: "oswald", label: "Oswald", group: "Узкие" },
  { key: "rubik", label: "Rubik ExtraBold", group: "Плотные" },
  { key: "exo2", label: "Exo 2", group: "Плотные" },
  { key: "unbounded", label: "Unbounded", group: "Плотные" },
  { key: "russo", label: "Russo One", group: "Акцентные" },
  { key: "play", label: "Play", group: "Акцентные" },
  { key: "philosopher", label: "Philosopher", group: "Акцентные" },
  { key: "yeseva", label: "Yeseva One", group: "Акцентные" },
  { key: "comfortaa", label: "Comfortaa", group: "Акцентные" },
  { key: "caveat", label: "Caveat", group: "Акцентные" },
  { key: "golos", label: "Golos Text", group: "CapCut" },
  { key: "onest", label: "Onest", group: "CapCut" },
  { key: "marmelad", label: "Marmelad", group: "CapCut" },
  { key: "badscript", label: "Bad Script", group: "Акцентные" },
  { key: "marckscript", label: "Marck Script", group: "Акцентные" },
  { key: "ruslan", label: "Ruslan Display", group: "Акцентные" },
  { key: "stalinist", label: "Stalinist One", group: "Акцентные" },
  { key: "underdog", label: "Underdog", group: "Акцентные" }
];

const BUNDLED_GROUPS = Object.fromEntries(BUNDLED_FONT_OPTIONS.map((f) => [f.key, f.group]));
let FONT_OPTIONS = BUNDLED_FONT_OPTIONS.slice();

function fontOptionsHTML(selected) {
  const groups = [];
  FONT_OPTIONS.forEach((f) => { if (!groups.includes(f.group)) groups.push(f.group); });
  return groups.map((g) => `<optgroup label="${esc(g)}">` + FONT_OPTIONS
    .filter((f) => f.group === g)
    .map((f) => `<option value="${esc(f.key)}" ${selected === f.key ? "selected" : ""}>${esc(f.label)}</option>`)
    .join("") + "</optgroup>").join("");
}

const BUNDLED_FONT_CSS = {
  montserrat: "VCMontserrat",
  russo: "VCRusso",
  ptsans: "VCPTSans",
  lato: "VCLato",
  play: "VCPlay",
  philosopher: "VCPhilosopher",
  oswald: "VCOswald",
  robotocond: "VCRobotoCond",
  inter: "VCInter",
  rubik: "VCRubik",
  manrope: "VCManrope",
  unbounded: "VCUnbounded",
  caveat: "VCCaveat",
  yeseva: "VCYeseva",
  exo2: "VCExo2",
  comfortaa: "VCComfortaa",
  golos: "VCGolos",
  onest: "VCOnest",
  marmelad: "VCMarmelad",
  badscript: "VCBadScript",
  marckscript: "VCMarckScript",
  ruslan: "VCRuslan",
  stalinist: "VCStalinist",
  underdog: "VCUnderdog"
};
let FONT_CSS = { ...BUNDLED_FONT_CSS };

async function loadFontCatalog() {
  try {
    const data = await api("/api/fonts");
    if (!Array.isArray(data) || !data.length) return;
    FONT_OPTIONS = data.map((f) => ({
      key: f.key,
      label: f.label,
      group: f.custom ? "Мои шрифты" : (BUNDLED_GROUPS[f.key] || "Другие")
    }));
    FONT_CSS = { ...BUNDLED_FONT_CSS };
    data.forEach((f) => { if (f.css) FONT_CSS[f.key] = f.css; });
  } catch (_) { /* офлайн: остаёмся на встроенных */ }
}

function refreshFontSelects(selected, target) {
  ["#fontSelect", "#tpFont", "#edFont"].forEach((sel) => {
    const el = $(sel);
    if (!el) return;
    const value = (target && sel === target) ? selected : el.value;
    el.innerHTML = fontOptionsHTML(value);
  });
}

async function uploadFont(file) {
  if (!file) return;
  const fd = new FormData();
  fd.append("file", file);
  let entry;
  try {
    const res = await fetch("/api/fonts", { method: "POST", body: fd });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "Не удалось загрузить шрифт");
    entry = data;
  } catch (err) {
    toast(err.message, "err");
    return;
  }
  const link = $("#customFontsCss");
  if (link) link.href = "/api/fonts.css?v=" + Date.now();
  await loadFontCatalog();
  const target = state.fontTarget || "#fontSelect";
  refreshFontSelects(entry.key, target);
  state.opts.subFont = entry.key;
  const select = $(target);
  if (select) {
    select.value = entry.key;
    select.dispatchEvent(new Event("change"));
  }
  toast(`Шрифт «${entry.label}» добавлен`);
  if (entry.has_cyrillic === false) {
    setTimeout(() => toast("В этом шрифте нет кириллицы — русские буквы могут замениться", "err"), 500);
  }
}

const SUB_POSITIONS = [
  ["bottom", "Снизу"],
  ["middle", "По центру"],
  ["top", "Сверху"]
];


const OPT_ICONS = {
  count: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h10"/></svg>',
  duration: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>',
  aspect: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><rect x="6" y="3" width="12" height="18" rx="2.5"/></svg>',
  frame: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8V4h4M20 8V4h-4M4 16v4h4M20 16v4h-4"/></svg>',
  subs: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="3"/><path d="M7 10h5M7 14h9"/></svg>',
  style: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 18 8.5 6 13 18M6 14h5"/><path d="M17 18v-4.5a2.5 2.5 0 0 1 5 0V18"/></svg>',
  access: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="10" width="14" height="10" rx="3"/><path d="M8 10V8a4 4 0 0 1 8 0v2"/></svg>',
};
function optIcon(name, tone) {
  return `<span class="opt-ico ${tone || "ico-purple"}">${OPT_ICONS[name] || ""}</span>`;
}

const SUB_SPEEDS = [
  ["calm", "Спокойно"],
  ["normal", "Обычно"],
  ["fast", "Быстро"]
];
const SPEED_MS = { calm: 640, normal: 440, fast: 300 };

const STYLE_PRESETS = [
  { key: "tiktok", label: "TikTok", opts: { subFont: "montserrat", subSize: 132, subPos: "bottom", subOffset: 10, accent: "yellow", uppercase: true } },
  { key: "reels", label: "Reels", opts: { subFont: "lato", subSize: 118, subPos: "middle", subOffset: 0, accent: "pink", uppercase: true } },
  { key: "soft", label: "Мягкий", opts: { subFont: "play", subSize: 110, subPos: "bottom", subOffset: 0, accent: "cyan", uppercase: false } },
  { key: "classic", label: "Классика", opts: { subFont: "ptsans", subSize: 122, subPos: "bottom", subOffset: 0, accent: "yellow", uppercase: true } },
  { key: "sport", label: "Спорт", opts: { subFont: "oswald", subSize: 132, subPos: "bottom", subOffset: 10, accent: "green", uppercase: true } },
  { key: "bold", label: "Дерзкий", opts: { subFont: "unbounded", subSize: 112, subPos: "middle", subOffset: 0, accent: "pink", uppercase: true } },
  { key: "hand", label: "Рукописный", opts: { subFont: "caveat", subSize: 152, subPos: "bottom", subOffset: 0, accent: "yellow", uppercase: false } },
  { key: "capcut", label: "CapCut", opts: { subFont: "golos", subSize: 126, subPos: "bottom", subOffset: 10, accent: "lime", uppercase: true } },
  { key: "meme", label: "Мем", opts: { subFont: "stalinist", subSize: 112, subPos: "middle", subOffset: 0, accent: "red", uppercase: true } },
  { key: "neon", label: "Неон", opts: { subFont: "onest", subSize: 124, subPos: "bottom", subOffset: 0, accent: "cyan", uppercase: true } },
  { key: "beauty", label: "Бьюти", opts: { subFont: "marmelad", subSize: 124, subPos: "bottom", subOffset: 0, accent: "pink", uppercase: false } },
  { key: "brush", label: "Кисть", opts: { subFont: "underdog", subSize: 128, subPos: "bottom", subOffset: 0, accent: "orange", uppercase: false } },
  { key: "script", label: "Скрипт", opts: { subFont: "marckscript", subSize: 142, subPos: "bottom", subOffset: 0, accent: "lavender", uppercase: false } }
];

const DUR_PRESETS = {
  "15-30": { min: 15, max: 30, target: 22, label: "15–30 сек" },
  "20-45": { min: 20, max: 45, target: 32, label: "20–45 сек" },
  "30-60": { min: 30, max: 60, target: 42, label: "30–60 сек" },
  "30-90": { min: 30, max: 90, target: 55, label: "30–90 сек" }
};

const state = {
  projects: [],
  current: null,
  detail: null,
  pollTimer: null,
  mainKey: "",
  health: null,
  bootDone: false,
  probeOpen: false,
  probeUrl: "",
  probeData: null,
  segmentsChoice: false,
  tmplPid: null,
  tmplTimer: null,
  tmplAnim: null,
  tmplDetail: null,
  opts: {
    count: 10,
    dur: "20-45",
    aspect: "9:16",
    mode: "auto",
    subtitles: true,
    accent: "yellow",
    subFont: "montserrat",
    subSize: 118,
    subPos: "bottom",
    subOffset: 0,
    subSpeed: "calm",
    cutPauses: false,
    cookies: "",
    fontTarget: "#fontSelect"
  }
};

/* ---------------- API ---------------- */

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: options.body instanceof FormData ? {} : { "Content-Type": "application/json" },
    ...options
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const data = await res.json();
      msg = data.detail || msg;
    } catch (_) {}
    throw new Error(msg);
  }
  return res.json();
}

function toast(text, kind) {
  const node = document.createElement("div");
  node.className = "toast" + (kind === "err" ? " err" : "");
  node.textContent = text;
  $("#toasts").appendChild(node);
  setTimeout(() => node.remove(), 4200);
}

/* ---------------- Sidebar ---------------- */

function renderSidebar() {
  const list = $("#projectList");
  if (!state.projects.length) {
    list.innerHTML = '<div class="hint" style="padding:8px 10px">Пока пусто. Добавьте первую ссылку.</div>';
    return;
  }
  list.innerHTML = state.projects.map((p) => {
    const when = new Date((p.created_at || 0) * 1000).toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
    const sub = p.status === "done" ? `${p.meta?.clips || ""} клипов · ${when}` : p.status === "error" ? "ошибка" : p.status === "running" ? "обработка…" : when;
    return `<button class="project-item ${state.current === p.id ? "active" : ""}" data-project="${p.id}">
      <span class="status-dot ${esc(p.status)}"></span>
      <span style="min-width:0">
        <span class="p-title">${esc(p.title || p.url)}</span>
        <span class="p-meta">${esc(sub)}</span>
      </span>
    </button>`;
  }).join("");
}

async function loadProjects() {
  try {
    state.projects = await api("/api/projects");
    renderSidebar();
  } catch (e) {
    console.error(e);
  }
}

/* ---------------- Hero ---------------- */

function heroHTML() {
  if (state.homeView === "streams") return streamHomeHTML();
  const o = state.opts;
  const counts = [5, 10, 20, 30, 50, 0];
  return `
  <section class="hero">
    <div class="eyebrow">${ICONS.spark} Автонарезка для Shorts · Reels · TikTok</div>
    <h1 class="hero-title">Одно видео —<br><span class="grad">десятки вирусных клипов</span></h1>
    <p class="hero-sub">Вставьте ссылку на YouTube, Twitch, TikTok, Instagram, VK или файл. Приложение найдёт самые цепляющие моменты, обрежет их в вертикаль с умным кадрированием по лицу, наложит субтитры с подсветкой слов и отрендерит готовые ролики.</p>

    <button class="btn-ghost" id="discoverBtn">Найти видео на YouTube</button>
    <div class="url-box">
      <input id="urlInput" type="text" placeholder="https://youtube.com/watch?v=… или https://twitch.tv/videos/…" autocomplete="off" spellcheck="false" />
      <button class="btn-primary" id="startBtn">Сделать нарезки</button>
    </div>
    <div class="upload-row">
      <span>или</span>
      <button class="link-btn" id="uploadBtn">загрузите видеофайлом</button>
      <span>· mp4, mov, webm · длинные подкасты и интервью</span>
    </div>
    <div class="hero-note">Twitch: VOD или клип. Прямой эфир — на вкладке «Прямой эфир» слева.</div>

    <div class="group-title"><span>Параметры нарезки</span><span class="group-hint">всё можно поменять позже</span></div>
    <div class="options">
      <div class="opt">
        ${optIcon("count", "ico-purple")}
        <span class="opt-label">Сколько нарезок</span>
        <div class="seg" data-group="count">
          ${counts.map((c) => `<button data-val="${c}" class="${o.count === c ? "active" : ""}">${c === 0 ? "Все" : c}</button>`).join("")}
        </div>
      </div>
      <div class="opt">
        ${optIcon("duration", "ico-blue")}
        <span class="opt-label">Длительность клипа</span>
        <div class="seg" data-group="dur">
          ${Object.entries(DUR_PRESETS).map(([k, v]) => `<button data-val="${k}" class="${o.dur === k ? "active" : ""}">${v.label}</button>`).join("")}
        </div>
      </div>
      <div class="opt">
        ${optIcon("aspect", "ico-cyan")}
        <span class="opt-label">Формат</span>
        <div class="seg" data-group="language" style="margin-bottom:10px">
          ${[["auto","Авто"],["ru","Русский"],["en","English"]].map(([v,l]) => `<button data-val="${v}" class="${(o.language||"auto") === v ? "active" : ""}">${l}</button>`).join("")}
        </div>
        <div class="seg" data-group="aspect">
          ${["9:16", "1:1", "16:9", "4:5"].map((a) => `<button data-val="${a}" class="${o.aspect === a ? "active" : ""}">${a}</button>`).join("")}
        </div>
      </div>
      <div class="opt">
        ${optIcon("frame", "ico-green")}
        <span class="opt-label">Кадр</span>
        <div class="seg" data-group="mode">
          <button data-val="auto" class="${o.mode === "auto" ? "active" : ""}">Умный кроп</button>
          <button data-val="blur" class="${o.mode === "blur" ? "active" : ""}">Размытый фон</button>
          <button data-val="crop" class="${o.mode === "crop" ? "active" : ""}">По центру</button>
        </div>
      </div>
      <div class="opt">
        ${optIcon("subs", "ico-yellow")}
        <span class="opt-label">Субтитры</span>
        <div class="opt-control">
          <label class="toggle"><input type="checkbox" id="subsToggle" ${o.subtitles ? "checked" : ""}/><span class="track"></span><span>Включены</span></label>
          <div class="swatches" id="accents">
            ${swatchesHTML(o.accent)}
          </div>
        </div>
      </div>
      <div class="opt">
        ${optIcon("frame", "ico-blue")}
        <span class="opt-label">Паузы</span>
        <div class="opt-control">
          <label class="toggle"><input type="checkbox" id="cutPausesToggle" ${o.cutPauses ? "checked" : ""}/><span class="track"></span><span>Вырезать паузы</span></label>
          <span class="opt-hint">тишина и «эээ» убираются склейкой</span>
        </div>
      </div>
      <div class="opt wide">
        <span class="opt-head">${optIcon("style", "ico-pink")}<span class="opt-label">Стиль субтитров</span></span>
        <div class="substyle">
          <label class="mini-field">
            <span>Шрифт</span>
            <div class="font-pick">
              <select id="fontSelect">
                ${fontOptionsHTML(o.subFont)}
              </select>
              <button type="button" class="font-add" id="uploadFontBtn" title="Загрузить свой шрифт">＋</button>
            </div>
          </label>
          <label class="mini-field grow">
            <span>Размер <b id="sizeVal">${o.subSize}</b></span>
            <input type="range" id="sizeRange" min="70" max="180" step="2" value="${o.subSize}" />
          </label>
          <label class="mini-field">
            <span>Положение</span>
            <select id="posSelect">
              ${SUB_POSITIONS.map(([k, label]) => `<option value="${k}" ${o.subPos === k ? "selected" : ""}>${label}</option>`).join("")}
            </select>
          </label>
          <label class="mini-field grow">
            <span>Сдвиг <b id="offsetVal">${o.subOffset}</b></span>
            <input type="range" id="offsetRange" min="-120" max="180" step="5" value="${o.subOffset}" />
          </label>
          <label class="mini-field">
            <span>Темп</span>
            <div class="seg" data-group="subSpeed">
              ${SUB_SPEEDS.map(([k, label]) => `<button data-val="${k}" class="${o.subSpeed === k ? "active" : ""}">${label}</button>`).join("")}
            </div>
          </label>
          <div class="font-sample" id="fontSample" style="font-family:${FONT_CSS[o.subFont] || "VCMontserrat"}">ПРИМЕР СУБТИТРОВ</div>
        </div>
      </div>
      <div class="composition-inline" id="compositionSettings"></div>
      <div class="opt">
        ${optIcon("access", "ico-gray")}
        <span class="opt-label">Доступ к источнику</span>
        <select id="cookiesSelect">
          <option value="">Без cookies</option>
          <option value="chrome">Cookies из Chrome</option>
          <option value="safari">Cookies из Safari</option>
          <option value="firefox">Cookies из Firefox</option>
          <option value="edge">Cookies из Edge</option>
        </select>
      </div>
    </div>

    <a class="tg-hero" href="https://t.me/ivanAI22" data-external="https://t.me/ivanAI22" target="_blank" rel="noopener">
      <span class="tg-ico">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M21.7 3.4 2.9 11.2c-.9.3-.9 1.5 0 1.8l4.6 1.6 1.7 5.4c.2.7 1.1.9 1.6.3l2.4-2.6 4.5 3.3c.6.4 1.5.1 1.7-.6l3-15.2c.2-.9-.7-1.6-1.5-1.3zM9.4 14.1l8.6-5.5-6.8 7-.2 3.1-1.6-4.6z"/></svg>
      </span>
      <span>Обновления и примеры клипов — в Telegram</span>
      <b>@ivanAI22</b>
      <span class="tg-arrow">↗</span>
    </a>
  </section>`;
}

function bindHero() {
  $("#discoverBtn")?.addEventListener("click", openDiscovery);
  const compositionRoot = $("#compositionSettings");
  if (compositionRoot) openComposition(null, compositionRoot);
  const main = $("#main");
  $$(".seg", main).forEach((seg) => {
    const group = seg.dataset.group;
    seg.addEventListener("click", (ev) => {
      const btn = ev.target.closest("button[data-val]");
      if (!btn) return;
      const raw = btn.dataset.val;
      state.opts[group] = group === "count" ? Number(raw) : raw;
      $$("button", seg).forEach((b) => b.classList.toggle("active", b === btn));
    });
  });
  const accents = $("#accents");
  if (accents) {
    accents.addEventListener("click", (ev) => {
      const btn = ev.target.closest(".swatch");
      if (!btn) return;
      state.opts.accent = btn.dataset.val;
      $$(".swatch", accents).forEach((b) => b.classList.toggle("active", b === btn));
    });
  }
  const subs = $("#subsToggle");
  if (subs) subs.addEventListener("change", () => { state.opts.subtitles = subs.checked; });
  const cut = $("#cutPausesToggle");
  if (cut) cut.addEventListener("change", () => { state.opts.cutPauses = cut.checked; });

  const cookies = $("#cookiesSelect");
  if (cookies) cookies.addEventListener("change", () => { state.opts.cookies = cookies.value; });

  const addFont = $("#uploadFontBtn");
  if (addFont) addFont.addEventListener("click", () => {
    state.fontTarget = "#fontSelect";
    $("#fontInput").click();
  });

  const fontSelect = $("#fontSelect");
  if (fontSelect) fontSelect.addEventListener("change", () => {
    state.opts.subFont = fontSelect.value;
    const sample = $("#fontSample");
    if (sample) sample.style.fontFamily = FONT_CSS[fontSelect.value] || "VCMontserrat";
  });

  const sizeRange = $("#sizeRange");
  if (sizeRange) sizeRange.addEventListener("input", () => {
    state.opts.subSize = Number(sizeRange.value);
    const label = $("#sizeVal");
    if (label) label.textContent = sizeRange.value;
  });

  const posSelect = $("#posSelect");
  if (posSelect) posSelect.addEventListener("change", () => { state.opts.subPos = posSelect.value; });

  const offsetRange = $("#offsetRange");
  if (offsetRange) offsetRange.addEventListener("input", () => {
    state.opts.subOffset = Number(offsetRange.value);
    const label = $("#offsetVal");
    if (label) label.textContent = offsetRange.value;
  });

  const startBtn = $("#startBtn");
  if (startBtn) startBtn.addEventListener("click", submitLink);
  const urlInput = $("#urlInput");
  if (urlInput) urlInput.addEventListener("keydown", (e) => { if (e.key === "Enter") submitLink(); });
  const uploadBtn = $("#uploadBtn");
  if (uploadBtn) uploadBtn.addEventListener("click", () => $("#fileInput").click());
}

function heroOptions() {
  const d = DUR_PRESETS[state.opts.dur] || DUR_PRESETS["20-45"];
  return {
    composition: state.composition || {},
    count: state.opts.count,
    min_dur: d.min,
    max_dur: d.max,
    target_dur: d.target,
    aspect: state.opts.aspect,
    mode: state.opts.mode,
    subtitles: state.opts.subtitles,
    accent: state.opts.accent,
    sub_font: state.opts.subFont,
    sub_size: state.opts.subSize,
    sub_position: state.opts.subPos,
    sub_offset: state.opts.subOffset,
    sub_speed: state.opts.subSpeed,
    cut_pauses: state.opts.cutPauses,
    language: state.opts.language || "auto",
    cookies_browser: state.opts.cookies
  };
}

async function submitLink() {
  const input = $("#urlInput");
  const url = (input.value || "").trim();
  if (!url) { input.focus(); toast("Вставьте ссылку на видео", "err"); return; }
  askQuality(url);
}

function formatSize(mb) {
  if (!mb) return "размер неизвестен";
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} ГБ` : `${mb} МБ`;
}

function closeProbe() {
  state.probeOpen = false;
  state.probeUrl = "";
  state.probeData = null;
  $("#modal").classList.add("hidden");
  $("#modal").innerHTML = "";
  const btn = $("#startBtn");
  if (btn) { btn.disabled = false; btn.textContent = "Сделать нарезки"; }
}

function askQuality(url) {
  state.probeOpen = true;
  state.probeUrl = url;
  state.probeData = null;
  $("#modal").innerHTML = `
    <div class="modal-backdrop" data-close="probe"></div>
    <div class="modal-panel quality-panel">
      <div class="modal-head">
        <h3>Проверка видео</h3>
        <button class="icon-btn" data-close="probe">${ICONS.close}</button>
      </div>
      <div id="qualityBody" class="quality-body">
        <span class="spinner"></span>
        <div>Смотрю длительность и доступные качества…</div>
      </div>
    </div>`;
  $("#modal").classList.remove("hidden");

  api("/api/probe", {
    method: "POST",
    body: JSON.stringify({ url, cookies_browser: state.opts.cookies })
  }).then((data) => {
    if (!state.probeOpen) return;
    state.probeData = data;
    renderQuality(data);
  }).catch((err) => {
    const body = $("#qualityBody");
    if (!body) return;
    body.innerHTML = `<div class="tmpl-error">${esc(err.message)}</div>
      <button class="btn-ghost" id="qualitySkip">Продолжить без рекомендации (1080p)</button>`;
    $("#qualitySkip").addEventListener("click", () => createFromProbe(1080));
  });
}

function renderQuality(data) {
  const body = $("#qualityBody");
  if (!body) return;
  const rec = data.recommended;
  const cards = data.options.map((o) => `
    <button class="quality-card ${o.height === rec ? "recommended" : ""}" data-quality="${o.height}">
      <span class="q-height">${o.height}p</span>
      <span class="q-size">${formatSize(o.size_mb)}</span>
      ${o.height === rec ? '<span class="q-badge">рекомендуем</span>' : ""}
    </button>`).join("");
  body.innerHTML = `
    <div class="quality-title">${esc(data.title)}</div>
    <div class="quality-meta">${fmtDur(data.duration)} · ${esc(data.uploader || "")}</div>
    <div class="quality-cards">${cards}</div>

    <div class="quality-note" id="qualityNote"></div>
    <div class="modal-foot" style="padding:16px 0 0;border:0">
      <button class="btn-ghost" data-close="probe">Отмена</button>
      <button class="btn-primary" id="qualityStart">Скачать и настроить</button>
    </div>`;
  let chosen = rec;
  state.segmentsChoice = false;
  const note = $("#qualityNote");
  const updateNote = () => {
    const opt = data.options.find((o) => o.height === chosen);
    if (!opt) return;
    const eco = $("#qualityEco")?.checked;
    state.segmentsChoice = false;
    if (eco) {
      const audioMb = data.audio_size_mb || Math.max(1, Math.round(data.duration * 0.012));
      note.textContent = `Сначала только аудио (~${formatSize(audioMb)}), анализ, затем видео скачается лишь для выбранных моментов — обычно в 5–20 раз меньше полного файла.`;
      return;
    }
    let text = `Будет скачано ${formatSize(opt.size_mb)}`;
    if (chosen === 360 && data.duration > 5400) text += " · для длинного видео это в разы быстрее, чем 1080p";
    if (chosen === 1080 && data.duration > 5400) text += " · на медленной связи займёт очень долго";
    note.textContent = text;
  };
  $("#qualityEco")?.addEventListener("change", updateNote);
  body.querySelectorAll(".quality-card").forEach((card) => card.addEventListener("click", () => {
    chosen = Number(card.dataset.quality);
    body.querySelectorAll(".quality-card").forEach((c) => c.classList.toggle("active", c === card));
    updateNote();
  }));
  body.querySelector(`.quality-card[data-quality="${chosen}"]`)?.classList.add("active");
  updateNote();
  $("#qualityStart").addEventListener("click", () => createFromProbe(chosen));
}

async function createFromProbe(height) {
  const url = state.probeUrl;
  if (!url) return;
  const btn = $("#qualityStart") || $("#qualitySkip");
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Запуск'; }
  try {
    const options = { ...heroOptions(), max_height: height, segments: state.segmentsChoice };
    const project = await api("/api/projects", {
      method: "POST",
      body: JSON.stringify({ url, options, prepare_only: true })
    });
    state.probeOpen = false;
    $("#modal").classList.add("hidden");
    $("#modal").innerHTML = "";
    await loadProjects();
    openProject(project.id);
    openTemplate(project.id);
  } catch (err) {
    toast(err.message, "err");
    if (btn) { btn.disabled = false; btn.textContent = "Скачать и настроить"; }
  }
}

async function uploadFile(file) {
  if (!file) return;
  if (file.size > 4 * 1024 * 1024 * 1024) { toast("Файл больше 4 ГБ", "err"); return; }
  const form = new FormData();
  form.append("file", file);
  form.append("options", JSON.stringify(heroOptions()));
  toast("Загружаю файл…");
  try {
    const project = await api("/api/upload", { method: "POST", body: form });
    await loadProjects();
    openProject(project.id);
    openTemplate(project.id);
  } catch (e) {
    toast(e.message || "Ошибка загрузки", "err");
  }
}

/* ---------------- Project view ---------------- */

function openProject(id) {
  if (state.current !== id) {
    state.current = id;
    state.detail = null;
    state.mainKey = "";
    history.replaceState(null, "", "#" + id);
  }
  renderSidebar();
  loadDetail(true);
  schedulePoll(80);
}

function schedulePoll(delay) {
  clearTimeout(state.pollTimer);
  state.pollTimer = setTimeout(poll, delay);
}

function isBusy(detail) {
  if (!detail) return false;
  const st = detail.project.status;
  return ["queued", "running", "preparing", "processing"].includes(st)
    || detail.clips.some((c) => c.status === "rendering");
}

async function loadDetail(force) {
  if (!state.current) return;
  try {
    const detail = await api(`/api/projects/${state.current}`);
    state.detail = detail;
    const item = state.projects.find((p) => p.id === detail.project.id);
    if (item) {
      item.status = detail.project.status;
      item.title = detail.project.title;
      item.stage = detail.project.stage;
      item.meta = detail.project.meta;
    } else {
      state.projects.unshift({
        id: detail.project.id, title: detail.project.title, status: detail.project.status,
        stage: detail.project.stage, created_at: detail.project.created_at,
        meta: detail.project.meta
      });
    }
    renderSidebar();
    renderMain(force);
    return detail;
  } catch (e) {
    if (String(e.message).includes("не найден")) {
      state.current = null;
      history.replaceState(null, "", location.pathname);
      renderMain(true);
    }
  }
}

async function poll() {
  if (!state.current) return;
  const detail = await loadDetail(false);
  if (isBusy(detail)) schedulePoll(1300);
  else if (detail) {
    loadProjects();
  }
}

function stepsHTML(project) {
  const p = project.progress || 0;
  const steps = [
    { t: "Загрузка", at: 14 },
    { t: "Распознавание речи", at: 58 },
    { t: "Поиск моментов", at: 62 },
    { t: "Рендер клипов", at: 100 }
  ];
  return steps.map((s, i) => {
    const done = p >= s.at;
    const active = !done && (i === 0 || p >= steps[i - 1].at);
    return `<div class="step ${done ? "done" : active ? "active" : ""}">
      <span class="n">${done ? "✓" : i + 1}</span>${s.t}</div>`;
  }).join("");
}

function runningHTML(project) {
  return `
  <div class="project-head">
    <div>
      <h2>${esc(project.title || project.url)}</h2>
      <div class="project-meta">
        <span>${esc(project.url.startsWith("local:") ? "загруженный файл" : project.url)}</span>
        ${project.duration ? `<span>${fmtDur(project.duration)} исходник</span>` : ""}
      </div>
    </div>
    <div class="project-actions">
      <button class="btn-ghost danger" data-action="cancel">Отменить</button>
    </div>
  </div>
  <div class="progress-card">
    <div class="progress-top">
      <div class="progress-stage" id="stageText">${esc(project.stage || "Готовим…")}</div>
      <div class="progress-pct" id="pctText">${Math.round(project.progress || 0)}%</div>
    </div>
    <div class="bar"><i id="barFill" style="width:${Math.max(2, project.progress || 0)}%"></i></div>
    <div class="steps" id="stepsRow">${stepsHTML(project)}</div>
  </div>
  <div class="section-title"><h3>Клипы</h3></div>
  <div id="clipsArea">${clipsGridHTML()}</div>`;
}

function updateLiveMeta(project) {
  const stage = $("#liveStage");
  if (!stage) return;
  const m = project.meta || {};
  stage.textContent = project.stage || "Запись";
  const dur = $("#liveDur");
  if (dur) dur.textContent = `${Math.round((m.live_duration || 0) / 60)} мин записи`;
  const bytes = $("#liveBytes");
  if (bytes) bytes.textContent = `${Math.round((m.live_bytes || 0) / 1048576)} МБ`;
  const clips = $("#liveClips");
  if (clips) clips.textContent = `клипов: ${m.live_clips || 0}`;
  const notice = $("#liveNotice");
  if (notice) {
    const html = liveNoticeHTML(project);
    if (notice.innerHTML !== html) notice.innerHTML = html;
  }
}

function updateProgress(project) {
  updateLiveMeta(project);
  const stage = $("#stageText");
  if (!stage) return;
  stage.textContent = project.stage || "Обработка…";
  $("#pctText").textContent = Math.round(project.progress || 0) + "%";
  $("#barFill").style.width = Math.max(2, project.progress || 0) + "%";
  const row = $("#stepsRow");
  if (row) {
    const html = stepsHTML(project);
    if (row.dataset.sig !== html) { row.innerHTML = html; row.dataset.sig = html; }
  }
  const clipsArea = $("#clipsArea");
  if (clipsArea) {
    const html = clipsGridHTML();
    if (clipsArea.dataset.sig !== String(state.detail.clips.length)) {
      clipsArea.dataset.sig = String(state.detail.clips.length);
      clipsArea.innerHTML = html;
      bindClips();
    }
  }
}

function cancelledHTML(project) {
  return `
  <div class="project-head">
    <div>
      <h2>${esc(project.title || project.url)}</h2>
      <div class="project-meta"><span>Загрузка отменена</span></div>
    </div>
    <div class="project-actions">
      <button class="btn-primary" data-action="retry-cancelled">Скачать заново</button>
      <button class="btn-ghost" data-action="home">${ICONS.back} Новый</button>
      <button class="btn-ghost danger" data-action="delete">${ICONS.trash} Удалить</button>
    </div>
  </div>
  <div class="error-box">Загрузка остановлена. Можно попробовать снова и выбрать качество поменьше — для длинного видео это в разы быстрее.</div>`;
}

function errorHTML(project) {
  return `
  <div class="project-head">
    <div>
      <h2>${esc(project.title || project.url)}</h2>
      <div class="project-meta"><span>${esc(project.url)}</span></div>
    </div>
    <div class="project-actions">
      <button class="btn-primary" data-action="retry">Повторить обработку</button>
      <button class="btn-ghost" data-action="home">${ICONS.back} К новому проекту</button>
      <button class="btn-ghost danger" data-action="delete">${ICONS.trash} Удалить</button>
    </div>
  </div>
  <div class="error-box"><strong>Не получилось обработать видео.</strong><br>${esc(project.error || "Неизвестная ошибка")}</div>`;
}

function clipsGridHTML() {
  const clips = (state.detail && state.detail.clips) || [];
  const project = state.detail && state.detail.project;
  if (!clips.length) {
    return `<div class="empty-clips">Клипы появятся здесь, как только будет найден первый момент…</div>`;
  }
  const cards = clips.map((c) => {
    const dur = Math.max(0, (c.end || 0) - (c.start || 0));
    const score = Math.round((c.score || 0) * 100);
    const p = project.id;
    const url = `/media/${p}/clips/clip_${String(c.idx + 1).padStart(2, "0")}.mp4?v=${Math.round(c.updated_at || 0)}`;
    const preview = c.has_preview ? `/media/${p}/previews/${c.id}.mp4?v=${Math.round(c.updated_at || 0)}` : url;
    const thumb = c.thumb ? `/media/${p}/thumbs/${c.id}.jpg?v=${Math.round(c.updated_at || 0)}` : "";
    const wide = (c.settings?.aspect || "9:16") === "16:9" ? " wide" : (c.settings?.aspect || "") === "1:1" ? " square" : "";
    const sp = c.settings?.score_parts || null;
    const partsLine = sp ? [
      ["хук", sp.hook], ["подача", sp.retention], ["эмоции", sp.emotion],
      ["конкретика", sp.specificity], ["завершённость", sp.completeness],
      ["реакция", sp.reaction], ["монтаж", sp.visual],
    ].filter(([k, v]) => typeof v === "number" && (v > 0.02 || !["реакция", "монтаж"].includes(k)))
      .map(([k, v]) => `<span>${k} ${Math.round(v * 100)}</span>`).join("") : "";
    if (c.status === "error") {
      return `<div class="clip-card${wide}">
        <div class="clip-media" style="display:grid;place-items:center;padding:16px;text-align:center">
          <div style="font-size:12px;color:#fca5a5;line-height:1.45">Не удалось отрендерить<br>${esc((c.error || "").slice(0, 90))}</div>
        </div>
        <div class="clip-body"><div class="clip-title">${esc(c.title || "Клип")}</div></div>
      </div>`;
    }
    if (c.status !== "ready") {
      return `<div class="clip-card${wide} rendering">
        <div class="clip-media"></div>
        <div class="clip-body"><div class="clip-title">${esc(c.title || "Клип")}</div></div>
      </div>`;
    }
    return `<div class="clip-card${wide}" data-clip="${c.id}">
      <div class="clip-media" data-action="edit">
        <video src="${preview}#t=0.1" ${thumb ? `poster="${thumb}"` : ""} muted loop playsinline preload="metadata"></video>
        <div class="play-hint">${ICONS.play}</div>
        <div class="score-badge ${score >= 70 ? "hot" : ""}" title="Оценка момента по структуре речи, а не прогноз просмотров">⚡ ${score}</div>
        <div class="dur-badge">${fmtDur(dur)}</div>
        <div class="clip-quick">
          <button class="glass-btn" data-action="copy" title="Копировать подпись">${ICONS.copy}</button>
          ${c.settings && c.settings.segments ? "" : `<button class="glass-btn" data-action="edit" title="Редактировать">${ICONS.edit}</button>`}
        </div>
      </div>
      <div class="clip-body">
        <div class="clip-title">${esc(c.title || "Без названия")}</div>
        ${partsLine ? `<div class="clip-parts">${partsLine}</div>` : ""}
        ${c.settings?.composition_info?.ad_at != null ? `<p class="discovery-note">Реклама с ${fmtDur(c.settings.composition_info.ad_at)} · ${esc(c.settings.composition_info.ad_reason)}</p>` : ""}
        <div class="clip-tools">
          <a class="download-btn" href="${url}" download="${esc(c.title || "clip")}.mp4" data-download-clip="${c.id}" title="Скачать MP4">
            ${ICONS.download}<span>Скачать MP4</span>
          </a>
          <a class="srt-btn" href="/api/clips/${c.id}/subtitles.srt" download title="Скачать субтитры (SRT)">SRT</a>
          <button class="youtube-publish-btn btn-ghost" data-youtube="${c.id}" type="button">${ICONS.play} На YouTube</button>
        </div>
      </div>
    </div>`;
  });
  return `<div class="grid" id="clipsGrid">${cards.join("")}</div>`;
}

function resLabel(m) {
  const h = m.source_height || 0;
  if (!h) return "";
  const w = m.width || 0;
  return w && h > w ? `${w}×${h}` : `${h}p`;
}

function qualityText(project) {
  const m = project.meta || {};
  const parts = [];
  if (m.source_height) parts.push(resLabel(m));
  if (m.vcodec && m.vcodec !== "none") {
    const v = String(m.vcodec);
    parts.push(v.startsWith("avc") || v.startsWith("h264") ? "H.264" : v.startsWith("vp9") ? "VP9" : v.startsWith("av01") ? "AV1" : v);
  }
  if (m.download_seconds) parts.push(`${Math.round(m.download_seconds)} с`);
  if (m.avg_speed_mbps) parts.push(`${m.avg_speed_mbps} МБ/с`);
  if (m.max_height && m.source_height && m.max_height <= 720) parts.push(`максимум ${m.max_height}p`);
  return parts.join(" · ");
}

function fallbackHTML(project) {
  const m = project.meta || {};
  if (m.fallback) {
    const reason = m.fallback_reason ? esc(String(m.fallback_reason)) : "источник отклонил загрузку";
    return `<div class="warn-box"><strong>1080p не удалось.</strong> ${reason}. Сейчас используется ${m.source_height || "?"}p.
      <button class="link-btn" data-action="retry-hd">Повторить в 1080p</button></div>`;
  }
  // часть фрагментов скачалась в низком разрешении (например, YouTube отдал SD)
  if (m.low_res_clips) {
    return `<div class="warn-box">${m.low_res_clips} из клипов собраны из фрагментов ${m.low_res_height || "SD"}p — источник отдал низкое качество.
      <button class="link-btn" data-action="retry-hd">Пересобрать в 1080p</button></div>`;
  }
  // экономный режим собрал клипы из фрагментов ниже 1080p — даём кнопку пересборки
  const econHeight = Number(m.max_height || (project.options && project.options.max_height) || 0);
  if (m.segments_mode && econHeight < 1080) {
    return `<div class="warn-box">Клипы собраны из фрагментов ${econHeight || 360}p.
      <button class="link-btn" data-action="retry-hd">Пересобрать в 1080p</button></div>`;
  }
  return "";
}

function streamHomeHTML() {
  const streams = state.projects.filter((p) => p.meta && p.meta.live);
  return `
  <section class="hero">
    <div class="eyebrow">${ICONS.spark} Прямой эфир</div>
    <h1 class="hero-title">Нарезки <span class="grad">по ходу стрима</span></h1>
    <p class="hero-sub">Вставьте ссылку на идущий эфир (Twitch, Kick). Приложение запишет его локально и будет находить моменты каждые несколько минут — клипы появятся до конца трансляции.</p>
    <div class="url-box">
      <input id="streamInput" type="text" placeholder="https://www.twitch.tv/канал или https://kick.com/канал" autocomplete="off" spellcheck="false" />
      <div class="seg" data-group="aspect" style="margin-top:10px">
        ${["9:16", "1:1", "16:9", "4:5"].map((a) => `<button data-val="${a}" class="${state.opts.aspect === a ? "active" : ""}">${a}</button>`).join("")}
      </div>
      <button class="btn-primary" id="streamStartBtn">Записать и нарезать</button>
    </div>
  </section>
  <div class="section-title"><h3>Активные записи</h3></div>
  <div class="project-list" id="streamList">${
    streams.length ? streams.map((p) => `
      <button class="project-item" data-project="${p.id}">
        <span class="status-dot live"></span>
        <span class="pi-title">${esc(p.title || p.url)}</span>
        <span class="pi-sub">${esc(p.stage || "")} · ${Math.round((p.meta.live_duration || 0) / 60)} мин${
          streamHint(p.meta) ? ` · ${streamHint(p.meta)}` : ""}</span>
      </button>`).join("") : `<div class="empty-clips">Записей пока нет — вставьте ссылку на эфир.</div>`
  }</div>`;
}

function streamHint(meta) {
  const m = meta || {};
  if (m.live_status === "offline") return "ждём эфир";
  if (m.live_status === "reconnecting") return "нет связи";
  return "";
}

function liveNoticeHTML(project) {
  const m = project.meta || {};
  const warnings = [];
  if (m.live_status === "offline") {
    warnings.push(`<div class="warn-box"><strong>Эфир ещё не идёт.</strong>
      Запись начнётся автоматически, как только канал выйдет в эфир. Можно оставить окно
      открытым или остановить запись.</div>`);
  }
  if (m.live_error && m.live_status !== "live" && m.live_status !== "offline") {
    warnings.push(`<div class="warn-box"><strong>Подключение:</strong> ${esc(String(m.live_error))}</div>`);
  }
  if (project.error) {
    warnings.push(`<div class="warn-box"><strong>Ошибка:</strong> ${esc(String(project.error))}</div>`);
  }
  return warnings.join("");
}

function streamHTML(project) {
  const m = project.meta || {};
  const mb = Math.round((m.live_bytes || 0) / 1048576);
  return `
  <div class="project-head">
    <div>
      <h2>${esc(project.title || project.url)}</h2>
      <div class="project-meta"><span class="status-dot live"></span><span id="liveStage">${esc(project.stage || "Запись")}</span><span id="liveDur">${Math.round((m.live_duration || 0) / 60)} мин записи</span><span id="liveBytes">${mb} МБ</span><span id="liveClips">клипов: ${m.live_clips || 0}</span></div>
    </div>
    <div class="project-actions">
      <button class="btn-ghost danger" data-action="stop-live">Остановить</button>
      <button class="btn-ghost danger" data-action="delete">${ICONS.trash} Удалить</button>
    </div>
  </div>
  <div id="liveNotice">${liveNoticeHTML(project)}</div>
  <div class="section-title"><h3>Клипы по ходу эфира</h3></div>
  <div id="clipsArea">${clipsGridHTML()}</div>`;
}

function reviewHTML(project) {
  const m = project.meta || {};
  const meta = [
    resLabel(m),
    project.duration ? fmtDur(project.duration) : "",
    m.pending ? `найдено ${m.pending} моментов` : "",
    m.download_seconds ? `скачано за ${Math.round(m.download_seconds)} с` : ""
  ].filter(Boolean).join(" · ");
  return `
  <div class="project-head">
    <div>
      <h2>${esc(project.title || project.url)}</h2>
      <div class="project-meta"><span>${m.segments_mode ? "Моменты найдены" : "Видео готово"}</span><span>${esc(meta)}</span></div>
    </div>
    <div class="project-actions">
      <button class="btn-primary" data-action="setup">Настроить субтитры</button>
      <button class="btn-ghost" data-action="save-source" title="Сохранить скачанное видео в выбранную папку">${ICONS.download} Сохранить видео</button>
      <button class="btn-ghost" data-action="home">${ICONS.back} Новый</button>
      <button class="btn-ghost danger" data-action="delete">${ICONS.trash} Удалить</button>
    </div>
  </div>
  <div class="review-card">
    ${project.source_url ? `<video src="${project.source_url}" controls muted playsinline></video>` : ""}
    <div>
      <div class="review-title">Шаблон ещё не выбран</div>
      <p class="review-text">Откройте настройку, посмотрите пример субтитров на видео, выберите шрифт, размер, цвет и положение. Нарезка начнётся после подтверждения.</p>
      <button class="btn-primary" data-action="setup">Открыть настройку</button>
    </div>
  </div>`;
}

function resultsHTML() {
  const { project, clips } = state.detail;
  const ready = clips.filter((c) => c.status === "ready");
  return `
  <div class="project-head">
    <div>
      <h2>${esc(project.title || project.url)}</h2>
      <div class="project-meta">
        <span>${ready.length} ${plural(ready.length, "клип", "клипа", "клипов")}</span>
        ${project.duration ? `<span>${fmtDur(project.duration)} исходник</span>` : ""}
        ${qualityText(project) ? `<span>${esc(qualityText(project))}</span>` : ""}
        ${project.language ? `<span>язык: ${esc(project.language)}</span>` : ""}
        ${project.meta?.elapsed ? `<span>обработано за ${Math.round(project.meta.elapsed)} с</span>` : ""}
      </div>
    </div>
    <div class="project-actions">
      ${ready.length ? `<a class="btn-primary" href="/api/projects/${project.id}/zip" data-download-zip="${project.id}" style="display:inline-flex;align-items:center;gap:7px">${ICONS.zip} Скачать всё</a>` : ""}
      <button class="btn-ghost" data-action="folder" title="Открыть папку с готовыми MP4">${ICONS.folder} Открыть папку</button>
      ${ready.length ? `<button class="btn-ghost" data-action="smart-all">Пересобрать в умный кроп</button>` : ""}
      <button class="btn-ghost" data-action="save-source" title="Сохранить скачанное видео в выбранную папку">${ICONS.download} Сохранить видео</button>
      <button class="btn-ghost" data-action="home">${ICONS.back} Новый</button>
      <button class="btn-ghost danger" data-action="delete">${ICONS.trash} Удалить</button>
    </div>
  </div>
  ${fallbackHTML(project)}
  ${project.error ? `<div class="error-box">${esc(project.error)}</div>` : ""}
  ${clipsGridHTML()}`;
}

function renderMain(force) {
  const main = $("#main");
  if (!state.current || !state.detail) {
    if (!state.current) {
      main.innerHTML = heroHTML();
      bindHero();
      state.mainKey = "hero";
    }
    return;
  }
  const project = state.detail.project;
  const clips = state.detail.clips;
  const running = ["queued", "running", "preparing", "processing"].includes(project.status);
  const key = `${project.id}:${project.status}:${clips.length}:${clips.map((c) => c.status).join("")}`;
  if (!force && running && state.mainKey === key) {
    updateProgress(project);
    return;
  }
  state.mainKey = key;
  if (running) {
    main.innerHTML = (project.meta && project.meta.live) ? streamHTML(project) : runningHTML(project);
    bindClips();
    updateProgress(project);
  } else if (project.status === "review") {
    main.innerHTML = reviewHTML(project) + manualClipHTML() + pipCardHTML(state.detail);
    initPip(state.detail);
  } else if (project.status === "cancelled") {
    main.innerHTML = cancelledHTML(project);
  } else if (project.status === "error") {
    main.innerHTML = errorHTML(project);
  } else {
    main.innerHTML = resultsHTML() + manualClipHTML() + pipCardHTML(state.detail) + `<button class="btn-ghost" id="projectComposition">Игра, логотип и реклама — пересобрать клипы</button>`;
    $("#projectComposition")?.addEventListener("click", () => openComposition(project.id));
    initPip(state.detail);
    bindClips();
  }
}

function bindClips() {
  const grid = $("#clipsGrid");
  if (grid) {
    grid.addEventListener("pointerover", (e) => {
      const media = e.target.closest(".clip-media");
      if (!media) return;
      const v = media.querySelector("video");
      if (v) v.play().catch(() => {});
    });
    grid.addEventListener("pointerout", (e) => {
      const media = e.target.closest(".clip-media");
      if (!media) return;
      if (media.contains(e.relatedTarget)) return;
      const v = media.querySelector("video");
      if (v) { v.pause(); try { v.currentTime = 0.1; } catch (_) {} }
    });
  }
}

/* ---------------- Sidebar ---------------- */

$("#projectList").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-project]");
  if (btn) openProject(btn.dataset.project);
});

/* ---------------- Main delegated actions ---------------- */

$("#main").addEventListener("click", async (e) => {
  const projBtn = e.target.closest("[data-project]");
  if (projBtn) { openProject(projBtn.dataset.project); return; }

  const dlClip = e.target.closest("[data-download-clip]");
  if (dlClip) {
    const native = window.pywebview && window.pywebview.api && window.pywebview.api.save_clip;
    if (native) {
      e.preventDefault();
      try {
        const res = await window.pywebview.api.save_clip(dlClip.dataset.downloadClip);
        if (res && res.ok) toast(`Сохранено: ${res.path || res.folder || "файл"}`);
        else if (res && res.cancelled) { /* диалог закрыт — ничего не говорим */ }
        else toast((res && res.error) || "Не удалось сохранить", "err");
      } catch (err) { toast(err.message || "Не удалось сохранить", "err"); }
    }
    return;
  }

  const dlZip = e.target.closest("[data-download-zip]");
  if (dlZip) {
    const native = window.pywebview && window.pywebview.api && window.pywebview.api.save_zip;
    if (native) {
      e.preventDefault();
      try {
        const res = await window.pywebview.api.save_zip(dlZip.dataset.downloadZip);
        if (res && res.ok) toast(`Архив сохранён: ${res.path || res.folder || "файл"}`);
        else if (res && res.cancelled) { /* диалог закрыт */ }
        else toast((res && res.error) || "Не удалось сохранить архив", "err");
      } catch (err) { toast(err.message || "Не удалось сохранить архив", "err"); }
    }
    return;
  }

  const actionEl = e.target.closest("[data-action]");
  if (!actionEl) return;
  const action = actionEl.dataset.action;

  if (action === "home") {
    state.current = null;
    state.detail = null;
    state.mainKey = "";
    history.replaceState(null, "", location.pathname);
    clearTimeout(state.pollTimer);
    renderMain(true);
    renderSidebar();
    return;
  }

  if (action === "smart-all") {
    if (!state.detail) return;
    const ready = state.detail.clips.filter((c) => c.status === "ready" || c.status === "error");
    if (!ready.length) return;
    toast(`Пересобираю ${ready.length} клипов с умным кропом…`);
    for (const clip of ready) {
      api(`/api/clips/${clip.id}/rerender`, {
        method: "POST",
        body: JSON.stringify({ mode: "auto" })
      }).catch(() => {});
    }
    setTimeout(() => { loadDetail(true); schedulePoll(800); }, 700);
    return;
  }

  if (action === "stop-live") {
    if (!state.detail) return;
    try {
      await api(`/api/streams/${state.detail.project.id}/stop`, { method: "POST" });
      toast("Запись остановлена");
      schedulePoll(800);
    } catch (err) { toast(err.message, "err"); }
    return;
  }

  if (action === "cancel") {
    if (!state.detail) return;
    const pid = state.detail.project.id;
    try {
      await api(`/api/projects/${pid}/cancel`, { method: "POST" });
      if (state.tmplPid === pid) closeTemplate(true);
      toast("Загрузка отменена");
      await loadDetail(true);
      schedulePoll(600);
    } catch (err) { toast(err.message, "err"); }
    return;
  }

  if (action === "retry-cancelled") {
    if (!state.detail) return;
    const pid = state.detail.project.id;
    try {
      await api(`/api/projects/${pid}/retry`, { method: "POST", body: JSON.stringify({ prepare_only: true }) });
      await loadDetail(true);
      openTemplate(pid);
      schedulePoll(600);
    } catch (err) { toast(err.message, "err"); }
    return;
  }

  if (action === "save-source") {
    if (!state.detail) return;
    const native = window.pywebview && window.pywebview.api;
    if (!native || !native.save_source) { toast("Доступно в настольном приложении"); return; }
    try {
      const res = await native.save_source(state.detail.project.id);
      if (res && res.ok) toast(`Сохранено: ${res.path}`);
      else if (res && res.cancelled) { /* отмена — молчим */ }
      else toast((res && res.error) || "Не удалось сохранить", "err");
    } catch (e) { toast(e.message, "err"); }
    return;
  }

  if (action === "folder") {
    if (!state.detail) return;
    const native = window.pywebview && window.pywebview.api && window.pywebview.api.open_project_folder;
    if (native) {
      try { await window.pywebview.api.open_project_folder(state.detail.project.id); }
      catch (err) { toast(err.message, "err"); }
    } else {
      toast("Папка с клипами доступна в настольной версии приложения");
    }
    return;
  }

  if (action === "setup") {
    if (!state.detail) return;
    openTemplate(state.detail.project.id);
    return;
  }

  if (action === "retry-hd") {
    if (!state.detail) return;
    try {
      toast("Пересобираю клипы в 1080p…");
      await api(`/api/projects/${state.detail.project.id}/retry`, {
        method: "POST",
        body: JSON.stringify({ force_hd: true })
      });
      await loadDetail(true);
      schedulePoll(600);
    } catch (err) { toast(err.message, "err"); }
    return;
  }

  if (action === "retry") {
    if (!state.detail) return;
    try {
      await api(`/api/projects/${state.detail.project.id}/retry`, { method: "POST" });
      toast("Запускаю обработку заново");
      await loadDetail(true);
      schedulePoll(600);
    } catch (err) { toast(err.message, "err"); }
    return;
  }

  if (action === "delete") {
    if (!state.detail) return;
    if (!confirm("Удалить проект и все клипы? Файлы будут стёрты с диска.")) return;
    try {
      await api(`/api/projects/${state.detail.project.id}`, { method: "DELETE" });
      state.projects = state.projects.filter((p) => p.id !== state.detail.project.id);
      state.current = null;
      state.detail = null;
      state.mainKey = "";
      clearTimeout(state.pollTimer);
      history.replaceState(null, "", location.pathname);
      renderSidebar();
      renderMain(true);
      toast("Проект удалён");
    } catch (err) { toast(err.message, "err"); }
    return;
  }

  const card = actionEl.closest("[data-clip]");
  const clipId = card && card.dataset.clip;

  if (action === "copy" && clipId) {
    const clip = state.detail.clips.find((c) => c.id === clipId);
    try {
      await navigator.clipboard.writeText(clip.caption || clip.title || "");
      toast("Подпись с хештегами скопирована");
    } catch (_) { toast("Не удалось скопировать", "err"); }
    return;
  }

  if (action === "edit" && clipId) {
    openEditor(clipId);
  }
});

/* ---------------- Template preview ---------------- */

function templateDefaults(project) {
  const o = project.options || {};
  return {
    font: o.sub_font || "montserrat",
    size: Number(o.sub_size || 118),
    pos: o.sub_position || "bottom",
    offset: Number(o.sub_offset || 0),
    speed: o.sub_speed || "calm",
    accent: o.accent || "yellow",
    uppercase: o.uppercase !== false,
    showHook: o.show_hook !== false
  };
}

function templateOptions() {
  const base = (state.tmplDetail && state.tmplDetail.project.options) || {};
  return {
    ...base,
    sub_font: $("#tpFont").value,
    sub_size: Number($("#tpSize").value),
    sub_position: $("#tpPos").value,
    sub_offset: Number($("#tpOffset").value),
    sub_speed: ($("#tpSpeed .active") || {}).dataset?.val || "calm",
    accent: state.tmplAccent,
    uppercase: $("#tpUpper").checked,
    show_hook: $("#tpHook").checked
  };
}

function updateTemplatePreview() {
  const stage = $("#tmplStage");
  const cap = $("#tmplCaption");
  if (!stage || !cap) return;
  const font = $("#tpFont").value;
  const size = Number($("#tpSize").value);
  const pos = $("#tpPos").value;
  const offset = Number($("#tpOffset").value);
  const upper = $("#tpUpper").checked;
  const accent = state.tmplAccent || "yellow";
  const width = stage.clientWidth || 340;
  const px = Math.max(10, Math.round(size * 0.45 * (width / 1080)));
  cap.style.fontFamily = FONT_CSS[font] || "VCMontserrat";
  cap.style.fontSize = px + "px";
  cap.style.textTransform = upper ? "uppercase" : "none";
  cap.style.setProperty("--hl", ACCENT_HEX[accent] || ACCENT_HEX.yellow);
  const offsetPct = (offset / 1920) * 100;
  cap.style.transform = "";
  if (pos === "top") {
    cap.style.top = `calc(${13.5 - offsetPct}% )`;
    cap.style.bottom = "auto";
    cap.style.transform = "translateY(0)";
  } else if (pos === "middle") {
    cap.style.top = `calc(${50 - offsetPct}%)`;
    cap.style.bottom = "auto";
    cap.style.transform = "translateY(-50%)";
  } else {
    cap.style.top = "auto";
    cap.style.bottom = `calc(${17.7 + offsetPct}%)`;
    cap.style.transform = "";
  }
  $("#tpSizeVal").textContent = size;
  $("#tpOffsetVal").textContent = offset;
  startCaptionPreview();
}

function startCaptionPreview() {
  clearInterval(state.tmplAnim);
  const cap = $("#tmplCaption");
  if (!cap) return;
  const words = $$(".w", cap);
  if (!words.length) return;
  const speed = (($("#tpSpeed .active") || {}).dataset || {}).val || "calm";
  let index = 0;
  const tick = () => {
    words.forEach((w, i) => w.classList.toggle("hl", i === index));
    index = (index + 1) % words.length;
  };
  tick();
  state.tmplAnim = setInterval(tick, SPEED_MS[speed] || SPEED_MS.calm);
}

function applyPreset(key) {
  const preset = STYLE_PRESETS.find((p) => p.key === key);
  if (!preset || !state.tmplDetail) return;
  const t = preset.opts;
  $("#tpFont").value = t.subFont;
  $("#tpSize").value = t.subSize;
  $("#tpPos").value = t.subPos;
  $("#tpOffset").value = t.subOffset;
  state.tmplAccent = t.accent;
  $("#tpUpper").checked = t.uppercase;
  $$("#tpAccents .swatch").forEach((b) => b.classList.toggle("active", b.dataset.val === t.accent));
  updateTemplatePreview();
}

function closeTemplate(keepProject) {
  clearTimeout(state.tmplTimer);
  clearInterval(state.tmplAnim);
  state.tmplTimer = null;
  state.tmplAnim = null;
  state.tmplPid = null;
  state.tmplDetail = null;
  $("#modal").classList.add("hidden");
  $("#modal").innerHTML = "";
  if (!keepProject) renderSidebar();
}

function openTemplate(pid) {
  if (state.tmplPid === pid) return;
  clearTimeout(state.tmplTimer);
  state.tmplPid = pid;
  state.tmplDetail = null;
  clearInterval(state.tmplAnim);
  state.tmplAccent = "yellow";
  state.tmplReady = false;

  $("#modal").innerHTML = `
    <div class="modal-backdrop" data-close="tmpl"></div>
    <div class="modal-panel tmpl-panel">
      <div class="modal-head">
        <h3>Настройка субтитров</h3>
        <button class="icon-btn" data-close="tmpl">${ICONS.close}</button>
      </div>
      <div class="tmpl-body">
        <div class="tmpl-left">
          <div class="tmpl-stage" id="tmplStage">
            <video id="tmplVideo" muted loop playsinline></video>
            <div class="tmpl-caption" id="tmplCaption"><span class="w hl">ПРИМЕР</span> <span class="w">СУБТИТРОВ</span></div>
            <div class="tmpl-veil" id="tmplVeil">
              <span class="spinner"></span>
              <div id="tmplStageText">Загрузка видео…</div>
              <div class="tmpl-bar"><i id="tmplBar" style="width:2%"></i></div>
            </div>
          </div>
          <div class="tmpl-hint">Так будет выглядеть вертикальный кадр. Видео можно поставить на паузу.</div>
        </div>
        <div class="tmpl-right">
          <div class="field">
            <label>Шаблоны</label>
            <div class="preset-row">
              ${STYLE_PRESETS.map((p) => `<button class="preset-chip" data-preset="${p.key}">${p.label}</button>`).join("")}
            </div>
          </div>
          <div class="row2">
            <div class="field">
              <label>Шрифт</label>
              <div class="font-pick">
                <select id="tpFont">
                  ${fontOptionsHTML("")}
                </select>
                <button type="button" class="font-add" id="tpFontAdd" title="Загрузить свой шрифт">＋</button>
              </div>
            </div>
            <div class="field">
              <label>Положение</label>
              <select id="tpPos">
                ${SUB_POSITIONS.map(([k, label]) => `<option value="${k}">${label}</option>`).join("")}
              </select>
            </div>
          </div>
          <div class="row2">
            <div class="field">
              <label>Размер <b id="tpSizeVal">118</b></label>
              <input type="range" id="tpSize" min="70" max="180" step="2" value="118" />
            </div>
            <div class="field">
              <label>Сдвиг <b id="tpOffsetVal">0</b></label>
              <input type="range" id="tpOffset" min="-120" max="180" step="5" value="0" />
            </div>
          </div>
          <div class="field">
            <label>Темп субтитров</label>
            <div class="seg" id="tpSpeed">
              ${SUB_SPEEDS.map(([k, label]) => `<button data-val="${k}" class="active">${label}</button>`).join("")}
            </div>
          </div>
          <div class="field">
            <label>Цвет подсветки</label>
            <div class="swatches" id="tpAccents">
              ${swatchesHTML(state.tmplAccent || "yellow")}
            </div>
          </div>
          <div class="field">
            <label>Оформление</label>
            <div style="display:flex;gap:14px;flex-wrap:wrap">
              <label class="toggle"><input type="checkbox" id="tpUpper" checked/><span class="track"></span><span>КАПСОМ</span></label>
              <label class="toggle"><input type="checkbox" id="tpHook" checked/><span class="track"></span><span>Хук сверху</span></label>
            </div>
          </div>
          <div class="tmpl-meta" id="tmplMeta"></div>
        </div>
      </div>
      <div class="modal-foot">
        <button class="btn-ghost" data-close="tmpl">Отмена</button>
        <button class="btn-primary" id="tmplStart" disabled>Сделать нарезки</button>
      </div>
    </div>`;

  $("#modal").classList.remove("hidden");
  updateTemplatePreview();

  $("#tpFont").addEventListener("change", updateTemplatePreview);
  const tpFontAdd = $("#tpFontAdd");
  if (tpFontAdd) tpFontAdd.addEventListener("click", () => {
    state.fontTarget = "#tpFont";
    $("#fontInput").click();
  });
  $("#tpSpeed").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-val]");
    if (!btn) return;
    $$("#tpSpeed button").forEach((b) => b.classList.toggle("active", b === btn));
    startCaptionPreview();
  });
  $("#tpSize").addEventListener("input", updateTemplatePreview);
  $("#tpPos").addEventListener("change", updateTemplatePreview);
  $("#tpOffset").addEventListener("input", updateTemplatePreview);
  $("#tpUpper").addEventListener("change", updateTemplatePreview);
  $("#tpAccents").addEventListener("click", (e) => {
    const b = e.target.closest(".swatch");
    if (!b) return;
    state.tmplAccent = b.dataset.val;
    $$("#tpAccents .swatch").forEach((x) => x.classList.toggle("active", x === b));
    updateTemplatePreview();
  });
  $$(".preset-chip", $("#modal")).forEach((btn) => btn.addEventListener("click", () => {
    $$(".preset-chip", $("#modal")).forEach((b) => b.classList.toggle("active", b === btn));
    applyPreset(btn.dataset.preset);
  }));
  $("#tmplStart").addEventListener("click", startFromTemplate);

  tmplPoll();
}

async function tmplPoll() {
  if (!state.tmplPid) return;
  try {
    const detail = await api(`/api/projects/${state.tmplPid}`);
    state.tmplDetail = detail;
    const project = detail.project;
    const veil = $("#tmplVeil");
    const text = $("#tmplStageText");
    if (!veil) return;

    if (project.status === "preparing" || project.status === "queued") {
      veil.classList.remove("hidden");
      text.textContent = project.stage || "Загрузка видео…";
      $("#tmplBar").style.width = Math.max(2, project.progress || 0) + "%";
      state.tmplTimer = setTimeout(tmplPoll, 1200);
      return;
    }
    if (project.status === "error") {
      veil.classList.remove("hidden");
      veil.innerHTML = `<div class="tmpl-error">${esc(project.error || "Не удалось загрузить видео")}</div>
        <button class="btn-ghost" id="tmplRetry">Повторить загрузку</button>`;
      $("#tmplRetry").addEventListener("click", async () => {
        await api(`/api/projects/${project.id}/retry`, { method: "POST", body: JSON.stringify({ force_hd: false, prepare_only: true }) });
        openTemplate(project.id);
      });
      return;
    }
    if (project.status === "review") {
      const defaults = templateDefaults(project);
      $("#tpFont").value = defaults.font;
      $("#tpSize").value = defaults.size;
      $("#tpPos").value = defaults.pos;
      $("#tpOffset").value = defaults.offset;
      $("#tpUpper").checked = defaults.uppercase;
      $("#tpHook").checked = defaults.showHook;
      $$("#tpSpeed button").forEach((b) => b.classList.toggle("active", b.dataset.val === defaults.speed));
      state.tmplAccent = defaults.accent;
      $$("#tpAccents .swatch").forEach((b) => b.classList.toggle("active", b.dataset.val === defaults.accent));
      updateTemplatePreview();

      const video = $("#tmplVideo");
      if (project.source_url && video.getAttribute("src") !== project.source_url) {
        video.setAttribute("src", project.source_url);
        video.play().catch(() => {});
      }
      veil.classList.add("hidden");
      $("#tmplStart").disabled = false;
      const m = project.meta || {};
      $("#tmplMeta").textContent = [
        "",
        m.pending ? `Найдено моментов: ${m.pending}` : "",
        !m.segments_mode && m.source_height ? `Источник: ${resLabel(m)}` : "",
        project.duration ? `Длительность: ${fmtDur(project.duration)}` : ""
      ].filter(Boolean).join(" · ");
      return;
    }
    if (project.status === "done") {
      closeTemplate(true);
      openProject(project.id);
    }
  } catch (err) {
    state.tmplTimer = setTimeout(tmplPoll, 1500);
  }
}

async function startFromTemplate() {
  if (!state.tmplPid || !state.tmplDetail) return;
  const btn = $("#tmplStart");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Запуск';
  try {
    const project = state.tmplDetail.project;
    await api(`/api/projects/${project.id}/start`, {
      method: "POST",
      body: JSON.stringify({ options: templateOptions() })
    });
    const pid = project.id;
    closeTemplate(true);
    toast("Шаблон применён — нарезаю видео");
    await loadProjects();
    openProject(pid);
    schedulePoll(500);
  } catch (err) {
    toast(err.message, "err");
    btn.disabled = false;
    btn.textContent = "Сделать нарезки";
  }
}

/* ---------------- Editor ---------------- *//* ---------------- Editor ---------------- */

function clipUrl(clip) {
  const p = state.detail.project.id;
  return `/media/${p}/clips/clip_${String(clip.idx + 1).padStart(2, "0")}.mp4?v=${Math.round(clip.updated_at || 0)}`;
}

async function loadAudioTracks(pid) {
  const sel = $("#edAudio");
  if (!sel) return;
  try {
    const data = await api(`/api/projects/${pid}/audio`);
    const tracks = data.tracks || [];
    if (tracks.length < 2) { sel.closest(".field").style.display = "none"; return; }
    sel.innerHTML = tracks.map((t, i) => {
      const lang = (t.language && t.language !== "und") ? t.language.toUpperCase() : "—";
      const title = t.title ? ` · ${t.title}` : "";
      return `<option value="${i}" ${i === (data.selected || 0) ? "selected" : ""}>${i + 1}. ${lang}${title}</option>`;
    }).join("");
    sel.addEventListener("change", async () => {
      try {
        await api(`/api/projects/${pid}/audio`, { method: "POST", body: JSON.stringify({ index: Number(sel.value) }) });
        toast("Звуковая дорожка выбрана — подействует при следующем рендере");
      } catch (e) { toast(e.message, "err"); }
    });
  } catch (e) { console.error(e); }
}

function openEditor(clipId) {
  const clip = state.detail.clips.find((c) => c.id === clipId);
  if (!clip) return;
  const project = state.detail.project;
  const liveDur = (project.meta && project.meta.live_duration) || 0;
  const maxT = Math.max(1, (project.duration || liveDur || clip.end) - 0.2);
  const s = clip.settings || {};
  const accent = s.accent || "yellow";
  const fontKey = s.sub_font || "montserrat";
  const fontSize = Number(s.sub_size || 118);
  const fontPos = s.sub_position || "bottom";
  const fontOffset = Number(s.sub_offset || 0);
  const subSpeed = s.sub_speed || "calm";

  $("#modal").innerHTML = `
    <div class="modal-backdrop" data-close></div>
    <div class="modal-panel">
      <div class="modal-head">
        <h3>Редактировать клип</h3>
        <button class="icon-btn" data-close>${ICONS.close}</button>
      </div>
      <div class="modal-body">
        <div class="editor-video"><video id="edVideo" src="${clipUrl(clip)}" controls playsinline></video></div>
        <div class="editor-fields">
          <div class="field">
            <label>Заголовок на видео (хук)</label>
            <input type="text" id="edHook" maxlength="90" value="${esc(clip.hook || clip.title || "")}" />
          </div>
          <div class="field">
            <label>Текст субтитров <span style="color:var(--muted-2);font-weight:400">— правьте имена и термины, тайминги сохранятся</span></label>
            <textarea id="edText" rows="3" style="width:100%;resize:vertical">${esc((clip.words || []).map((w) => w.word).join(" "))}</textarea>
          </div>
          <div class="row2">
            <div class="field">
              <label>Начало</label>
              <div class="range-row">
                <input type="range" id="edStart" min="0" max="${maxT}" step="0.1" value="${clip.start}" />
                <input type="number" id="edStartNum" min="0" max="${maxT}" step="0.1" value="${clip.start.toFixed(1)}" />
              </div>
            </div>
            <div class="field">
              <label>Конец</label>
              <div class="range-row">
                <input type="range" id="edEnd" min="0" max="${maxT}" step="0.1" value="${clip.end}" />
                <input type="number" id="edEndNum" min="0" max="${maxT}" step="0.1" value="${clip.end.toFixed(1)}" />
              </div>
            </div>
          </div>
          <div class="row2">
            <div class="field">
              <label>Формат</label>
              <select id="edAspect">
                ${["9:16", "1:1", "16:9", "4:5"].map((a) => `<option value="${a}" ${(s.aspect || "9:16") === a ? "selected" : ""}>${a}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Звуковая дорожка</label>
              <select id="edAudio"><option value="0">основная</option></select>
            </div>
            <div class="field">
              <label>Кадрирование</label>
              <select id="edMode">
                <option value="auto" ${s.mode === "auto" ? "selected" : ""}>Умный кроп (по лицу)</option>
                <option value="blur" ${s.mode === "blur" || !s.mode ? "selected" : ""}>Размытый фон</option>
                <option value="crop" ${s.mode === "crop" ? "selected" : ""}>По центру</option>
              </select>
            </div>
          </div>
          <div class="field">
            <label>Субтитры</label>
            <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">
              <label class="toggle"><input type="checkbox" id="edSubs" ${s.subtitles !== false ? "checked" : ""}/><span class="track"></span><span>Показывать</span></label>
              <label class="toggle"><input type="checkbox" id="edUpper" ${s.uppercase !== false ? "checked" : ""}/><span class="track"></span><span>КАПСОМ</span></label>
              <label class="toggle"><input type="checkbox" id="edShowHook" ${s.show_hook !== false ? "checked" : ""}/><span class="track"></span><span>Хук сверху</span></label>
              <label class="toggle"><input type="checkbox" id="edCutPauses" ${s.cut_pauses ? "checked" : ""}/><span class="track"></span><span>Вырезать паузы</span></label>
            </div>
          </div>
          <div class="row2">
            <div class="field">
              <label>Шрифт субтитров</label>
              <div class="font-pick">
                <select id="edFont">
                  ${fontOptionsHTML(fontKey)}
                </select>
                <button type="button" class="font-add" id="edFontAdd" title="Загрузить свой шрифт">＋</button>
              </div>
              <div class="font-sample ed-sample" id="edFontSample" style="font-family:${FONT_CSS[fontKey] || "VCMontserrat"}">ПРИМЕР СУБТИТРОВ</div>
            </div>
            <div class="field">
              <label>Положение</label>
              <select id="edPos">
                ${SUB_POSITIONS.map(([k, label]) => `<option value="${k}" ${fontPos === k ? "selected" : ""}>${label}</option>`).join("")}
              </select>
            </div>
          </div>
          <div class="row2">
            <div class="field">
              <label>Размер <b id="edSizeVal">${fontSize}</b></label>
              <input type="range" id="edSize" min="70" max="180" step="2" value="${fontSize}" />
            </div>
            <div class="field">
              <label>Сдвиг <b id="edOffVal">${fontOffset}</b></label>
              <input type="range" id="edOffset" min="-120" max="180" step="5" value="${fontOffset}" />
            </div>
          </div>
          <div class="field">
            <label>Темп субтитров</label>
            <div class="seg" id="edSpeed">
              ${SUB_SPEEDS.map(([k, label]) => `<button data-val="${k}" class="${subSpeed === k ? "active" : ""}">${label}</button>`).join("")}
            </div>
          </div>
          <div class="field">
            <label>Цвет подсветки</label>
            <div class="swatches" id="edAccents">
              ${swatchesHTML(accent)}
            </div>
          </div>
          <div class="field">
            <label>Подпись для публикации</label>
            <textarea id="edCaption">${esc(clip.caption || "")}</textarea>
          </div>
        </div>
      </div>
      <div class="modal-foot">
        <button class="btn-ghost" data-close>Отмена</button>
        <button class="btn-primary" id="edSave">Перерендерить</button>
      </div>
    </div>`;

  $("#modal").classList.remove("hidden");

  let chosenAccent = accent;
  $("#edAccents").addEventListener("click", (e) => {
    const b = e.target.closest(".swatch");
    if (!b) return;
    chosenAccent = b.dataset.val;
    $$(".swatch", $("#edAccents")).forEach((x) => x.classList.toggle("active", x === b));
  });

  $("#edSize").addEventListener("input", (e) => { $("#edSizeVal").textContent = e.target.value; });
  $("#edFont").addEventListener("change", () => {
    const sample = $("#edFontSample");
    if (sample) sample.style.fontFamily = FONT_CSS[$("#edFont").value] || "VCMontserrat";
  });
  const edFontAdd = $("#edFontAdd");
  if (edFontAdd) edFontAdd.addEventListener("click", () => {
    state.fontTarget = "#edFont";
    $("#fontInput").click();
  });
  $("#edSpeed").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-val]");
    if (!btn) return;
    $$("#edSpeed button").forEach((b) => b.classList.toggle("active", b === btn));
  });
  $("#edOffset").addEventListener("input", (e) => { $("#edOffVal").textContent = e.target.value; });

  const start = $("#edStart"), end = $("#edEnd");
  const startNum = $("#edStartNum"), endNum = $("#edEndNum");
  const video = $("#edVideo");

  const syncNumbers = () => {
    startNum.value = Number(start.value).toFixed(1);
    endNum.value = Number(end.value).toFixed(1);
  };
  start.addEventListener("input", () => {
    if (Number(start.value) > Number(end.value) - 3) start.value = Math.max(0, Number(end.value) - 3);
    syncNumbers();
    try { video.currentTime = Number(start.value); } catch (_) {}
  });
  end.addEventListener("input", () => {
    if (Number(end.value) < Number(start.value) + 3) end.value = Math.min(maxT, Number(start.value) + 3);
    syncNumbers();
  });
  startNum.addEventListener("change", () => { start.value = startNum.value; start.dispatchEvent(new Event("input")); });
  endNum.addEventListener("change", () => { end.value = endNum.value; end.dispatchEvent(new Event("input")); });

  $("#edSave").addEventListener("click", async () => {
    const btn = $("#edSave");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Рендер…';
    const payload = {
      start: Number(start.value),
      end: Number(end.value),
      hook: $("#edHook").value,
      caption: $("#edCaption").value,
      text: (() => {
        const box = $("#edText");
        const before = (clip.words || []).map((w) => w.word).join(" ");
        return box && box.value.trim() !== before.trim() ? box.value.trim() : undefined;
      })(),
      aspect: $("#edAspect").value,
      mode: $("#edMode").value,
      subtitles: $("#edSubs").checked,
      uppercase: $("#edUpper").checked,
      show_hook: $("#edShowHook").checked,
      cut_pauses: $("#edCutPauses").checked,
      accent: chosenAccent,
      sub_font: $("#edFont").value,
      sub_size: Number($("#edSize").value),
      sub_position: $("#edPos").value,
      sub_offset: Number($("#edOffset").value),
      sub_speed: ($("#edSpeed .active") || {}).dataset?.val || "calm"
    };
    try {
      await api(`/api/clips/${clip.id}/rerender`, { method: "POST", body: JSON.stringify(payload) });
      closeModal();
      toast("Клип перерендеривается");
      await loadDetail(true);
      schedulePoll(900);
    } catch (e) {
      toast(e.message, "err");
      btn.disabled = false;
      btn.textContent = "Перерендерить";
    }
  });
}

function closeModal() {
  $("#modal").classList.add("hidden");
  $("#modal").innerHTML = "";
}

$("#main").addEventListener("click", async (e) => {
  if (!e.target.closest("#mcAdd")) return;
  if (!state.current) return;
  const start = $("#mcStart").value.trim();
  const end = $("#mcEnd").value.trim();
  if (!start || !end) { toast("Укажите начало и конец", "err"); return; }
  const btn = e.target.closest("#mcAdd");
  btn.disabled = true;
  try {
    await api(`/api/projects/${state.current}/clips`, {
      method: "POST",
      body: JSON.stringify({ start, end, trim_silence: $("#mcTrim").checked }),
    });
    toast("Клип добавлен — рендерю");
    poll();
  } catch (err) {
    toast(err.message, "err");
  } finally { btn.disabled = false; }
});

$("#modal").addEventListener("click", (e) => {
  if (!e.target.closest("[data-close]")) return;
  if (state.probeOpen) closeProbe();
  else if (state.tmplPid) closeTemplate();
  else closeModal();
});
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || $("#modal").classList.contains("hidden")) return;
  if (state.probeOpen) closeProbe();
  else if (state.tmplPid) closeTemplate();
  else closeModal();
});

/* ---------------- Boot ---------------- */

$("#newBtn").addEventListener("click", () => {
  state.current = null;
  state.detail = null;
  state.mainKey = "";
  state.homeView = "";
  clearTimeout(state.pollTimer);
  history.replaceState(null, "", location.pathname);
  renderMain(true);
  renderSidebar();
  const input = $("#urlInput");
  if (input) input.focus();
});

$("#streamBtn")?.addEventListener("click", () => {
  state.current = null;
  state.detail = null;
  state.homeView = "streams";
  clearTimeout(state.pollTimer);
  history.replaceState(null, "", location.pathname);
  renderMain(true);
});

$("#main").addEventListener("click", async (e) => {
  if (e.target.closest("#streamStartBtn")) {
    const input = $("#streamInput");
    const url = (input && input.value || "").trim();
    if (!url) { toast("Вставьте ссылку на эфир", "err"); return; }
    try {
      const project = await api("/api/streams", { method: "POST", body: JSON.stringify({ url, options: heroOptions() }) });
      await loadProjects();
      openProject(project.id);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
});

$("#fileInput").addEventListener("change", (e) => {
  const file = e.target.files && e.target.files[0];
  e.target.value = "";
  uploadFile(file);
});

$("#fontInput").addEventListener("change", (e) => {
  const file = e.target.files && e.target.files[0];
  e.target.value = "";
  uploadFont(file);
});

document.addEventListener("click", (e) => {
  const link = e.target.closest("a[data-external]");
  if (!link) return;
  e.preventDefault();
  const url = link.getAttribute("data-external") || "";
  const api = window.pywebview && window.pywebview.api;
  if (api && api.open_url) {
    api.open_url(url).catch(() => { try { window.open(url, "_blank", "noopener"); } catch (_) {} });
  } else {
    try { window.open(url, "_blank", "noopener"); } catch (_) {}
  }
});

async function checkHealth() {
  try {
    const h = await api("/api/health");
    state.health = h;
    const el = $("#health");
    el.classList.toggle("ok", !!h.ok);
    el.classList.toggle("bad", !h.ok);
    $("#healthText").textContent = h.ok
      ? (h.model === false
          ? "Готов · модель скачается при первом видео"
          : `Движок готов · ffmpeg${h.whisper ? " · Whisper" : " · без Whisper"}`)
      : "ffmpeg не найден";
  } catch (_) {
    $("#health").classList.add("bad");
    $("#healthText").textContent = "Сервер недоступен";
  }
}

async function checkUpdates() {
  try {
    const res = await fetch("/api/update");
    if (!res.ok) return;
    renderUpdate(await res.json());
  } catch (_) { /* офлайн — просто не показываем */ }
}

function renderUpdate(data) {
  const card = $("#updateCard");
  if (!card) return;
  const dismissed = localStorage.getItem("vcUpdateDismissed");
  if (!data || !data.available || !data.latest || dismissed === data.latest) {
    card.hidden = true;
    return;
  }
  const url = data.url || "https://github.com/vanwild11/viralcut/releases/latest";
  card.href = url;
  card.setAttribute("data-external", url);
  $("#updateTitle").textContent = `Доступна версия ${data.latest}`;
  const note = String(data.notes || "").split("\n").map((l) => l.replace(/^#+\s*/, "").trim()).find(Boolean);
  $("#updateSub").textContent = note ? note.slice(0, 70) : "Скачать с GitHub";
  card.hidden = false;
  if (localStorage.getItem("vcUpdateSeen") !== data.latest) {
    localStorage.setItem("vcUpdateSeen", data.latest);
    toast(`Вышла новая версия ${data.latest} — скачать на GitHub`);
  }
}

async function pollSystem() {
  try {
    const res = await fetch("/api/system");
    if (!res.ok) return;
    renderSystem(await res.json());
  } catch (_) { /* сервер недоступен — оставляем прошлые значения */ }
}

function sysLevel(percent) {
  if (percent == null) return "";
  if (percent >= 85) return "hot";
  if (percent >= 60) return "warn";
  return "";
}

const fmtGb = (mb) => (mb / 1024).toFixed(1).replace(".", ",");

function renderSystem(data) {
  if (!data) return;
  if (data.disabled) {
    const card = $("#sysCard");
    if (card) card.style.display = "none";
    return;
  }
  const set = (barId, valId, percent) => {
    const bar = $(barId);
    const val = $(valId);
    if (!bar || !val) return;
    if (percent == null || Number.isNaN(percent)) {
      bar.style.width = "0%";
      bar.className = "";
      val.textContent = "н/д";
      return;
    }
    bar.style.width = `${Math.max(2, Math.min(100, percent))}%`;
    bar.className = sysLevel(percent);
    val.textContent = `${Math.round(percent)}%`;
  };
  set("#sysCpuBar", "#sysCpuVal", data.cpu);
  set("#sysRamBar", "#sysRamVal", data.ram ? data.ram.percent : null);
  set("#sysGpuBar", "#sysGpuVal", data.gpu ? data.gpu.percent : null);

  // память отдельной строкой — проценты в полоске, гигабайты текстом
  const ramText = $("#sysRamText");
  if (ramText) {
    const ram = data.ram || {};
    ramText.textContent = ram.total_mb
      ? `RAM ${fmtGb(ram.used_mb)} / ${fmtGb(ram.total_mb)} ГБ`
      : "RAM н/д";
  }

  const chip = $("#sysHw");
  if (chip) {
    const name = data.gpu && data.gpu.name ? String(data.gpu.name) : "";
    chip.textContent = name || (data.app && data.app.hw ? String(data.app.hw).replace("h264_", "") : "GPU");
    // откуда цифра: pdh (Intel/AMD/NVIDIA), nvidia-smi или ADL для AMD
    const gpu = data.gpu || {};
    chip.title = [
      gpu.vendor ? gpu.vendor.toUpperCase() : "",
      gpu.source && gpu.source !== "none" ? `источник: ${gpu.source}` : ""
    ].filter(Boolean).join(" · ");
  }

  // текущий процесс: что именно делает приложение
  const job = $("#sysJob");
  const dot = $("#sysDot");
  if (job) {
    if (data.job && data.job.stage) {
      const pct = Math.round(data.job.progress || 0);
      const stage = String(data.job.stage).replace(/ · \d+ с$/, "");
      job.textContent = `${stage}${pct > 0 ? ` · ${pct}%` : ""}`;
      job.classList.add("active");
      job.title = data.job.title || "";
      if (dot) dot.classList.add("active");
    } else {
      job.textContent = "Простой";
      job.classList.remove("active");
      job.title = "";
      if (dot) dot.classList.remove("active");
    }
  }

  const worst = Math.max(data.cpu || 0, (data.ram && data.ram.percent) || 0, (data.gpu && data.gpu.percent) || 0);
  if (dot) {
    dot.className = `hud-dot ${sysLevel(worst)}`.trim();
  }
}

/* ---------------- Настройки ---------------- */

async function chooseFolder(kind) {
  const native = window.pywebview && window.pywebview.api;
  const input = kind === "download" ? $("#setDownloadDir") : $("#setClipsDir");
  if (!native || !native.choose_folder) {
    toast("Выбор папки доступен в настольном приложении");
    return;
  }
  try {
    const res = await native.choose_folder(input ? input.value : "");
    if (res && res.ok && res.path && input) input.value = res.path;
  } catch (e) {
    toast(e.message || "Не удалось выбрать папку", "err");
  }
}

async function openSettings() {
  let youtubeStatus = null;
  try { youtubeStatus = await api('/api/youtube/status'); } catch (_) {}
  let conf = { encoder: "auto", download_dir: "", clips_dir: "", ask_folder: true, hw_available: null };
  try { conf = await api("/api/settings"); } catch (e) { console.error(e); }
  const modes = [["auto", "Авто"], ["gpu", "Видеокарта"], ["cpu", "Процессор"]];
  $("#modal").innerHTML = `
    <div class="modal-backdrop" data-close></div>
    <div class="modal-panel settings-panel" style="max-width:520px">
      <div class="modal-head">
        <h3>Настройки</h3>
        <button class="icon-btn" data-close>${ICONS.close}</button>
      </div>
      <div class="modal-body">
        <div class="set-section">
          <div class="set-label">Чем кодировать клипы</div>
          <div class="set-seg" id="setEncoder">
            ${modes.map(([k, label]) => `<button data-val="${k}" class="${conf.encoder === k ? "active" : ""}">${label}</button>`).join("")}
          </div>
          <div class="set-hint">
            Видеокарта — быстрее и не грузит процессор${conf.hw_available ? ` (доступно: ${esc(conf.hw_available)})` : " (аппаратный энкодер не найден)"}.
            Процессор — чуть выше качество на сложных сценах.
          </div>
        </div>
        <div class="set-section">
          <div class="set-label">Куда сохранять скачанные видео</div>
          <div class="set-path">
            <input type="text" id="setDownloadDir" placeholder="Спросить при первом сохранении" value="${esc(conf.download_dir || "")}" />
            <button class="btn-ghost" type="button" id="setDownloadPick">Выбрать…</button>
          </div>
        </div>
        <div class="set-section">
          <div class="set-label">Куда сохранять готовые клипы</div>
          <div class="set-path">
            <input type="text" id="setClipsDir" placeholder="Загрузки/ViralCut" value="${esc(conf.clips_dir || "")}" />
            <button class="btn-ghost" type="button" id="setClipsPick">Выбрать…</button>
          </div>
        </div>
        <div class="set-section">
          <label class="toggle"><input type="checkbox" id="setAskFolder" ${conf.ask_folder ? "checked" : ""}/><span class="track"></span><span>Спрашивать папку при каждом сохранении</span></label>
        </div>
        <div class="set-section" id="youtubeSettingsSection">
          <div class="set-label">YouTube</div>
          <div id="youtubeAccount" class="youtube-account">${youtubeAccountHTML(youtubeStatus)}</div>
          <div class="youtube-settings-actions">
            <label class="btn-ghost composition-upload">Выбрать OAuth-файл<input id="youtubeClientFile" type="file" accept="application/json,.json"></label>
            <button class="btn-primary" type="button" id="youtubeConnect">Подключить канал</button>
            <button class="btn-ghost" type="button" id="youtubeDisconnect" ${youtubeStatus?.connected?'':'hidden'}>Отключить</button>
          </div>
          <details class="youtube-setup"><summary>Как подключить впервые</summary>
            <ol><li>В Google Cloud создайте проект и включите YouTube Data API v3.</li><li>Настройте OAuth consent screen. Если приложение в режиме Testing, добавьте свой Google-аккаунт в Test users.</li><li>Создайте OAuth client ID типа Desktop app, скачайте JSON и выберите его здесь.</li><li>Нажмите «Подключить канал» и разрешите доступ в окне Google.</li></ol>
            <a href="https://console.cloud.google.com/apis/library/youtube.googleapis.com" target="_blank" rel="noopener">Открыть Google Cloud ↗</a>
          </details>
          <div class="set-hint">Доступ сохраняется в системном хранилище паролей. Видео отправляется только по кнопке публикации.</div>
          <p id="youtubeSettingsMessage" role="status" class="set-hint"></p>
        </div>
        <div class="set-section">
          <div class="set-label">Журнал приложения</div>
          <div class="set-hint">Если приложение закрылось само (например, при «Пересобрать»), здесь видно, на каком этапе это случилось и с какой ошибкой.</div>
          <button class="btn-ghost" type="button" id="setDiag">Разобрать журнал</button>
          <pre id="setDiagOut" class="diag-out hidden"></pre>
        </div>
      </div>
      <div class="modal-foot">
        <button class="btn-ghost" data-close>Отмена</button>
        <button class="btn-primary" id="setSave">Сохранить</button>
      </div>
    </div>`;
  $("#modal").classList.remove("hidden");
  bindYoutubeSettings();
  const diagBtn = $("#setDiag");
  if (diagBtn) diagBtn.addEventListener("click", async () => {
    const out = $("#setDiagOut");
    diagBtn.disabled = true;
    diagBtn.innerHTML = '<span class="spinner"></span> Читаю…';
    try {
      const data = await api("/api/diagnostics?tail=15");
      if (out) {
        out.textContent = data.report || "Пусто";
        out.classList.remove("hidden");
      }
    } catch (err) {
      toast(err.message, "err");
    } finally {
      diagBtn.disabled = false;
      diagBtn.textContent = "Разобрать журнал";
    }
  });
  $("#setDownloadPick").addEventListener("click", () => chooseFolder("download"));
  $("#setClipsPick").addEventListener("click", () => chooseFolder("clips"));
  let encoder = conf.encoder || "auto";
  $$("#setEncoder button").forEach((b) => b.addEventListener("click", () => {
    encoder = b.dataset.val;
    $$("#setEncoder button").forEach((x) => x.classList.toggle("active", x === b));
  }));
  $("#setSave").addEventListener("click", async () => {
    const btn = $("#setSave");
    btn.disabled = true;
    try {
      await api("/api/settings", {
        method: "POST",
        body: JSON.stringify({
          encoder,
          download_dir: $("#setDownloadDir").value.trim(),
          clips_dir: $("#setClipsDir").value.trim(),
          ask_folder: $("#setAskFolder").checked,
        }),
      });
      closeModal();
      toast("Настройки сохранены");
      pollSystem();
    } catch (e) {
      toast(e.message, "err");
    } finally {
      btn.disabled = false;
    }
  });
}

function bindHud() {
  const head = $("#sysToggle");
  const card = $("#sysCard");
  if (!head || !card) return;
  try {
    if (localStorage.getItem("vcHudCollapsed") === "1") card.classList.add("collapsed");
  } catch (_) {}

  // сохранённая позиция: пользователь мог перетащить панель
  const placeHud = (x, y) => {
    const r = card.getBoundingClientRect();
    const left = Math.min(Math.max(8, x), Math.max(8, window.innerWidth - r.width - 8));
    const top = Math.min(Math.max(8, y), Math.max(8, window.innerHeight - r.height - 8));
    card.style.left = `${left}px`;
    card.style.top = `${top}px`;
    card.style.right = "auto";
    card.style.bottom = "auto";
    return { left, top };
  };
  const saved = (() => {
    try { return JSON.parse(localStorage.getItem("vcHudPos") || "null"); } catch (_) { return null; }
  })();
  if (saved && Number.isFinite(saved.x) && Number.isFinite(saved.y)) {
    const pos = placeHud(saved.x, saved.y);
    try { localStorage.setItem("vcHudPos", JSON.stringify({ x: pos.left, y: pos.top })); } catch (_) {}
  }
  window.addEventListener("resize", () => {
    const stored = (() => {
      try { return JSON.parse(localStorage.getItem("vcHudPos") || "null"); } catch (_) { return null; }
    })();
    if (stored && Number.isFinite(stored.x)) placeHud(stored.x, stored.y);
  });

  let drag = null;
  head.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    const r = card.getBoundingClientRect();
    drag = { offX: e.clientX - r.left, offY: e.clientY - r.top, moved: false,
             startX: e.clientX, startY: e.clientY };
    card.classList.add("dragging");
    try { head.setPointerCapture(e.pointerId); } catch (_) {}
  });
  head.addEventListener("pointermove", (e) => {
    if (!drag) return;
    if (!drag.moved && Math.hypot(e.clientX - drag.startX, e.clientY - drag.startY) < 4) return;
    drag.moved = true;
    placeHud(e.clientX - drag.offX, e.clientY - drag.offY);
  });
  const finish = (e) => {
    if (!drag) return;
    const moved = drag.moved;
    drag = null;
    card.classList.remove("dragging");
    try { head.releasePointerCapture(e.pointerId); } catch (_) {}
    if (moved) {
      const r = card.getBoundingClientRect();
      try { localStorage.setItem("vcHudPos", JSON.stringify({ x: r.left, y: r.top })); } catch (_) {}
      return;
    }
    // это был клик, а не перетаскивание — сворачиваем
    card.classList.toggle("collapsed");
    try {
      localStorage.setItem("vcHudCollapsed", card.classList.contains("collapsed") ? "1" : "0");
    } catch (_) {}
  };
  head.addEventListener("pointerup", finish);
  head.addEventListener("pointercancel", finish);
}

/* ---------------- Окно стримера (камера) ---------------- */

function manualClipHTML() {
  return `
    <div class="pip-card" id="manualCard">
      <div class="pip-head">
        <div>
          <div class="pip-title">Добавить по таймкоду</div>
          <div class="pip-sub">Свой момент, мимо алгоритма. Время в формате мм:сс или секунды.</div>
        </div>
      </div>
      <div class="pip-controls">
        <input type="text" id="mcStart" placeholder="00:00" style="width:90px;padding:8px 10px;border-radius:10px;border:1px solid var(--separator);background:var(--grouped-2);color:var(--text)" />
        <span>—</span>
        <input type="text" id="mcEnd" placeholder="00:45" style="width:90px;padding:8px 10px;border-radius:10px;border:1px solid var(--separator);background:var(--grouped-2);color:var(--text)" />
        <label class="toggle"><input type="checkbox" id="mcTrim" checked/><span class="track"></span><span>Подрезать тишину</span></label>
        <button class="btn-primary" id="mcAdd" type="button">Добавить клип</button>
      </div>
    </div>`;
}

function pipCardHTML(detail) {
  const project = detail.project;
  if (!project) return "";
  const conf = (project.options && project.options.pip) || {};
  const on = conf.enabled !== false;
  const pos = conf.pos || [0.72, 0.78];
  const corner = conf.cam_corner || "bottom-right";
  const corners = [["top-left", "↖"], ["top-right", "↗"], ["bottom-left", "↙"], ["bottom-right", "↘"]];
  const slots = [];
  for (let row = 0; row < 3; row += 1) {
    for (let col = 0; col < 3; col += 1) {
      const x = col / 2;
      const y = row / 2;
      const active = Math.abs(pos[0] - x) < 0.04 && Math.abs(pos[1] - y) < 0.04;
      slots.push(`<button class="pip-slot ${active ? "active" : ""}" data-x="${x}" data-y="${y}" type="button" aria-label="окно ${col},${row}"></button>`);
    }
  }
  return `
    <div class="pip-card" id="pipCard">
      <div class="pip-head">
        <div>
          <div class="pip-title">Окно стримера</div>
          <div class="pip-sub">Главным остаётся рабочее поле, а камера стримера — отдельным окном. Выберите, где она в кадре и куда поставить окно.</div>
        </div>
        <label class="toggle"><input type="checkbox" id="pipToggle" ${on ? "checked" : ""}/><span class="track"></span></label>
      </div>
      <div class="pip-grid">
        <div class="pip-block">
          <div class="pip-label">Камера в кадре</div>
          <div class="pip-corners" id="pipCamCorner">
            ${corners.map(([key, icon]) => `<button class="pip-corner ${corner === key ? "active" : ""}" data-corner="${key}" type="button">${icon}</button>`).join("")}
          </div>
          <div class="pip-hint">В каком углу исходника сидит стример</div>
        </div>
        <div class="pip-block">
          <div class="pip-label">Окно на клипе</div>
          <div class="pip-slots" id="pipSlots">${slots.join("")}</div>
          <div class="pip-hint">Куда его поставить: края или по центру</div>
        </div>
        <div class="pip-block">
          <div class="pip-label">Размер окна</div>
          <input type="range" id="pipSize" min="16" max="42" value="${Math.round((conf.size || 0.28) * 100)}"/>
          <div class="pip-hint"><span id="pipSizeVal">${Math.round((conf.size || 0.28) * 100)}%</span> ширины клипа</div>
        </div>
      </div>
      <div class="pip-controls">
        <button class="btn-primary" id="pipApply" type="button">Применить</button>
        <button class="btn-ghost" id="pipRebuild" type="button">Пересобрать с окном</button>
      </div>
    </div>`;
}

async function initPip(detail) {
  const card = $("#pipCard");
  if (!card || !detail || !detail.project) return;
  const project = detail.project;
  let conf = (project.options && project.options.pip) || {};
  conf = {
    enabled: conf.enabled !== false,
    pos: conf.pos || [0.72, 0.78],
    cam_corner: conf.cam_corner || "bottom-right",
    size: conf.size || 0.28,
    radius: conf.radius || 20,
  };

  async function savePip() {
    try {
      await api(`/api/projects/${project.id}/pip`, {
        method: "POST",
        body: JSON.stringify({
          enabled: conf.enabled,
          pos: conf.pos,
          cam_corner: conf.cam_corner,
          size: conf.size,
          radius: conf.radius,
        }),
      });
    } catch (e) { console.error("pip save", e); }
  }

  $("#pipToggle").checked = conf.enabled;
  $("#pipToggle").addEventListener("change", () => { conf.enabled = $("#pipToggle").checked; savePip(); });

  $("#pipCamCorner").addEventListener("click", (e) => {
    const btn = e.target.closest(".pip-corner");
    if (!btn) return;
    conf.cam_corner = btn.dataset.corner;
    $$("#pipCamCorner .pip-corner").forEach((b) => b.classList.toggle("active", b === btn));
    savePip();
  });

  $("#pipSlots").addEventListener("click", (e) => {
    const btn = e.target.closest(".pip-slot");
    if (!btn) return;
    conf.pos = [Number(btn.dataset.x), Number(btn.dataset.y)];
    $$("#pipSlots .pip-slot").forEach((b) => b.classList.toggle("active", b === btn));
    savePip();
  });

  $("#pipSize").addEventListener("input", (e) => {
    conf.size = Number(e.target.value) / 100;
    $("#pipSizeVal").textContent = `${e.target.value}%`;
  });
  $("#pipSize").addEventListener("change", savePip);

  $("#pipApply").addEventListener("click", async () => { await savePip(); toast("Окно сохранено"); });
  $("#pipRebuild").addEventListener("click", async () => {
    await savePip();
    try {
      const res = await api(`/api/projects/${project.id}/pip/apply`, { method: "POST", body: JSON.stringify({}) });
      toast(`Пересобираю клипов: ${res.clips}`);
      poll();
    } catch (e) { toast(e.message, "err"); }
  });
}

function bindUpdateCard() {
  const card = $("#updateCard");
  if (!card) return;
  const hide = $("#updateHide");
  if (hide) {
    hide.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const title = $("#updateTitle").textContent || "";
      const version = title.replace(/^[^\d]*/, "").trim();
      if (version) localStorage.setItem("vcUpdateDismissed", version);
      card.hidden = true;
    });
  }
}

window.addEventListener("hashchange", () => {
  const id = location.hash.replace("#", "");
  if (id && id !== state.current) {
    openProject(id);
  } else if (!id && state.current) {
    state.current = null;
    state.detail = null;
    state.mainKey = "";
    clearTimeout(state.pollTimer);
    renderMain(true);
    renderSidebar();
  }
});

/* ---------------- Надёжный старт ---------------- */

function showFatal(message, details) {
  const main = $("#main");
  if (!main) return;
  main.innerHTML = `
    <div class="fatal-box">
      <div class="fatal-title">Интерфейс не загрузился</div>
      <p class="fatal-text">${esc(message)}</p>
      ${details ? `<pre class="fatal-details">${esc(details)}</pre>` : ""}
      <div class="fatal-actions">
        <button class="btn-primary" id="fatalReload">Перезагрузить</button>
        <button class="btn-ghost" id="fatalCopy">Скопировать ошибку</button>
      </div>
      <p class="fatal-hint">Если не помогает — закройте приложение и откройте заново. Файл лога: в папке данных ViralCut, app.log.</p>
    </div>`;
  const reload = $("#fatalReload");
  if (reload) reload.addEventListener("click", () => location.reload());
  const copy = $("#fatalCopy");
  if (copy) copy.addEventListener("click", () => {
    const text = `${message}\n${details || ""}`;
    try { navigator.clipboard.writeText(text); toast("Ошибка скопирована"); }
    catch (_) { toast("Не удалось скопировать", "err"); }
  });
}

window.addEventListener("error", (event) => {
  if (state.bootDone) return;
  showFatal("Ошибка в скрипте приложения", String(event.message || event.error || ""));
});
window.addEventListener("unhandledrejection", (event) => {
  if (state.bootDone) return;
  showFatal("Не удалось загрузить данные", String((event.reason && event.reason.message) || event.reason || ""));
});

async function withRetry(fn, tries = 4, delay = 500) {
  let lastError = null;
  for (let i = 0; i < tries; i += 1) {
    try { return await fn(); } catch (err) { lastError = err; await new Promise((r) => setTimeout(r, delay)); }
  }
  throw lastError;
}

(async function boot() {
  // каждый шаг изолирован: падение одного не должно оставлять пустой экран
  const watchdog = setTimeout(() => {
    if (!state.bootDone) showFatal("Интерфейс не загрузился за 12 секунд",
      "Сервер мог не ответить. Проверьте, что не блокирует антивирус/файрвол.");
  }, 12000);

  try { bindUpdateCard(); } catch (e) { console.error(e); }
  try { $("#settingsBtn")?.addEventListener("click", openSettings); } catch (e) { console.error(e); }
  try { bindHud(); } catch (e) { console.error(e); }
  try { pollSystem(); setInterval(pollSystem, 2000); } catch (e) { console.error(e); }
  try { checkUpdates(); setInterval(checkUpdates, 30 * 60 * 1000); } catch (e) { console.error(e); }

  try {
    await withRetry(() => checkHealth(), 5, 700);
  } catch (e) {
    console.error(e);
  }

  try { await loadFontCatalog(); } catch (e) { console.error(e); }

  try {
    await withRetry(() => loadProjects(), 4, 600);
  } catch (e) {
    clearTimeout(watchdog);
    showFatal("Не удалось получить список проектов", String((e && e.message) || e));
    return;
  }

  state.bootDone = true;
  clearTimeout(watchdog);

  try {
    const hash = location.hash.replace("#", "");
    if (hash && state.projects.some((p) => p.id === hash)) {
      openProject(hash);
    } else {
      renderMain(true);
    }
  } catch (e) {
    console.error(e);
    showFatal("Не удалось отрисовать экран", String((e && e.stack) || e));
  }
  setInterval(checkHealth, 20000);
})();

/* YouTube discovery: selecting a recommendation opens the existing confirmation. */
function openDiscovery() {
  const modal = $("#modal");
  modal.innerHTML = `<div class="modal-backdrop" data-close="discovery"></div>
    <div class="modal-panel discovery-panel"><div class="modal-head"><h3>Видео для нарезок</h3>
    <button class="icon-btn" data-close="discovery" aria-label="Закрыть">${ICONS.close}</button></div>
    <form id="discoveryForm" class="discovery-form">
    <label>Аудитория<select name="audience"><option value="ru">Русскоязычная</option><option value="en">Англоязычная</option></select></label>
    <label>Тема<select name="topic"><option value="general">Подкасты и интервью</option><option value="business">Бизнес</option><option value="science">Наука и технологии</option><option value="psychology">Психология</option><option value="comedy">Юмор</option></select></label>
    <label>Свой запрос<input name="query" maxlength="120" placeholder="Например: космос / space" /></label>
    <label>Порядок<select name="sort"><option value="recommended">Для нарезки</option><option value="views">Больше просмотров</option></select></label>
    <button class="btn-primary" type="submit">Найти рекомендации</button></form>
    <p class="discovery-note">Видео от 4 минут до 4 часов. Выбор языка ориентировочный, по заголовку. Скачивание начнётся только после вашего подтверждения качества и размера.</p>
    <div id="discoveryResults" aria-live="polite"></div></div>`;
  modal.classList.remove("hidden");
  modal.querySelectorAll('[data-close="discovery"]').forEach(el => el.addEventListener("click", () => {
    modal.classList.add("hidden"); modal.innerHTML = "";
  }));
  const form = $("#discoveryForm");
  form.addEventListener("submit", async ev => {
    ev.preventDefault();
    const results = $("#discoveryResults");
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true; results.innerHTML = '<p><span class="spinner"></span> Ищем видео на YouTube…</p>';
    const values = Object.fromEntries(new FormData(form));
    try {
      const data = await api("/api/discovery", {method:"POST", body:JSON.stringify(values)});
      if (!results.isConnected) return;
      results.innerHTML = `<p class="discovery-note">${esc(data.notice)}</p><div class="discovery-grid">${data.items.map((v,i) => `
        <article class="discovery-card"><img src="${esc(v.thumbnail)}" alt="" loading="lazy" />
        <h4>${esc(v.title)}</h4><p>${esc(v.channel)} · ${fmtDur(v.duration)}</p>
        <p>${v.views == null ? "Просмотры неизвестны" : Number(v.views).toLocaleString("ru-RU") + " просмотров"}</p>
        <p>${esc(v.reason)} · язык по заголовку: ${esc(v.language_hint)}</p>
        <a href="${esc(v.url)}" target="_blank" rel="noopener">Посмотреть на YouTube ↗</a>
        <button class="btn-primary" data-pick="${i}">Выбрать для нарезки</button></article>`).join("")}</div>
        ${data.items.length ? "" : "<p>Подходящие видео не найдены. Попробуйте другую тему или запрос на выбранном языке.</p>"}`;
      results.querySelectorAll("[data-pick]").forEach(el => el.addEventListener("click", () => {
        const v = data.items[Number(el.dataset.pick)];
        state.opts.language = "auto";
        askQuality(v.url);
      }));
    } catch (err) { if (results.isConnected) results.textContent = err.message; }
    finally { btn.disabled = false; }
  });
}

async function openComposition(projectId = null, mount = null) {
  let saved = state.composition || {};
  if (projectId) saved = state.detail?.project?.options?.composition || {};
  const draft = {...saved};
  const modal = mount || document.querySelector("#modal");
  const $ = selector => modal.querySelector(selector);
  modal.innerHTML = `<div class="modal-backdrop" data-close></div><div class="modal-panel discovery-panel">
    <div class="modal-head"><h3>Игра, логотип и реклама</h3><button class="icon-btn" data-close aria-label="Закрыть">${ICONS.close}</button></div>
    <div class="composition-body">
    <p class="discovery-note">Настройки применяются ко всем клипам проекта. Это формат с дополнительным видеорядом, без обещаний влияния на внимание.</p>
    <section class="composition-section"><h4>Видео с игрой</h4>
    <label class="toggle"><input type="checkbox" id="gameEnabled" ${draft.game?'checked':''}><span class="track"></span><span> Добавить игровой видеоряд без звука</span></label>
    <div class="discovery-form"><label>Игра<select id="gameStyle"><option value="auto">Автовыбор: Minecraft Parkour</option><option value="minecraft parkour gameplay no commentary">Minecraft Parkour</option><option value="subway surfers gameplay no commentary">Subway Surfers</option><option value="trackmania gameplay no commentary">Trackmania</option></select></label>
    <label>Расположение игры<select id="gamePosition"><option value="bottom">Снизу</option><option value="top">Сверху</option></select></label></div>
    <p class="discovery-note">Автовыбор предлагает Minecraft Parkour как непрерывный фон. Содержание основного ролика не анализируется. Игра повторяется до конца клипа.</p>
    <button class="btn-ghost" id="gameSearch">Подобрать игровой ролик на YouTube</button>
    <label class="btn-ghost composition-upload">Загрузить свою игру<input type="file" data-asset="game" accept="video/*"></label>
    <p id="gameAsset">${draft.game?'Игровой файл выбран':'Игровой файл не выбран'}</p>
    <video id="gamePreview" class="composition-preview" controls muted playsinline ${draft.game?`src="/api/composition/assets/${esc(draft.game)}"`:"hidden"}></video>
    <label class="toggle"><input id="gameVariety" type="checkbox" ${draft.game_variety!==false?"checked":""}><span class="track"></span><span> Разный игровой участок для каждой нарезки</span></label>
    <label>Начало игрового участка, секунды (пусто — авто)<input id="gameStart" type="number" min="0" step="0.5" value="${draft.game_start == null?'':Number(draft.game_start)}" placeholder="Авто: участок с движением"></label>
    <p id="gameAnalysis" class="discovery-note">Проверьте, что в предпросмотре идёт игра. Автопоиск движения может ошибаться.</p><div id="gameResults" aria-live="polite"></div></section>
    <section class="composition-section"><h4>Логотип на всех клипах</h4>
    <label class="toggle"><input type="checkbox" id="logoEnabled" ${draft.logo?'checked':''}><span class="track"></span><span> Добавить логотип</span></label>
    <label class="btn-ghost composition-upload">Загрузить изображение<input type="file" data-asset="logo" accept="image/png,image/jpeg,image/webp"></label>
    <p id="logoAsset">${draft.logo?'Логотип выбран':'Поддерживается прозрачный PNG'}</p>
    <label class="toggle"><input type="checkbox" id="logoBackground" ${draft.logo_remove_background?'checked':''}><span class="track"></span><span> Убрать однотонный фон логотипа</span></label>
    <div class="discovery-form"><label>Положение<select id="logoPosition"><option value="top-right">Вверху справа</option><option value="top-left">Вверху слева</option><option value="bottom-right">Внизу справа</option><option value="bottom-left">Внизу слева</option></select></label>
    <label>Размер (% ширины)<input id="logoSize" type="number" min="5" max="30" value="${Number(draft.logo_size)||9}"></label></div></section>
    <section class="composition-section"><h4>Рекламная вставка</h4>
    <label class="toggle"><input type="checkbox" id="adEnabled" ${draft.ad?'checked':''}><span class="track"></span><span> Вставить рекламу в каждый клип</span></label>
    <label class="btn-ghost composition-upload">Загрузить рекламное видео<input type="file" data-asset="ad" accept="video/*"></label>
    <p id="adAsset">${draft.ad?'Рекламный файл выбран':'Ролик от 1 до 120 секунд'}</p>
    <p class="discovery-note">Ищем паузу в средней части готового клипа. Если паузы нет — вставляем в середину. После рекламы видео продолжается с места остановки. Проверьте монтаж перед публикацией.</p></section>
    <p id="compositionStatus" role="status"></p><button class="btn-primary" id="compositionSave">${projectId?'Сохранить и пересобрать клипы':'Сохранить для нового проекта'}</button>
    </div></div>`;
  if (mount) {
    const body=modal.querySelector('.composition-body');
    modal.replaceChildren(body);
    body.querySelector(':scope > .discovery-note')?.remove();
    const labels=['Игра','Логотип','Реклама'];
    body.querySelectorAll('.composition-section').forEach((section,i)=>{
      const details=document.createElement('details');
      details.className='composition-section composition-disclosure';
      details.open=Boolean(draft[['game','logo','ad'][i]]);
      const summary=document.createElement('summary');
      summary.innerHTML=`<span class="composition-icon">${[ICONS.play,ICONS.spark,ICONS.play][i]}</span><span>${labels[i]}</span><small>${draft[['game','logo','ad'][i]]?'Включено':'Не добавлено'}</small>`;
      section.querySelector('h4')?.remove();
      details.append(summary,...Array.from(section.childNodes));
      section.replaceWith(details);
    });
    $('#compositionSave').hidden=true;
  } else modal.classList.remove('hidden');
  $('#gamePosition').value = draft.game_position || 'bottom';
  $('#logoPosition').value = draft.logo_position || 'top-right';
  async function previewGame() {
    if(!draft.game) return;
    const video=$('#gamePreview'); const note=$('#gameAnalysis');
    video.hidden=false; video.src='/api/composition/assets/'+encodeURIComponent(draft.game);
    try {
      const info=await api('/api/composition/game-info/'+encodeURIComponent(draft.game));
      if(!video.isConnected)return;
      const start=$('#gameStart').value===''?info.start:Number($('#gameStart').value);
      const seek=()=>{video.currentTime=Math.min(start,Math.max(0,video.duration-1));};
      if(video.readyState>=1)seek();else video.addEventListener('loadedmetadata',seek,{once:true});
      note.textContent=`Автопоиск: с ${fmtDur(info.start)}, участок ${fmtDur(info.length)}. Проверьте его перед сохранением.`;
    }catch(e){if(note.isConnected)note.textContent=e.message;}
  }
  $('#gameStart').addEventListener('change',()=>{const v=$('#gamePreview');if(v.src&&$('#gameStart').value!=='')v.currentTime=Number($('#gameStart').value);});
  if(draft.game)previewGame();
  let busy = 0;
  const status = $('#compositionStatus');
  const save = $('#compositionSave');
  const lock = delta => { busy += delta; save.disabled = busy > 0; if(mount){const start=document.querySelector('#startBtn');if(start)start.disabled=busy>0;} };
  modal.querySelectorAll('[data-asset]').forEach(input => input.addEventListener('change', async () => {
    const file = input.files[0]; if (!file) return;
    const kind = input.dataset.asset;
    lock(1); status.textContent = 'Загружаем файл…';
    try {
      const body = new FormData(); body.append('kind',kind); body.append('file',file);
      const result = await api('/api/composition/upload',{method:'POST',body});
      draft[kind] = result.id; $(`#${kind}Asset`).textContent = result.name;
      if(kind==='game'){$('#gameStart').value='';await previewGame();}
      $(`#${kind}Enabled`).checked = true; syncInline(); status.textContent = 'Файл готов';
    } catch(e) { status.textContent = e.message; }
    finally { lock(-1); }
  }));
  $('#gameSearch').addEventListener('click', async () => {
    const results = $('#gameResults');
    const searchBtn = $('#gameSearch'); searchBtn.disabled = true;
    results.textContent = 'Ищем игровой видеоряд…';
    try {
      const style = $('#gameStyle').value;
      const data = await api('/api/discovery',{method:'POST',body:JSON.stringify({audience:'en',topic:'gameplay',query:style==='auto'?'':style,sort:'views'})});
      if (!results.isConnected) return;
      results.innerHTML = `<p class="discovery-note">Рекомендуем первый по просмотрам среди подходящих результатов. Выберите запись, на использование которой у вас есть разрешение. Скачается до 3 минут из середины записи (720p); затем найдём участок с движением.</p><div class="discovery-grid">${data.items.slice(0,6).map((v,i)=>`<article class="discovery-card"><img src="${esc(v.thumbnail)}" alt="" loading="lazy"><h4>${esc(v.title)}</h4><p>${v.views == null?'Просмотры неизвестны':Number(v.views).toLocaleString('ru-RU')+' просмотров'}</p><a href="${esc(v.url)}" target="_blank" rel="noopener">Посмотреть ↗</a><button class="btn-primary" data-game="${i}">${i===0?'Скачать рекомендованный':'Скачать этот ролик'}</button></article>`).join('')}</div>${data.items.length?'':'Подходящие записи не найдены. Загрузите свой файл.'}`;
      results.querySelectorAll('[data-game]').forEach(button=>button.addEventListener('click',async()=>{
        const v=data.items[Number(button.dataset.game)];
        lock(1); results.querySelectorAll('button').forEach(b=>b.disabled=true); status.textContent='Скачиваем игровой участок и проверяем движение…';
        try {
          const result=await api('/api/composition/game',{method:'POST',body:JSON.stringify({video_id:v.id})});
          draft.game=result.id; if (!status.isConnected) return;
          $('#gameAsset').textContent=v.title; $('#gameEnabled').checked=true; $('#gameStart').value=''; await previewGame(); syncInline(); status.textContent='Игровой фон готов — проверьте предпросмотр';
        } catch(e) { if(status.isConnected) status.textContent=e.message; }
        finally {lock(-1);results.querySelectorAll('button').forEach(b=>b.disabled=false);}
      }));
    } catch(e) {results.textContent=e.message;} finally {searchBtn.disabled=false;}
  });
  function collectComposition(strict=false) {
    const conf={game_position:$('#gamePosition').value,logo_position:$('#logoPosition').value,logo_size:Number($('#logoSize').value),logo_remove_background:$('#logoBackground').checked,game_start:$('#gameStart').value===''?null:Number($('#gameStart').value),game_variety:$('#gameVariety').checked};
    for(const kind of ['game','logo','ad']) {
      if($(`#${kind}Enabled`).checked) {
        if(!draft[kind]) {
          if(strict)throw new Error('Сначала выберите файл: '+({game:'игра',logo:'логотип',ad:'реклама'}[kind]));
        } else conf[kind]=draft[kind];
      }
    }
    return conf;
  }
  function syncInline() {
    if(!mount)return;
    state.composition=collectComposition();
    const kinds=['game','logo','ad'];
    mount.querySelectorAll('summary small').forEach((label,i)=>{
      const enabled=$(`#${kinds[i]}Enabled`).checked;
      label.textContent=enabled?(draft[kinds[i]]?'Включено':'Выберите файл'):'Выключено';
      label.classList.toggle('is-on',enabled&&Boolean(draft[kinds[i]]));
    });
  }
  if(mount)mount.addEventListener('change',syncInline);
  save.addEventListener('click',async()=>{
    let conf;
    try {conf=collectComposition(true);}catch(e){status.textContent=e.message;return;}
    try {
      if(projectId) {
        lock(1);
        await api(`/api/projects/${projectId}/composition`,{method:'POST',body:JSON.stringify(conf)});
        toast('Настройки сохранены, клипы пересобираются');
      } else {state.composition=conf;toast('Настройки композиции сохранены');}
      if(!mount)closeModal();
    } catch(e) {status.textContent=e.message;} finally {if(projectId)lock(-1);}
  });
}


/* ---------------- YouTube publishing ---------------- */
function youtubeAccountHTML(status) {
  if(!status)return '<span class="set-hint">Не удалось проверить подключение</span>';
  if(status.connected)return `<span class="youtube-account-dot connected"></span><span><b>${esc(status.channel?.title||'Канал подключён')}</b><small>Готов к загрузке видео</small></span>`;
  return `<span class="youtube-account-dot"></span><span><b>Канал не подключён</b><small>${esc(status.storage_error||status.auth_error||(status.connecting?'Ожидаем входа в Google…':status.configured?'OAuth настроен · можно подключить канал':'Подключите свой канал для публикации'))}</small></span>`;
}

function bindYoutubeSettings() {
  const message=$('#youtubeSettingsMessage');
  const update=async()=>{
    if(!message.isConnected)return;
    const status=await api('/api/youtube/status');
    $('#youtubeAccount').innerHTML=youtubeAccountHTML(status);
    $('#youtubeDisconnect').hidden=!status.connected;
    $('#youtubeConnect').disabled=status.connected||status.connecting;
    if(status.connecting&&message.isConnected)setTimeout(()=>update().catch(()=>{}),1500);
    return status;
  };
  update().catch(()=>{});
  $('#youtubeClientFile').addEventListener('change',async ev=>{
    const file=ev.target.files[0];if(!file)return;
    message.textContent='Проверяем OAuth-файл…';
    try {
      const body=new FormData();body.append('file',file);
      await api('/api/youtube/client',{method:'POST',body});
      message.textContent='Файл готов. Теперь подключите канал.';await update();
    }catch(e){message.textContent=e.message;}
  });
  $('#youtubeConnect').addEventListener('click',async()=>{
    const button=$('#youtubeConnect');button.disabled=true;
    // Open a blank window during the user gesture so browser popup protection permits OAuth.
    const native=window.pywebview?.api;
    const authWindow=native?.open_url?null:window.open('about:blank','viralcut-youtube-auth');
    try {
      const result=await api('/api/youtube/connect',{method:'POST'});
      if(native?.open_url)await native.open_url(result.authorization_url);
      else if(authWindow)authWindow.location.href=result.authorization_url;
      else {
        message.innerHTML=`<a href="${esc(result.authorization_url)}" target="_blank" rel="noopener">Открыть вход в Google ↗</a>`;
      }
      await update();
    }catch(e){authWindow?.close();message.textContent=e.message;button.disabled=false;}
  });
  $('#youtubeDisconnect').addEventListener('click',async()=>{
    try {
      const result=await api('/api/youtube/disconnect',{method:'POST'});
      message.textContent=result.revoked?'Канал отключён.': 'Канал отключён здесь. Отозвать доступ в Google не удалось — это можно сделать в настройках Google-аккаунта.';
      await update();
    }catch(e){message.textContent=e.message;}
  });
}

$('#main').addEventListener('click',ev=>{
  const button=ev.target.closest('[data-youtube]');
  if(button){ev.preventDefault();ev.stopPropagation();openYoutubePublish(button.dataset.youtube);}
});

async function openYoutubePublish(clipId) {
  const clip=state.detail?.clips?.find(c=>c.id===clipId);if(!clip)return;
  let status;
  try{status=await api('/api/youtube/status');}catch(e){toast(e.message,'err');return;}
  const project=state.detail.project;
  const url=`/media/${project.id}/clips/clip_${String(clip.idx+1).padStart(2,'0')}.mp4?v=${Math.round(clip.updated_at||0)}`;
  $('#modal').innerHTML=`<div class="modal-backdrop" data-close></div><div class="modal-panel youtube-panel">
    <div class="modal-head"><h3>Публикация на YouTube</h3><button class="icon-btn" data-close aria-label="Закрыть">${ICONS.close}</button></div>
    <div class="youtube-publish-layout"><div class="youtube-preview-column"><video controls playsinline preload="metadata" poster="/media/${project.id}/thumbs/${clip.id}.jpg?v=${Math.round(clip.updated_at||0)}" src="${esc(url)}#t=0.1"></video><p class="set-hint">Проверьте клип перед загрузкой. Вертикальный ролик подходящей длительности YouTube может отнести к Shorts.</p></div>
    <div class="youtube-fields"><div class="youtube-account">${youtubeAccountHTML(status)}</div>
    ${!status.connected?'<button class="btn-primary" id="youtubeGoSettings">Подключить канал в настройках</button>':''}
    <form id="youtubePublishForm">
      <label class="youtube-field">Название<input id="youtubeTitle" maxlength="100" required value="${esc((clip.title||'Новый клип').slice(0,100))}"><small id="youtubeTitleCount"></small></label>
      <label class="youtube-field">Описание<textarea id="youtubeDescription" maxlength="5000" rows="4">${esc(clip.caption||'')}</textarea></label>
      <label class="youtube-field">Доступ<select id="youtubePrivacy"><option value="private">Личное — только вы</option><option value="unlisted">Доступ по ссылке</option><option value="public">Открытый доступ — всем</option></select></label>
      <label class="youtube-field">Аудитория<select id="youtubeAudience" required><option value="">Выберите аудиторию</option><option value="no">Видео не для детей</option><option value="yes">Видео для детей</option></select></label>
      <label class="toggle"><input type="checkbox" id="youtubeSynthetic"><span class="track"></span><span>Реалистичный изменённый или ИИ-контент</span></label>
      <label class="toggle"><input type="checkbox" id="youtubePaid" ${project.options?.composition?.ad?'checked':''}><span class="track"></span><span>Есть платная реклама или интеграция</span></label>
      <label class="toggle"><input type="checkbox" id="youtubeSchedule"><span class="track"></span><span>Опубликовать по расписанию</span></label>
      <label class="youtube-field" id="youtubeScheduleField" hidden>Дата и время (часовой пояс этого компьютера)<input type="datetime-local" id="youtubePublishAt"></label>
      <p class="set-hint" id="youtubePublishHint">Видео будет загружено как личное. Позже доступ можно поменять в YouTube Studio.</p>
      <button class="btn-primary" id="youtubeSubmit" type="submit" ${status.connected?'':'disabled'}>Загрузить на YouTube</button>
    </form>
    <div id="youtubeUploadStatus" class="youtube-upload-status" aria-live="polite"></div>
    </div></div></div>`;
  $('#modal').classList.remove('hidden');
  $('#youtubeGoSettings')?.addEventListener('click',openSettings);
  const form=$('#youtubePublishForm');const output=$('#youtubeUploadStatus');let currentJob=null;
  const updateForm=()=>{
    $('#youtubeTitleCount').textContent=`${$('#youtubeTitle').value.length} / 100`;
    const scheduled=$('#youtubeSchedule').checked;
    $('#youtubeScheduleField').hidden=!scheduled;$('#youtubePublishAt').required=scheduled;
    if(scheduled)$('#youtubePrivacy').value='private';
    $('#youtubePrivacy').disabled=scheduled;
    $('#youtubePublishHint').textContent=scheduled?'Сейчас файл загрузится как личный. В выбранное время YouTube откроет доступ всем.':$('#youtubePrivacy').value==='public'?'После загрузки видео будет доступно всем.':'Видео загрузится с выбранным доступом.';
  };
  form.addEventListener('input',updateForm);form.addEventListener('change',updateForm);updateForm();
  async function showJob(job) {
    if(!output.isConnected)return;
    currentJob=job;
    const busy=['queued','uploading','cancelling'].includes(job.status);
    $('#youtubeSubmit').disabled=busy||(job.status==='done'&&job.clip_updated_at===clip.updated_at)||!status.connected;
    const labels={queued:'В очереди',uploading:'Загружаем видео',done:'Видео загружено',error:'Загрузка не завершена',interrupted:'Загрузка прервана',cancelled:'Загрузка отменена'};
    output.innerHTML=`<b>${labels[job.status]||'Загрузка'}</b>${busy?`<progress max="100" value="${Number(job.progress)||0}"></progress><span>${Number(job.progress)||0}%</span><button type="button" class="btn-ghost" id="youtubeCancelUpload">Отменить загрузку</button>`:''}${job.url?`<a href="${esc(job.url)}" target="_blank" rel="noopener">Открыть видео на YouTube ↗</a>`:''}<p class="set-hint">${esc(job.error||job.message||'')}</p>`;
    $('#youtubeCancelUpload')?.addEventListener('click',async()=>{
      try{await api(`/api/youtube/uploads/${job.id}/cancel`,{method:'POST'});output.querySelector('b').textContent='Отменяем загрузку…';}catch(e){toast(e.message,'err');}
    });
    if(busy)setTimeout(async()=>{
      if(!output.isConnected)return;
      try{const jobs=await api('/api/youtube/uploads?clip_id='+encodeURIComponent(clipId));const next=jobs.find(j=>j.id===job.id);if(next)showJob(next);}catch(e){output.textContent='Не удалось обновить статус. Откройте публикацию ещё раз для проверки.';}
    },1500);
  }
  form.addEventListener('submit',async ev=>{
    ev.preventDefault();const button=$('#youtubeSubmit');button.disabled=true;
    try {
      const payload={title:$('#youtubeTitle').value.trim(),description:$('#youtubeDescription').value,privacy:$('#youtubePrivacy').value,made_for_kids:$('#youtubeAudience').value==='yes',synthetic_media:$('#youtubeSynthetic').checked,paid_promotion:$('#youtubePaid').checked};
      if($('#youtubeSchedule').checked){
        const when=new Date($('#youtubePublishAt').value);
        if(!Number.isFinite(when.getTime())||when<=new Date())throw new Error('Выберите будущее время публикации');
        payload.publish_at=when.toISOString();
      }
      const job=await api(`/api/youtube/clips/${clipId}/publish`,{method:'POST',body:JSON.stringify(payload)});showJob(job);
    }catch(e){output.textContent=e.message;button.disabled=!status.connected;}
  });
  try{const jobs=await api('/api/youtube/uploads?clip_id='+encodeURIComponent(clipId));if(jobs.length)showJob(jobs[0]);}catch(_){}
}
