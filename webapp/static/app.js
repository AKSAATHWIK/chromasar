/* ChromaSAR front-end.
 *
 * Two design decisions drive everything here:
 *
 * 1. The server returns raw PROBABILITY / CONFIDENCE maps, never a thresholded result.
 *    Gating, scoring and histograms happen on canvas in the browser, so dragging a
 *    slider re-gates the output and recomputes IoU in the same frame - no round trip.
 *
 * 2. One large viewer with layer tabs, not a wall of thumbnails. Six 250px tiles are
 *    unreadable and make the page feel cluttered; one 600px pane you switch between is
 *    how actual GIS tools present this.
 */
const $ = (id) => document.getElementById(id);
const api = async (u) => {
  const r = await fetch(u);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};
const loadImg = (src) => new Promise((res, rej) => {
  const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = src;
});
const pixels = (img) => {
  const c = document.createElement("canvas");
  c.width = img.width; c.height = img.height;
  const x = c.getContext("2d", { willReadFrequently: true });
  x.drawImage(img, 0, 0);
  return x.getImageData(0, 0, c.width, c.height);
};
const toast = (msg) => {
  const t = $("toast"); t.textContent = msg; t.classList.add("show");
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), 2600);
};

/* Numbers count up, but requestAnimationFrame is throttled to zero in hidden tabs -
   a setTimeout guarantees the final value lands even when rAF never fires. */
function animateTo(el, val, digits = 3, suffix = "") {
  const from = parseFloat(el.dataset.v || "0") || 0;
  const to = isFinite(val) ? val : 0;
  el.dataset.v = to;
  const final = to.toFixed(digits) + suffix;
  const t0 = performance.now(), dur = 420;
  const step = (t) => {
    const k = Math.min(1, (t - t0) / dur);
    const e = 1 - Math.pow(1 - k, 3);
    el.textContent = (from + (to - from) * e).toFixed(digits) + suffix;
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
  clearTimeout(el._fin);
  el._fin = setTimeout(() => { el.textContent = final; }, dur + 60);
}
const paintRange = (el) => {
  const p = (el.value - el.min) / (el.max - el.min) * 100;
  el.style.setProperty("--pct", p + "%");
};
document.querySelectorAll("input[type=range]").forEach((r) => {
  paintRange(r); r.addEventListener("input", () => paintRange(r));
});

/* ---------------- tabs ---------------- */
document.querySelectorAll("nav button").forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll("nav button").forEach((x) => x.classList.remove("active"));
    document.querySelectorAll(".view").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    $("view-" + b.dataset.view).classList.add("active");
  };
});

/* ---------------- layer switcher ---------------- */
function initLayers(barId, stageSel, noteId) {
  const bar = $(barId);
  const stage = document.querySelector(stageSel);
  const show = (layer) => {
    stage.querySelectorAll("[data-pane]").forEach((p) => {
      p.classList.toggle("on", p.dataset.pane === layer);
    });
    bar.querySelectorAll("button").forEach((b) => {
      b.classList.toggle("active", b.dataset.layer === layer);
    });
    $(noteId).textContent = layer === "compare" ? "drag the divider" : "";
    const lg = $("f-legend");
    if (lg) lg.style.visibility = layer === "agree" ? "visible" : "hidden";
  };
  bar.querySelectorAll("button").forEach((b) => { b.onclick = () => show(b.dataset.layer); });
  show("compare");
  return show;
}

/* ---------------- drag-to-compare ---------------- */
function initCompare(el) {
  let drag = false;
  const set = (clientX) => {
    const r = el.getBoundingClientRect();
    el.style.setProperty("--split",
      Math.max(0, Math.min(100, ((clientX - r.left) / r.width) * 100)) + "%");
  };
  el.addEventListener("pointerdown", (e) => {
    drag = true; el.setPointerCapture(e.pointerId); set(e.clientX);
  });
  el.addEventListener("pointermove", (e) => { if (drag) set(e.clientX); });
  ["pointerup", "pointerleave"].forEach((ev) =>
    el.addEventListener(ev, () => { drag = false; }));
  el.style.setProperty("--split", "50%");
}

