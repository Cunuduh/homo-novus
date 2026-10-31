let lookFile = "", lookGhost = true;
const NS = "http://www.w3.org/2000/svg";
const $ = id => document.getElementById(id);
const clientId = crypto.randomUUID();
const hexPts = (cx, cy, r) => [0, 1, 2, 3, 4, 5].map(i => {
  const a = Math.PI / 3 * i - Math.PI / 2;
  return `${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`;
}).join(" ");

// Slots sit on the figure, in the drawing's own coordinates (800 x 1087).
const PARTS = [
  { key: "face", label: "Caput", plain: "face", num: "I", hex: [398, 272, 58], tag: [466, 228], focus: .36, sample: ["face_lincoln.jpg", "face_curie.jpg"] },
  { key: "arms", label: "Brachia", plain: "arms", num: "II", hex: [212, 338, 58], tag: [150, 262], focus: .55, sample: ["arms_houdini.jpg", "arms_melba.jpg"] },
  { key: "torso", label: "Truncus", plain: "torso", num: "III", hex: [398, 446, 90], tag: [498, 450], focus: .5, sample: ["torso_roosevelt.jpg", "torso_tubman.jpg"] },
  { key: "legs", label: "Crura", plain: "legs", num: "IV", hex: [398, 646, 72], tag: [482, 650], focus: .76, sample: ["legs_keaton.jpg", "legs_earhart.jpg"] },
];
const SEAMS = ["M398 330L398 356", "M270 338Q300 340 336 392", "M398 500L398 574"];
const files = {};
const svg = $("overlay");
const el = (name, attrs = {}, parent = svg) => {
  const n = document.createElementNS(NS, name);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
};

const picker = document.createElement("input");
picker.type = "file"; picker.accept = "image/*"; picker.hidden = true;
document.body.appendChild(picker);
let target = null;
picker.onchange = () => { if (picker.files[0] && target) setPart(target, picker.files[0]); picker.value = ""; };
const choose = part => { target = part; picker.click(); };

const chalkMask = el("mask", { id: "outside-circle", maskUnits: "userSpaceOnUse", x: 0, y: 0, width: 800, height: 1087 });
el("rect", { x: 0, y: 0, width: 800, height: 1087, fill: "#fff" }, chalkMask);
el("ellipse", { cx: 399.2, cy: 446.9, rx: 337, ry: 336, fill: "#000" }, chalkMask);
el("image", { href: "assets/vitruvian_chalk.png", x: 0, y: 0, width: 800, height: 1087, class: "chalk" });
// Faint honeycomb construction lines behind the slots.
for (const [x, y] of [[300, 196], [496, 196], [114, 338], [310, 338], [486, 338], [584, 338], [290, 560], [506, 560], [212, 700], [584, 700], [290, 740], [506, 740]])
  el("polygon", { points: hexPts(x, y, 52), class: "guide" });

