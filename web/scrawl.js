// While the model warms up, frantic pens scrawl Leonardo's figure out of crazed lines. They trace the actual
// ink of the drawing, starting wild and settling, then the scrawl thins out as sampling steps finish.
const Scrawl = (() => {
  const c = document.getElementById("scrawl"), x = c.getContext("2d");
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const PENS = 9, SETTLE_MS = 12000, HOLD_ALPHA = .5;
  let ink = [], raf = 0, on = false, t0 = 0, last = 0, pens = [], op = 1, target = 1, map = null;

  const art = new Image();
  art.onload = () => {
    // Sample ink points in the viewBox crop (40 100 720 720), keeping those inside the circle.
    const s = 720, o = document.createElement("canvas"); o.width = o.height = s;
    const g = o.getContext("2d", { willReadFrequently: true });
    const k = art.width / 800;
    g.drawImage(art, 40 * k, 100 * k, 720 * k, 720 * k, 0, 0, s, s);
    const d = g.getImageData(0, 0, s, s).data;
    for (let y = 0; y < s; y += 2) for (let u = 0; u < s; u += 2) {
      const dx = u + 40 - 399, dy = y + 100 - 447;
      if (d[(y * s + u) * 4 + 3] > 110 && dx * dx + dy * dy < 335 * 335) ink.push([u, y]);
    }
  };
  art.src = "assets/vitruvian_chalk.png";

  function layout() {
    const box = c.getBoundingClientRect(), dr = document.getElementById("drawing").getBoundingClientRect();
    const dpr = Math.min(devicePixelRatio || 1, 2), W = Math.round(box.width * dpr), H = Math.round(box.height * dpr);
    if (c.width !== W || c.height !== H) { c.width = W; c.height = H; }
    map = { sx: dr.width / 720 * dpr, ox: (dr.left - box.left) * dpr, oy: (dr.top - box.top) * dpr, dpr };
  }
  const place = p => [p[0] * map.sx + map.ox, p[1] * map.sx + map.oy];
  const rand = a => a[Math.floor(Math.random() * a.length)];
  function nextPoint(from) {
    // Prefer nearby ink, so pens follow lines; a pen occasionally leaps elsewhere.
    if (Math.random() < .025) return rand(ink);
    let best = null, bd = 1e12;
    for (let i = 0; i < 26; i++) {
      const q = rand(ink), d = (q[0] - from[0]) ** 2 + (q[1] - from[1]) ** 2;
      if (d > 9 && d < bd) { bd = d; best = q; }
    }
    return best || rand(ink);
  }
  function frame(now) {
    raf = requestAnimationFrame(frame);
    if (now - last < 50) return;
    last = now;
    if (!ink.length) return;
    const age = now - t0, wild = Math.max(0, 1 - age / SETTLE_MS);
    op += (target - op) * .035;
    c.style.opacity = op.toFixed(3);
    if (target === 0 && op < .012) { api.stop(); return; }
    if (!pens.length) pens = Array.from({ length: PENS }, () => { const p = rand(ink); return { p, q: place(p), hue: Math.random() }; });
    x.lineCap = "round"; x.lineJoin = "round";
    const reach = (1.5 + wild * 70) * map.dpr, strokes = 2;
    // Old lines fade as new ones land, so it stays a drawing instead of filling up to white.
    x.globalCompositeOperation = "destination-out"; x.fillStyle = "rgba(0,0,0,.022)"; x.fillRect(0, 0, c.width, c.height);
    x.globalCompositeOperation = "source-over";
    for (const pen of pens) {
      x.beginPath(); x.moveTo(pen.q[0], pen.q[1]);
      for (let i = 0; i < strokes; i++) {
        pen.p = nextPoint(pen.p);
        const [tx, ty] = place(pen.p);
        const jx = tx + (Math.random() - .5) * reach, jy = ty + (Math.random() - .5) * reach;
        const cx = (pen.q[0] + jx) / 2 + (Math.random() - .5) * reach * 1.4, cy = (pen.q[1] + jy) / 2 + (Math.random() - .5) * reach * 1.4;
        x.quadraticCurveTo(cx, cy, jx, jy);
        pen.q = [jx, jy];
      }
      const pale = pen.hue > .82;
      x.strokeStyle = pale ? `rgba(226,214,186,${HOLD_ALPHA})` : `rgba(198,204,226,${HOLD_ALPHA})`;
      x.lineWidth = (.5 + Math.random() * .55 + wild * .3) * map.dpr;
      x.stroke();
    }
  }
  const api = {
    start() {
      if (still) return;
      cancelAnimationFrame(raf); c.hidden = false; layout(); x.clearRect(0, 0, c.width, c.height);
      on = true; t0 = performance.now(); last = 0; op = 1; target = 1; pens = []; c.style.opacity = 1; c.hidden = false;
      raf = requestAnimationFrame(frame);
    },
    level(v) { target = v; },
    stop() { cancelAnimationFrame(raf); raf = 0; on = false; c.hidden = true; x.clearRect(0, 0, c.width, c.height); },
  };
  return api;
})();