/* ---------------- histogram ---------------- */
function drawHist(canvas, counts, cut, lo, hi) {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (!w) return;
  canvas.width = w * dpr; canvas.height = h * dpr;
  const g = canvas.getContext("2d");
  g.scale(dpr, dpr); g.clearRect(0, 0, w, h);
  const max = Math.max(...counts, 1);
  const bw = w / counts.length;
  for (let i = 0; i < counts.length; i++) {
    const bh = Math.pow(counts[i] / max, 0.42) * (h - 10);
    g.fillStyle = (i / counts.length) >= cut ? hi : lo;
    g.fillRect(i * bw, h - bh, Math.max(bw - 0.5, 0.6), bh);
  }
  g.strokeStyle = "#fff"; g.lineWidth = 1.5;
  g.beginPath(); g.moveTo(cut * w, 0); g.lineTo(cut * w, h); g.stroke();
}

/* ---------------- status ---------------- */
(async () => {
  try {
    const s = await api("/api/status");
    const set = (id, on, text) => {
      const el = $(id); el.className = "pill " + (on ? "on" : "off");
      el.querySelector("span").textContent = text;
    };
    set("pill-device", true, s.device.toUpperCase());
    set("pill-flood", s.flood_model, s.flood_model ? `flood · ${s.flood_chips}` : "flood missing");
    set("pill-color", s.color_model, s.color_model ? `colorization · ${s.sar_pairs}` : "colorization off");
    if (!s.color_model) $("c-run").disabled = true;
  } catch (e) { console.error(e); }
})();

/* ===================== FLOOD ===================== */
let FLOOD = null, LAST_REPORT = null;
const showFlood = initLayers("f-layers", "#view-flood .stage", "f-layer-note");
initCompare($("f-compare"));

async function initFlood() {
  try {
    const d = await api("/api/flood/samples");
    const regions = Object.keys(d.regions);
    $("f-region").innerHTML = regions
      .map((r) => `<option value="${r}">${r} · ${d.regions[r].length}</option>`).join("");
    const fill = () => {
      const r = $("f-region").value;
      $("f-chip").innerHTML = d.regions[r]
        .map((n) => `<option value="${n}">${n.replace(r + "_", "")}</option>`).join("");
    };
    $("f-region").onchange = fill;
    if (regions.includes("India")) $("f-region").value = "India";
    fill();
  } catch (e) {
    $("f-warn").innerHTML = `<div class="warn"><div>${e.message}</div></div>`;
  }
}

async function runFlood() {
  const name = $("f-chip").value;
  if (!name) return;
  const btn = $("f-run");
  btn.disabled = true; btn.innerHTML = '<span class="spin"></span>running';
  document.body.classList.add("busy");
  try {
    const d = await api(`/api/flood/predict?name=${encodeURIComponent(name)}`);
    $("f-vv").src = d.sar_vv; $("f-vv-b").src = d.sar_vv; $("f-vh").src = d.sar_vh;
    $("f-empty").classList.add("hide");
    $("m-ms-chip").textContent = d.ms + " ms";

    const probImg = await loadImg(d.prob);
    const labImg = d.label ? await loadImg(d.label) : null;
    const permImg = d.permanent ? await loadImg(d.permanent) : null;
    FLOOD = {
      prob: pixels(probImg), label: labImg ? pixels(labImg) : null,
      perm: permImg ? pixels(permImg) : null,
      w: probImg.width, h: probImg.height, name,
    };
    ["f-pred", "f-pred2", "f-agree", "f-perm-map"].forEach((id) => {
      $(id).width = FLOOD.w; $(id).height = FLOOD.h;
    });
    if (FLOOD.perm) {
      const g = $("f-perm-map").getContext("2d");
      const im = g.createImageData(FLOOD.w, FLOOD.h);
      for (let i = 0; i < FLOOD.w * FLOOD.h; i++) {
        const on = FLOOD.perm.data[i * 4] > 127, k = i * 4;
        im.data[k] = on ? 90 : 12; im.data[k + 1] = on ? 140 : 18;
        im.data[k + 2] = on ? 230 : 26; im.data[k + 3] = 255;
      }
      g.putImageData(im, 0, 0);
    }
    FLOOD.hist = new Array(64).fill(0);
    for (let i = 0; i < FLOOD.w * FLOOD.h; i++)
      FLOOD.hist[Math.min(63, FLOOD.prob.data[i * 4] >> 2)]++;

    render();
    loadReport();
    toast(`${name} · ${d.ms} ms · ${d.size[0]}×${d.size[1]}`);
  } catch (e) {
    $("f-warn").innerHTML = `<div class="warn"><div>${e.message}</div></div>`;
  } finally {
    document.body.classList.remove("busy");
    btn.disabled = false; btn.innerHTML = 'Run detection <kbd>R</kbd>';
  }
}