const defs = el("defs");
for (const p of PARTS) {
  const [cx, cy, r] = p.hex;
  const points = hexPts(cx, cy, r);
  el("polygon", { points }, el("clipPath", { id: "clip-" + p.key }, defs));
  const g = el("g", { class: `zone zone-${p.key}`, tabindex: 0, role: "button", "aria-label": `Add image: ${p.plain}` });
  el("polygon", { points: hexPts(cx, cy, r + 8), class: "halo" }, g);
  el("polygon", { points, class: "plate" }, g);
  p.image = el("image", { x: cx - r, y: cy - r, width: r * 2, height: r * 2, "clip-path": `url(#clip-${p.key})` }, g);
  p.image.style.display = "none";
  el("polygon", { points, class: "rim" }, g);
  el("text", { x: cx, y: cy, class: "plus" }, g).textContent = "+";
  el("text", { x: p.tag[0], y: p.tag[1], class: "tag" }).textContent = p.label;
  p.zone = g;
  g.onclick = () => choose(p);
  g.onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); choose(p); } };
  for (const ev of ["dragenter", "dragover"]) g.addEventListener(ev, e => { e.preventDefault(); g.classList.add("over"); });
  g.addEventListener("dragleave", () => g.classList.remove("over"));
  g.addEventListener("drop", e => { e.preventDefault(); g.classList.remove("over"); const f = e.dataTransfer.files[0]; if (f) setPart(p, f); });

  const li = document.createElement("li");
  li.className = "part";
  li.tabIndex = 0; li.setAttribute("role", "button"); li.setAttribute("aria-label", `Add image: ${p.plain}`);
  li.onkeydown = e => { if (e.target === li && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); showParts(); choose(p); } };
  li.innerHTML = `<div><b>${p.label}</b><small>${p.plain}</small></div>
    <span class="num">${p.num}</span><button type="button" class="x" hidden aria-label="Remove ${p.plain}">Remove</button>`;
  $("rows").appendChild(li);
  p.row = li;
  li.onclick = () => { showParts(); choose(p); };
  li.querySelector(".x").onclick = e => { e.stopPropagation(); clearPart(p); };
  const mark = on => { li.classList.toggle("on", on); g.classList.toggle("on", on); };
  for (const n of [li, g]) { n.addEventListener("pointerenter", () => mark(true)); n.addEventListener("pointerleave", () => mark(false)); }
  for (const ev of ["dragenter", "dragover"]) li.addEventListener(ev, e => { e.preventDefault(); mark(true); });
  li.addEventListener("dragleave", () => mark(false));
  li.addEventListener("drop", e => { e.preventDefault(); e.stopPropagation(); mark(false); const f = e.dataTransfer.files[0]; if (f) setPart(p, f); });
}
// A file dropped anywhere else fills the first empty slot.
for (const ev of ["dragover", "drop"]) document.addEventListener(ev, e => e.preventDefault());
document.addEventListener("drop", e => {
  if (e.target.closest && e.target.closest(".zone")) return;
  [...e.dataTransfer.files].filter(f => f.type.startsWith("image/")).forEach(f => {
    const open = PARTS.find(p => !files[p.key]);
    if (open) setPart(open, f);
  });
});

const sutures = SEAMS.map(d => { const n = el("path", { d, class: "suture" }); n.style.visibility = "hidden"; return n; });
const setSutures = f => sutures.forEach((n, i) => { n.style.visibility = f > i / SEAMS.length ? "visible" : "hidden"; });

// Crops a photo to its hexagon, in monochrome with a little grain.
function portrait(img, p) {
  const size = p.hex[2] * 4, s = Math.max(size / img.width, size / img.height), side = size / s;
  const sx = (img.width - side) / 2, sy = Math.max(0, Math.min(img.height - side, img.height * p.focus - side / 2));
  const c = document.createElement("canvas"); c.width = c.height = size;
  const x = c.getContext("2d");
  x.filter = "grayscale(1) contrast(1.15)";
  x.drawImage(img, sx, sy, side, side, 0, 0, size, size);
  x.filter = "none";
  const d = x.getImageData(0, 0, size, size), a = d.data;
  for (let i = 0; i < a.length; i += 4) {
    const n = (Math.random() - .5) * 22;
    a[i] = a[i] * .92 + n; a[i + 1] = a[i + 1] * .98 + n; a[i + 2] = a[i + 2] * .98 + n;
  }
  x.putImageData(d, 0, 0);
  return c.toDataURL("image/jpeg", .9);
}

function showParts() {
  document.body.classList.remove("showing");
  $("reveal").hidden = true; $("result").hidden = true;
}
$("again").onclick = showParts;

async function setPart(p, file) {
  showParts();
  let bmp;
  try { bmp = await createImageBitmap(file); }
  catch { say("Couldn't read that file as an image.", true); return; }
  files[p.key] = file;
  p.image.setAttribute("href", portrait(bmp, p));
  p.image.style.display = "";
  p.zone.classList.add("full");
  p.row.querySelector("small").textContent = file.name;
  p.row.querySelector(".x").hidden = false;
  refresh();
}
function clearPart(p) {
  showParts();
  delete files[p.key];
  p.image.style.display = "none";
  p.zone.classList.remove("full");
  p.row.querySelector("small").textContent = p.plain;
  p.row.querySelector(".x").hidden = true;
  refresh();
}