function render() {
  if (!FLOOD) return;
  const thr = +$("f-thr").value / 100;
  const { prob, label, w, h } = FLOOD;
  const usePerm = $("f-perm").checked && FLOOD.perm;
  const pc = $("f-pred").getContext("2d");
  const pc2 = $("f-pred2").getContext("2d");
  const ac = $("f-agree").getContext("2d");
  const pred = pc.createImageData(w, h), agree = ac.createImageData(w, h);
  let tp = 0, fp = 0, fn = 0, permWet = 0, floodWet = 0, valid = 0;

  for (let i = 0; i < w * h; i++) {
    const k = i * 4, g = prob.data[k];
    let p = g / 255 > thr;
    const isPerm = usePerm && FLOOD.perm.data[k] > 127;
    if (p) { if (isPerm) permWet++; else floodWet++; }
    // Permanent water is removed from BOTH prediction and truth. Removing it from one
    // side only turns every river pixel into a false negative (measured: 0.861 -> 0.263).
    if (usePerm && isPerm) p = false;

    if (p) { pred.data[k] = 61; pred.data[k + 1] = 220; pred.data[k + 2] = 255; }
    else { const v = g * 0.42; pred.data[k] = v; pred.data[k + 1] = v * 1.04; pred.data[k + 2] = v * 1.12; }
    pred.data[k + 3] = 255;

    if (label) {
      const L = label.data[k];
      let r = 17, gg = 26, b = 38;
      if (L !== 128 && !(usePerm && isPerm)) {
        valid++;
        const t = L === 255;
        if (p && t) { tp++; r = 62; gg = 224; b = 143; }
        else if (p && !t) { fp++; r = 255; gg = 95; b = 109; }
        else if (!p && t) { fn++; r = 90; gg = 166; b = 255; }
        else { r = 10; gg = 16; b = 24; }
      }
      agree.data[k] = r; agree.data[k + 1] = gg; agree.data[k + 2] = b; agree.data[k + 3] = 255;
    }
  }
  pc.putImageData(pred, 0, 0);
  pc2.putImageData(pred, 0, 0);
  if (label) ac.putImageData(agree, 0, 0);

  if (label && valid) {
    animateTo($("m-iou"), tp / Math.max(tp + fp + fn, 1));
    animateTo($("m-prec"), tp / Math.max(tp + fp, 1));
    animateTo($("m-rec"), tp / Math.max(tp + fn, 1));
  } else {
    ["m-iou", "m-prec", "m-rec"].forEach((i) => ($(i).textContent = "n/a"));
  }
  animateTo($("m-flood"), (floodWet * 100) / 1e6, 2, " km²");   // 10 m pixels
  $("m-perm-chip").textContent = `permanent ${((permWet * 100) / 1e6).toFixed(2)} km²`;
  drawHist($("f-hist"), FLOOD.hist, thr, "#24384d", "#3ddcff");
}