// Each click loads the next set of test photos.
let sampleSet = 0;
$("sample").onclick = async () => {
  const set = sampleSet++ % PARTS[0].sample.length;
  for (const p of PARTS) {
    const name = p.sample[set], r = await fetch("/refs/" + name);
    await setPart(p, new File([await r.blob()], name, { type: "image/jpeg" }));
  }
};

let lab = { comfy: false, modes: {} }, running = false;
function say(text, bad) { $("status").textContent = text; $("status").classList.toggle("bad", !!bad); }
function refresh() {
  const need = PARTS.filter(p => !files[p.key]);
  let msg = "", ready = false;
  if (running) msg = "";
  else if (!lab.comfy) msg = "The image engine isn't running.";
  else if (!lab.modes.turbo) msg = "Getting ready…";
  else if (need.length) msg = "Missing: " + need.map(p => p.plain).join(", ") + ".";
  else ready = true;
  $("go").disabled = !ready || running;
  say(msg, !lab.comfy);
}
async function poll() {
  try { lab = await (await fetch("/api/status")).json(); } catch { lab = { comfy: false, modes: {} }; }
  if (!running) refresh();
  if (!lab.modes.turbo) setTimeout(poll, 1000);  // catch the engine coming back quickly
}
poll(); setInterval(poll, 8000);