async function loadReport() {
  const name = $("f-chip").value;
  if (!name) return;
  try {
    const d = await api(`/api/flood/report?name=${encodeURIComponent(name)}`
      + `&thr=${+$("f-thr").value / 100}&exclude_permanent=${$("f-perm").checked}`);
    LAST_REPORT = d;
    $("f-report").innerHTML = d.narrative.map((l) => `<li>${l}</li>`).join("");
    $("f-sev").textContent = d.severity;
    $("f-alert").innerHTML = d.alert
      ? `<div class="alert on"><span class="badge">alert</span>Flood extent
         ${d.metrics.flood_pct_of_scene.toFixed(1)}% of scene · confidence sufficient
         to act</div>`
      : `<div class="alert off"><span class="badge">no alert</span>${
          d.severity === "negligible" ? "Below alert threshold"
            : "Extent significant but too much of the scene is low-confidence — "
              + "routed for analyst review"}</div>`;
  } catch (e) {
    $("f-report").innerHTML = `<li>${e.message}</li>`;
  }
}

$("f-thr").oninput = () => { $("f-thr-v").textContent = (+$("f-thr").value / 100).toFixed(2); render(); };
$("f-thr").onchange = loadReport;
$("f-perm").onchange = () => { render(); loadReport(); };
$("f-run").onclick = runFlood;

/* ---------------- upload ---------------- */
const drop = $("f-drop");
drop.onclick = () => $("f-upload").click();
["dragenter", "dragover"].forEach((e) => drop.addEventListener(e, (ev) => {
  ev.preventDefault(); drop.classList.add("over");
}));
["dragleave", "drop"].forEach((e) => drop.addEventListener(e, (ev) => {
  ev.preventDefault(); drop.classList.remove("over");
}));
drop.addEventListener("drop", (ev) => ev.dataTransfer.files[0] && upload(ev.dataTransfer.files[0]));
$("f-upload").onchange = (e) => e.target.files[0] && upload(e.target.files[0]);

async function upload(file) {
  const fd = new FormData(); fd.append("file", file);
  $("f-warn").innerHTML = `<div class="warn"><span class="spin"></span><div>running ${file.name}…</div></div>`;
  try {
    const r = await fetch("/api/flood/upload", { method: "POST", body: fd });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "upload failed");
    $("f-vv").src = d.sar_vv; $("f-vv-b").src = d.sar_vv;
    $("f-empty").classList.add("hide");
    const probImg = await loadImg(d.prob);
    FLOOD = { prob: pixels(probImg), label: null, perm: null,
              w: probImg.width, h: probImg.height, name: file.name,
              hist: new Array(64).fill(0) };
    for (let i = 0; i < FLOOD.w * FLOOD.h; i++)
      FLOOD.hist[Math.min(63, FLOOD.prob.data[i * 4] >> 2)]++;
    ["f-pred", "f-pred2", "f-agree", "f-perm-map"].forEach((id) => {
      $(id).width = FLOOD.w; $(id).height = FLOOD.h;
    });
    $("f-warn").innerHTML = ""; render();
    toast(`${file.name} processed`);
  } catch (err) {
    $("f-warn").innerHTML = `<div class="warn"><div>${err.message}</div></div>`;
  }
}

/* ---------------- region sweep ---------------- */
$("f-batch-n").oninput = () => { $("f-batch-n-v").textContent = $("f-batch-n").value; };
$("f-batch").onclick = async () => {
  const region = $("f-region").value, btn = $("f-batch");
  btn.disabled = true; btn.innerHTML = '<span class="spin"></span>sweeping';
  document.body.classList.add("busy");
  try {
    const d = await api(`/api/flood/batch?region=${encodeURIComponent(region)}`
      + `&limit=${+$("f-batch-n").value}&thr=${+$("f-thr").value / 100}`);
    $("f-batch-out").innerHTML = `
      <table class="batch">
        <tr><th>scene</th><th>flood km²</th><th>IoU</th></tr>
        ${d.worst.map((r) => `<tr data-chip="${r.scene}">
          <td>${r.scene.replace(d.region + "_", "")}</td>
          <td>${r.flood_km2.toFixed(2)}</td>
          <td>${r.iou !== undefined ? r.iou.toFixed(3) : "—"}</td></tr>`).join("")}
      </table>
      <div class="note tiny"><b>${d.chips}</b> chips · <b>${d.flood_km2.toFixed(1)} km²</b>
        flood of ${d.water_km2.toFixed(1)} km² water${
        d.mean_iou !== null ? ` · mean IoU ${d.mean_iou.toFixed(3)}` : ""} ·
        ${(d.ms / 1000).toFixed(1)} s</div>`;
    $("f-batch-out").querySelectorAll("tr[data-chip]").forEach((tr) => {
      tr.onclick = () => { $("f-chip").value = tr.dataset.chip; runFlood(); };
    });
    toast(`${d.chips} chips · ${d.flood_km2.toFixed(1)} km² flood`);
  } catch (e) {
    $("f-batch-out").innerHTML = `<div class="note tiny">${e.message}</div>`;
  } finally {
    document.body.classList.remove("busy");
    btn.disabled = false; btn.innerHTML = 'Sweep region <kbd>B</kbd>';
  }
};

/* ---------------- exports ---------------- */
const dl = (url, fname) => {
  const a = document.createElement("a");
  a.href = url; a.download = fname; a.click();
};
const exportTif = (kind) => {
  const name = $("f-chip").value;
  if (!name) return toast("pick a scene first");
  const q = `name=${encodeURIComponent(name)}&thr=${+$("f-thr").value / 100}`
    + `&exclude_permanent=${$("f-perm").checked}&kind=${kind}`;
  dl(`/api/flood/export?${q}`, `chromasar_${name}_${kind}.tif`);
  toast(`${kind} GeoTIFF downloading`);
};
$("ex-tif").onclick = () => exportTif("mask");
$("ex-prob").onclick = () => exportTif("probability");
$("ex-json").onclick = () => {
  if (!LAST_REPORT) return toast("run a detection first");
  const b = new Blob([JSON.stringify(LAST_REPORT, null, 2)], { type: "application/json" });
  dl(URL.createObjectURL(b), `chromasar_${LAST_REPORT.metrics.scene}.json`);
  toast("report downloaded");
};
$("ex-png").onclick = () => {
  const pane = document.querySelector("#view-flood .stage [data-pane].on");
  const el = pane && (pane.querySelector("canvas") || pane.querySelector("img"));
  if (!el) return toast("nothing to export");
  if (el.tagName === "CANVAS") dl(el.toDataURL("image/png"), `chromasar_view.png`);
  else dl(el.src, "chromasar_view.png");
  toast("view exported");
};

/* ===================== COLORIZATION ===================== */
let COLOR = null;
const showColor = initLayers("c-layers", "#view-color .stage", "c-layer-note");
initCompare($("c-compare"));

async function initColor() {
  try {
    const d = await api("/api/color/samples");
    $("c-chip").innerHTML = d.samples
      .map((n) => `<option value="${n}">${n.replace(".png", "").slice(-24)}</option>`).join("");
  } catch (e) { /* dataset absent */ }
}

async function runColor() {
  const name = $("c-chip").value;
  if (!name) return;
  const btn = $("c-run");
  btn.disabled = true; btn.innerHTML = '<span class="spin"></span>sampling';
  document.body.classList.add("busy");
  try {
    const d = await api(`/api/color/predict?name=${encodeURIComponent(name)}`
      + `&passes=${+$("c-passes").value}`);
    $("c-sar-b").src = d.sar;
    if (d.truth) $("c-truth").src = d.truth;
    $("c-empty").classList.add("hide");
    animateTo($("cm-conf"), d.mean_confidence);
    animateTo($("cm-ms"), d.ms, 0, " ms");

    const col = await loadImg(d.color), cf = await loadImg(d.confidence);
    const truth = d.truth ? await loadImg(d.truth) : null;
    COLOR = { color: pixels(col), conf: pixels(cf),
              truth: truth ? pixels(truth) : null, w: col.width, h: col.height };
    ["c-out", "c-out2", "c-conf"].forEach((id) => {
      $(id).width = COLOR.w; $(id).height = COLOR.h;
    });
    COLOR.hist = new Array(64).fill(0);
    for (let i = 0; i < COLOR.w * COLOR.h; i++)
      COLOR.hist[Math.min(63, COLOR.conf.data[i * 4] >> 2)]++;
    renderColor();
    toast(`${d.passes} stochastic passes · ${d.ms} ms`);
  } catch (e) {
    $("c-warn").innerHTML = `<div class="warn"><div>${e.message}</div></div>`;
  } finally {
    document.body.classList.remove("busy");
    btn.disabled = false; btn.textContent = "Colorize";
  }
}