const STAGES = [
  { nodes: ["453", "454", "474"], from: 0, to: .35, text: "Encoding" },
  { nodes: ["451", "469", "458", "505", "507"], from: .35, to: .97, text: "Sampling" },
  { nodes: ["457"], from: .97, to: 1, text: "Decoding" },
];
let timer, started, jobId, stepTimes = [], stepsLeft = null;
const fmt = s => String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(Math.floor(s % 60)).padStart(2, "0");
// ComfyUI has no ETA, so this uses this run's step times, falling back to the last run's total.
function etaSeconds() {
  const gaps = stepTimes.slice(1).map((t, i) => t - stepTimes[i]);
  if (stepsLeft !== null && gaps.length) {
    const recent = gaps.slice(-3);
    return recent.reduce((a, b) => a + b) / recent.length * stepsLeft + 5;
  }
  const last = Number(localStorage.getItem("lastRunSeconds")) || 60;
  return Math.max(last - (Date.now() - started) / 1000, 0);
}
function showEta() {
  const s = (Date.now() - started) / 1000;
  $("clock").textContent = fmt(s);
  $("eta").textContent = "about " + fmt(Math.ceil(etaSeconds())) + " left";
}
function setProgress(f, text, value, max) {
  $("thread").style.width = f * 100 + "%";
  setSutures(f);
  if (text) $("stage").textContent = text;
  $("count").innerHTML = max ? `${String(value).padStart(2, "0")}<small>/${max}</small>` : "";
}
// Binary frames: uint32 type, then type 1 = uint32 format + image, type 4 = uint32 metadata length + JSON + image.
function showPreview(buf) {
  const v = new DataView(buf), type = v.getUint32(0);
  let offset, mime = "image/jpeg";
  if (type === 1) { if (v.getUint32(4) === 2) mime = "image/png"; offset = 8; }
  else if (type === 4) {
    const len = v.getUint32(4);
    const meta = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 8, len)));
    if (meta.image_type) mime = meta.image_type;
    offset = 8 + len;
  } else return;
  createImageBitmap(new Blob([new Uint8Array(buf, offset)], { type: mime })).then(bmp => lookGhost ? ghostFrame(bmp) : bmp).then(crossfadeTo);
}
// The same filter as preprocess.ghost: key out paper-light pixels, then invert what's left to pale lines.
// The paper level is a plane fitted through the four edges, standing in for the server's fuller surface fit.
async function ghostFrame(bmp) {
  const w = bmp.width, h = bmp.height, c = document.createElement("canvas");
  c.width = w; c.height = h;
  const x = c.getContext("2d", { willReadFrequently: true });
  x.drawImage(bmp, 0, 0); bmp.close();
  const img = x.getImageData(0, 0, w, h), d = img.data;
  const lumAt = i => .3 * d[i] + .59 * d[i + 1] + .11 * d[i + 2];
  const m = Math.max(4, Math.round(w * .05)), edge = { l: [], r: [], t: [], b: [] };
  for (let y = 0; y < h; y += 7) for (let k = 0; k < w; k += 7) {
    const v = lumAt((y * w + k) * 4);
    if (k < m) edge.l.push(v); else if (k >= w - m) edge.r.push(v);
    if (y < m) edge.t.push(v); else if (y >= h - m) edge.b.push(v);
  }
  const med = a => { a.sort((p, q) => p - q); return a[a.length >> 1] || 200; };
  const L = med(edge.l), R = med(edge.r), T = med(edge.t), B = med(edge.b), mid = (L + R + T + B) / 4;
  for (let y = 0, i = 0; y < h; y++) for (let k = 0; k < w; k++, i += 4) {
    const u = k / w - .5, v = y / h - .5, paper = mid + (R - L) * u + (B - T) * v, lum = lumAt(i);
    const ink = Math.min(1, Math.max(0, (paper - lum - 14) / Math.max(paper - 45, 1)));
    const alpha = Math.min(1, Math.pow(ink, .7) * 1.15), tone = Math.min(1, Math.max(0, 1 - lum / 255));
    d[i] = 150 + tone * 105; d[i + 1] = 138 + tone * 112; d[i + 2] = 150 + tone * 100;
    d[i + 3] = alpha * d[i + 3];
  }
  x.putImageData(img, 0, 0);
  return createImageBitmap(c);
}
// Draws previews with high-quality scaling. Each new frame fades in from exactly what is on screen,
// so an unfinished fade never jumps, and the two layers are mixed additively so brightness never dips.
const hold = document.createElement("canvas");
let previewTo = null, hasHold = false, fadeStart = 0, fadeRaf = 0, fadeMs = 4500, lastPaint = 0, blurNow = 12, blurTarget = 12;
const stepMs = () => { const g = stepTimes.slice(1).map((t, i) => t - stepTimes[i]).slice(-3); return g.length ? Math.min(g.reduce((a, b) => a + b) / g.length * 1000, 8000) : 4500; };
const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
function drawFit(x, c, bmp) {
  const s = Math.min(c.width / bmp.width, c.height / bmp.height), w = bmp.width * s, h = bmp.height * s;
  x.drawImage(bmp, (c.width - w) / 2, (c.height - h) / 2, w, h);
}
function paintPreview(now) {
  fadeRaf = requestAnimationFrame(paintPreview);
  if (now - lastPaint < 40) return;
  lastPaint = now;
  const c = $("preview"), box = c.getBoundingClientRect(), dpr = devicePixelRatio || 1;
  const W = Math.round(box.width * dpr), H = Math.round(box.height * dpr);
  if (c.width !== W || c.height !== H) { c.width = W; c.height = H; hasHold = false; }
  const x = c.getContext("2d");
  x.imageSmoothingEnabled = true; x.imageSmoothingQuality = "high";
  const f = still ? 1 : Math.min((now - fadeStart) / fadeMs, 1), e = f * f * (3 - 2 * f);
  blurNow += (blurTarget - blurNow) * .05;
  x.clearRect(0, 0, W, H);
  x.globalCompositeOperation = "lighter";
  if (hasHold && f < 1) { x.globalAlpha = 1 - e; x.drawImage(hold, 0, 0); }
  x.globalAlpha = hasHold ? e : Math.min(1, (now - fadeStart) / 1500);
  x.filter = blurNow > .2 ? `blur(${(blurNow * dpr).toFixed(2)}px)` : "none";
  drawFit(x, c, previewTo);
  x.filter = "none"; x.globalAlpha = 1; x.globalCompositeOperation = "source-over";
}
function crossfadeTo(bmp) {
  if (!running) { bmp.close(); return; }
  const c = $("preview");
  if (previewTo && c.width) {
    hold.width = c.width; hold.height = c.height;
    hold.getContext("2d").drawImage(c, 0, 0);
    hasHold = true;
    previewTo.close();
  }
  previewTo = bmp; fadeStart = performance.now(); fadeMs = stepMs();
  c.hidden = false;
  if (!fadeRaf) fadeRaf = requestAnimationFrame(paintPreview);
}
function clearPreview() {
  cancelAnimationFrame(fadeRaf); fadeRaf = 0;
  if (previewTo) previewTo.close();
  previewTo = null; hasHold = false; blurNow = blurTarget = 12;
  $("preview").hidden = true;
  Scrawl.stop();
  document.body.classList.remove("fog");
}
// As steps finish, the fog and chalk thin out and the preview sharpens.
function emerge(f) {
  const left = Math.pow(1 - f, 1.25);
  Scrawl.level(left);
  blurTarget = left * 12;
}
const ws = () => {
  const s = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/ws?clientId=${clientId}`);
  s.binaryType = "arraybuffer";
  let stage = null;
  s.onmessage = e => {
    if (typeof e.data !== "string") { if (running) showPreview(e.data); return; }
    const m = JSON.parse(e.data);
    if (!running || (m.data && m.data.prompt_id && m.data.prompt_id !== jobId)) return;
    if (m.type === "executing" && m.data.node) {
      stage = STAGES.find(x => x.nodes.includes(String(m.data.node))) || stage;
      if (stage) setProgress(stage.from, stage.text);
    } else if (m.type === "progress" && stage) {
      if (stage.text === "Sampling") { stepTimes.push(Date.now() / 1000); stepsLeft = m.data.max - m.data.value; }
      setProgress(stage.from + (stage.to - stage.from) * m.data.value / m.data.max, stage.text, m.data.value, m.data.max);
      if (stage.text === "Sampling") emerge(m.data.value / m.data.max);
      showEta();
    } else if (m.type === "execution_success" || m.type === "execution_error" || m.type === "execution_interrupted") {
      finish(m.type);
    }
  };
  s.onclose = () => setTimeout(ws, 2000);
};
ws();

$("ledger").onsubmit = async e => {
  e.preventDefault();
  const fd = new FormData();
  for (const p of PARTS) fd.append(p.key, files[p.key], files[p.key].name);
  fd.append("mode", "turbo");
  fd.append("client_id", clientId);
  running = true; refresh(); say("");
  $("vigil").hidden = false; $("result").hidden = true; $("reveal").hidden = true; document.body.classList.add("showing");
  setProgress(0, "Isolating body parts");
  Scrawl.start();
  document.body.classList.add("fog");
  document.body.classList.add("running");
  Sky.wrath(true);
  started = Date.now();
  stepTimes = []; stepsLeft = null; showEta();
  timer = setInterval(showEta, 1000);
  try {
    const r = await fetch("/api/generate", { method: "POST", body: fd });
    if (!r.ok) throw new Error((await r.text()).slice(0, 400));
    const j = await r.json();
    jobId = j.id; $("seedline").textContent = "Seed " + j.seed;
  } catch (err) { end(); say("Failed: " + err.message, true); }
};
$("abort").onclick = () => fetch("/api/interrupt", { method: "POST" });

function end() {
  setTimeout(poll, 900);
  running = false; document.body.classList.remove("running"); clearInterval(timer); $("vigil").hidden = true; clearPreview(); if ($("reveal").hidden) document.body.classList.remove("showing"); Sky.wrath(false); setSutures(0); refresh();
}
async function finish(kind) {
  if (!running) return;
  if (kind === "execution_interrupted") { end(); say("Cancelled."); return; }
  let j = { state: "running" };
  for (let i = 0; i < 20 && j.state === "running"; i++) {
    j = await (await fetch("/api/job/" + jobId)).json();
    if (j.state === "running") await new Promise(r => setTimeout(r, 500));
  }
  // Keep the last preview, as sharp as it got, for the blend into the finished image.
  let lastFrame = null;
  const pv = $("preview");
  if (!pv.hidden && pv.width) { lastFrame = document.createElement("canvas"); lastFrame.width = pv.width; lastFrame.height = pv.height; lastFrame.getContext("2d").drawImage(pv, 0, 0); }
  end();
  if (j.state !== "done" || !j.images.length) { say("Failed: " + (j.message || "no image returned."), true); return; }
  const i = j.images[0];
  const url = `/api/view?filename=${encodeURIComponent(i.filename)}&subfolder=${encodeURIComponent(i.subfolder)}`;
  localStorage.setItem("lastRunSeconds", Math.round((Date.now() - started) / 1000));
  $("keep").href = url; $("keep").download = i.filename;
  $("result").hidden = false;
  document.body.classList.add("showing");
  showLook(i.filename, lastFrame);
}
// Download what's on screen: the graded image with its transparency.
function bakeDownload(c) {
  const o = document.createElement("canvas"); o.width = c.width; o.height = c.height;
  const x = o.getContext("2d"); x.filter = "url(#grade)"; x.drawImage(c, 0, 0);
  o.toBlob(b => { if (b) $("keep").href = URL.createObjectURL(b); }, "image/png");
}
// Experiment: each run has a ghost version (inverted ink lines) and a cut-out, and this switches between them.
function showLook(filename, from) {
  lookFile = filename;
  const name = lookGhost ? filename.replace(".png", "_ghost.png") : filename;
  $("look").textContent = lookGhost ? "Show cut-out" : "Show ghost";
  $("keep").download = name;
  const url = `/api/view?filename=${encodeURIComponent(name)}&subfolder=`;
  $("keep").href = url;
  reveal(url, from);
}
$("look").onclick = () => { lookGhost = !lookGhost; showLook(lookFile); };
function reveal(url, from) {
  const img = new Image();
  img.onload = () => {
    const c = $("reveal"), x = c.getContext("2d");
    c.width = img.width; c.height = img.height; c.hidden = false;
    const done = () => { x.clearRect(0, 0, c.width, c.height); x.drawImage(img, 0, 0); bakeDownload(c); };
    if (!from || matchMedia("(prefers-reduced-motion: reduce)").matches) { done(); return; }
    // Blend straight from the last preview into the finished image.
    const t0 = performance.now(), span = 700;
    const step = now => {
      const f = Math.min((now - t0) / span, 1);
      if (f >= 1) { done(); return; }
      x.clearRect(0, 0, c.width, c.height);
      x.globalCompositeOperation = "lighter";
      x.globalAlpha = 1 - f; x.drawImage(from, 0, 0, c.width, c.height);
      x.globalAlpha = f; x.drawImage(img, 0, 0);
      x.globalAlpha = 1; x.globalCompositeOperation = "source-over";
      requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };
  img.src = url;
}

// Sizes the stacked title to fill the left column, leaving height for the controls.
function fitTitle() {
  const t = $("title"), side = $("side"), probe = 100;
  t.style.fontSize = probe + "px";
  const [a, b] = t.children;
  const indent = parseFloat(getComputedStyle(t).paddingLeft);
  const widest = Math.max(a.getBoundingClientRect().width, b.getBoundingClientRect().width + probe * .35);
  const room = (side.clientWidth - indent - 24) * .92;  // letter overhang and the wear filter need margin
  const size = Math.max(70, Math.min(probe * room / widest, (innerHeight - 575) / 1.75));
  t.style.fontSize = size + "px";
}
addEventListener("resize", fitTitle);
document.fonts.ready.then(fitTitle);