function renderColor() {
  if (!COLOR) return;
  const gate = +$("c-thr").value / 100;
  const { color, conf, truth, w, h } = COLOR;
  const oc = $("c-out").getContext("2d"), oc2 = $("c-out2").getContext("2d");
  const cc = $("c-conf").getContext("2d");
  const out = oc.createImageData(w, h), cmap = cc.createImageData(w, h);
  let gated = 0, se = 0, n = 0;
  for (let i = 0; i < w * h; i++) {
    const k = i * 4, c = conf.data[k] / 255;
    if (c < gate) { gated++; out.data[k] = out.data[k + 1] = out.data[k + 2] = 84; }
    else {
      out.data[k] = color.data[k]; out.data[k + 1] = color.data[k + 1];
      out.data[k + 2] = color.data[k + 2];
      if (truth) for (let ch = 0; ch < 3; ch++) {
        const d0 = (color.data[k + ch] - truth.data[k + ch]) / 255; se += d0 * d0; n++;
      }
    }
    out.data[k + 3] = 255;
    cmap.data[k] = Math.round(255 * (1 - c));
    cmap.data[k + 1] = Math.round(215 * c);
    cmap.data[k + 2] = Math.round(70 + 40 * c);
    cmap.data[k + 3] = 255;
  }
  oc.putImageData(out, 0, 0); oc2.putImageData(out, 0, 0); cc.putImageData(cmap, 0, 0);
  animateTo($("cm-gated"), 100 * gated / (w * h), 1, "%");
  if (truth && n) animateTo($("cm-psnr"), 10 * Math.log10(1 / (se / n)), 2, " dB");
  drawHist($("c-hist"), COLOR.hist, gate, "#4a2418", "#3ee08f");
}

$("c-thr").oninput = () => { $("c-thr-v").textContent = (+$("c-thr").value / 100).toFixed(2); renderColor(); };
$("c-passes").oninput = () => { $("c-passes-v").textContent = $("c-passes").value; };
$("c-run").onclick = runColor;

/* ---------------- chrome ---------------- */
$("hamb").onclick = () => document.querySelector(".pills").classList.toggle("open");

document.addEventListener("keydown", (e) => {
  if (["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName)) return;
  const k = e.key.toLowerCase();
  if (k === "r") { e.preventDefault(); $("f-run").click(); }
  else if (k === "p") { $("f-perm").checked = !$("f-perm").checked; render(); loadReport(); }
  else if (k === "b") $("f-batch").click();
  else if (k === "e") $("ex-tif").click();
  else if (k >= "1" && k <= "3") document.querySelectorAll("nav button")[+k - 1].click();
  else if (k === "arrowright" || k === "arrowleft") {
    const sel = $("f-chip");
    sel.selectedIndex = Math.max(0, Math.min(sel.length - 1,
      sel.selectedIndex + (k === "arrowright" ? 1 : -1)));
    runFlood();
  }
});
const hint = document.createElement("div");
hint.className = "kbd-hint";
hint.innerHTML = "<kbd>R</kbd> run · <kbd>P</kbd> permanent · <kbd>B</kbd> sweep · "
  + "<kbd>E</kbd> export · <kbd>←→</kbd> scenes";
document.body.appendChild(hint);

initFlood();
initColor();
